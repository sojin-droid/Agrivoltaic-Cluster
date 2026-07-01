#!/usr/bin/env python3
"""당진 parcels geojson → Supabase 적재용 CSV (지오메트리=WKT).
사용: 이 폴더에서  python3 make_parcels_csv.py
출력: dangjin_parcels.csv  (Supabase 대시보드 CSV Import용)
메모리 절약을 위해 ijson 스트리밍을 쓰되, 없으면 표준 json으로 폴백.
"""
import csv, os, sys, json

SRC = os.path.join(os.path.dirname(__file__), "..", "chungnam", "44270_dangjin", "dangjin_parcels.geojson")
OUT = os.path.join(os.path.dirname(__file__), "dangjin_parcels.csv")
SGG = "44270"
NEEDS = ["needs_S0_clean","needs_agp_other","needs_agp_protect","needs_agp_core","needs_facility",
 "needs_jongchunji","needs_military","needs_eco","needs_park","needs_mining","needs_terrain",
 "needs_landuse","needs_baekdu","needs_forest","needs_upper_law"]
COLS = ["sgg_code","pnu","area_m2","slope_mean","ownership_name","category","subagpromo_name"] \
     + [n.lower() for n in NEEDS] + ["geom_wkt"]

def ring(r): return "(" + ", ".join("%s %s" % (c[0], c[1]) for c in r) + ")"
def wkt(g):
    t = g["type"]; c = g["coordinates"]
    polys = [c] if t == "Polygon" else (c if t == "MultiPolygon" else None)
    if polys is None: return None
    return "MULTIPOLYGON(" + ", ".join("(" + ", ".join(ring(r) for r in poly) + ")" for poly in polys) + ")"

def rowof(ft):
    p = ft["properties"]; wk = wkt(ft["geometry"])
    if not wk: return None
    return [SGG, p.get("pnu"), p.get("area_m2"), p.get("slope_mean"),
            p.get("ownership_name"), p.get("category"), p.get("subagpromo_name")] \
         + [p.get(n) for n in NEEDS] + [wk]

def features_stream():
    try:
        import ijson
        with open(SRC, "rb") as f:
            for ft in ijson.items(f, "features.item"):
                yield ft
    except ImportError:
        with open(SRC, encoding="utf-8") as f:
            for ft in json.load(f)["features"]:
                yield ft

def main():
    n = 0
    with open(OUT, "w", newline="", encoding="utf-8") as fo:
        w = csv.writer(fo); w.writerow(COLS)
        for ft in features_stream():
            r = rowof(ft)
            if r: w.writerow(r); n += 1
            if n % 20000 == 0: print("...", n, flush=True)
    print("DONE rows:", n, "->", OUT)

if __name__ == "__main__":
    main()
