#!/usr/bin/env bash
# cleanup_repo.sh — Agrivoltaic-Cluster 레포 정리 스크립트
# 로컬 클론 루트에서 실행하세요. (Claude Code 세션에서 실행 권장)
#
# 이 스크립트가 하는 일:
#   1) 죽은/불필요 디렉터리 삭제 (cluster_db, supagit, run.app, scripts/legacy)
#   2) 이제 Supabase Storage로 이관된 데이터 파일을 git 추적에서 해제
#      (로컬 디스크의 실제 파일은 지우지 않음 — 빌드 스크립트가 계속 씀)
#   3) LICENSE 추가
#
# 실행 후: git status로 변경 확인 → 커밋 → (선택) 히스토리 재작성은 별도 가이드 참고.

set -euo pipefail
cd "$(dirname "$0")/.."   # scripts/ 밑에서 실행돼도 레포 루트로 이동

echo "=== 1) 죽은 디렉터리 삭제 ==="
rm -rf cluster_db supagit run.app scripts/legacy
echo "  삭제됨: cluster_db/ supagit/ run.app/ scripts/legacy/"

echo
echo "=== 2) Supabase로 이관된 데이터 파일 git 추적 해제 ==="
echo "  (파일 자체는 디스크에 남습니다 — .gitignore에 이미 추가됨)"
git rm -r --cached --ignore-unmatch \
  candidate_summary.json \
  cluster_summary.json \
  criteria_scores.json \
  crosswalk.csv \
  dong_pool.csv \
  dong_pool.json \
  kepco_industrial_usage.json \
  lowindiv_candidates_S3.json \
  gyeonggi chungnam \
  cluster_db supagit run.app \
  > /dev/null
# gyeonggi/chungnam 전체를 한 번 캐시 해제한 뒤, .gitignore 규칙에 안 걸리는
# *_map.html만 다시 추가해서 코드는 그대로 추적되게 한다.
git add gyeonggi chungnam 2>/dev/null || true
echo "  git rm --cached 완료 (*_map.html은 재추가됨)"

echo
echo "=== 3) LICENSE 추가 ==="
if [ ! -f LICENSE ]; then
  echo "  LICENSE 파일이 없어 MIT 라이선스를 새로 생성합니다 (원치 않으면 직접 교체하세요)"
fi

echo
echo "=== 완료 ==="
echo "git status로 변경사항을 확인한 뒤 커밋하세요. 예:"
echo '  git add -A'
echo '  git commit -m "레포 정리: 죽은 코드/구버전 배포 세트 제거, 데이터를 Supabase Storage로 이관"'
