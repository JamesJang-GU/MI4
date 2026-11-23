# NOTICE / Attribution — MI4

## MI4
- Project: MI4 — Global Freight & Trade Intelligence
- Integration layer for MI2 + WorldMonitor.
- Composite index, transmission-chain weights, alert rules, and dashboard UI are original to MI4 and are not official MI2 or WorldMonitor indices.

## MI2
- Source: https://github.com/JamesJang-GU/MI2
- Copyright © JamesJang-GU
- Used: `summary.json` and per-module SQLite snapshots (SCFI/BDI, Linerlytica, Alphaliner, forwarders, TAC, oil, macro).

## WorldMonitor — Chokepoint Status open data
- Source: https://www.worldmonitor.app/data/v1/chokepoints/
- License: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)
- Attribution (must reproduce):
  > WorldMonitor (https://www.worldmonitor.app). Scores and statuses are computed by WorldMonitor from IMF PortWatch, NGA Maritime Safety Information, and AIS data via aisstream.io.
- Upstream: IMF PortWatch, NGA Maritime Safety Information, AISstream, Lloyd's Joint War Committee listed areas + open-source reporting.

## WorldMonitor — Five-Factor Scorecard
- Source: https://api.worldmonitor.app/api/scorecard/v1/list-five-factor-scorecards
- Public endpoint, no key. Pillars: food, energy, demographics, technology, defense.

## WorldMonitor — Embed map (free)
- Source: https://www.worldmonitor.app/embed (iframe, layers: conflicts, earthquakes, weather)
- Free embed; the visible "Powered by World Monitor" link in the panel header must be kept.
- Paid WorldMonitor API tiers (API Starter and above) are intentionally not used.

## GDACS — Global Disaster Alert and Coordination System
- Source: https://www.gdacs.org/ (API: https://www.gdacs.org/gdacsapi/)
- Joint initiative of the European Commission Joint Research Centre and UN OCHA.
- Attribution: "Source: GDACS (https://www.gdacs.org)".

## USGS Earthquake Hazards Program
- Source: https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php
- U.S. Government work, public domain. Courtesy of the U.S. Geological Survey.

## World Bank Open Data
- Source: https://data.worldbank.org/ (indicators NY.GDP.MKTP.KD.ZG, FP.CPI.TOTL.ZG, NE.TRD.GNFS.ZS)
- License: CC BY 4.0. Attribution: "The World Bank: World Development Indicators".

## User-supplied freight indices
- `data/manual/scfi.csv`, `ccfi.csv`, `bdi.csv` are supplied by the repository owner. SCFI/CCFI (Shanghai Shipping Exchange) and BDI (Baltic Exchange) remain the property of their publishers; the supplier is responsible for redistribution rights.
