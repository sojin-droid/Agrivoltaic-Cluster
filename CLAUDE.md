# CLAUDE.md

경기·충남 14개 시군의 **영농형 태양광 RE100 입지 분석 뷰어**. 산업단지 주변 농지 필지의
태양광 발전 잠재량·자급률·특구 후보 클러스터를 지도로 시각화한다.

## 실행 (빌드 시스템 없음 — 순수 정적 + Python)
- `python3 -m http.server 8002` 후 브라우저에서:
  - `http://localhost:8002/index.html` — **전국 메인 뷰어**(14개 시군 카드: 시나리오별 후보 수/합계MW/평균 개인비율/grid_ok, 다중선택 시 합계)
  - `http://localhost:8002/<sido>/<code_name>/<시군>_map.html` — 시군 상세(시나리오·개인비율 상한 t·후보 폴리곤·읍면동 코로플레스·필지 점 레이어)
- 편의 실행: `run.command`(mac) / `run.bat`(win). `package.json` 없음(npm 불필요).
- **2026-07-04부로 뷰어가 "산단 반경 선택" 모델에서 "특구 후보 클러스터 열람" 모델로 전면 재구축됨**
  (구 UI: 산단 선택→반경 슬라이더→필지 실시간 계산. 신 UI: 시나리오/개인비율 상한으로
  미리 계산된 후보 클러스터를 필터링해 보기만 함 — 클라이언트 계산 없음).

## 구조
- `index.html`, `<시군>_map.html` — **템플릿에서 생성됨(직접 손편집 금지)**. 소스는
  `scripts/templates/index_template.html`/`viewer_template.html` + `scripts/build_viewer.py`.
- `scripts/sggs_data.json` — 시군 메타(이름·좌표·산단 URL, 과거 index.html의 SGGS 배열을
  1회 추출해 고정) — `build_viewer.py`의 입력.
- `chungnam/*/`, `gyeonggi/*/` — 시군별 폴더. 각 `<시군>_map.html` + 데이터 파일.
- `supagit/` — 동일 뷰어의 **Supabase 연동 변형**(현재 `config.js` 자격증명 placeholder, 미연결). 범위 밖이면 건드리지 말 것.
- `scripts/` — 빌드 스크립트. `scripts/legacy/` = 폐기된 `_patch_*.py` 5종(과거 문자열
  치환 패치 방식, 더 이상 안 씀 — 참고용으로만 보존). `cluster_db/clusters.db` = 옛
  클러스터 원천 DB(생성 스크립트 유실, `candidate_clusters` 파이프라인과 무관).

## ⚠️ 반드시 지킬 규칙
- **`index.html`/`<시군>_map.html`을 손으로 직접 편집 금지.** `scripts/templates/*.html`을
  고치고 `python3 scripts/build_viewer.py`로 전체 재생성할 것(멱등 가드 없음 — 템플릿이
  항상 진실이라 매번 덮어씀). 과거 `_patch_*.py`(정확 문자열 치환 + 멱등 가드) 방식은
  폐기, `scripts/legacy/`에 참고용으로만 남음.
- **발전 계산식·표시값을 임의로 바꾸지 말 것**: 설비용량 MW = `면적(m²) × 0.045 ÷ 1000`,
  연간발전량 MWh = `MW × 8760 × 0.15`(설비이용률 15%), 자급률 = `연간발전량 ÷ 소비량 × 100`.
- **비밀키**: `.env`의 `KEPCO_API_KEY`/`SGIS_CONSUMER_KEY`/`SGIS_CONSUMER_SECRET`는 gitignore 대상.
  값을 출력/커밋하지 말 것. 코드에서는 항상 `.env`에서만 읽는다(하드코딩 금지).
- **grid_ok_pct 계산 규칙(확정, 2026-07-04)**: `grid_ok_pct = true 개수 / (true+false 개수)`.
  `null`(=`pool_incomplete`, 계통 데이터 일부 없음)은 **분모에서 제외**하고 "판정불가 N건"으로
  별도 표기한다 — null을 fail로 세면 화성·평택처럼 동 데이터 공백이 큰 시군이 실제로는
  계통 여유가 나쁘지 않은데도 부당하게 나빠 보인다. `scripts/build_candidate_summary.py`와
  `viewer_template.html`/`index_template.html` 양쪽에 동일하게 적용돼 있음 — 한쪽만
  고치지 말 것.

## 데이터 파이프라인 (변경 후 재생성 필요)
- `<시군>_parcels.geojson`(원본 폴리곤, 무거움·gitignore) → **`scripts/build_points.py`** →
  `<시군>_points.json`(경량 점, gitignore). 시군 상세 뷰어가 소비. 필지 변경 시 재생성.
  **⚠️ 알려진 한계(2026-07-06 확인)**: 14개 시군 전부 `<시군>_parcels.geojson`이 그
  시군의 산업단지·대형소비처 각각으로부터 **반경 10km 이내 필지만** 포함한다(실측:
  당진·보령·평택·홍성 4개 시군 전부 "필지→최근접 산단 거리" 최대값이 10.0~10.1km로
  동일 — 우연 아님). 원본 zip 백업(`gyeonggi_chungnam-*.zip`)의 당진 parcels.geojson도
  동일 필지 수(96,837개)에 속성으로 `distance_to_complex_m`/`nearest_complex`가 이미
  박혀있어 같은 반경 필터가 생성 단계에서부터 적용된 것으로 확인됨 — 뷰어/파이프라인
  버그 아니라 **원본 데이터 자체의 수집 범위 제약**. 산단에서 10km 넘게 떨어진 농지는
  특구 후보 클러스터링(및 이를 쓰는 모든 다운스트림 산출물)에서 처음부터 빠져있다.
  전체 행정구역 기준 원본은 다른 컴퓨터에 있어 이 세션에서는 교체 불가(2026-07-06
  기준) — 필지 전체 커버리지가 필요한 분석/의사결정 전에는 이 한계를 감안할 것.
- 클러스터 폴리곤 `_clusters_<scen>.geojson` → **`scripts/build_cluster_summary.py`** →
  `cluster_summary.json`(~19KB, 전 시군·전 시나리오, **커밋 대상** — 원본 폴리곤이 gitignore라 이게 런타임 데이터). 클러스터 변경 시 재생성.
- `.gitignore`: `*_parcels.geojson`, `*_points.json`, `cluster_db/*.db`, `.env` 제외. `cluster_summary.json`은 커밋.
- **동-여유풀 파이프라인**(KEPCO DL 여유용량을 동 단위로 합산 — 상세는 아래 도메인 메모):
  순서대로 6단계 실행, 앞 단계 산출물이 뒤 단계 입력.
  1. `scripts/build_dong_list.py` — 필지 PNU에 실제 등장하는 읍면동만 추려 `scripts/dong_list.csv`(gitignore)
     생성. 소스는 `cache/beopjeongdong_raw.txt`(법정동코드 gist 미러, gitignore, 재다운로드 가능 —
     신선도 미검증이라 못 찾는 코드는 `cache/dong_list_unresolved.json`에 로그).
  2. `scripts/kepco_client.py` — 읍면동별로 `addrLidong` 단독 호출(리 이름 없이). 원본 응답을
     `addr_lidong_raw/<8자리코드>.json`(gitignore)에 캐시, 이미 있는 코드는 재호출 안 함(`--force`로 무시 가능).
     `--sigungu <5자리코드>`로 특정 시군구만 샘플 실행 가능.
  3. `scripts/build_dl_dong_index.py` — DL↔동 many-to-many 역인덱스(`dl_dong_index.csv`, gitignore) 생성.
     같은 dl_id가 동마다 vol1/2/3 값이 다르게 관측되면 `sanity_check_log/dl_consistency_log.json`에
     경고만 남기고 중단 안 함.
  4. `scripts/build_dong_pool.py` — 균등분할 안분(`equal_split`, `--method`로 교체 가능하게 레지스트리 분리)
     후 vol2(변압기)→vol1(변전소) 순 동 단위 로컬 min() 클램프. 최종 `dong_pool.csv`/`dong_pool.json`
     (**커밋 대상** — `dong_code, dong_name, pool_capacity_kw, contributing_dl_ids,
     capped_by_upper_hierarchy, apportion_method`).
  5. `scripts/build_sigungu_dong_pool.py` — `<시군>_points.json`의 PNU 앞 8자리로 `dong_pool.json`을
     필터링해 `<시군>_dong_pool.json`(gitignore, build artifact)로 시군별 분리. 포맷:
     `{dong_code: [dong_name, pool_capacity_kw, capped(0/1)]}`.
  6. `scripts/_patch_dong_pool.py` — 14개 `<시군>_map.html`에 일괄 패치(멱등 마커 `/* DONGPOOL_PATCH */`):
     필지 팝업에 소속 동 여유용량 표시, 결과 패널에 "계통 연계 여유(참고)"/"계통 제약 감안 시" MW
     비교 지표, 사이드바에 선택 반경 내 동별 여유용량 목록 패널, 상한 캡 걸린 동 필지를 흐리게
     표시하는 토글(`#chk-dong-pool-warn`) 추가. 기존 MW/GWh/자급률 계산식은 그대로 두고 참고용
     지표만 옆에 추가 — PNU→동코드는 `pnu.substring(0,8)`로 클라이언트에서 즉석 매칭.
  - `scripts/sanity_check_ri_cache.py` — 과거 리 단위 수동 탐침(`cache/ri_probe_*.json`, **삭제 금지**,
    재현 불가한 기록)이 동-풀의 DL 집합 부분집합인지 대조 → `sanity_check_log/ri_cache_sanity.json`.
  - DL 데이터가 없는 동은 KEPCO가 `{"errCd":"404","errMsg":"NotFound"}`로 응답(정상적인 "결과 없음",
    존재하지 않는 동 이름으로도 동일하게 재현됨 — 호출 실패 아니라 캐시에 빈 데이터로 저장).
- **특구 후보 클러스터링**(`scripts/build_candidate_clusters.py`, `--scenario`로 S0/S3/SMAX 반복 실행,
  생략 시 3개 전부): `<시군>_points.json` 적격 필지(needs_upper_law==0 & 시나리오 키) 전체에
  DBSCAN 1회(eps=200m, minPts=3, 순수 Python 격자 이웃탐색) → `total_mw > CAP_MW(50)`인
  클러스터는 **용량 제약 영역성장(region growing)** 으로 무손실 분할(eps 사다리 방식은 폐기 —
  준연속 농지에서 eps 축소가 전역 파편화를 낳음, 2026-07-03). 시드=가장 가까운 산단까지
  거리 최소, 다음 필지가 CAP(kW) 초과시키면 그 필지는 넣지 않고 덩어리 확정. 산출물
  `<시군>_candidate_clusters_{scen}.json`/`<시군>_candidate_dong_summary_{scen}.json`(전부
  gitignore, build artifact). 클러스터 필드: `indiv_ratio`(면적가중 개인비율, `ownership_category
  =='개인'` 단독 판정), `grid_ok`(bool|**null**), `usable_mw`/`grid_margin_kw`(동 데이터 일부
  누락 시 `pool_incomplete=true`+`grid_ok=null`, margin/usable_mw는 알려진 동 기준 **하한값**으로
  유지 — 보수적 방향으로만 틀림), `split_method`("none"|"region_grow"), `isolated`(n<minPts).
  t(개인비율 상한, 10~50%)는 클러스터링과 무관한 **사후 표시 필터**일 뿐 재계산 없음.
  PNU는 유일키가 아님(같은 PNU가 정책구역 경계로 잘려 면적 다른 여러 행으로 존재) — 분할 시
  PNU로 재조회하지 말고 원본 멤버 dict를 그대로 넘길 것(과거 실제 버그, 최대 9% 면적 유실).
- **읍면동 경계 파이프라인**(뷰어 코로플레스용, 2026-07-04 fetch+crosswalk 완료 — 다음은
  뷰어 빌드):
  1. `scripts/fetch_dong_boundaries.py` — SGIS(행정안전부 국가데이터처) 행정구역경계 API
     (`https://sgisapi.mods.go.kr/OpenAPI3/boundary/hadmarea.geojson`, 인증은 `.env`의
     `SGIS_CONSUMER_KEY`/`SGIS_CONSUMER_SECRET`로 accessToken 발급 후 사용)로 경기·충남
     읍면동 경계 전체를 받는다. **⚠️ SGIS는 우리 PNU/법정동 8자리와 완전히 다른 통계청
     고유 시도코드를 쓴다 — 경기=`31`, 충남=`34`(법정동 41/44 아님). 서울만 `11`로 두
     체계가 우연히 같아서 헷갈리기 쉬움(실측 확인: 41/44로는 시도 단계부터 전부
     `errCd:-100` 실패, 31/34로 정상 응답).** 시군구 5자리·읍면동 8자리로 우리와 자릿수는
     같지만 숫자 자체가 무관해 **직접 조인 불가** — 이름 매칭 + point-in-polygon 폴백 필요
     (2단계). 응답 좌표계는 EPSG:5179(UTM-K, pyproj로 4326 변환 — `pip3 install pyproj`
     필요, build_points.py엔 미실행 방어 코드로만 있었음). `year`는 2000~2025만 허용
     (2026 불가). 산출: `boundary_raw/{31,34}.json`(SGIS 원본, EPSG:5179, gitignore) →
     `boundary_dong_4326.json`(경기+충남 전체 809개 읍면동 통합, EPSG:4326, 6.29MB,
     **gitignore** — SGIS 재호출로 재생성 가능한 중간 산출물).
  2. `scripts/build_dong_crosswalk.py` — 1차 이름 매칭: `scripts/dong_list.csv`의
     `(sigungu_name, addrLidong)` × `boundary_dong_4326.json`의 `sgis_name`(공백 분리
     파싱: 첫 토큰=시도, 마지막 토큰=읍면동명, 중간 전부=시군구명 — "안산시 상록구"처럼
     시군구 2단어도 대응) 3중 문자열 매칭. **읍/면은 거의 다 성공하지만 도심 "OO동"은
     실측 기준 실패의 98%(155개 중 152개)를 차지** — 법정동 여러 개가 행정동 하나로
     통합돼 SGIS엔 그 법정동 이름 자체가 없음(예: "신부동"/"신당동" 등 SGIS에 문자열
     자체가 없음, 오타 문제 아님). 2차 point-in-polygon 폴백: 이름 매칭 실패 동의 S3
     적격 필지 대표점 전부를 그 시군구 소속 SGIS 폴리곤들에 포함판정(shapely
     `prepared`) 후 다수결로 배정, 분산 비율(%) 기록 → confidence(≥90%=high,
     70~90%=medium, <70%=low). 최종 매칭률(2026-07-04): 동 수 299/314(95.2%),
     S3 적격 필지 수 100%(실패 15개 전부 필지 0개 — 파주 접경지 "동"11개+3개 면,
     화성 반송동 1개), dong_pool_kw 98.1%. A그룹 신설 8개 동(dong_list.csv에도
     없던 것)은 전부 point-in-polygon으로 SGIS 2025 폴리곤 발견됨(화성 동탄6~9동,
     용인 처인구 이동읍/남사읍, 홍성 홍북읍) — 경계는 있지만 KEPCO 미조회라 풀
     데이터는 없음(`no_pool_data:true`로 구분).
  3. **폴리곤 공유 시 pool_kw 재집계 규칙(중요, 확정)**: 도심 통합으로 여러 법정동이
     SGIS 폴리곤 하나를 공유하게 되면(실측 43개 폴리곤), 각 법정동의 `dong_pool_kw`를
     **단순 합산하지 않는다** — 같은 DL이 여러 법정동에 걸쳐 있으면 이중계상된다.
     대신 그 폴리곤에 속한 모든 법정동의 `dl_dong_index.csv` 원본 행을 모아 `dl_id`
     유니크 기준으로 재집계(같은 dl_id는 한 번만) 후 `build_dong_pool.py`와 동일한
     2단(vol2→vol1) 캡을 다시 적용한다. `equal_split`은 쓰지 않음 — 이미 하나의
     행정단위로 합쳐지는 것이므로 vol3를 나누지 않고 전체 값을 쓴다.
  4. **미매칭 동 처리 방침(확정)**: 크로스워크 실패한 동은 `<시군>_dong_boundary.json`
     (시군별 경량 파일, **커밋 대상**)의 `dong_to_polygon`에 **키 자체가 없음** — 가짜
     placeholder geometry를 넣지 않는다. 포맷: `{"polygons": {sgis_code: {sgis_name,
     geometry(4326), pool_kw|null, no_pool_data, member_dongs:[법정동8자리,...]}},
     "dong_to_polygon": {법정동8자리: sgis_code}}` — 클라이언트는 기존과 동일하게
     `pnu.substring(0,8)`로 `dong_to_polygon` 조회 후 없으면 "데이터 없음" 해칭.
  5. **파일 커밋 정책(확정)**: `boundary_raw/*.json`·`boundary_dong_4326.json`은
     gitignore(SGIS 재호출로 재생성 가능). `crosswalk.csv`(루트, ~31KB)와
     `<시군>_dong_boundary.json`(시군별, 14개 합계 ~3.1MB)은 **커밋 대상** — 원본
     SGIS 호출 없이는 못 만드는 런타임 데이터라 `dong_pool.json`과 같은 성격.
- **뷰어 생성 파이프라인**(템플릿 방식, 2026-07-04 전면 재구축):
  1. `scripts/build_candidate_clusters.py` 산출물이 `members`(필지 PNU 배열, 파일 용량의
     94.8% 차지 — 평택 S3 실측 3.4MB 중 3.2MB)를 뷰어에서 안 쓰길래 출력을 분리했다:
     `<시군>_candidate_clusters_{scen}.json`(hull+지표만, `cluster_id` 필드 추가, **커밋
     대상** — 뷰어가 직접 fetch)과 `<시군>_candidate_members_{scen}.json`
     (`{cluster_id:[pnu,...]}`, gitignore, 뷰어 미사용 — 특구 확정 시 필지 명세 조회용).
  2. `scripts/build_candidate_summary.py` — 14개 시군 × 3시나리오의 경량 클러스터
     파일을 집계해 `candidate_summary.json`(루트, 커밋 대상, ~5KB)로. grid_ok_pct
     규칙은 위 "반드시 지킬 규칙" 참조.
  3. `scripts/build_viewer.py` — `scripts/templates/{viewer,index}_template.html` +
     `scripts/sggs_data.json`(+ 시군별 `<시군>_complexes.json`)에서 14개
     `<시군>_map.html` + `index.html`을 매번 전체 재생성. 플레이스홀더
     `{{PFX}}/{{SGG_NAME}}/{{SGG_CODE}}/{{CENTER_LAT}}/{{CENTER_LON}}/{{COMPLEXES_JSON}}`
     (시군 상세), `{{SGGS_JSON}}`(index, `lat`/`lon` 포함 — 전국 지도 마커용) 문자열
     치환뿐 — 로직 분기 없음.
  4. 시군 상세 페이지의 fetch는 전부 **lazy + 메모리 캐싱**: 시나리오 버튼 클릭
     시점에 그 시나리오의 `candidate_clusters_{scen}.json`만 가져오고(세션당 최대
     3회), 필지 점 레이어·코로플레스·변압기 아이콘 토글도 켤 때 처음 한 번만 각각
     `<시군>_points.json`/`<시군>_dong_boundary.json`을 가져온다(코로플레스와 변압기
     아이콘은 `boundaryData` 캐시를 공유).
  5. 코로플레스 색 구간은 **그 시군 데이터만으로 매번 재계산되는 5분위**라
     시군 간 색 비교 불가 — 범례에 실제 kW 경계값과 "본 시군 내 상대 구간" 문구를
     항상 같이 표시한다(구현 시 확정, 오독 방지 목적).
  6. **2026-07-06 추가**: index.html에 Leaflet 전국 지도 복원(14개 시군 원형 마커,
     반경=후보 합계MW, 색=grid_ok_pct, 클릭 시 시군 상세 이동). 영농형 최소단위
     1유닛=1,000㎡=45kW(기존 0.045kW/m² 공식에서 그대로 도출) 정의해 클러스터
     팝업/상세카드에 SVG 아이콘 반복 표시(10개 초과 시 "아이콘 1개=N유닛" 스케일).
     시군 상세에 지번/PNU 검색 추가 — PNU 정확일치면 그대로, 아니면 입력 문자열에
     `<시군>_dong_boundary.json`의 `sgis_name` 마지막 토큰(읍면동명)이 포함되는지
     부분매칭해 그 동 중심점(centroid, 외곽 링 정점 평균)에서 최근접 적격 필지를
     찾고 "⚠ 근사" 라벨 명시(거리 m 포함).
  7. **2026-07-06 추가(PPA 아이디어 ①③)**: 클러스터 상세카드에 인근 RE100 대형
     수요처(`COMPLEXES`의 `is_demand_only`) 최단 직선거리 매칭 — 충당률(연간발전량/
     수요 elec_gwh)이 100% 넘으면 "수요 초과(잉여 판매 가능)"로 표기, "직선거리(실제
     계통 경로 아님)" 각주 필수(과장 방지). PPA 수익성 계산기는
     `scripts/agrivoltaic_economics.py`(IRR/NPV/할인회수기간, 원리금균등 상환 모델)를
     JS로 이식해 클러스터의 실제 `total_mw`/`annual_gwh`로 즉석 계산 — 사전계산 JSON
     아님(클러스터마다 별도 산출 없이 그 자리에서 재계산). 기존 발전공식(MW/GWh)은
     `annual_gwh`를 연차별 출력저하(0.5%/년) 적용의 1년차 입력값으로만 쓰고 재정의하지
     않음. 상수는 `PPA_CONFIG` 블록에 모음 — SMP 118.54원/kWh(기준시점 2026 EPSIS),
     REC 가중치 1.0(영농형 정식 가중치 미확정 가정), CAPEX/OPEX는 전국 단일값(시군별
     편차 미반영) 각주 상시 표시. 사업기간 Base(8)/Reform1(20)/Reform2(23)는 지도의
     S0/S3/SMAX(필지 적격성) 시나리오와 무관한 별도 축(정책시사점_v2 §6 사업기간 가정).

- **실측 산업용 전력수요 파이프라인**(`scripts/build_kepco_usage.py`, 2026-07-06): 한전
  빅데이터센터(bigdata.kepco.co.kr) "산업분류별 전력사용량"은 오픈API가 없어(SSO 로그인
  필요) `metadata/kepco_usage/*.xlsx`로 수동 다운로드(2023.01~2025.12 3개년 누적,
  gitignore — 로그인 없이는 스크립트로 재생성 불가). 시군명 첫 토큰으로 카드 코드 매핑,
  안산(1)/(2)는 총사용량이 서로 달라(6.4B vs 14.2B kWh) 별개 데이터로 판단해 시흥시와
  합산 후 41390에 매핑. 3개년 합계를 3으로 나눠 연평균 GWh 환산(제조업 단독/전체산업
  합계 각각) → `kepco_industrial_usage.json`(루트, 커밋 대상). 용인시 파일은 헤더가
  "전체(시도)/전체(시군구)"인 전국 집계 오export로 확인돼(용인시 단독 행 없음) 제외,
  재다운로드 대기 중(`note` 필드로 표시). 뷰어에는 시군구 전체업종 합산치라 산단 단위
  추정 소비량과 1:1 비교 불가라는 각주와 함께 병기.
- **특구 필요도 criteria 점수화**(`scripts/build_criteria_scores.py`, 2026-07-06): 5개
  지표(산단 생산실적 증감률·RE100 대형 수요처 수·grid_ok_pct·후보 클러스터 합계
  MW·평균 개인소유 비율, 전부 candidate_summary.json의 **S3 고정 기준**)를 시군별
  min-max 정규화 후 가중합. 가중치는 스크립트 상단 `WEIGHTS`/`RENORM_WITHOUT_GROWTH`
  상수로 조정(기본 균등 20%씩). 국가산단 생산실적은
  `metadata/한국산업단지공단_국가산업단지 산업동향정보_생산실적_20260331.csv`(cp949,
  커밋 대상)에 있는 시군만 유효(석문→당진, 아산, 파주탄현→파주, 시화/시화MTV/반월→
  시흥·안산 4개 카드만 실측치 존재 — 용인첨단시스템반도체/송산그린시티는 행은 있지만
  아직 가동실적 없어 값이 빈 문자열이라 데이터없음과 동일 취급). 데이터 없는 10개
  시군은 이 지표를 빼고 나머지 4개를 25%씩으로 재정규화(0점 처리 아님). 결과
  `criteria_scores.json`(루트, 커밋 대상)을 상위 1/3=gold/중위 1/3=silver/하위=bronze
  배지로 index 카드에 표시, hover 시 지표별 breakdown 툴팁.

## 도메인 메모
- **pnu(19자리)**: `[:2]`=시도, `[2:5]`=시군구, `[5:8]`=읍면동, `[8:10]`=리. (예 당진 = 44270)
- **ownership_category**: 6분류 표준 표기 `개인·공공·국유·법인·종중·종교·기타`(종중·종교는 **가운뎃점**). ORDER/COLORS 키도 이 표기로 통일.
- 시나리오: `S0`(현행법, `needs_S0_clean`만) / `S3`(특별법·법개정, 5개 키 OR) /
  `SMAX`(이론최대, **needs_\* 15개 전부 OR** — 확정 2026-07-03). `needs_upper_law`도 이
  OR 집합에 포함되지만 `eligible_parcels()`의 별도 하드 제외(문화재·생태·공원·군사 등
  13종)가 시나리오 무관하게 항상 적용되므로 SMAX도 그 13종까지 풀지는 않는다.
  `cluster_db/clusters.db`(생성 스크립트 유실, 외부 산출물)의 과거 SMAX 결과와 지금
  정의가 달라도 정상 — 그 DB는 재현 대상이 아님.
- **KEPCO 분산전원 API**: `GET/POST https://bigdata.kepco.co.kr/openapi/v1/dispersedGeneration.do`
  (`metroCd`=pnu[:2], `cityCd`=**pnu[2:5](3자리, 44270 아님)**, `addrLidong`=동/면명, `addrLi`=리명(선택),
  `apiKey`, `returnType=json|xml`). 응답 필드: `vol1`=변전소 여유용량, `vol2`=변압기 여유용량,
  `vol3`=DL(배전선로) 여유용량(단위 kW). `addrLidong`만 주고 `addrLi`를 생략하면 그 읍/면 전체 리의
  DL을 합쳐서 돌려준다(2026-07-01 합덕읍 실측: addrLi 없이 18건, 기존 8리 부분 탐침 union의 상위집합).
  **동·리 모두 다중 DL이라 필지→단일 DL 태깅 불가**(리 단위 위상 클러스터링 폐기) → DL은 동 단위
  "풀"로만 다룬다 — 실측 기준 DL의 61%가 2개 이상 동에 걸침. 자세한 파이프라인은 위 데이터 파이프라인
  절의 "동-여유풀 파이프라인" 참조.

## 검증
- 템플릿을 고쳤으면 `python3 scripts/build_viewer.py`로 재생성 후 `python3 -m http.server`로
  띄워 브라우저(또는 playwright 등 헤드리스 브라우저)로 확인(가장 무거운 평택 페이지 기준).
  콘솔 에러 없는지 반드시 확인 — 페이지 셸은 뜨는데 fetch만 조용히 실패하는 경우가 있다.
- 시군 상세 회귀 체크리스트: 시나리오 3종 전환 시 후보 폴리곤·요약 패널 갱신, t 슬라이더로
  개인비율 상한 낮출수록 후보 수 단조감소, 후보 클릭 시 상세 카드(usable_mw가
  pool_incomplete면 "≥" 접두), 필지 점/코로플레스 토글 lazy fetch 정상 동작(켤 때만 요청).
