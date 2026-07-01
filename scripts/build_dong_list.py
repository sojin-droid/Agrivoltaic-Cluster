"""
동-여유풀 파이프라인 1단계: KEPCO addrLidong 질의 대상(읍면동) 목록 생성.

대상 범위는 "14개 시군 전체 행정구역"이 아니라 **실제 필지 PNU에 등장하는
읍면동(8자리 법정동코드)만** 사용한다. 필지는 산단 반경 기준으로 뽑혀 있어서
인접 시군(예: 아산 파일에 당진 필지 일부)까지 자연히 포함되고, 반대로 필지가
없는 행정동은 애초에 여유용량을 붙일 대상이 아니므로 제외한다.

법정동코드 원본은 cache/beopjeongdong_raw.txt (gist 미러, 법정동코드/법정동명/
폐지여부 tab-separated). 출력은 scripts/dong_list.csv:
  code(8자리), sigungu_code, sigungu_name, addrLidong, metroCd, cityCd, parcel_count
"""
import csv
import glob
import json
import re
from collections import Counter

RAW_PATH = "cache/beopjeongdong_raw.txt"
OUT_PATH = "scripts/dong_list.csv"
UNRESOLVED_PATH = "cache/dong_list_unresolved.json"
PARCEL_GLOB = ["chungnam/*/*_parcels.geojson", "gyeonggi/*/*_parcels.geojson"]

PNU_RE = re.compile(r'"pnu":\s*"(\d{19})"')


def load_name_table():
    names = {}
    with open(RAW_PATH, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader)
        for code, name, status in reader:
            if status == "존재":
                names[code] = name
    return names


def count_umd_codes():
    counts = Counter()
    for pattern in PARCEL_GLOB:
        for path in glob.glob(pattern):
            with open(path, encoding="utf-8") as f:
                for chunk in iter(lambda: f.read(1 << 20), ""):
                    for m in PNU_RE.finditer(chunk):
                        counts[m.group(1)[:8]] += 1
    return counts


def main():
    names = load_name_table()
    umd_counts = count_umd_codes()

    targets = []
    missing = []
    for umd_code, parcel_count in umd_counts.items():
        sgg_code = umd_code[:5]
        umd_full = names.get(umd_code + "00")
        sgg_full = names.get(sgg_code + "00000")
        if umd_full is None or sgg_full is None:
            missing.append(umd_code)
            continue
        addrLidong = umd_full[len(sgg_full):].strip()
        targets.append({
            "code": umd_code,
            "sigungu_code": sgg_code,
            "sigungu_name": sgg_full.split(" ", 1)[1] if " " in sgg_full else sgg_full,
            "addrLidong": addrLidong,
            "metroCd": umd_code[:2],
            "cityCd": umd_code[2:5],
            "parcel_count": parcel_count,
        })

    targets.sort(key=lambda t: t["code"])
    with open(OUT_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "code", "sigungu_code", "sigungu_name", "addrLidong",
            "metroCd", "cityCd", "parcel_count",
        ])
        writer.writeheader()
        writer.writerows(targets)

    print(f"targets: {len(targets)}  (missing lookup: {len(missing)})")
    if missing:
        print("  missing codes (사람 확인 필요):", missing[:20])
        with open(UNRESOLVED_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "note": "beopjeongdong_raw.txt(gist 미러, 신선도 미검증)에 없는 8자리 코드. "
                         "최근 신설 법정동(예: 화성 동탄2, 용인 처인구 개편)일 가능성이 높음. "
                         "동-풀 파이프라인에서 제외되고 KEPCO 호출 대상에 포함되지 않음.",
                "codes": missing,
                "parcel_counts": {c: umd_counts[c] for c in missing},
            }, f, ensure_ascii=False, indent=2)
        print(f"  -> {UNRESOLVED_PATH} 에 기록")
    by_sgg = Counter(t["sigungu_name"] for t in targets)
    for name, cnt in sorted(by_sgg.items(), key=lambda x: -x[1]):
        print(f"  {name}: {cnt}")


if __name__ == "__main__":
    main()
