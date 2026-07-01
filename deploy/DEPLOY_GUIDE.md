# 당진 파일럿 배포 가이드 (Supabase 백엔드 + GitHub 프론트엔드)

영농형 태양광 RE100 분석 도구를 **비공개(로그인)** 로 온라인 배포하는 절차.
무거운 필지(parcels)는 Supabase(PostGIS), 나머지(HTML·클러스터·차트)는 GitHub.

---

## A. Supabase 백엔드

### A-1. 프로젝트 생성
1. https://supabase.com → 로그인 → **New project**
2. 이름(예: `agrivoltaic-re100`), DB 비밀번호 설정(메모해 둘 것), 리전은 **Northeast Asia (Seoul)** 권장
3. 생성까지 1~2분 대기

### A-2. 스키마 + RPC 실행
대시보드 → **SQL Editor** → New query 에 차례로 붙여넣고 RUN:
1. `01_schema.sql`  (PostGIS 확장, parcels/clusters/sgg_summary 테이블)
2. `02_rpc_and_rls.sql`  (반경검색 RPC + 비공개 RLS)

### A-3. 필지 데이터 적재 (CSV Import)
1. `03_import_from_csv.sql` 의 **1) staging 테이블 생성** 부분만 먼저 실행
2. 대시보드 → **Table Editor** → `parcels_staging` 선택 → **Insert ▸ Import data from CSV**
   → `deploy/dangjin_parcels.csv` (28MB, 96,837행) 업로드
   - 업로드가 오래 걸리거나 실패하면: CSV를 절반씩 나눠 두 번 올리거나, 아래 "대안 적재" 참고
3. 업로드 완료 후, `03_import_from_csv.sql` 의 **2) 변환+적재** 와 **3) 시군 종합** 부분 실행
   - `parcels_loaded` 카운트가 96,837 근처면 성공

### A-4. 로그인 사용자 만들기 (비공개 접근)
1. 대시보드 → **Authentication** → **Users** → **Add user** → 이메일/비밀번호 입력
   (이 계정으로 사이트에 로그인)
2. (선택) Authentication → Providers → Email 에서 "Confirm email" 끄면 즉시 로그인 가능
3. (권장) 일반 가입 차단: Authentication → Sign In / Providers → **Allow new users to sign up** 끄기
   → 관리자가 추가한 사용자만 접근

### A-5. API 키 확인
대시보드 → **Project Settings → API**:
- **Project URL** 과 **anon public** 키 복사 → `supabase-config.js` 에 붙여넣기
- ⚠ `service_role` 키는 절대 프론트엔드/깃허브에 넣지 말 것

---

## B. 프론트엔드 (GitHub)

### B-1. supabase-config.js 채우기
저장소 루트 `supabase-config.js` 의 두 값을 A-5 에서 복사한 값으로 교체.

### B-2. GitHub 저장소에 올리기
- `.gitignore` 가 `*_parcels.geojson`(1.2GB) 와 `deploy/*.csv` 를 제외 → 무거운 원본은 안 올라감
- 올라가는 것: `index.html`, 각 시군 `*_map.html`, `*_clusters_*.geojson`(소형), `*_complexes.json`, `charts/` 등
- GitHub Desktop 또는: 새 저장소 생성 후 이 폴더를 push

### B-3. Pages 배포
저장소 → **Settings → Pages** → Source: `main` 브랜치 / 루트 → 저장
→ 몇 분 뒤 `https://<사용자>.github.io/<저장소>/chungnam/44270_dangjin/dangjin_map.html` 접속

---

## C. 검증
1. 배포 URL 접속 → 로그인 화면 표시
2. A-4 계정으로 로그인 → 지도 진입
3. 산단 선택 → 필지가 지도에 표시(Supabase RPC) → 반경 조절 → MW·자급률 계산 확인
4. 정책 토글 / 클러스터 레이어 동작 확인

---

## 참고 / 주의

- **GitHub Pages 는 URL 만 알면 공개**입니다. 무거운 필지는 Supabase 로그인으로 보호되지만,
  HTML 셸과 소형 클러스터 geojson 은 URL 로 접근 가능합니다. 클러스터까지 완전 비공개로 하려면
  클러스터 데이터도 Supabase 로 옮기거나(추가 작업), Vercel/Cloudflare Access 등 인증 호스팅을 쓰면 됩니다.
- **CSV가 너무 커서 대시보드 import 가 실패할 때(대안 적재):**
  Mac 터미널에서 PostGIS 직적재가 가장 안정적입니다.
  `brew install gdal` 후:
  ```
  ogr2ogr -f PostgreSQL "PG:host=<DB호스트> port=5432 dbname=postgres user=postgres password=<비번>" \
    chungnam/44270_dangjin/dangjin_parcels.geojson \
    -nln parcels -append -nlt MULTIPOLYGON -lco GEOMETRY_NAME=geom -t_srs EPSG:4326
  ```
  (컬럼명이 다르면 -sql 로 매핑)
- **13개 시군 확장**: 동일 구조. 각 시군 parcels CSV 생성(`make_parcels_csv.py` 의 SGG/경로만 변경) →
  같은 parcels 테이블에 `sgg_code` 만 다르게 append. 프론트는 각 map.html 의 `SGG_CODE` 만 맞추면 됨.
  전체 13개 ≈ 1.2GB → Supabase 무료 500MB 초과 가능, Pro($25/월) 또는 시군 분할 검토.
