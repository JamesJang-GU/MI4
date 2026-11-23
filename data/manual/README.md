# data/manual — 사용자 제공 운임 지수

SCFI / CCFI / BDI는 이 폴더의 CSV로 공급합니다. `build.py`가 읽어 Freight 패널 카드와 상세 drawer에 반영합니다.
`main`에 이 폴더 변경이 push되면 `mi4-daily` 워크플로가 바로 재빌드합니다.

| 파일 | 카드 | 파일이 없을 때 |
|---|---|---|
| `scfi.csv` | SCFI 종합 + 항로별 | MI2 SCFI로 대체 |
| `ccfi.csv` | CCFI 종합 + 항로별 | "데이터 대기" 카드 |
| `bdi.csv`  | BDI + BCI/BPI/BSI 등 | MI2 BDI로 대체 |

## 형식 (UTF-8 CSV, 헤더 필수)

```csv
date,series,value
2026-11-20,COMPOSITE,1234.56
2026-11-20,Europe,1500
2026-11-20,US West Coast,2100
2026-11-13,COMPOSITE,1210.02
2026-11-13,Europe,1480
2026-11-13,US West Coast,2050
```

- `date` — `YYYY-MM-DD`
- `series` — `COMPOSITE` = 종합지수(카드 헤드라인·차트). 그 외 이름은 항로/서브지수 표로 표시 (예: BDI는 `BCI`, `BPI`, `BSI`, `BHSI`)
- `value` — 숫자. 천 단위 콤마 허용 (`"1,234.5"`는 따옴표로 감싸기)
- 행 순서 무관. 최근 1년치가 차트에 사용되고, 전 기간 대비 변동률은 직전 날짜 값 기준
- 읽을 수 없는 행은 경고만 출력하고 건너뜀
- `COMPOSITE` 행이 하나도 없으면 파일 전체를 무시함 (위 표의 대체 동작 적용)
- Excel에서는 "CSV UTF-8(쉼표로 분리)"로 저장
