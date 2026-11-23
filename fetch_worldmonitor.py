#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch WorldMonitor free-tier data for the unified dashboard.

Public (no key):
  - Chokepoint status open data (daily snapshots, CC-BY-4.0)
  - Five-Factor Country Scorecard

Paid-tier endpoints (API Starter and above) are intentionally not used.

Usage:
    python3 fetch_worldmonitor.py

Output:
    data/chokepoints-*.json, data/scorecard.json
"""
from __future__ import annotations

import json
import ssl
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)

UA = 'MI4-GlobalIntel/0.1.0 (contact: ops@example.test)'
PUBLIC = 'https://www.worldmonitor.app'
API = 'https://api.worldmonitor.app'
TIMEOUT = 30


def fetch(url: str, headers=None, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json', **(headers or {})})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.loads(r.read().decode('utf-8'))


def public_data():
    print('[public] chokepoint index…')
    idx = fetch(f'{PUBLIC}/data/v1/chokepoints/index.json')
    (DATA / 'chokepoints-index.json').write_text(json.dumps(idx, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    dates = idx.get('dates', [])
    latest = fetch(f'{PUBLIC}/data/v1/chokepoints/latest.json')
    (DATA / 'chokepoints-latest.json').write_text(json.dumps(latest, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    for d in dates:
        p = DATA / f'chokepoints-{d}.json'
        if p.exists():
            continue
        print(f'[public] chokepoint snapshot {d}…')
        try:
            snap = fetch(f'{PUBLIC}/data/v1/chokepoints/{d}.json')
            p.write_text(json.dumps(snap, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        except Exception as e:
            print(f'  skip {d}: {e}')
    print('[public] scorecard…')
    sc = fetch(f'{API}/api/scorecard/v1/list-five-factor-scorecards')
    (DATA / 'scorecard.json').write_text(json.dumps(sc, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'[public] {len(latest.get("chokepoints", []))} chokepoints, {len(sc.get("scorecards", []))} countries')


def main():
    public_data()
    return 0


if __name__ == '__main__':
    sys.exit(main())
