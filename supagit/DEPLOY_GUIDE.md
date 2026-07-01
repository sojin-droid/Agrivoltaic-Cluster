# supagit 배포 가이드 — 공개 개요 + 로그인 상세

이 `supagit/` 폴더만 GitHub에 올리면 됩니다. (원본 시군/index 파일은 건드리지 않음)

구조
- **공개**: `index.html` — 전국 시군·클러스터·저개인후보 개요 (로그인 불필요)
- **로그인 전용**: `chungnam/44270_dangjin/dangjin_map.html` — 필지 줌인 상세 (지자체 컨설팅용)
- 모든 데이터는 Supabase에: 필지(로그인), 클러스터·저개인후보·시군요약(공개)
- `config.js` — Supabase 주소·키
- `sql/` — 백엔드 생성/적재 SQL,  `data/` — 적재용 CSV/JSON (GitHub엔 안 올림)

---

## A. Supabase 백엔드

### A-1. 프로젝트 생성
supabase.com → New project → DB 비밀번호 메모, 리전 **Seoul** 권장.

### A-2. 스키마 + RPC + RLS
SQL Editor 에서 순서대로 RUN:
1. `sql/01_schema.sql`
2. `sql/02_rpc_rls.sql`  ← 공개/로그인 권한이 여기서 갈림

### A-3. 데이터 적재
**필지** (`data/dangjin_parcels.csv`, 96,837행)
1. `sql/03_import_parcels.sql` 의 **① staging** 부분 RUN
2. Table Editor → `parcels_staging` → **Import data from CSV** → `dangjin_parcels.csv`
3. 같은 파일의 **② 변환+적재**, **③ 시군요약** RUN

**클러스터** (8행 — CSV 불필요)
- `sql/04_import_clusters.sql` 전체를 SQL Editor에 붙여넣고 RUN (지오메트리 내장 직접 INSERT)

**저개인 후보** (전국)
- `sql/05_import_lowindiv.sql` 전체 RUN (CSV 불필요, JSON 내장)

### A-4. 로그인 계정 (상세 페이지용)
Authentication → Users → **Add user**:
- Email: `planit@planit.institute`   비밀번호: `planit`
- Providers → Email 에서 "Confirm email" 끄면 즉시 로그인
- "Allow new sign-ups" 끄기 권장(관리자 추가 사용자만)
- 나중에 계정/비번 변경: 여기서 사용자 추가/수정만 하면 됨 (코드 수정 불필요)

### A-5. 키 입력
Project Settings → API 의 **Project URL / anon public** 키를 `config.js` 에 붙여넣기.

---

## B. GitHub 배포
1. `supagit/` 폴더를 새 저장소로 push (`.gitignore` 가 data CSV 등 제외)
2. Settings → Pages → Source: main / 루트
3. 접속:
   - 공개 개요: `https://<아이디>.github.io/<저장소>/`
   - 상세(로그인): `.../chungnam/44270_dangjin/dangjin_map.html`

---

## C. 검증
1. 개요 페이지 → 로그인 없이 시군·클러스터·저개인후보 표시
2. 산단/클러스터 클릭 → "이 시군 상세 지도" → 상세 페이지 → **로그인 화면**
3. `planit` / `planit` 로그인 → 필지 표시(Supabase) → 반경·자급률 계산

---

## 확장 (13개 시군)
- 각 시군 parcels CSV: `make_parcels_csv.py` 의 경로/SGG만 바꿔 생성 → 같은 `parcels` 테이블에 append
- 각 시군 클러스터 CSV: `make_clusters_csv.py` 동일
- 상세 페이지 복제 후 `SGG_CODE` 만 변경
- 전체 필지 ≈ 1.2GB → 무료 500MB 초과 가능, Pro($25/월) 또는 시군 분할 검토

## 주의
- `config.js` 의 anon key는 공개 안전(RLS 보호). **service_role 키·DB비번은 절대 넣지 말 것.**
- 대시보드 CSV Import 가 느리거나 실패하면 README 의 ogr2ogr 직적재(Mac) 사용.
