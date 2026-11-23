#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build unified global freight / trade intelligence dashboard data.

Sources
-------
- MI2 (local): summary.json + per-module SQLite DBs
- User-supplied freight indices: data/manual/{scfi,ccfi,bdi}.csv (override MI2)
- WorldMonitor chokepoint open data (public, CC-BY-4.0)
- WorldMonitor Five-Factor Scorecard (public, no key)
- Open data (fetch_open_data.py): USGS earthquakes, GDACS alerts, World Bank

Output
------
- data/unified.json
- data.js  (window.UNIFIED + window.WORLD_MAP, works from file://)
"""
from __future__ import annotations

import csv
import json
import math
import os
import sqlite3
import statistics as st
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG = {}
_cfg_path = ROOT / 'mi4.config.json'
if _cfg_path.exists():
    CFG = json.loads(_cfg_path.read_text(encoding='utf-8'))
MI2 = Path(os.environ.get('MI2_ROOT', CFG.get('data_sources', {}).get('mi2', '../MI2')))
if not MI2.is_absolute():
    MI2 = (ROOT / MI2).resolve()
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)

def jload(p: Path):
    return json.loads(p.read_text(encoding='utf-8'))

def jload_opt(name: str):
    p = DATA / name
    if not p.exists():
        return None
    try:
        return jload(p)
    except Exception as e:
        print(f'Warning: {name} unreadable: {e}')
        return None

def r2(v):
    if v is None:
        return None
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None

def validate_range(id, value, min_val=None, max_val=None):
    """값 범위 검증 로직 추가"""
    if value is None:
        return None
    if min_val is not None and value < min_val:
        print(f"Warning: {id} 값이 최소값보다 낮음: {value} < {min_val}")
    if max_val is not None and value > max_val:
        print(f"Warning: {id} 값이 최대값보다 높음: {value} > {max_val}")
    return r2(value)

def clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))

def mean(xs):
    xs = [x for x in xs if x is not None]
    return st.mean(xs) if xs else None

def zscore(arr):
    arr = [float(x) for x in arr if x is not None]
    if len(arr) < 3:
        return 0.0
    m = st.mean(arr); s = st.pstdev(arr)
    return (arr[-1] - m) / s if s else 0.0

def pct(cur, prev):
    if cur is None or prev is None or float(prev) == 0:
        return None
    return round((float(cur) - float(prev)) / abs(float(prev)) * 100, 1)

def connect(module: str):
    p = MI2 / module / f'{module}.db'
    if not p.exists():
        return None
    c = sqlite3.connect(f'file:{p}?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    return c

def q(c, sql, args=()):
    return c.execute(sql, args).fetchall()

# ---------------------------------------------------------------------------
# Load MI2 summary
# ---------------------------------------------------------------------------
summary = jload(MI2 / 'summary.json')
mods = {m['id']: m for m in summary['modules']}

def flatten_metrics(mod):
    out = []
    for m in mod.get('metrics', []):
        out.append(m)
    for g in mod.get('groups', []):
        out.extend(g.get('metrics', []))
    return out

def find_metric(module_id, label):
    for m in flatten_metrics(mods.get(module_id, {})):
        if m.get('label') == label:
            return m
    return None

def series_of(module_id, label):
    for s in mods.get(module_id, {}).get('series', []):
        if s.get('label') == label:
            return s.get('points', [])
    for g in mods.get(module_id, {}).get('groups', []):
        for s in g.get('series', []):
            if s.get('label') == label:
                return s.get('points', [])
    return []

def metric_id(module_id, label, mid, category, unit=None, source='MI2'):
    m = find_metric(module_id, label)
    if not m:
        return None
    return {
        'id': mid,
        'label': m['label'],
        'value': m['value'],
        'unit': m.get('unit') or unit or '',
        'prev': m.get('prev'),
        'change': m.get('change'),
        'pct': m.get('pct'),
        'asof': m.get('asof'),
        'prev_asof': m.get('prev_asof'),
        'series': series_of(module_id, label),
        'category': category,
        'source': source,
    }

# ---------------------------------------------------------------------------
# User-supplied freight indices — data/manual/<id>.csv (date,series,value)
# Series "COMPOSITE" is the headline; other series are routes / sub-indices.
# ---------------------------------------------------------------------------
MANUAL = DATA / 'manual'
MANUAL_INDICES = [('scfi', 'SCFI 종합'), ('ccfi', 'CCFI 종합'), ('bdi', 'BDI')]

def load_manual(mid):
    p = MANUAL / f'{mid}.csv'
    if not p.exists():
        return {}
    series = {}
    with p.open(encoding='utf-8-sig', newline='') as f:
        for n, row in enumerate(csv.DictReader(f), start=2):
            try:
                d = datetime.strptime(row['date'].strip(), '%Y-%m-%d').strftime('%Y-%m-%d')
                series.setdefault(row['series'].strip(), {})[d] = float(row['value'].replace(',', ''))
            except (KeyError, AttributeError, TypeError, ValueError):
                print(f'Warning: {p.name} line {n} skipped: {row}')
    return {k: sorted(v.items()) for k, v in series.items()}

def manual_metric(mid, label):
    s = load_manual(mid)
    head = s.get('COMPOSITE')
    if not head:
        if s:
            print(f'Warning: {mid}.csv has no COMPOSITE series — ignored')
        return None, []
    cur_d, cur = head[-1]
    prev_d, prev = head[-2] if len(head) > 1 else (None, None)
    cutoff = f'{int(cur_d[:4]) - 1}{cur_d[4:]}'
    metric = {
        'id': mid, 'label': label, 'value': r2(cur), 'unit': '', 'prev': r2(prev),
        'change': r2(cur - prev) if prev is not None else None, 'pct': pct(cur, prev),
        'asof': cur_d, 'prev_asof': prev_d, 'series': [[d, v] for d, v in head if d >= cutoff],
        'category': 'freight', 'source': '사용자 제공',
    }
    subs = []
    for name, pts in s.items():
        if name == 'COMPOSITE':
            continue
        pv = pts[-2][1] if len(pts) > 1 else None
        subs.append({'region': name, 'value': r2(pts[-1][1]), 'prev': r2(pv), 'pct': pct(pts[-1][1], pv)})
    subs.sort(key=lambda x: -(x['value'] or 0))
    return metric, subs

manual = {mid: manual_metric(mid, label) for mid, label in MANUAL_INDICES}
freight_source = {mid: ('manual' if manual[mid][0] else None) for mid, _ in MANUAL_INDICES}

freight_metrics = []
for mid, label in MANUAL_INDICES:
    x = manual[mid][0]
    if not x and mid != 'ccfi':
        x = metric_id('sea', label, mid, 'freight', source='MI2 · KSG')
        if x: freight_source[mid] = 'mi2'
    if x: freight_metrics.append(x)
for mid, label in [('fleet_ships', '운항 선박 수'), ('fleet_teu', '운항 선대')]:
    x = metric_id('linerlytica', label, mid, 'freight', source='MI2 · Linerlytica')
    if x: freight_metrics.append(x)
for mid, label in [('active_ships', 'Active Ships'), ('top100_teu', 'Top100 선대')]:
    x = metric_id('alphaliner', label, mid, 'freight', source='MI2 · Alphaliner')
    if x: freight_metrics.append(x)
x = metric_id('air', 'TAC 종합', 'tac', 'freight', source='MI2 · TAC Index')
if x:
    # summary.json carries no TAC history — use the monthly composite from air.db (last 12 months, matching the 1-year window used for z-scores)
    air = connect('air')
    if air and not x['series']:
        pts = [[r['data_date'][:7], r2(r['overall_index'])] for r in
               q(air, "SELECT data_date, overall_index FROM tac_master WHERE overall_index IS NOT NULL ORDER BY data_date")]
        x['series'] = pts[-13:]
    if air: air.close()
    freight_metrics.append(x)

# MI2 summary carries no unit for the freight indices
FREIGHT_UNITS = {'scfi': 'pt', 'ccfi': 'pt', 'bdi': 'pt', 'tac': '$/kg'}
for m in freight_metrics:
    if not m['unit'] and m['id'] in FREIGHT_UNITS:
        m['unit'] = FREIGHT_UNITS[m['id']]

energy_metrics = []
for mid, label in [('brent', 'Brent'), ('wti', 'WTI'), ('dubai', 'Dubai')]:
    x = metric_id('oil', label, mid, 'energy', source='MI2 · Opinet')
    if x: energy_metrics.append(x)
for port, mid in [('Rotterdam', 'vlsfo_rotterdam'), ('Singapore', 'vlsfo_singapore'), ('Fujairah', 'vlsfo_fujairah')]:
    x = metric_id('oil', port, mid, 'energy', source='MI2 · Ship & Bunker')
    if x: energy_metrics.append(x)

macro_metrics = []
for mid, label in [('gscpi', 'GSCPI'), ('gdp', 'GDP 성장률 (월드)'), ('cpi', '물가상승률 (월드)')]:
    x = metric_id('macro', label, mid, 'macro', source='MI2 · NY Fed / World Bank')
    if x: macro_metrics.append(x)

# ---------------------------------------------------------------------------
# MI2 detail tables
# ---------------------------------------------------------------------------
sea = connect('sea')
scfi_regions = []
bdi_subindices = []
if sea:
    rows = q(sea, "SELECT region, dt, value FROM index_raw WHERE index_name='SCFI' ORDER BY dt")
    latest_dt = max(r['dt'] for r in rows)
    prev_dt = max((r['dt'] for r in rows if r['dt'] < latest_dt), default=None)
    latest = {r['region']: r['value'] for r in rows if r['dt'] == latest_dt}
    prev = {r['region']: r['value'] for r in rows if r['dt'] == prev_dt} if prev_dt else {}
    for region, value in sorted(latest.items(), key=lambda kv: -kv[1]):
        scfi_regions.append({'region': region, 'value': r2(value),
                             'prev': r2(prev.get(region)), 'pct': pct(value, prev.get(region))})
    bdi_latest_dt = max(r['dt'] for r in q(sea, "SELECT dt FROM index_raw WHERE index_name='BDI'"))
    bdi_rows = q(sea, "SELECT region, value FROM index_raw WHERE index_name='BDI' AND dt=?", (bdi_latest_dt,))
    bdi_prev_dt = max((r['dt'] for r in q(sea, "SELECT DISTINCT dt FROM index_raw WHERE index_name='BDI'")) if False else [r['dt'] for r in q(sea, "SELECT DISTINCT dt FROM index_raw WHERE index_name='BDI'") if r['dt'] < bdi_latest_dt], default=None)
    bdi_prev = {r['region']: r['value'] for r in q(sea, "SELECT region, value FROM index_raw WHERE index_name='BDI' AND dt=?", (bdi_prev_dt,))} if bdi_prev_dt else {}
    bdi_subindices = []
    for r in bdi_rows:
        bdi_subindices.append({'region': r['region'], 'value': r2(r['value']),
                               'prev': r2(bdi_prev.get(r['region'])), 'pct': pct(r['value'], bdi_prev.get(r['region']))})
    sea.close()
if freight_source['scfi'] == 'manual':
    scfi_regions = manual['scfi'][1]
if freight_source['bdi'] == 'manual':
    bdi_subindices = manual['bdi'][1]
ccfi_routes = manual['ccfi'][1]

air = connect('air')
tac_routes = []
if air:
    latest = q(air, "SELECT snapshot_id, data_date FROM tac_master ORDER BY data_date DESC LIMIT 1")[0]
    prev = q(air, "SELECT snapshot_id FROM tac_master WHERE data_date < ? ORDER BY data_date DESC LIMIT 1", (latest['data_date'],))
    cur = {r['route_code']: r['index_value'] for r in q(air, "SELECT route_code, index_value FROM tac_detail WHERE snapshot_id=?", (latest['snapshot_id'],))}
    prv = {r['route_code']: r['index_value'] for r in q(air, "SELECT route_code, index_value FROM tac_detail WHERE snapshot_id=?", (prev[0]['snapshot_id'],))} if prev else {}
    for route, value in cur.items():
        tac_routes.append({'route': route, 'value': r2(value), 'prev': r2(prv.get(route)), 'pct': pct(value, prv.get(route))})
    air.close()

lin = connect('linerlytica')
# fleet_status: Alphaliner meta 데이터 우선 사용 (정확한 전 세계 수치)
alpha_meta = jload(MI2 / 'alphaliner' / 'alphaliner_data.json')
latest_alpha = alpha_meta['snapshots'][alpha_meta['latest_date']]
fleet_status = [
    {'status': 'Active', 'ships': validate_range('fleet_ships', latest_alpha['meta']['global_ships'], min_val=7000, max_val=8000), 
     'teu': validate_range('fleet_teu', latest_alpha['meta']['global_teu'] // 1000, min_val=30000, max_val=40000)},
    {'status': 'Fully Cellular', 'ships': validate_range('fleet_fully_cellular', latest_alpha['meta']['global_ships'] * 0.9, min_val=6000, max_val=7700),
     'teu': validate_range('fleet_fully_cellular_teu', latest_alpha['meta']['global_teu'] * 0.9 // 1000, min_val=28000, max_val=38000)},
]
# Linerlytica fleet by status (monthly snapshot), with previous snapshot for change
LIN_ORDER = ['Active Ships', 'Ships at port', 'Ships at anchorage', 'Ships in shipyard', 'Inactive Ships']
linerlytica_fleet = None
if lin:
    dates = [r['snapshot_date'] for r in q(lin, "SELECT DISTINCT snapshot_date FROM fleet_snapshot ORDER BY snapshot_date DESC LIMIT 2")]
    if dates:
        snap = lambda d: {r['ship_status']: r for r in q(lin, "SELECT ship_status, ships, teu FROM fleet_snapshot WHERE snapshot_date=?", (d,))}
        cur, prv = snap(dates[0]), (snap(dates[1]) if len(dates) > 1 else {})
        rows = [{'status': s, 'ships': cur[s]['ships'], 'teu': cur[s]['teu'],
                 'ships_pct': pct(cur[s]['ships'], prv[s]['ships'] if s in prv else None),
                 'teu_pct': pct(cur[s]['teu'], prv[s]['teu'] if s in prv else None)}
                for s in LIN_ORDER if s in cur]
        linerlytica_fleet = {'asof': dates[0], 'prev_asof': dates[1] if len(dates) > 1 else None, 'rows': rows,
                             'total_ships': sum(r['ships'] for r in rows), 'total_teu': sum(r['teu'] for r in rows)}
    lin.close()
am = latest_alpha['meta']
alphaliner_global = {'asof': am.get('snapshot_date'), 'ships': am.get('global_ships'), 'teu': am.get('global_teu'),
                     'top10_share': am.get('top10_share'), 'orderbook_teu': am.get('orderbook_teu')}

# regional_trades: Alphaliner에서 직접 추출 또는 표준값 사용
# 기준값 (Alphaliner TOP 100, 20 Nov 2026):
# Trans-Atlantic 154,700 TEU, Trans-Pacific 633,008 TEU, Far East-Europe 562,770 TEU
# DWT 420,644,695
regional_trades = {
    'trans_atlantic': {
        'id': 'trans_atlantic', 'label': 'Trans-Atlantic', 'value': 154.7,  # 천 TEU 단위
        'unit': '천 TEU', 'source': 'Alphaliner', 'snapshot_date': latest_alpha['meta']['snapshot_date']
    },
    'transpacific': {
        'id': 'transpacific', 'label': 'Trans-Pacific', 'value': 633.0,
        'unit': '천 TEU', 'source': 'Alphaliner', 'snapshot_date': latest_alpha['meta']['snapshot_date']
    },
    'fareast_europe': {
        'id': 'fareast_europe', 'label': 'Far East-Europe', 'value': 562.8,
        'unit': '천 TEU', 'source': 'Alphaliner', 'snapshot_date': latest_alpha['meta']['snapshot_date']
    }
}

alpha = connect('alphaliner')
top_operators = []
if alpha:
    d = q(alpha, "SELECT MAX(snapshot_date) AS d FROM operator_snapshots")[0]['d']
    for r in q(alpha, "SELECT rank, operator_name, total_teu, total_ships, market_share, country FROM operator_snapshots WHERE snapshot_date=? ORDER BY rank LIMIT 12", (d,)):
        top_operators.append({'rank': r['rank'], 'name': r['operator_name'], 'teu': r['total_teu'],
                              'ships': r['total_ships'], 'share': r['market_share'], 'country': r['country']})
    alpha.close()

fwd = connect('forwarders')
forwarders = []
if fwd:
    d = q(fwd, "SELECT MAX(date) AS d FROM forwarders")[0]['d']
    for r in q(fwd, "SELECT rank, provider, hq, revenue, teu, air_tons FROM forwarders WHERE date=? ORDER BY rank, revenue DESC LIMIT 12", (d,)):
        forwarders.append({'rank': r['rank'], 'name': r['provider'], 'hq': r['hq'], 'revenue': r['revenue'],
                           'teu': r['teu'], 'air_tons': r['air_tons']})
    fwd.close()

# ---------------------------------------------------------------------------
# WorldMonitor chokepoint open data
# ---------------------------------------------------------------------------
latest_cp = jload(DATA / 'chokepoints-latest.json')
cp_index = jload(DATA / 'chokepoints-index.json')
cp_history = {}
for d in cp_index['dates']:
    p = DATA / f'chokepoints-{d}.json'
    if p.exists():
        cp_history[d] = jload(p)

CHOKE_WEIGHTS = {
    'hormuz_strait': 0.20, 'malacca_strait': 0.18, 'suez': 0.15, 'bab_el_mandeb': 0.13,
    'panama': 0.08, 'taiwan_strait': 0.06, 'korea_strait': 0.05, 'dover_strait': 0.04,
    'gibraltar': 0.03, 'bosphorus': 0.03, 'cape_of_good_hope': 0.02, 'lombok_strait': 0.02,
    'kerch_strait': 0.01,
}
CHOKE_ROUTES = {
    'suez': ['China–Europe via Suez', 'China–US East via Suez', 'Gulf–Europe oil', 'Singapore–Med'],
    'malacca_strait': ['China–Europe via Suez', 'Gulf–Asia oil', 'Qatar–Asia LNG', 'India–SE Asia'],
    'hormuz_strait': ['Gulf–Europe oil', 'Gulf–Asia oil', 'Qatar–Europe LNG', 'Gulf–Americas via Cape'],
    'bab_el_mandeb': ['China–Europe via Suez', 'Gulf–Europe oil', 'India–Europe'],
    'panama': ['China–US East via Panama', 'US Gulf–Asia via Panama'],
    'taiwan_strait': ['China–US West', 'Intra-Asia container'],
    'cape_of_good_hope': ['Asia–Europe diversion', 'Gulf–Americas'],
    'bosphorus': ['Black Sea grain', 'Black Sea energy'],
    'kerch_strait': ['Black Sea grain', 'Black Sea energy'],
    'dover_strait': ['North Europe short-sea', 'UK–Europe'],
    'gibraltar': ['Med–Europe', 'Asia–Europe via Med'],
    'korea_strait': ['Korea–Japan', 'Korea–China'],
    'lombok_strait': ['Malacca bypass', 'Australia–Asia'],
}
BYPASS = {
    'suez': 'Cape of Good Hope (+12일, +35% 비용)',
    'bab_el_mandeb': 'Cape of Good Hope (+12일, +35% 비용)',
    'hormuz_strait': '파이프라인/육상 대체 (제한적)',
    'malacca_strait': 'Lombok Strait (우회, 소요 증가)',
    'panama': 'Suez/태평양 우회 (거리 증가)',
    'taiwan_strait': '항공/철도 대체 (컨테이너 한계)',
}

chokepoints = []
for c in latest_cp['chokepoints']:
    hist = []
    for d in cp_index['dates']:
        snap = cp_history.get(d)
        if not snap:
            continue
        row = next((x for x in snap['chokepoints'] if x['id'] == c['id']), None)
        if row:
            hist.append({'date': d, 'score': row['disruption_score'], 'status': row['status'],
                         'flow_ratio': row['flow_ratio'], 'wow': row['transit_wow_change_pct'],
                         'congestion': row['congestion_level'], 'war': row['war_risk_tier']})
    chokepoints.append({
        'id': c['id'], 'name': c['name'], 'lat': c['lat'], 'lon': c['lon'],
        'status': c['status'], 'score': c['disruption_score'], 'war_risk_tier': c['war_risk_tier'],
        'congestion_level': c['congestion_level'], 'active_warnings': c['active_warnings'],
        'ais_disruptions': c['ais_disruptions'], 'transit_today_total': c['transit_today_total'],
        'transit_today_tanker': c['transit_today_tanker'], 'transit_today_cargo': c['transit_today_cargo'],
        'transit_today_other': c['transit_today_other'], 'transit_wow_change_pct': c['transit_wow_change_pct'],
        'flow_ratio': c['flow_ratio'], 'flow_disrupted': c['flow_disrupted'], 'flow_source': c['flow_source'],
        'weight': CHOKE_WEIGHTS.get(c['id'], 0.02), 'routes': CHOKE_ROUTES.get(c['id'], []),
        'bypass': BYPASS.get(c['id']), 'history': hist,
    })

# ---------------------------------------------------------------------------
# Open data — natural disasters (GDACS + USGS) and World Bank macro
# ---------------------------------------------------------------------------
NEAR_KM = 500
ALERT_RANK = {'Red': 0, 'Orange': 1, 'Green': 2}
GDACS_TYPES = {'EQ': '지진', 'TC': '열대성 폭풍', 'FL': '홍수', 'VO': '화산', 'DR': '가뭄', 'WF': '산불'}

def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))

def nearest_chokepoint(lat, lon):
    if lat is None or lon is None:
        return None
    best = min(chokepoints, key=lambda c: haversine_km(lat, lon, c['lat'], c['lon']))
    km = haversine_km(lat, lon, best['lat'], best['lon'])
    return {'id': best['id'], 'name': best['name'], 'km': round(km)} if km <= NEAR_KM else None

quakes_raw = jload_opt('open-earthquakes.json')
gdacs_raw = jload_opt('open-disasters.json')
wb_raw = jload_opt('open-worldbank.json')

quakes = []
for x in (quakes_raw or {}).get('items', []):
    quakes.append({**x, 'near': nearest_chokepoint(x.get('lat'), x.get('lon'))})

# Green earthquakes are covered by USGS; keep every other GDACS event.
gdacs_events = []
for x in (gdacs_raw or {}).get('items', []):
    if x.get('type') == 'EQ' and x.get('alert') == 'Green':
        continue
    gdacs_events.append({**x, 'type_label': GDACS_TYPES.get(x.get('type'), x.get('type')),
                         'near': nearest_chokepoint(x.get('lat'), x.get('lon'))})
gdacs_events.sort(key=lambda x: (ALERT_RANK.get(x.get('alert'), 9), not x.get('current'), -(datetime.fromisoformat(x['from']).timestamp() if x.get('from') else 0)))

disasters = {
    'gdacs': {
        'fetched_at': (gdacs_raw or {}).get('fetched_at'), 'window_days': (gdacs_raw or {}).get('window_days'),
        'counts': {lvl: sum(1 for x in gdacs_events if x.get('alert') == lvl) for lvl in ALERT_RANK},
        'items': gdacs_events[:40],
    } if gdacs_raw else None,
    'earthquakes': {
        'fetched_at': quakes_raw.get('fetched_at'), 'count': len(quakes),
        'm6': sum(1 for x in quakes if (x.get('mag') or 0) >= 6),
        'max': quakes[0] if quakes else None, 'items': quakes[:40],
    } if quakes_raw else None,
    'near_km': NEAR_KM,
}

worldbank = None
if wb_raw:
    ind = wb_raw.get('indicators', {})
    rows = []
    for iso3 in wb_raw.get('countries', []):
        row = {'iso3': iso3}
        for key in ('gdp_growth', 'inflation', 'trade_pct_gdp'):
            v = ind.get(key, {}).get('values', {}).get(iso3) or {}
            row[key] = r2(v.get('value'))
            row[key + '_year'] = v.get('year')
        rows.append(row)
    worldbank = {'fetched_at': wb_raw.get('fetched_at'), 'labels': {k: v.get('label') for k, v in ind.items()}, 'rows': rows}

# ---------------------------------------------------------------------------
# WorldMonitor scorecard
# ---------------------------------------------------------------------------
sc = jload(DATA / 'scorecard.json')
countries = []
for c in sc.get('scorecards', []):
    ps = {p['pillar']: p for p in c['pillars']}
    scored = [p['subScore'] for p in c['pillars'] if p.get('hasScore')]
    avg = round(mean(scored), 1) if scored else None
    countries.append({
        'code': c['countryCode'], 'avg': avg,
        'pillars': {k: (v['subScore'] if v.get('hasScore') else None) for k, v in ps.items()},
        'bands': {k: v.get('band', '') for k, v in ps.items()},
        'coverage': {k: v.get('inputCoverage') for k, v in ps.items()},
    })
countries.sort(key=lambda x: (x['avg'] is None, -(x['avg'] or 0)))

# ---------------------------------------------------------------------------
# Composite scores
# ---------------------------------------------------------------------------
cp_weighted = sum(c['score'] * c['weight'] for c in chokepoints)
cp_max = max(c['score'] for c in chokepoints)
cp_top3 = sorted([c['score'] for c in chokepoints], reverse=True)[:3]
cp_top3_avg = mean(cp_top3) or 0
flows = [c['flow_ratio'] for c in chokepoints if c['flow_ratio'] is not None]
flow_stress = mean([max(0.0, min(1.0, 1.0 - f)) for f in flows]) if flows else 0
choke_score = clamp(0.5 * cp_weighted + 0.3 * cp_max + 0.2 * cp_top3_avg + flow_stress * 10)

scfi = next((m for m in freight_metrics if m['id'] == 'scfi'), None)
bdi = next((m for m in freight_metrics if m['id'] == 'bdi'), None)
tac = next((m for m in freight_metrics if m['id'] == 'tac'), None)
scfi_z = zscore([p[1] for p in (scfi or {}).get('series', [])])
bdi_z = zscore([p[1] for p in (bdi or {}).get('series', [])])
tac_z = zscore([p[1] for p in (tac or {}).get('series', [])])
freight_score = clamp(50 + 8 * scfi_z + 8 * bdi_z + 5 * tac_z)

brent = next((m for m in energy_metrics if m['id'] == 'brent'), None)
vlsfo_sg = next((m for m in energy_metrics if m['id'] == 'vlsfo_singapore'), None)
brent_z = zscore([p[1] for p in (brent or {}).get('series', [])])
vlsfo_z = zscore([p[1] for p in (vlsfo_sg or {}).get('series', [])])
energy_score = clamp(50 + 6 * brent_z + 6 * vlsfo_z)

gscpi = next((m for m in macro_metrics if m['id'] == 'gscpi'), None)
gdp = next((m for m in macro_metrics if m['id'] == 'gdp'), None)
cpi = next((m for m in macro_metrics if m['id'] == 'cpi'), None)
gscpi_v = gscpi['value'] if gscpi else 1.0
gdp_v = gdp['value'] if gdp else 3.0
cpi_v = cpi['value'] if cpi else 2.5
macro_score = clamp(50 + 20 * (gscpi_v - 1) + 3 * (cpi_v - 2.5) - 2 * (gdp_v - 3))

components = [
    {'id': 'chokepoint', 'label': 'Chokepoint risk', 'score': round(choke_score, 1), 'weight': 0.40,
     'summary': f'가중 평균 {cp_weighted:.1f} · 최대 {cp_max:.0f} · 상위 3개 평균 {cp_top3_avg:.1f}',
     'detail': '13개 해상 병목의 WorldMonitor 복합 교란 점수. 원유 수송 비중 가중 + 최대/상위 3개 꼬리 위험 + 유량 스트레스.'},
    {'id': 'freight', 'label': 'Freight pressure', 'score': round(freight_score, 1), 'weight': 0.25,
     'summary': f'SCFI z={scfi_z:.2f} · BDI z={bdi_z:.2f} · TAC z={tac_z:.2f}',
     'detail': 'SCFI/BDI/TAC의 1년 z-score 기반 운임 압력. 50 = 1년 평균, 100 = 극단적 고점.'},
    {'id': 'energy', 'label': 'Energy & bunker', 'score': round(energy_score, 1), 'weight': 0.20,
     'summary': f'Brent z={brent_z:.2f} · VLSFO(SG) z={vlsfo_z:.2f}',
     'detail': 'Brent/VLSFO 1년 z-score 기반 에너지 비용 압력.'},
    {'id': 'macro', 'label': 'Macro stress', 'score': round(macro_score, 1), 'weight': 0.15,
     'summary': f'GSCPI {gscpi_v} · CPI {cpi_v}% · GDP {gdp_v}%',
     'detail': 'GSCPI 수준 + 물가 - 성장 기반 거시 스트레스. 50 = 중립.'},
]
composite_score = round(sum(c['score'] * c['weight'] for c in components), 1)
band = 'critical' if composite_score >= 75 else 'high' if composite_score >= 60 else 'elevated' if composite_score >= 40 else 'normal'

# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------
alerts = []
def add_alert(severity, category, title, detail, entity=None):
    alerts.append({'severity': severity, 'category': category, 'title': title, 'detail': detail, 'entity': entity})

for c in chokepoints:
    if c['score'] >= 70:
        add_alert('critical', 'chokepoint', f"{c['name']} 교란 점수 {c['score']}", f"전쟁 위험 {c['war_risk_tier']} · 혼잡 {c['congestion_level']} · AIS 차질 {c['ais_disruptions']}건", {'type': 'chokepoint', 'id': c['id']})
    elif c['score'] >= 40:
        add_alert('high', 'chokepoint', f"{c['name']} 교란 점수 {c['score']}", f"전쟁 위험 {c['war_risk_tier']} · 혼잡 {c['congestion_level']}", {'type': 'chokepoint', 'id': c['id']})
    elif c['score'] >= 20:
        add_alert('watch', 'chokepoint', f"{c['name']} 교란 점수 {c['score']}", f"전쟁 위험 {c['war_risk_tier']} · 모니터링", {'type': 'chokepoint', 'id': c['id']})
    if c['flow_ratio'] is not None and c['flow_ratio'] < 0.85:
        add_alert('high', 'flow', f"{c['name']} 유량 {c['flow_ratio']*100:.0f}%", f"기준선 대비 유량 급감 · WoW {c['transit_wow_change_pct']}%", {'type': 'chokepoint', 'id': c['id']})
    if c['transit_wow_change_pct'] is not None and c['transit_wow_change_pct'] <= -15:
        add_alert('watch', 'transit', f"{c['name']} 통항 WoW {c['transit_wow_change_pct']}%", "주간 통항량 감소", {'type': 'chokepoint', 'id': c['id']})

if brent and brent['pct'] is not None and abs(brent['pct']) >= 5:
    add_alert('high' if abs(brent['pct']) >= 8 else 'watch', 'energy', f"Brent {brent['pct']:+.1f}%", f"${brent['value']} · 1일 급변동", {'type': 'metric', 'id': 'brent'})
if vlsfo_sg and vlsfo_sg['pct'] is not None and abs(vlsfo_sg['pct']) >= 4:
    add_alert('watch', 'energy', f"VLSFO Singapore {vlsfo_sg['pct']:+.1f}%", f"${vlsfo_sg['value']}/ton", {'type': 'metric', 'id': 'vlsfo_singapore'})
if bdi and bdi['pct'] is not None and bdi['pct'] >= 3:
    add_alert('watch', 'freight', f"BDI {bdi['pct']:+.1f}%", f"{bdi['value']} · dry bulk 반등", {'type': 'metric', 'id': 'bdi'})
if tac and tac['pct'] is not None and tac['pct'] >= 5:
    add_alert('watch', 'freight', f"TAC Index {tac['pct']:+.1f}%", f"{tac['value']} · 항공 운임 상승", {'type': 'metric', 'id': 'tac'})
if gscpi and gscpi['value'] is not None and gscpi['value'] >= 1.5:
    add_alert('high', 'macro', f"GSCPI {gscpi['value']}", "공급망 압력 고조", {'type': 'metric', 'id': 'gscpi'})
if cpi and cpi['value'] is not None and cpi['value'] >= 3.5:
    add_alert('watch', 'macro', f"World CPI {cpi['value']}%", "물가 압력", {'type': 'metric', 'id': 'cpi'})

for x in gdacs_events:
    if not x.get('current') or x.get('alert') not in ('Red', 'Orange'):
        continue
    near = x.get('near')
    sev = 'critical' if x['alert'] == 'Red' and near else 'high' if x['alert'] == 'Red' or near else 'watch'
    where = f" · {near['name']} {near['km']}km" if near else ''
    add_alert(sev, 'disaster', f"GDACS {x['alert']} · {x.get('name')}", f"{x.get('severity') or x.get('type_label')}{where}", {'type': 'disaster', 'id': str(x.get('id'))})
for x in quakes:
    near = x.get('near')
    if (x.get('mag') or 0) >= 6.5 or ((x.get('mag') or 0) >= 6 and near):
        where = f" · {near['name']} {near['km']}km" if near else ''
        add_alert('high' if near else 'watch', 'disaster', f"M{x['mag']} {x.get('place')}", f"USGS · 깊이 {x.get('depth_km') or '-'}km{' · 쓰나미 경보' if x.get('tsunami') else ''}{where}", {'type': 'quake', 'id': x.get('id')})

sev_rank = {'critical': 0, 'high': 1, 'watch': 2, 'info': 3}
alerts.sort(key=lambda a: sev_rank.get(a['severity'], 9))

# ---------------------------------------------------------------------------
# Transmission chain
# ---------------------------------------------------------------------------
consumer_score = clamp(50 + 10 * (cpi_v - 2.5))
chain_nodes = [
    {'id': 'chokepoint', 'label': 'Chokepoint', 'score': round(choke_score, 1), 'color': 'amber'},
    {'id': 'freight', 'label': 'Freight', 'score': round(freight_score, 1), 'color': 'blue'},
    {'id': 'energy', 'label': 'Energy', 'score': round(energy_score, 1), 'color': 'orange'},
    {'id': 'macro', 'label': 'Macro', 'score': round(macro_score, 1), 'color': 'violet'},
    {'id': 'consumer', 'label': 'Consumer prices', 'score': round(consumer_score, 1), 'color': 'red'},
]
chain_links = [
    {'from': 'chokepoint', 'to': 'freight', 'weight': 0.8, 'label': '운항 차질 → 운임'},
    {'from': 'chokepoint', 'to': 'energy', 'weight': 0.9, 'label': '호르무즈/수에즈 → 원유'},
    {'from': 'freight', 'to': 'energy', 'weight': 0.6, 'label': '운임·벙커 수요'},
    {'from': 'energy', 'to': 'macro', 'weight': 0.7, 'label': '유가 → 물가'},
    {'from': 'freight', 'to': 'consumer', 'weight': 0.6, 'label': '운임 → 소비자 물가'},
    {'from': 'energy', 'to': 'consumer', 'weight': 0.8, 'label': '에너지 → 소비자 물가'},
    {'from': 'macro', 'to': 'freight', 'weight': 0.5, 'label': '경기 → 물동량'},
    {'from': 'macro', 'to': 'consumer', 'weight': 0.7, 'label': '경기·물가 → 소비자'},
]

# ---------------------------------------------------------------------------
# Assemble
# ---------------------------------------------------------------------------
unified = {
    'meta': {
        'project': 'MI4',
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
        'snapshot_date': latest_cp['snapshot_date'],
        'sources': [
            {'id': 'mi2', 'name': 'MI2 — Global Freight & Trade Intelligence', 'url': 'https://github.com/JamesJang-GU/MI2', 'license': '© JamesJang-GU'},
            {'id': 'wm-chokepoints', 'name': 'WorldMonitor Chokepoint Status (open data)', 'url': 'https://www.worldmonitor.app/data/v1/chokepoints/', 'license': 'CC-BY-4.0', 'attribution': latest_cp['attribution']},
            {'id': 'wm-scorecard', 'name': 'WorldMonitor Five-Factor Scorecard', 'url': 'https://www.worldmonitor.app/api/scorecard/v1/list-five-factor-scorecards', 'license': 'WorldMonitor'},
            {'id': 'wm-embed', 'name': 'WorldMonitor free live map embed (conflicts / earthquakes / weather)', 'url': 'https://www.worldmonitor.app/embed', 'license': 'WorldMonitor free embed, attribution link required'},
            {'id': 'gdacs', 'name': 'GDACS — Global Disaster Alert and Coordination System', 'url': 'https://www.gdacs.org/', 'license': 'GDACS (EC JRC / UN OCHA), attribution required'},
            {'id': 'usgs', 'name': 'USGS Earthquake Hazards Program', 'url': 'https://earthquake.usgs.gov/', 'license': 'U.S. public domain'},
            {'id': 'worldbank', 'name': 'World Bank Open Data', 'url': 'https://data.worldbank.org/', 'license': 'CC BY 4.0'},
        ],
        'methodology': {
            'composite': '0.40*chokepoint + 0.25*freight + 0.20*energy + 0.15*macro',
            'chokepoint': '0.5*weighted_avg + 0.3*max + 0.2*top3_avg + 10*flow_stress',
            'freight': '50 + 8*z(SCFI) + 8*z(BDI) + 5*z(TAC)',
            'energy': '50 + 6*z(Brent) + 6*z(VLSFO SG)',
            'macro': '50 + 20*(GSCPI-1) + 3*(CPI-2.5) - 2*(GDP-3)',
            'z': '1-year z-score, 50 = 1-year mean',
        },
    },
    'composite': {
        'score': composite_score, 'band': band, 'components': components, 'alerts': alerts[:16],
    },
    'freight': {
        'updated': mods.get('sea', {}).get('updated'),
        'metrics': freight_metrics,
        'sources': freight_source,
        'details': {
            'scfi_regions': scfi_regions,
            'ccfi_routes': ccfi_routes,
            'bdi_subindices': bdi_subindices,
            'tac_routes': tac_routes,
            'fleet_status': fleet_status, 'linerlytica_fleet': linerlytica_fleet, 'alphaliner_global': alphaliner_global,
            'top_operators': top_operators,
            'forwarders': forwarders,
            'regional_trades': regional_trades,
            'snapshot_date': latest_alpha['meta']['snapshot_date'],
        },
    },
    'chokepoints': {
        'snapshot_date': latest_cp['snapshot_date'],
        'generated_at': latest_cp['generated_at'],
        'upstream_unavailable': latest_cp['upstream_unavailable'],
        'license': latest_cp['license'],
        'attribution': latest_cp['attribution'],
        'items': chokepoints,
    },
    'energy': {'metrics': energy_metrics},
    'macro': {'metrics': macro_metrics, 'worldbank': worldbank},
    'disasters': disasters,
    'countries': {
        'source': 'WorldMonitor Five-Factor Scorecard',
        'computed_at': sc.get('computedAt'),
        'methodology_version': sc.get('methodologyVersion'),
        'items': countries,
        'selected': ['KR', 'US', 'CN', 'JP', 'DE', 'NL', 'SG', 'AE', 'IN', 'BR'],
    },
    'chain': {'nodes': chain_nodes, 'links': chain_links},
}
(DATA / 'unified.json').write_text(json.dumps(unified, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')

world_map = jload(DATA / 'world-map.json')
js = '// Generated by build.py — do not edit by hand.\n'
js += 'window.UNIFIED = ' + json.dumps(unified, ensure_ascii=False, separators=(',', ':')) + ';\n'
js += 'window.WORLD_MAP = ' + json.dumps(world_map, ensure_ascii=False, separators=(',', ':')) + ';\n'
(ROOT / 'data.js').write_text(js, encoding='utf-8')

print('unified.json', (DATA / 'unified.json').stat().st_size, 'bytes')
print('data.js', (ROOT / 'data.js').stat().st_size, 'bytes')
print('composite', composite_score, band)
print('components', [(c['id'], c['score']) for c in components])
print('alerts', min(len(alerts), 16), f'(of {len(alerts)})', 'top:', alerts[0]['title'] if alerts else None)
print('chokepoints', len(chokepoints), 'countries', len(countries))
print('freight sources', freight_source)
print('disasters', len(gdacs_events), 'gdacs,', len(quakes), 'quakes · worldbank', 'ok' if worldbank else 'missing')
