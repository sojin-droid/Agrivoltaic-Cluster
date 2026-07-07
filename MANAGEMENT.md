# 사이트 관리 가이드

이 문서 하나로 사이트 운영의 전부를 설명합니다. 대부분의 작업은 Claude Code에게
아래 절차를 그대로 시키면 됩니다.

## 0. 한눈에 보기

```
[분석 파이프라인 scripts/*.py]
        │ 재실행
        ▼
[요약 JSON: candidate_summary, criteria_scores, cluster_summary, kepco, lowindiv …]
        │                                    │
        │ scripts/migrate_to_supabase.py     │ scripts/build_viewer.py
        ▼                                    ▼
[Supabase Storage 버킷 agrivoltaic-data]   [map.html + 14개 <시군>_map.html]  ← 생성물
        ▲ fetch                              (소스: scripts/templates/*.html)
        │
[index.html · insight.html · method.html]  ← 손편집 페이지 (assets/style.css·site.js 공유)
```

| 손대도 되는 파일 | 절대 손편집 금지 (생성물) |
|---|---|
| `index.html`, `insight.html`, `method.html` | `map.html` |
| `assets/style.css`, `assets/site.js` | `gyeonggi·chungnam/**/<시군>_map.html` |
| `scripts/templates/map_template.html`, `viewer_template.html` (생성 원본) | |
| `scripts/*.py`, `MANAGEMENT.md`, `README.md` | |

생성물을 직접 고치면 다음 `build_viewer.py` 실행 때 사라집니다.

## 1. 데이터 갱신 (분석을 다시 돌렸을 때)

```bash
# 1) 해당 파이프라인 재실행 (예: 클러스터 재계산 → 요약 재생성)
python3 scripts/build_candidate_clusters.py
python3 scripts/build_candidate_summary.py   # 등 — 순서는 CLAUDE.md 참조

# 2) Supabase에 업로드 (덮어쓰기 안전 — x-upsert)
python3 scripts/migrate_to_supabase.py --dry-run   # 목록 먼저 확인
python3 scripts/migrate_to_supabase.py
```

- 웹페이지 수치는 전부 fetch라 **업로드만 하면 자동 반영** (index/insight/method 수정 불필요).
- 단, index.html 히어로의 `data-target` 정적 기본값(fetch 실패 시 폴백)은 크게 달라졌을 때 한 번 맞춰주세요.
- **새 데이터 파일**을 추가했으면 `scripts/migrate_to_supabase.py`의 `ROOT_FILES` 배열에 파일명 1줄 추가.
- 업로드에는 `.env`의 `SUPABASE_SERVICE_ROLE_KEY` 필요 (§7 참고).

## 2. 지도 수정 (전국 지도·시군 상세)

```bash
# scripts/templates/map_template.html (전국) 또는 viewer_template.html (시군) 수정 후
python3 scripts/build_viewer.py
```

- `map.html`·`<시군>_map.html`은 매번 템플릿에서 전체 재생성됩니다 — 직접 편집 금지.
- 발전공식·grid_ok_pct 규칙 등 바꾸면 안 되는 값은 `CLAUDE.md`의 "반드시 지킬 규칙" 참조.

## 3. 서사·인사이트 페이지 수정 (Story/Insight/Method)

- `index.html` / `insight.html` / `method.html`을 **직접 편집**하면 됩니다. 각 파일 상단 주석에 수정 포인트 안내.
- 숫자가 사는 곳 두 종류:
  - **fetch 렌더 구간** — Supabase에서 자동 로드, 손댈 필요 없음.
  - **본문 서술 속 하드코딩** (예: "2.4배", 기준시점 연도) — 직접 수정.
- 데이터 URL 상수 `DATA_BASE`는 **각 페이지 `<script>` 상단 + `scripts/build_viewer.py`** 총 4곳 —
  Supabase 프로젝트를 옮기면 전부 바꿔야 합니다 (`grep -rn "taemfahsyeplbrrweopo" .`로 확인).

## 4. 디자인 변경 (색·서체)

- `assets/style.css` 맨 위 `:root` 변수만 바꾸면 손편집 3페이지에 일괄 반영.
- 지도 페이지(생성물)의 색은 템플릿 안에 별도 hex로 있음 — 같은 색으로 맞추려면 템플릿에서 수정 후 재빌드.

## 5. 새 시각화 추가

시각화 부품 창고: **해운 사이트 `lab.html`** (planit-shipping-site zip). 각 데모 블록은
자급자족(HTML+JS 한 덩어리)이라 `<section>` 통째로 복사 → 데이터 배열만 fetch 결과로 교체.

| 패턴 | 용도 | 현재 사용처 |
|---|---|---|
| 01 스크롤 리빌 | 섹션 등장 효과 (`class="reveal"`) | 전 페이지 |
| 02 숫자 카운트업 | 핵심 수치 (`.count[data-target]`) | index 히어로 |
| 07 탭 필터 | 목록 분류 | insight 저개인소유 |
| 08 정렬 표 | 순위표 | insight 종합 순위 |
| 09 파라미터 차트 | 슬라이더 연동 재계산 | insight 이용률 민감도 |
| 14 히트맵 | 행×열 매트릭스 | insight 시군×지표 |
| 16 링 게이지 | 달성률 하나 크게 | insight RE100 충당률 |
| 18 시나리오 모핑 바 | 시나리오 토글 비교 | index S0/S3/SMAX |

Claude Code에게 시키는 프롬프트 예:
- "insight.html에 lab 12번 바 차트 레이스 패턴으로 시나리오별 시군 순위 변화 섹션 추가해줘. 데이터는 candidate_summary.json."
- "index.html 히어로 아래에 lab 05번 동심원 패턴으로 특구 확산 단계를 그려줘."

## 6. 배포

```bash
git add -A && git commit -m "..." && git push
```

- push하면 GitHub Pages가 1–2분 내 자동 재배포: https://sojin-droid.github.io/Agrivoltaic-Cluster/
- 로컬 미리보기: `./run.command` (또는 `python3 -m http.server 8002`) → http://localhost:8002
- 배포 전 체크: 브라우저 콘솔 에러 0, Network 탭에서 supabase.co 요청 전부 200.

## 7. 주의사항

- **`.env` 커밋 금지** (.gitignore 처리됨). `SUPABASE_SERVICE_ROLE_KEY`는 업로드 스크립트 전용 —
  브라우저 코드·커밋·채팅에 절대 노출 금지. 유출 시 Supabase 대시보드에서 즉시 재발급.
- **데이터 JSON을 git에 다시 add 금지** — .gitignore가 막지만 `git add -f`는 쓰지 말 것.
  (데이터는 Supabase가 원본, git은 코드만.)
- Supabase 무료 플랜 한도(Storage 1GB·전송량) 참고 — 현재 데이터 ~191MB.
- git 히스토리에는 과거 대용량 파일이 남아 있어 clone이 무겁습니다(의도된 트레이드오프).
  정리하려면 git filter-repo 필요 — 되돌릴 수 없으므로 별도 세션에서 백업 후 진행.
