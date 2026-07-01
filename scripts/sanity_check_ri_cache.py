"""
동-여유풀 파이프라인 4단계: 기존 리 탐침 캐시(cache/ri_probe_*.json)를
dl_dong_index와 대조하는 sanity check.

리 탐침 캐시는 "그 리에 addrLi로 걸리는 DL 이름(dlNm) 목록"을 담고 있다.
addrLidong 단독 호출(우리 파이프라인의 실제 호출 방식)은 그 상위 읍/면 전체의
DL 합집합을 돌려주므로, 캐시의 각 리 DL 목록은 상위 읍/면의 dl_dong_index DL
이름 집합의 **부분집합**이어야 한다. 부분집합이 아니면 불일치로 로그에 남긴다
(중단하지 않음 — 원인 분석은 별도 스텝).

캐시 삭제 금지: 이 스크립트는 읽기만 한다.
"""
import glob
import json
from collections import defaultdict

INDEX_PATH = "dl_dong_index.csv"
CACHE_GLOB = "cache/ri_probe_*.json"
LOG_PATH = "sanity_check_log/ri_cache_sanity.json"

# 캐시의 "target" 필드(예: "합덕읍 (당진)")를 dong_list.csv 상의 dong_code로 매핑.
TARGET_TO_DONG_CODE = {
    "합덕읍 (당진)": "44270250",
}


def load_dong_dl_names():
    import csv
    dong_dl_names = defaultdict(set)
    with open(INDEX_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            dong_dl_names[row["dong_code"]].add(row["dlNm"])
    return dong_dl_names


def main():
    dong_dl_names = load_dong_dl_names()
    results = []

    for path in sorted(glob.glob(CACHE_GLOB)):
        with open(path, encoding="utf-8") as f:
            cache = json.load(f)
        target = cache.get("target")
        dong_code = TARGET_TO_DONG_CODE.get(target)
        if dong_code is None:
            results.append({"cache_file": path, "target": target,
                             "status": "SKIP", "reason": "dong_code 매핑 없음"})
            continue

        dl_names_at_dong = dong_dl_names.get(dong_code)
        if dl_names_at_dong is None:
            results.append({"cache_file": path, "target": target,
                             "status": "SKIP", "reason": f"dl_dong_index에 {dong_code} 없음(아직 미실행?)"})
            continue

        for ri_name, dls in cache.get("results", {}).items():
            if dls is None:
                results.append({"cache_file": path, "target": target, "ri_name": ri_name,
                                 "status": "NULL_IN_CACHE", "cached_dls": None})
                continue
            missing = sorted(set(dls) - dl_names_at_dong)
            if missing:
                results.append({
                    "cache_file": path, "target": target, "ri_name": ri_name,
                    "status": "MISMATCH",
                    "cached_dls": dls,
                    "missing_from_dong_pool": missing,
                    "dong_pool_dls": sorted(dl_names_at_dong),
                })
            else:
                results.append({"cache_file": path, "target": target, "ri_name": ri_name,
                                 "status": "OK", "cached_dls": dls})

    import os
    os.makedirs("sanity_check_log", exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    ok = sum(1 for r in results if r["status"] == "OK")
    mismatch = [r for r in results if r["status"] == "MISMATCH"]
    null_ = sum(1 for r in results if r["status"] == "NULL_IN_CACHE")
    skip = sum(1 for r in results if r["status"] == "SKIP")
    print(f"OK: {ok}, MISMATCH: {len(mismatch)}, NULL_IN_CACHE(캐시 자체가 null): {null_}, SKIP: {skip}")
    for r in mismatch:
        print(f"  MISMATCH {r['ri_name']}: 캐시엔 있는데 동 풀에 없음 -> {r['missing_from_dong_pool']}")
    print(f"-> {LOG_PATH}")


if __name__ == "__main__":
    main()
