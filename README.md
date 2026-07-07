# 경기·충남 영농형 태양광 RE100 특구 후보

## ▶ 바로 열기
**https://sojin-droid.github.io/Agrivoltaic-Cluster/**

설치·다운로드 없이 크롬(또는 엣지)에서 링크만 열면 바로 열립니다.

## 무엇을 볼 수 있나
- **Story**(첫 화면, `index.html`): 연구 소개 랜딩 — 핵심 수치, 시나리오별 후보 용량
  모핑 차트, 방법론 요약, 각 페이지로 가는 길잡이.
- **전국 지도**(`map.html`, 상단 메뉴 Map): 14개 시군의 특구 후보 클러스터 요약을 지도 위
  원형 마커로, 특구 필요도를 🥇🥈🥉 배지로 표시. "산단-특구 매칭선" 토글을 켜면 RE100
  대형 수요처와 인근 시군을 계통 여유 상태(실선/점선)로 이어서 보여줌.
- **Insight**(`insight.html`): 시군 종합 순위표(정렬 가능), 시군×지표 히트맵, RE100 수요
  충당률 게이지, 이용률 민감도 도구, 저(低)개인소유 후보 목록.
- **Method**(`method.html`): 발전공식·시나리오 정의·특구 필요도 지표와 가중치·데이터
  출처·알려진 한계.
- **시군 상세**(지도 마커나 카드 클릭): 시나리오(S0 현행법 / S3 특별법 / SMAX 이론최대)
  별 특구 후보 클러스터 폴리곤, 개인소유 비율 상한 슬라이더, 읍면동 계통 여유용량
  코로플레스, 변압기 아이콘, 필지 점 레이어, 지번/PNU 검색.
- **클러스터 클릭 시**: 설비용량·연간발전량·계통 여유, 영농형 최소단위(1유닛=1,000㎡=
  45kW) 아이콘, 인근 RE100 수요처까지 거리·충당률, PPA 수익성 계산기(IRR/NPV/회수기간).

## 데이터·방법론 요약
- 발전공식(고정): 설비용량 MW = 면적(m²) × 0.045 ÷ 1000, 연간발전량 MWh = MW × 8760 ×
  0.15(설비이용률 15%, 한국전력거래소 EPSIS 기준)
- 시나리오: S0(현행법, 최소 요건만) / S3(특별법·법개정, 5개 정책요건 중 하나 이상) /
  SMAX(이론최대, 15개 요건 중 하나 이상 — 하드 법적 제한지역 13종은 시나리오 무관 항상 제외)
- 병기 통계: 실측 산업용 전력수요(한국전력공사 빅데이터센터), 국가산업단지 생산실적
  (한국산업단지공단) — 각 수치의 출처·기준시점·한계는 화면 각주에 표시
- 필지 원본 데이터는 산업단지·대형소비처 반경 10km 이내로 수집돼 있어, 그보다 먼
  농지는 특구 후보 분석에 포함되지 않음(알려진 한계, 상세는 `CLAUDE.md` 참조)

<details>
<summary><b>개발자용: 로컬에서 실행·수정하기</b></summary>

빌드 시스템 없음 — 순수 정적 파일 + Python. 템플릿을 고치는 개발 작업을 할 때만 필요하고,
그냥 뷰어를 보기만 할 거라면 위 GitHub Pages 링크만으로 충분합니다.

### 실행
- **Mac/Linux**: 터미널에서 `./run.command` 실행(최초 1회 `chmod +x run.command`)
- **Windows**: `run.bat` 더블클릭
- **수동**: 이 폴더에서 터미널 열고 `python3 -m http.server 8002` 실행 후
  브라우저에서 http://localhost:8002 접속

### 데이터 위치
무거운 런타임 데이터(필지 점, 클러스터 후보, 읍면동 경계, 요약 통계 등)는 이 저장소가
아니라 **Supabase Storage 공개 버킷**(`agrivoltaic-data`)에서 서빙됩니다. 뷰어는
`DATA_BASE` URL로 직접 `fetch()`하며 버킷이 공개 읽기라 별도 키가 필요 없습니다.
로컬에서 데이터 파이프라인을 재실행한 뒤에는 `scripts/migrate_to_supabase.py`로
갱신분을 업로드하세요(`.env.example` 참고, 업로드에는 service_role 키 필요 — 절대 커밋 금지).

### 페이지 수정 시 필수 절차
- **지도 페이지**(`map.html`/`<시군>_map.html`)는 **직접 손편집 금지** — 전부
  `scripts/templates/{map,viewer}_template.html`에서 생성됩니다. 템플릿을 고친 뒤
  반드시 `python3 scripts/build_viewer.py`로 재생성.
- **서사 페이지**(`index.html`/`insight.html`/`method.html`)와 `assets/`는 손편집 대상 —
  빌더가 건드리지 않습니다.

관리 절차 전체(데이터 갱신, 시각화 추가, 배포 등)는 **`MANAGEMENT.md`** 에, 데이터
파이프라인(클러스터·전력수요·criteria 점수화 등) 구조와 실행 순서는 `CLAUDE.md`에
정리돼 있습니다.

### 폴더 구조
```
gyeonggi_chungnam/
  index.html     연구 소개 랜딩(Story) — 손편집
  map.html       전국 지도(build_viewer.py 산출물 — 손편집 금지)
  insight.html   데이터 인사이트(순위표·히트맵·게이지) — 손편집
  method.html    방법론·출처·한계 — 손편집
  assets/        공용 style.css(디자인 토큰) + site.js(인터랙션)
  gyeonggi/      경기 7개 시군 카드(코드만; 데이터는 Supabase)
  chungnam/      충남 7개 시군 카드(코드만; 데이터는 Supabase)
  scripts/       빌드·데이터 파이프라인 스크립트 + templates/ + migrate_to_supabase.py
  supabase/      Storage 버킷·정책 설정 SQL
  metadata/      원본 통계(산단 생산실적 CSV, 한전 전력사용량 엑셀 등)
  MANAGEMENT.md  사이트 관리 가이드
  run.command / run.bat   로컬 서버 실행 편의 스크립트
```

</details>
