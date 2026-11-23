# MI4 — Global Freight & Trade Intelligence

**MI4**는 MI2(해운·항공 운송 크롤러), WorldMonitor **무료 티어** 데이터, 키 없는 원천 공개데이터(USGS·GDACS·World Bank), 사용자 제공 운임 지수(SCFI/CCFI/BDI)를 **한 화면 대시보드**로 통합한 프로젝트입니다.

> WorldMonitor 유료 플랜(API Starter 이상)이 필요한 항목은 사용하지 않습니다. 서버 측 REST 호출·재배포가 무료로 허용되는 데이터만 씁니다.

## 1. 카테고리별 구성

| 카테고리 | 데이터 | 소스 | 패널 |
|---|---|---|---|
| 해상 병목 | 13개 쵸크포인트 점수·상태·통항량 | WorldMonitor open data (CC BY 4.0) | Map + CHOKE board |
| 해운 운임 | SCFI / CCFI / BDI (+ 항로·서브지수) | **사용자 제공 CSV** (`data/manual/`), SCFI·BDI는 MI2 대체 | FREIGHT |
| 선대/역량·항공 | Linerlytica, Alphaliner, 포워더, TAC | MI2 | FREIGHT |
| 에너지 | Dubai/Brent/WTI, VLSFO 3항구 | MI2 | ENERGY |
| 거시 | GSCPI, World GDP/CPI + 10개국 GDP 성장률·CPI·무역/GDP | MI2 + World Bank (CC BY 4.0) | ECONOMIC |
| 자연재해 | 재난 경보(지진·태풍·홍수·화산·가뭄·산불), M4.5+ 지진 | GDACS, USGS | DISASTER + 지도 마커 |
| 국가 회복력 | 5-factor scorecard (196개국) | WorldMonitor public endpoint | RESILIENCE |
| 분쟁·기상 | 실시간 지도 (분쟁·지진·기상 레이어) | WorldMonitor 무료 embed | CONFLICT |
| 통합 | 복합 스트레스, 전이 체인, 인사이트, 알림 | MI4 | SYS / FLOW / INSIGHT / ALERT |

**제외 (WorldMonitor 유료)**: shipping rates, commodity quotes, energy prices, chokepoint history/bypass, country exposure, macro signals, world CPI, FRED, news/conflict API, `/api/bootstrap`.

## 2. 데이터 소스 & 라이선스

| 소스 | 접근 | 라이선스 |
|---|---|---|
| MI2 `summary.json` + SQLite | 로컬 (`../MI2`) | © JamesJang-GU |
| 사용자 제공 SCFI/CCFI/BDI | `data/manual/*.csv` | 제공자 |
| WorldMonitor Chokepoint Status open data | `https://www.worldmonitor.app/data/v1/chokepoints/` | **CC-BY-4.0** |
| WorldMonitor Five-Factor Scorecard | `https://api.worldmonitor.app/api/scorecard/v1/list-five-factor-scorecards` | WorldMonitor |
| WorldMonitor embed map | `https://www.worldmonitor.app/embed` (iframe, 시간당 갱신) | 무료, attribution 링크 필수 |
| GDACS 재난 경보 | `https://www.gdacs.org/gdacsapi/` | EC JRC / UN OCHA, attribution |
| USGS 지진 | `https://earthquake.usgs.gov/earthquakes/feed/` | U.S. public domain |
| World Bank Open Data | `https://api.worldbank.org/v2/` | **CC BY 4.0** |

**Chokepoint attribution (필수):**
> WorldMonitor (https://www.worldmonitor.app). Scores and statuses are computed by WorldMonitor from IMF PortWatch, NGA Maritime Safety Information, and AIS data via aisstream.io.

전체 attribution/라이선스: `NOTICE.md`.

## 3. Quick start

```bash
# 1) 공개 데이터 갱신 (키 없이)
python3 fetch_worldmonitor.py
python3 fetch_open_data.py

# 2) 대시보드 생성 (MI2 DB + WorldMonitor + open data + data/manual)
python3 make_map.py
python3 build.py

# 3) 단일 파일 생성 + 로컬 서버
python3 make_standalone.py
python3 -m http.server 8080
# → http://localhost:8080/
```

또는 `standalone.html`을 직접 열기 (단일 파일, 외부 의존성 없음).

### SCFI / CCFI / BDI 제공

`data/manual/scfi.csv`, `ccfi.csv`, `bdi.csv`를 `date,series,value` 형식으로 넣습니다 (`series=COMPOSITE`가 종합지수). 형식 상세: [`data/manual/README.md`](data/manual/README.md). 파일이 없으면 SCFI·BDI는 MI2 값, CCFI는 "데이터 대기" 카드로 표시됩니다.

## 4. 화면 구성

```
┌────────────┬──────────────────────────────────────┬────────────┐
│ SYS 복합   │ MAP 쵸크포인트 + 재해 마커            │ ALERT      │
├────────────┴──────┬──────────────────────┬────────┴────────────┤
│ CHOKE 병목 보드   │ FREIGHT SCFI·CCFI·BDI│ DISASTER GDACS/USGS │
├────────────┬──────┴─────┬────────────────┼─────────────────────┤
│ ENERGY     │ ECONOMIC   │ RESILIENCE     │ CONFLICT (WM embed) │
│            │ MI2 + WB   │                │                     │
├────────────┴────────────┴───────┬────────┴─────────────────────┤
│ TRANSMISSION CHAIN              │ KEY INSIGHTS                 │
└─────────────────────────────────┴──────────────────────────────┘
```

- **복합 스트레스 지수**: 0–100, `0.40*chokepoint + 0.25*freight + 0.20*energy + 0.15*macro`
- **클릭**: 지도 노드, 병목 행, 지표 카드, 재해/지진, 국가, 체인 노드, 인사이트, 알림 → 상세 drawer
- **병목 인근 재해**: 쵸크포인트 500km 이내 재해·지진은 `near` 표시 + 알림 등급 상향
- **상세 drawer**: 시계열 차트(hover), 통계, 관련 표(SCFI 항로/BDI 서브/선대 상태/Top 오퍼레이터/포워더/VLSFO 항구), 관련 지표 pill, 출처
- **국가 전체 196개**: `ALL 196 →` → 검색 가능한 전체 랭킹
- **반응형**: 1440×900 1화면, <1250px 2열, <760px 1열

## 5. 파일 구조

```
MI4/
├── index.html              # 대시보드 (data.js 참조)
├── standalone.html         # data.js 인라인 단일 파일
├── data.js                 # build.py 생성 (window.UNIFIED + window.WORLD_MAP)
├── build.py                # MI2 DB + WorldMonitor JSON → unified.json / data.js
├── fetch_worldmonitor.py   # WorldMonitor 무료 티어 데이터 수집
├── fetch_open_data.py      # USGS / GDACS / World Bank 수집
├── make_map.py             # worldmonitor TopoJSON → SVG land path
├── make_standalone.py      # index.html + data.js → standalone.html
├── mi4.config.json         # 프로젝트 설정 (MI2/WorldMonitor 경로)
├── Makefile                # fetch / build / standalone / serve
├── data/
│   ├── unified.json        # 통합 데이터
│   ├── world-map.json      # SVG land path
│   ├── chokepoints-*.json  # WorldMonitor 일별 스냅샷
│   ├── chokepoints-latest.json
│   ├── scorecard.json
│   ├── open-earthquakes.json   # USGS
│   ├── open-disasters.json     # GDACS
│   ├── open-worldbank.json     # World Bank
│   └── manual/                 # 사용자 제공 SCFI/CCFI/BDI CSV
├── shot-main.png
├── shot-detail.png
└── NOTICE.md
```

## 6. 운영 아키텍처

```
MI2 GitHub Actions (매일 00:00 KST)
  └─ 7개 크롤러 → <module>.db
        └─ run_all.py --summary-only → summary.json
                    │
WorldMonitor open data (매일 06:23 UTC)                │
  └─ chokepoints/{date}.json + latest.json             │
  └─ scorecard (public)                                │
                    │                                  │
                    └──────────► MI4 build.py ◄────────┘
                                      │
                                      ├─ data/unified.json
                                      ├─ data.js
                                      └─ standalone.html
                                      │
                              GitHub Pages / 정적 호스팅
```

### 배포 옵션

1. **정적(현재)**: GitHub Pages에 `index.html` + `data.js` + `standalone.html` 업로드. 서버 비용 0.
2. **자동화**: GitHub Actions cron으로 `fetch_worldmonitor.py && fetch_open_data.py && build.py && make_standalone.py` 실행 후 커밋.
3. **프론트 교체**: `data/unified.json` 스키마를 유지하면 React/Vue/Next.js로 이식 가능.

## 7. 복합 지수 계산식

```text
chokepoint = 0.5*weighted_avg + 0.3*max + 0.2*top3_avg + 10*flow_stress
             weights: hormuz .20, malacca .18, suez .15, bab_el_mandeb .13, panama .08, … (합 1.0)
freight    = 50 + 8*z(SCFI) + 8*z(BDI) + 5*z(TAC)
energy     = 50 + 6*z(Brent) + 6*z(VLSFO Singapore)
macro      = 50 + 20*(GSCPI-1) + 3*(CPI-2.5) - 2*(GDP-3)
composite  = 0.40*chokepoint + 0.25*freight + 0.20*energy + 0.15*macro
z(x)       = 1년 z-score; 50 = 1년 평균
```

- `flow_stress` = `mean(clamp(1 - flow_ratio, 0, 1))` (flow_ratio가 있는 쵸크포인트만)
- `top3_avg` = disruption score 상위 3개 평균
- **한계**: 가중치/체인은 휴리스틱. WorldMonitor/MI2 공식 지수 아님.

## 8. 현재 스냅샷 (2026-11-05)

- 복합 지수 **56.6 / elevated**
- Chokepoint 51.0 · Freight 63.4 · Energy 58.7 · Macro 57.4
- 최다 위험: **Strait of Hormuz 75 (war_zone)**, Kerch 70 (war_zone), Bab el-Mandeb 40 (critical)
- SCFI 3,687.35 · BDI 2,694 · TAC 5.21
- Brent 94.62 (-8.7%) · WTI 88.12 (-8.3%) · VLSFO Singapore 901.5 $/ton (-4.2%)
- GSCPI 1.28 · World CPI 3.04% · World GDP 2.92%


## 10. GitHub에 올리기 / 배포

### 1) GitHub에서 repo 생성
- https://github.com/new → 이름 `MI4` → Public → Create.
- 또는 CLI(gh)가 있으면:
  ```bash
  gh repo create JamesJang-GU/MI4 --public --source=. --push
  ```

### 2) Local MI4 push
```bash
cd /home/user/MI4
git remote add origin https://github.com/JamesJang-GU/MI4.git
git push -u origin main
```

### 3) GitHub Pages
- Settings → Pages → Build and deployment → Source: **Deploy from a branch**
- Branch: **main** → /(root) → Save
- URL: `https://jamesjang-gu.github.io/MI4/`

### 4) Daily build workflow (이미 포함됨)
`.github/workflows/mi4-daily.yml`
- 매일 **01:00 KST** (`cron: "0 16 * * *"`)
- MI2 repo clone → WorldMonitor 무료 데이터 + USGS/GDACS/World Bank fetch → `build.py` → `make_standalone.py` → commit/push
- `data/manual/**` push 시에도 즉시 실행, Actions 탭에서 수동 실행(`Run workflow`) 가능
- MI2의 00:00 KST 크롤링이 끝난 뒤 실행되도록 01:00 KST로 설정
- `data/world-map.json`은 커밋되어 있으므로 CI에서는 `make_map.py`를 실행하지 않음 (지도 갱신 시에만 로컬에서 실행 후 커밋)

### 5) 확인
- `https://jamesjang-gu.github.io/MI4/` 열기
- 헤더 `MI4 CORE`, 12개 패널, 13개 지도 노드, 196개국 확인
- 쵸크포인트/지표/국가 클릭 → 상세 drawer
- Actions 탭에서 `mi4-daily` 실행 로그 확인

## 9. 한계 / 다음 단계

- **원자재**: MI2에는 유가만 있음. 금/구리/리튬 등은 WorldMonitor 유료이므로 제외.
- **뉴스/분쟁**: WorldMonitor news/conflict API는 유료. 분쟁은 무료 embed 지도로만 표시 (수치 미연동).
- **상관분석**: 체인 가중치는 정성적. 실제 시계열 상관/회귀로 보정 가능.
- **알림**: 임계치 초과 시 Slack/Teams/Telegram 웹훅 연동 가능.
- **라이선스**: 데이터 라이선스는 `NOTICE.md` 참조. 코드 라이선스는 별도 지정 필요.
