#!/usr/bin/env python3
"""migrate_to_supabase.py — 루트 및 <시군> 폴더의 데이터 파일(json/csv/geojson)을
Supabase Storage 공개 버킷(agrivoltaic-data)에 업로드한다.

이 저장소는 이제 "코드(GitHub) / 데이터(Supabase Storage)"로 역할을 나눈다:
- GitHub: index.html, <시군>_map.html, scripts/, 문서
- Supabase Storage: candidate_summary.json 등 무거운 런타임 데이터

버킷은 공개 읽기(public read)로 설정되어 있어 브라우저에서 별도 인증 없이
`{SUPABASE_URL}/storage/v1/object/public/agrivoltaic-data/<path>` 로 바로 fetch 가능.
업로드(쓰기)에는 service_role 키가 필요하므로 .env에서 읽는다 — 이 키는 절대
커밋하거나 브라우저 코드에 넣지 말 것.

사용법:
  1) .env.example을 .env로 복사하고 SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 채우기
     (대시보드 → Project Settings → API → service_role secret)
  2) pip install requests python-dotenv --break-system-packages  (이미 있으면 생략)
  3) python3 scripts/migrate_to_supabase.py            # 실제 업로드
     python3 scripts/migrate_to_supabase.py --dry-run  # 무엇이 올라갈지만 확인
"""
import argparse
import mimetypes
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUCKET = "agrivoltaic-data"

# 루트에서 올릴 파일(빌드 산출물/파이프라인 요약 — 런타임에 쓰이는 것 + 참고용 전부)
ROOT_FILES = [
    "candidate_summary.json",
    "cluster_summary.json",
    "criteria_scores.json",
    "crosswalk.csv",
    "dong_pool.csv",
    "dong_pool.json",
    "kepco_industrial_usage.json",
    "kepco_sector_profile.json",
    "cluster_climate_risk.json",
    "lowindiv_candidates_S3.json",
]

# 시군 폴더(province/시군코드_이름) 하위에서 올릴 확장자
SGG_EXTS = (".json", ".geojson", ".csv")
PROVINCE_DIRS = ["gyeonggi", "chungnam"]

# 업로드 제외: 원본 필지 폴리곤(개당 ~100MB, 로컬 전용 — .gitignore 주석 참조).
# 뷰어는 경량 <시군>_points.json만 fetch하므로 버킷에 올릴 이유가 없고,
# 포함 시 총량이 1.4GB를 넘어 Supabase 무료 플랜 Storage 한도(1GB)를 초과한다.
EXCLUDE_SUFFIXES = ("_parcels.geojson",)


def load_env():
    env_path = os.path.join(ROOT, ".env")
    if os.path.exists(env_path):
        for line in open(env_path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def collect_files():
    """(local_abs_path, storage_key) 튜플 목록 반환"""
    out = []
    for name in ROOT_FILES:
        p = os.path.join(ROOT, name)
        if os.path.exists(p):
            out.append((p, name))
        else:
            print(f"  [스킵] 루트 파일 없음: {name}")

    for prov in PROVINCE_DIRS:
        prov_dir = os.path.join(ROOT, prov)
        if not os.path.isdir(prov_dir):
            continue
        for dirpath, _, filenames in os.walk(prov_dir):
            for fn in filenames:
                if not fn.endswith(SGG_EXTS):
                    continue  # _map.html 등 코드 파일은 제외
                if fn.endswith(EXCLUDE_SUFFIXES):
                    continue  # 원본 필지 등 로컬 전용 대용량
                local = os.path.join(dirpath, fn)
                rel = os.path.relpath(local, ROOT)  # 예: gyeonggi/41390_siheung_ansan/xxx.json
                out.append((local, rel))
    return out


def upload_one(session, base_url, service_key, local_path, storage_key, dry_run):
    size_kb = os.path.getsize(local_path) / 1024
    if dry_run:
        print(f"  [dry-run] {storage_key} ({size_kb:.0f} KB)")
        return True

    content_type = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
    url = f"{base_url}/storage/v1/object/{BUCKET}/{storage_key}"
    with open(local_path, "rb") as f:
        data = f.read()
    resp = session.post(
        url,
        headers={
            "Authorization": f"Bearer {service_key}",
            "apikey": service_key,
            "Content-Type": content_type,
            "x-upsert": "true",  # 이미 있으면 덮어쓰기
        },
        data=data,
        timeout=120,
    )
    if resp.status_code not in (200, 201):
        print(f"  [실패] {storage_key}: {resp.status_code} {resp.text[:200]}")
        return False
    print(f"  [완료] {storage_key} ({size_kb:.0f} KB)")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="업로드하지 않고 목록만 출력")
    args = parser.parse_args()

    load_env()
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not args.dry_run and (not supabase_url or not service_key):
        print("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY가 필요합니다. .env를 확인하세요.")
        print("(.env.example 참고, --dry-run으로 먼저 목록만 확인 가능)")
        sys.exit(1)

    files = collect_files()
    total_mb = sum(os.path.getsize(p) for p, _ in files) / (1024 * 1024)
    print(f"업로드 대상: {len(files)}개 파일, 총 {total_mb:.1f} MB\n")

    if args.dry_run:
        for local, key in files:
            upload_one(None, None, None, local, key, dry_run=True)
        return

    import requests

    session = requests.Session()
    ok, fail = 0, 0
    for local, key in files:
        if upload_one(session, supabase_url, service_key, local, key, dry_run=False):
            ok += 1
        else:
            fail += 1
    print(f"\n완료: 성공 {ok}개, 실패 {fail}개")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
