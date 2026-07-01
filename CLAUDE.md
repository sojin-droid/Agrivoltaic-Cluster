# CLAUDE.md

경기·충남 14개 시군의 **영농형 태양광 RE100 입지 분석 뷰어**. 산업단지 주변 농지 필지의
태양광 발전 잠재량·자급률·특구 후보 클러스터를 지도로 시각화한다.

## 실행 (빌드 시스템 없음 — 순수 정적 + Python)
- `python3 -m http.server 8002` 후 브라우저에서:
  - `http://localhost:8002/index.html` — **전국 메인 뷰어**(14개 시군 개요 + 클러스터 요약 + 다중선택)
  - `http://localhost:8002/<sido>/<code_name>/<시군>_map.html` — 시군 상세(필지·반경·정책 토글)
- 편의 실행: `run.command`(mac) / `run.bat`(win). `package.json` 없음(npm 불필요).

## 구조
- `index.html` — 전국 뷰어. `SGGS` 배열(시군 좌표·산단·code)이 핵심. 클러스터 요약은 `cluster_summary.json` 로드.
- `chungnam/*/`, `gyeonggi/*/` — 시군별 폴더. 각 `<시군>_map.html` + 데이터 파일.
- `supagit/` — 동일 뷰어의 **Supabase 연동 변형**(현재 `config.js` 자격증명 placeholder, 미연결). 범위 밖이면 건드리지 말 것.
- `scripts/` — 빌드·일괄패치 스크립트. `cluster_db/clusters.db` = 클러스터 원천 DB.

## ⚠️ 반드시 지킬 규칙
- **14개 `<시군>_map.html`은 거의 동일하며 손으로 개별 편집 금지.** 반드시 `scripts/_patch_*.py`
  컨벤션(glob 14개 → 문자열 치환 → 멱등 가드 → 재기록)으로 일괄 패치한다. 참고: `_patch_points.py`, `_patch_detail_layout.py`.
- **발전 계산식·표시값을 임의로 바꾸지 말 것**: 설비용량 MW = `면적(m²) × 0.045 ÷ 1000`,
  연간발전량 MWh = `MW × 8760 × 0.15`(설비이용률 15%), 자급률 = `연간발전량 ÷ 소비량 × 100`.
- **비밀키**: `.env`의 `KEPCO_API_KEY`는 gitignore 대상. 값을 출력/커밋하지 말 것.

## 데이터 파이프라인 (변경 후 재생성 필요)
- `<시군>_parcels.geojson`(원본 폴리곤, 무거움·gitignore) → **`scripts/build_points.py`** →
  `<시군>_points.json`(경량 점, gitignore). 시군 상세 뷰어가 소비. 필지 변경 시 재생성.
- 클러스터 폴리곤 `_clusters_<scen>.geojson` → **`scripts/build_cluster_summary.py`** →
  `cluster_summary.json`(~19KB, 전 시군·전 시나리오, **커밋 대상** — 원본 폴리곤이 gitignore라 이게 런타임 데이터). 클러스터 변경 시 재생성.
- `.gitignore`: `*_parcels.geojson`, `*_points.json`, `cluster_db/*.db`, `.env` 제외. `cluster_summary.json`은 커밋.
- **동-여유풀 파이프라인**(KEPCO DL 여유용량을 동 단위로 합산 — 상세는 아래 도메인 메모):
  순서대로 4단계 실행, 앞 단계 산출물이 뒤 단계 입력.
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
  - `scripts/sanity_check_ri_cache.py` — 과거 리 단위 수동 탐침(`cache/ri_probe_*.json`, **삭제 금지**,
    재현 불가한 기록)이 동-풀의 DL 집합 부분집합인지 대조 → `sanity_check_log/ri_cache_sanity.json`.
  - DL 데이터가 없는 동은 KEPCO가 `{"errCd":"404","errMsg":"NotFound"}`로 응답(정상적인 "결과 없음",
    존재하지 않는 동 이름으로도 동일하게 재현됨 — 호출 실패 아니라 캐시에 빈 데이터로 저장).

## 도메인 메모
- **pnu(19자리)**: `[:2]`=시도, `[2:5]`=시군구, `[5:8]`=읍면동, `[8:10]`=리. (예 당진 = 44270)
- **ownership_category**: 6분류 표준 표기 `개인·공공·국유·법인·종중·종교·기타`(종중·종교는 **가운뎃점**). ORDER/COLORS 키도 이 표기로 통일.
- 시나리오: `S0`(현행법) / `S3`(특별법·법개정) / `SMAX`(이론최대).
- **KEPCO 분산전원 API**: `GET/POST https://bigdata.kepco.co.kr/openapi/v1/dispersedGeneration.do`
  (`metroCd`=pnu[:2], `cityCd`=**pnu[2:5](3자리, 44270 아님)**, `addrLidong`=동/면명, `addrLi`=리명(선택),
  `apiKey`, `returnType=json|xml`). 응답 필드: `vol1`=변전소 여유용량, `vol2`=변압기 여유용량,
  `vol3`=DL(배전선로) 여유용량(단위 kW). `addrLidong`만 주고 `addrLi`를 생략하면 그 읍/면 전체 리의
  DL을 합쳐서 돌려준다(2026-07-01 합덕읍 실측: addrLi 없이 18건, 기존 8리 부분 탐침 union의 상위집합).
  **동·리 모두 다중 DL이라 필지→단일 DL 태깅 불가**(리 단위 위상 클러스터링 폐기) → DL은 동 단위
  "풀"로만 다룬다 — 실측 기준 DL의 61%가 2개 이상 동에 걸침. 자세한 파이프라인은 위 데이터 파이프라인
  절의 "동-여유풀 파이프라인" 참조.

## 검증
- 뷰어 변경은 `python3 -m http.server`로 띄워 브라우저에서 확인(가장 무거운 평택 페이지 기준). 필지 렌더는 canvas 점.
- 시군 상세 회귀 기준(기본 산단·5.0km·토글 off): 선택 필지 수·MW·GWh·자급률이 변경 전과 일치해야 함.
