#!/usr/bin/env python3
"""build_points.py — 필지 폴리곤 GeoJSON → 경량 점(point) 파일 선계산.

각 시군 <시군>_parcels.geojson 을 읽어 필지마다 대표점(shapely representative_point,
= ST_PointOnSurface, 항상 폴리곤 내부 보장)을 계산하고, _map.html 이 실제로 소비하는
속성만 담은 경량 컬럼형 JSON(<시군>_points.json)으로 출력한다. 폴리곤 geometry는 미포함.

CRS 처리:
  - 파일별로 입력 CRS를 감지(geojson 'crs' 멤버). CRS84 / EPSG:4326 / 멤버없음 → 경위도이므로 변환 없음.
  - 투영(미터)좌표인 경우에만: representative_point 를 원본 평면좌표에서 계산한 뒤
    결과 점만 EPSG:4326 으로 변환(pyproj). 4326 으로 먼저 바꾼 뒤 점을 찍지 않는다.
  (본 데이터는 14개 전부 CRS84 이므로 변환 경로는 실행되지 않음 — 방어적으로 구현.)

출력 포맷(컬럼형, 경량):
  {
    "sgg_name", "sgg_code", "crs", "n",
    "needs_order": [needs_* 15개 키 순서],
    "owncat": [고유 라벨...], "cat": [...], "promo": [...],   # 사전(인덱스 참조)
    "rows": [[pnu, lat, lon, area_m2, slope, owncatIdx, catIdx, promoIdx, needsBits], ...]
  }
  - needsBits: needs_order 순서의 0/1 플래그를 비트로 압축한 정수.
  - area_m2 는 원본 폴리곤 스칼라 값을 그대로(재계산·반올림 없음).
"""
import json, glob, os, re, sys, random
from shapely.geometry import shape

# _map.html 이 필지 피처에서 실제 소비하는 needs_* 15개 (고정 순서 = 비트 위치)
NEEDS_ORDER = [
    "needs_S0_clean", "needs_agp_other", "needs_agp_protect", "needs_agp_core",
    "needs_facility", "needs_jongchunji", "needs_military", "needs_eco",
    "needs_park", "needs_mining", "needs_terrain", "needs_landuse",
    "needs_baekdu", "needs_forest", "needs_upper_law",
]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUTS = sorted(glob.glob(os.path.join(ROOT, "chungnam", "*", "*_parcels.geojson")) +
                glob.glob(os.path.join(ROOT, "gyeonggi", "*", "*_parcels.geojson")))

GEOGRAPHIC = ("CRS84", "EPSG::4326", "EPSG:4326", "4326")


def detect_crs(crs_member):
    """geojson crs 멤버 문자열 → (라벨, is_geographic, epsg_or_None)."""
    if not crs_member:
        return ("(none → default CRS84/EPSG:4326)", True, None)
    name = crs_member
    if any(g in name for g in GEOGRAPHIC):
        return (name, True, 4326)
    m = re.search(r"EPSG:*:?(\d+)", name)
    epsg = int(m.group(1)) if m else None
    return (name, False, epsg)


def build_one(path):
    pfx = os.path.basename(path).replace("_parcels.geojson", "")
    with open(path) as f:
        gj = json.load(f)
    crs_member = (gj.get("crs", {}) or {}).get("properties", {}).get("name")
    crs_label, is_geo, epsg = detect_crs(crs_member)

    transformer = None
    if not is_geo:
        from pyproj import Transformer
        transformer = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)

    feats = gj["features"]
    owncat_dict, cat_dict, promo_dict = [], [], []
    owncat_idx, cat_idx, promo_idx = {}, {}, {}

    def diget(d, idx, v):
        v = "" if v is None else str(v)
        if v not in idx:
            idx[v] = len(d); d.append(v)
        return idx[v]

    rows = []
    for ft in feats:
        p = ft["properties"]
        geom = shape(ft["geometry"])
        rp = geom.representative_point()  # 원본 좌표계에서 계산(항상 내부)
        x, y = rp.x, rp.y
        if transformer is not None:
            x, y = transformer.transform(x, y)  # 결과 점만 4326 으로
        lon, lat = round(x, 6), round(y, 6)
        area = p.get("area_m2")  # 원본 스칼라 그대로
        slope = p.get("slope_mean")
        slope = None if slope is None else round(float(slope), 1)
        bits = 0
        for i, k in enumerate(NEEDS_ORDER):
            if p.get(k) == 1:
                bits |= (1 << i)
        rows.append([
            p.get("pnu"), lat, lon, area, slope,
            diget(owncat_dict, owncat_idx, p.get("ownership_category")),
            diget(cat_dict, cat_idx, p.get("category")),
            diget(promo_dict, promo_idx, p.get("subagpromo_name")),
            bits,
        ])

    out = {
        "sgg_name": gj.get("name") or pfx,
        "sgg_code": pfx,
        "crs": crs_label,
        "n": len(rows),
        "needs_order": NEEDS_ORDER,
        "owncat": owncat_dict,
        "cat": cat_dict,
        "promo": promo_dict,
        "rows": rows,
    }
    out_path = os.path.join(os.path.dirname(path), pfx + "_points.json")
    with open(out_path, "w") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    # ── 표본 검증: 임의 5필지의 대표점 within(폴리곤) + area_m2 원본 일치 ──
    rng = random.Random(42)
    sample_idx = rng.sample(range(len(feats)), min(5, len(feats)))
    within_ok, area_ok = 0, 0
    for si in sample_idx:
        geom = shape(feats[si]["geometry"])
        rp = geom.representative_point()
        if rp.within(geom):
            within_ok += 1
        if rows[si][3] == feats[si]["properties"].get("area_m2"):
            area_ok += 1

    in_size = os.path.getsize(path)
    out_size = os.path.getsize(out_path)
    return {
        "pfx": pfx, "n": len(rows), "crs": crs_label, "is_geo": is_geo,
        "in_mb": in_size / 1e6, "out_mb": out_size / 1e6,
        "ratio": in_size / out_size if out_size else 0,
        "owncat": owncat_dict,
        "within": f"{within_ok}/{len(sample_idx)}",
        "area_match": f"{area_ok}/{len(sample_idx)}",
        "out_path": os.path.relpath(out_path, ROOT),
    }


def main():
    print(f"입력 {len(INPUTS)}개 시군 처리\n")
    results = []
    for path in INPUTS:
        r = build_one(path)
        results.append(r)
        print(f"  ✓ {r['pfx']:14s} n={r['n']:>6} | {r['in_mb']:6.1f}MB → "
              f"{r['out_mb']:5.2f}MB ({r['ratio']:4.1f}x) | crs={'geo' if r['is_geo'] else r['crs']} | "
              f"within {r['within']} area {r['area_match']}", flush=True)

    print("\n=== 용량표 ===")
    print(f"{'시군':14s} {'필지':>7} {'원본MB':>8} {'점MB':>7} {'배율':>6}")
    tot_in = tot_out = 0
    for r in results:
        tot_in += r["in_mb"]; tot_out += r["out_mb"]
        print(f"{r['pfx']:14s} {r['n']:>7} {r['in_mb']:>8.1f} {r['out_mb']:>7.2f} {r['ratio']:>5.1f}x")
    print(f"{'합계':14s} {'':>7} {tot_in:>8.1f} {tot_out:>7.2f} {tot_in/tot_out:>5.1f}x")

    print("\n=== ownership_category 시군별 고유 라벨 ===")
    all_labels = set()
    for r in results:
        labels = [l for l in r["owncat"] if l != ""]
        all_labels.update(labels)
        print(f"  {r['pfx']:14s} {sorted(labels)}")
    print(f"\n  전체 합집합({len(all_labels)}종): {sorted(all_labels)}")

    print("\n=== CRS 감지 ===")
    for r in results:
        print(f"  {r['pfx']:14s} {r['crs']}")

    print("\n=== 표본 검증(시군당 5필지) ===")
    wfail = [r['pfx'] for r in results if not r['within'].startswith(r['within'].split('/')[1])]
    afail = [r['pfx'] for r in results if not r['area_match'].startswith(r['area_match'].split('/')[1])]
    print(f"  within 전부 통과: {'YES' if not wfail else 'NO ' + str(wfail)}")
    print(f"  area_m2 전부 일치: {'YES' if not afail else 'NO ' + str(afail)}")


if __name__ == "__main__":
    main()
