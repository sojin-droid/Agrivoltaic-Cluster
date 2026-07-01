#!/usr/bin/env python3
"""개인소유 비율이 낮은 ≥50MW 영농형 특구 후보 탐색 (윈도우 방식, 중심점 기반·고속).

핵심 아이디어:
  '특구'는 연속된 한 덩어리여야 하고, 그 안의 적격 농지를 통째로 쓴다.
  따라서 반경 ≤ R 의 컴팩트한 원 안에 ≥50MW(≈111ha)의 적격 농지가 담기는 위치 중,
  그 원의 '자연 개인소유 비율'이 가장 낮은 곳을 찾는다. (개인 필지를 건너뛰지 않음 →
  실제로 지을 수 있는 블록의 개인 비율·동의 가구 수를 정직하게 반영)

절차:
  1. 시나리오 적격 필지(기본 S3)만 추려 200m 격자 셀에 집계(개인/비개인 면적·개인필지수).
  2. 각 셀을 중심으로 사각 링을 넓혀가며 담긴 적격 농지면적 ≥ target 까지 확장 → 윈도우.
  3. 반경 ≤ max_radius(컴팩트) 인 윈도우만 채택. 중복 제거(NMS, nms_m).
  4. 개인비율↑·개인필지수 기준 정렬 + Pareto. 각 윈도우 중심좌표 보유(추후 변전소 매칭용).

사용: python3 lowindiv_cluster.py <parcels.geojson> <시군명> [--scen S3] [--cell 200]
      [--target-mw 50] [--max-radius 1500] [--nms 700] [--json-out f.json]
"""
import json, sys, math, argparse
from collections import defaultdict

PANEL_DENSITY = 0.045 / 1000          # MW per m²
S3_KEYS = ["needs_S0_clean", "needs_agp_other", "needs_agp_protect", "needs_facility", "needs_agp_core"]
S0_KEYS = ["needs_S0_clean"]

def centroid(geom):
    c = geom["coordinates"]
    ring = c[0][0] if geom["type"] == "MultiPolygon" else c[0]
    n = len(ring)
    return sum(p[0] for p in ring)/n, sum(p[1] for p in ring)/n   # lon, lat

def _hav_km(a,b,c,d):
    import math
    R=6371; t=math.pi/180
    return 2*R*math.asin(math.sqrt(math.sin((c-a)*t/2)**2+math.cos(a*t)*math.cos(c*t)*math.sin((d-b)*t/2)**2))

def load_eligible(path, keys, exclude_zones=None, sgg_code=None):
    """exclude_zones: list of (lat, lon, radius_km) — 위성으로 확인된 기개발지(미군기지·공장부지 등).
       sgg_code: 5자리 시군구코드. 지정 시 다른 시군 PNU 필지는 제외(광역 데이터 누수 방지)."""
    gj = json.load(open(path, encoding="utf-8"))
    out = []
    skip_zone = skip_sgg = 0
    for f in gj["features"]:
        p = f["properties"]
        if p.get("needs_upper_law") == 1:
            continue
        if not any(p.get(k) == 1 for k in keys):
            continue
        if sgg_code:
            pnu = p.get("pnu", "")
            if pnu and not pnu.startswith(sgg_code):
                skip_sgg += 1
                continue
        lon, lat = centroid(f["geometry"])
        if exclude_zones and any(_hav_km(z[0],z[1],lat,lon) <= z[2] for z in exclude_zones):
            skip_zone += 1
            continue
        cat = p.get("ownership_category")
        if cat == "개인":      b = "ind"
        elif cat in (None, ""): b = "unk"
        else:                  b = "non"
        out.append({"lon": lon, "lat": lat, "area": p.get("area_m2") or 0.0,
                    "b": b, "cx": p.get("nearest_complex") or "(미상)"})
    if skip_zone: print(f"  [exclude] 기개발지 마스크로 {skip_zone}개 제외")
    if skip_sgg: print(f"  [exclude] 타 시군 PNU {skip_sgg}개 제외")
    return out

def windows(parcels, cell, target_mw, max_radius, nms_m, max_unknown=10.0, min_avg_area_m2=800):
    """min_avg_area_m2: 윈도우 안 적격 필지 평균면적 하한(㎡).
       정상 농지는 ≈1,000~3,000㎡, 도시 구획정리된 옛 농지는 600~800㎡ 이하라 시가지 시그널 차단용."""
    if not parcels:
        return []
    target_area = target_mw / PANEL_DENSITY
    lat0 = sum(p["lat"] for p in parcels)/len(parcels)
    lon0 = sum(p["lon"] for p in parcels)/len(parcels)
    kx = 111320*math.cos(math.radians(lat0)); ky = 111320
    # 격자 셀 집계
    cells = {}
    for p in parcels:
        x = (p["lon"]-lon0)*kx; y = (p["lat"]-lat0)*ky
        k = (int(x//cell), int(y//cell))
        c = cells.get(k)
        if c is None:
            c = cells[k] = {"a_ind":0.0,"a_non":0.0,"a_unk":0.0,"n_ind":0,"n_unk":0,"n_all":0,"sx":0.0,"sy":0.0,"cxs":defaultdict(float)}
        a = p["area"]; b = p["b"]
        if b=="ind": c["a_ind"]+=a; c["n_ind"]+=1
        elif b=="unk": c["a_unk"]+=a; c["n_unk"]+=1
        else: c["a_non"]+=a
        c["n_all"]+=1; c["sx"]+=x; c["sy"]+=y; c["cxs"][p["cx"]]+=a
    keys = list(cells)
    max_ring = max(1, int(max_radius//cell))
    wins = []
    for (gx,gy) in keys:
        a_ind=a_non=a_unk=0.0; n_ind=n_unk=n_all=0; cxs=defaultdict(float)
        rr = 0; reached_at = None
        while rr <= max_ring:
            # 체비셰프 거리 == rr 인 링의 셀 추가
            for dx in range(-rr, rr+1):
                for dy in range(-rr, rr+1):
                    if max(abs(dx),abs(dy)) != rr:
                        continue
                    c = cells.get((gx+dx, gy+dy))
                    if not c: continue
                    a_ind+=c["a_ind"]; a_non+=c["a_non"]; a_unk+=c["a_unk"]
                    n_ind+=c["n_ind"]; n_unk+=c["n_unk"]; n_all+=c["n_all"]
                    for k2,v in c["cxs"].items(): cxs[k2]+=v
            if a_ind+a_non+a_unk >= target_area:
                reached_at = rr; break
            rr += 1
        if reached_at is None:
            continue
        area = a_ind+a_non+a_unk; radius = (reached_at+0.5)*cell
        if radius > max_radius:
            continue
        unk_pct = a_unk/area*100
        if unk_pct > max_unknown:        # 소유불명 비율 과다 → 신뢰 불가, 제외
            continue
        avg_area = area/n_all if n_all else 0
        if avg_area < min_avg_area_m2:   # 평균 필지가 너무 작으면 도시화/구획정리 시그널 → 제외
            continue
        cc = cells[(gx,gy)]
        wins.append({
            "ind_ratio_pct": round(a_ind/area*100,1), "unknown_pct": round(unk_pct,1),
            "conservative_pct": round((a_ind+a_unk)/area*100,1),
            "n_ind_parcels": n_ind, "n_unknown_parcels": n_unk, "n_parcels": n_all,
            "mw": round(area*PANEL_DENSITY,1), "area_ha": round(area/1e4,1), "radius_m": round(radius),
            "lon": round(cc["sx"]/cc["n_all"]/kx+lon0,5), "lat": round(cc["sy"]/cc["n_all"]/ky+lat0,5),
            "nearest_complex": max(cxs, key=cxs.get), "_gx":gx, "_gy":gy})
    # 중복 제거(NMS): 개인비율 낮은 것 우선, 중심 nms_m 이내 중복 제거
    wins.sort(key=lambda w:(w["ind_ratio_pct"], w["n_ind_parcels"]))
    kept = []
    nms_cells = nms_m/cell
    for w in wins:
        if all(math.hypot(w["_gx"]-k["_gx"], w["_gy"]-k["_gy"]) > nms_cells for k in kept):
            kept.append(w)
    for w in kept: del w["_gx"]; del w["_gy"]
    return kept

def pareto(cs):
    out=[]
    for c in cs:
        dom=any(o is not c and o["ind_ratio_pct"]<=c["ind_ratio_pct"] and o["n_ind_parcels"]<=c["n_ind_parcels"]
                and (o["ind_ratio_pct"]<c["ind_ratio_pct"] or o["n_ind_parcels"]<c["n_ind_parcels"]) for o in cs)
        if not dom: out.append(c)
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("geojson"); ap.add_argument("sgg")
    ap.add_argument("--scen", default="S3"); ap.add_argument("--cell", type=float, default=200)
    ap.add_argument("--target-mw", type=float, default=50); ap.add_argument("--max-radius", type=float, default=1500)
    ap.add_argument("--nms", type=float, default=700); ap.add_argument("--json-out")
    ap.add_argument("--max-unknown", type=float, default=10.0)
    ap.add_argument("--exclude", action="append", default=[],
                    help='기개발지 마스크 "lat,lon,radius_km" (반복 가능). 예: --exclude 36.970,127.004,4 (캠프 험프리스)')
    ap.add_argument("--sgg-code", default=None,
                    help="5자리 시군구코드 (예: 44270). 지정 시 다른 시군 PNU 필지 제외(광역 데이터 누수 차단)")
    ap.add_argument("--min-avg-area", type=float, default=800,
                    help="윈도우 평균 필지 면적 하한(㎡). 시가지 구획정리 시그널 차단용")
    a = ap.parse_args()
    keys = S3_KEYS if a.scen == "S3" else S0_KEYS
    zones = []
    for z in a.exclude:
        parts = z.split(",")
        zones.append((float(parts[0]), float(parts[1]), float(parts[2])))
    parcels = load_eligible(a.geojson, keys, exclude_zones=zones if zones else None, sgg_code=a.sgg_code)
    cs = windows(parcels, a.cell, a.target_mw, a.max_radius, a.nms, a.max_unknown, a.min_avg_area)
    print(f"\n=== {a.sgg} ({a.scen}, cell={a.cell:.0f}m, ≥{a.target_mw:.0f}MW, R≤{a.max_radius:.0f}m, 불명≤{a.max_unknown:.0f}%) — 적격필지 {len(parcels):,} ===")
    print(f"컴팩트 ≥{a.target_mw:.0f}MW 후보(중복제거): {len(cs)}개")
    print(f"{'개인%':>6} {'불명%':>6} {'개인필지':>7} {'총필지':>7} {'MW':>5} {'면적ha':>6} {'반경m':>6}  최근접산단  (중심 lat,lon)")
    for c in cs[:15]:
        print(f"{c['ind_ratio_pct']:6.1f} {c['unknown_pct']:6.1f} {c['n_ind_parcels']:7d} {c['n_parcels']:7d} {c['mw']:5.0f} {c['area_ha']:6.0f} {c['radius_m']:6d}  {c['nearest_complex']}  ({c['lat']},{c['lon']})")
    pf = pareto(cs)
    print(f"\n  Pareto 최적(개인비율·개인필지수): {len(pf)}개")
    for c in pf[:10]:
        print(f"   개인 {c['ind_ratio_pct']:.1f}% (불명 {c['unknown_pct']:.1f}%) · 개인필지 {c['n_ind_parcels']}개 · {c['mw']:.0f}MW · R{c['radius_m']}m · {c['nearest_complex']}")
    if a.json_out:
        json.dump(cs, open(a.json_out,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
        print("저장:", a.json_out)
