"""
동-여유풀 파이프라인 3단계: addr_lidong_raw/*.json 원본에서
DL(배전선로) ↔ 동(읍면동) many-to-many 역인덱스를 만든다.

dl_id = f"{substCd}:{dlCd}" — 변전소코드+DL코드 조합이 DL의 실질적 유일키.
(dlCd 두 자리는 변전소 안에서만 유일하고 전국적으로는 겹친다.)

같은 dl_id가 여러 동 질의에서 반복 등장하면 그 동들에 걸친 DL이라는 뜻.
이때 vol1/vol2/vol3(및 subst/mtr 용량)가 동 질의마다 다르게 나오면
dl_consistency_log.json 에 경고로 남기고 계속 진행한다(중단하지 않음).

출력:
  dl_dong_index.csv   — dl_id × dong 조합별 1행(many-to-many 원자료)
  dl_consistency_log.json — vol1/vol2/vol3 불일치 dl_id 목록
"""
import argparse
import csv
import glob
import json
from collections import defaultdict

RAW_DIR = "addr_lidong_raw"
INDEX_PATH = "dl_dong_index.csv"
CONSISTENCY_LOG_PATH = "sanity_check_log/dl_consistency_log.json"

FIELDS = [
    "dl_id", "dong_code", "dong_name", "sigungu_code", "sigungu_name",
    "substCd", "substNm", "mtrNo", "dlCd", "dlNm",
    "substPwr", "mtrPwr", "dlPwr", "vol1", "vol2", "vol3",
]


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sigungu", help="특정 시군구코드만 (샘플 검증용)")
    args = ap.parse_args()

    rows = []
    observed = defaultdict(list)  # dl_id -> [(dong_code, vol1, vol2, vol3), ...]

    paths = sorted(glob.glob(f"{RAW_DIR}/*.json"))
    for path in paths:
        with open(path, encoding="utf-8") as f:
            rec = json.load(f)
        if args.sigungu and rec["sigungu_code"] != args.sigungu:
            continue
        data = (rec.get("response") or {}).get("data") or []
        for item in data:
            dl_id = f"{item['substCd']}:{item['dlCd']}"
            vol1, vol2, vol3 = num(item.get("vol1")), num(item.get("vol2")), num(item.get("vol3"))
            row = {
                "dl_id": dl_id,
                "dong_code": rec["code"],
                "dong_name": rec["addrLidong"],
                "sigungu_code": rec["sigungu_code"],
                "sigungu_name": rec["sigungu_name"],
                "substCd": item.get("substCd"),
                "substNm": item.get("substNm"),
                "mtrNo": item.get("mtrNo"),
                "dlCd": item.get("dlCd"),
                "dlNm": item.get("dlNm"),
                "substPwr": item.get("substPwr"),
                "mtrPwr": item.get("mtrPwr"),
                "dlPwr": item.get("dlPwr"),
                "vol1": vol1,
                "vol2": vol2,
                "vol3": vol3,
            }
            rows.append(row)
            observed[dl_id].append((rec["code"], vol1, vol2, vol3))

    # dedup: 같은 dl_id가 같은 dong에서 두 번 나올 일은 없어야 하지만 방어적으로 처리
    seen = set()
    deduped = []
    for r in rows:
        key = (r["dl_id"], r["dong_code"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    rows = deduped

    # consistency check: 같은 dl_id가 여러 동에 걸칠 때 vol1/2/3 값이 동일한지
    inconsistent = {}
    for dl_id, obs in observed.items():
        dong_codes = {o[0] for o in obs}
        if len(dong_codes) < 2:
            continue
        vol_sets = {(o[1], o[2], o[3]) for o in obs}
        if len(vol_sets) > 1:
            inconsistent[dl_id] = [
                {"dong_code": o[0], "vol1": o[1], "vol2": o[2], "vol3": o[3]} for o in obs
            ]

    with open(INDEX_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    import os
    os.makedirs("sanity_check_log", exist_ok=True)
    with open(CONSISTENCY_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "note": "같은 dl_id가 여러 동에 걸쳐 나타나면서 vol1/vol2/vol3 값이 동마다 다르게 관측됨. "
                    "실시간 여유용량 데이터라 호출 시점차로 변동했을 수도 있고, dl_id 충돌(다른 물리 DL이 "
                    "같은 substCd:dlCd를 우연히 공유)일 수도 있음. 원인 분석은 별도 스텝 — 여기서는 경고만.",
            "inconsistent_dl_count": len(inconsistent),
            "details": inconsistent,
        }, f, ensure_ascii=False, indent=2)

    dl_dong_counts = defaultdict(set)
    for r in rows:
        dl_dong_counts[r["dl_id"]].add(r["dong_code"])
    multi_dong = {k: v for k, v in dl_dong_counts.items() if len(v) > 1}

    print(f"raw files: {len(paths)}  (sigungu 필터: {args.sigungu or '없음'})")
    print(f"dl_dong_index rows: {len(rows)}")
    print(f"unique dl_id: {len(dl_dong_counts)}")
    print(f"동 2개 이상에 걸친 dl_id: {len(multi_dong)}")
    print(f"vol 불일치 dl_id: {len(inconsistent)} -> {CONSISTENCY_LOG_PATH}")
    if multi_dong:
        sample = list(multi_dong.items())[:5]
        for dl_id, dongs in sample:
            print(f"  예시 {dl_id}: {sorted(dongs)}")


if __name__ == "__main__":
    main()
