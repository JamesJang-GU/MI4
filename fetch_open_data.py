#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch keyless open-data sources that fill WorldMonitor categories
not available on the free tier.

Sources (no key, open license):
  - USGS Earthquake Hazards: M4.5+ past week (U.S. public domain)
  - GDACS (EU JRC / UN OCHA): disaster alerts, past 30 days
  - World Bank Open Data: GDP growth / CPI inflation / trade % GDP (CC BY 4.0)

Each source is fetched independently; a failed source keeps its previous file.

Usage:
    python3 fetch_open_data.py

Output:
    data/open-earthquakes.json, data/open-disasters.json, data/open-worldbank.json
"""
from __future__ import annotations

import json
import ssl
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)

UA = 'MI4-GlobalIntel/0.1.0 (contact: ops@example.test)'
TIMEOUT = 45

USGS_URL = 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson'
GDACS_URL = 'https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH'
WB_URL = 'https://api.worldbank.org/v2/country/{countries}/indicator/{indicator}?format=json&mrnev=1&per_page=100'

WB_COUNTRIES = ['KOR', 'USA', 'CHN', 'JPN', 'DEU', 'NLD', 'SGP', 'ARE', 'IND', 'BRA']
WB_INDICATORS = {
    'gdp_growth': 'NY.GDP.MKTP.KD.ZG',
    'inflation': 'FP.CPI.TOTL.ZG',
    'trade_pct_gdp': 'NE.TRD.GNFS.ZS',
}


def fetch(url: str):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
        return json.loads(r.read().decode('utf-8'))


def now_utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def save(name: str, obj):
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')


def earthquakes():
    raw = fetch(USGS_URL)
    items = []
    for f in raw.get('features', []):
        p = f.get('properties', {})
        coords = (f.get('geometry') or {}).get('coordinates') or [None, None, None]
        items.append({
            'id': f.get('id'), 'mag': p.get('mag'), 'place': p.get('place'),
            'time': datetime.fromtimestamp(p['time'] / 1000, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ') if p.get('time') else None,
            'lon': coords[0], 'lat': coords[1], 'depth_km': coords[2] if len(coords) > 2 else None,
            'alert': p.get('alert'), 'tsunami': p.get('tsunami'), 'sig': p.get('sig'), 'url': p.get('url'),
        })
    items.sort(key=lambda x: -(x['mag'] or 0))
    save('open-earthquakes.json', {
        'fetched_at': now_utc(), 'source': 'USGS Earthquake Hazards Program',
        'url': USGS_URL, 'license': 'U.S. public domain', 'items': items,
    })
    return f'{len(items)} quakes'


def disasters():
    today = datetime.now(timezone.utc).date()
    url = (f'{GDACS_URL}?eventlist=EQ;TC;FL;VO;DR;WF&alertlevel=Green;Orange;Red'
           f'&fromDate={today - timedelta(days=30)}&toDate={today}')
    raw = fetch(url)
    items = []
    for f in raw.get('features', []):
        p = f.get('properties', {})
        coords = (f.get('geometry') or {}).get('coordinates') or [None, None]
        sev = p.get('severitydata') or {}
        items.append({
            'type': p.get('eventtype'), 'id': p.get('eventid'), 'name': p.get('name'),
            'alert': p.get('alertlevel'), 'score': p.get('alertscore'), 'country': p.get('country'),
            'iso3': p.get('iso3'), 'from': p.get('fromdate'), 'to': p.get('todate'),
            'current': p.get('iscurrent'), 'severity': sev.get('severitytext'),
            'lon': coords[0] if isinstance(coords[0], (int, float)) else None,
            'lat': coords[1] if isinstance(coords[1], (int, float)) else None,
            'url': (p.get('url') or {}).get('report'),
        })
    save('open-disasters.json', {
        'fetched_at': now_utc(), 'source': 'GDACS — Global Disaster Alert and Coordination System',
        'url': 'https://www.gdacs.org/', 'license': 'GDACS (EC JRC / UN OCHA), attribution required',
        'window_days': 30, 'items': items,
    })
    return f'{len(items)} events'


def worldbank():
    countries = ';'.join(WB_COUNTRIES)
    out = {}
    for key, ind in WB_INDICATORS.items():
        raw = fetch(WB_URL.format(countries=countries, indicator=ind))
        rows = raw[1] if isinstance(raw, list) and len(raw) > 1 and raw[1] else []
        out[key] = {
            'indicator': ind,
            'label': rows[0]['indicator']['value'] if rows else ind,
            'values': {r['countryiso3code']: {'value': r['value'], 'year': r['date']} for r in rows if r.get('value') is not None},
        }
    save('open-worldbank.json', {
        'fetched_at': now_utc(), 'source': 'World Bank Open Data', 'url': 'https://data.worldbank.org/',
        'license': 'CC BY 4.0', 'countries': WB_COUNTRIES, 'indicators': out,
    })
    return f'{len(out)} indicators × {len(WB_COUNTRIES)} countries'


def main():
    failed = 0
    for name, fn in [('usgs', earthquakes), ('gdacs', disasters), ('worldbank', worldbank)]:
        try:
            print(f'[open] {name}: {fn()}')
        except Exception as e:
            failed += 1
            print(f'[open] {name} failed, keeping previous file: {type(e).__name__}: {e}')
    return 0 if failed < 3 else 1


if __name__ == '__main__':
    sys.exit(main())
