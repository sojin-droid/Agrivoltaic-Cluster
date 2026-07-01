#!/usr/bin/env python3
"""build_cluster_summary.py — 전국 index.html 용 경량 클러스터 요약 빌드.

왜 필요한가: 시군별 `_clusters_ranked_<scen>.json` 과 cluster_db/clusters.db 의 centroid_lat/lon 이
대부분 결측이라 전국 지도의 클러스터 대표점 소스로 못 쓴다. 신뢰 가능한 좌표 소스는 폴리곤
`_clusters_<scen>.geojson`(모든 클러스터에 geometry 존재)뿐이다. 여기서 **중심점 + 지표만** 뽑아
단일 경량 파일 `cluster_summary.json` 으로 출력한다(폴리곤 geometry 미포함 → 런타임 경량).

출력 포맷:
  { "<scen>": { "<sgg_code>": [ {rank,mw,n,ratio,lat,lon,nearest,dist_km,demand_gwh,pareto}, ... ] } }
  - lat/lon = 폴리곤 representative_point()(= ST_PointOnSurface, 항상 내부 보장), 경위도(EPSG:4326).
  - ratio = 개인비율 0~1 (geojson '개인비율_pct' / 100). mw/n/nearest 등은 geojson properties 그대로.
"""
import json, glob, os, re
from shapely.geometry import shape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENARIOS = ["S0", "S3", "SMAX"]
OUT_PATH = os.path.join(ROOT, "cluster_summary.json")


def sgg_code_of(path):
    # .../chungnam/44270_dangjin/dangjin_clusters_S3.geojson → 44270
    folder = os.path.basename(os.path.dirname(path))
    m = re.match(r"(\d+)_", folder)
    return m.group(1) if m else folder


def main():
    out = {s: {} for s in SCENARIOS}
    tot = 0
    per_city = {}   # code → {scen: n}
    for scen in SCENARIOS:
        files = sorted(glob.glob(os.path.join(ROOT, "chungnam", "*", "*_clusters_%s.geojson" % scen)) +
                       glob.glob(os.path.join(ROOT, "gyeonggi", "*", "*_clusters_%s.geojson" % scen)))
        for path in files:
            code = sgg_code_of(path)
            with open(path, encoding="utf-8") as f:
                gj = json.load(f)
            arr = []
            for ft in (gj.get("features") or []):
                p = ft["properties"]
                rp = shape(ft["geometry"]).representative_point()
                pct = p.get("개인비율_pct")
                arr.append({
                    "smaa_rank": p.get("smaa_rank"),
                    "mw": p.get("mw"),
                    "n": p.get("n_parcels"),
                    "ratio": (pct / 100.0) if isinstance(pct, (int, float)) else None,
                    "lat": round(rp.y, 6),
                    "lon": round(rp.x, 6),
                    "nearest_complex": p.get("nearest_complex"),
                    "dist_km": p.get("dist_km"),
                    "demand_gwh": p.get("demand_gwh"),
                    "pareto_layer": p.get("pareto_layer"),
                })
            # 순위 오름차순 정렬(있으면)
            arr.sort(key=lambda c: (c["smaa_rank"] is None, c["smaa_rank"]))
            out[scen][code] = arr
            tot += len(arr)
            per_city.setdefault(code, {})[scen] = len(arr)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    size = os.path.getsize(OUT_PATH)
    print("cluster_summary.json 생성: %s (%.1f KB), 총 클러스터 %d개\n" %
          (os.path.relpath(OUT_PATH, ROOT), size / 1024, tot))
    print("%-14s %5s %5s %5s" % ("sgg_code", "S0", "S3", "SMAX"))
    for code in sorted(per_city):
        c = per_city[code]
        print("%-14s %5d %5d %5d" % (code, c.get("S0", 0), c.get("S3", 0), c.get("SMAX", 0)))
    # 좌표 결측 점검
    missing = sum(1 for s in SCENARIOS for code in out[s] for c in out[s][code]
                  if c["lat"] is None or c["lon"] is None)
    print("\n좌표 결측 클러스터: %d (0이어야 정상)" % missing)


if __name__ == "__main__":
    main()
