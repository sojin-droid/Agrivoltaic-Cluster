#!/usr/bin/env python3
"""공공·법인 주도형 특구 — 필지 단위 '성장' 클러스터 계산.

윈도우(원) 근사 대신 실제 필지를 합친다:
  비개인(국유·공공·법인) 앵커에서 시작 → 인접 필지(중심 거리 ≤ ADJ)를 우선 비개인,
  부족하면 개인 순서로 흡수하며 50MW(=111ha) 채울 때까지 성장.
  각 필지가 합쳐지는 시점의 '누적 개인소유 비율'을 기록 → 프론트의 개인 상한 슬라이더가
  그 비율 이하까지의 prefix만 그리면, 상한을 바꿀수록 실제 필지 클러스터가 단계적으로 자란다.

출력(시군별, 경량): pnu 배열 + 누적개인% + 누적MW. 지오메트리는 클라이언트가 이미 로드한
parcels.geojson에서 pnu로 조회 → 파일은 작게 유지.

사용: python3 lowindiv_growth.py <parcels.geojson> <시군명> --sgg-code 44270
      [--exclude lat,lon,km ...] [--target-mw 50] [--adj 200] [--top 8] [--out f.json]
"""
import json, math, argparse
from collections import defaultdict

PANEL_DENSITY = 0.045 / 1000          # MW per m²
HA_PER_MW = 1.0 / PANEL_DENSITY / 1e4 # ≈ 2.222 ha/MW
S3_KEYS = ["needs_S0_clean","needs_agp_other","needs_agp_protect","needs_facility","needs_agp_core"]
S0_KEYS = ["needs_S0_clean"]

def centroid(geom):
    c = geom["coordinates"]
    ring = c[0][0] if geom["type"] == "MultiPolygon" else c[0]
    n = len(ring)
    return sum(p[0] for p in ring)/n, sum(p[1] for p in ring)/n

def hav_km(a,b,c,d):
    R=6371; t=math.pi/180
    return 2*R*math.asin(math.sqrt(math.sin((c-a)*t/2)**2+math.cos(a*t)*math.cos(c*t)*math.sin((d-b)*t/2)**2))

def load(path, keys, sgg_code, zones):
    gj = json.load(open(path, encoding="utf-8"))
    out=[]
    for f in gj["features"]:
        p=f["properties"]
        if p.get("needs_upper_law")==1: continue
        if not any(p.get(k)==1 for k in keys): continue
        pnu=p.get("pnu","")
        if sgg_code and pnu and not pnu.startswith(sgg_code): continue
        lon,lat=centroid(f["geometry"])
        if zones and any(hav_km(z[0],z[1],lat,lon)<=z[2] for z in zones): continue
        cat=p.get("ownership_category")
        if cat in (None,""): continue          # 소유불명 제외(성장에서도 비개인 단정 불가)
        out.append({"pnu":pnu,"lon":lon,"lat":lat,"area":p.get("area_m2") or 0.0,
                    "ind":1 if cat=="개인" else 0,"cx":p.get("nearest_complex") or "(미상)"})
    return out

def grow(parcels, adj_m, target_mw, top, nms_km=1.2):
    if not parcels: return []
    target_area = target_mw/PANEL_DENSITY
    lat0=sum(p["lat"] for p in parcels)/len(parcels)
    lon0=sum(p["lon"] for p in parcels)/len(parcels)
    kx=111320*math.cos(math.radians(lat0)); ky=111320
    for p in parcels:
        p["x"]=(p["lon"]-lon0)*kx; p["y"]=(p["lat"]-lat0)*ky
    grid=defaultdict(list)
    for i,p in enumerate(parcels):
        grid[(int(p["x"]//adj_m),int(p["y"]//adj_m))].append(i)
    def neigh(i):
        p=parcels[i]; gx,gy=int(p["x"]//adj_m),int(p["y"]//adj_m); r=[]
        for dx in(-1,0,1):
            for dy in(-1,0,1):
                for j in grid.get((gx+dx,gy+dy),()):
                    if j!=i:
                        q=parcels[j]
                        if (p["x"]-q["x"])**2+(p["y"]-q["y"])**2<=adj_m*adj_m: r.append(j)
        return r
    used=[False]*len(parcels)
    seeds=sorted([i for i,p in enumerate(parcels) if not p["ind"]], key=lambda i:-parcels[i]["area"])
    clusters=[]
    for s in seeds:
        if used[s]: continue
        members=[s]; used[s]=True
        a_ind=0.0; a_non=parcels[s]["area"]
        order=[s]; seen={s}
        fr_non=[]; fr_ind=[]
        for j in neigh(s):
            (fr_non if not parcels[j]["ind"] else fr_ind).append(j); seen.add(j)
        while (a_ind+a_non)<target_area:
            j=None
            if fr_non:
                fr_non.sort(key=lambda k:parcels[k]["area"]); j=fr_non.pop()
            elif fr_ind:
                fr_ind.sort(key=lambda k:parcels[k]["area"]); j=fr_ind.pop()
            else:
                break
            if used[j]: continue
            used[j]=True; members.append(j); order.append(j)
            if parcels[j]["ind"]: a_ind+=parcels[j]["area"]
            else: a_non+=parcels[j]["area"]
            for k in neigh(j):
                if k not in seen and not used[k]:
                    (fr_non if not parcels[k]["ind"] else fr_ind).append(k); seen.add(k)
        mw=(a_ind+a_non)*PANEL_DENSITY
        if mw < target_mw*0.6:   # 50MW의 60%도 못 채우면 후보 제외
            continue
        # 누적 배열 (성장 순서)
        cum_a=0.0; cum_ai=0.0; cum_ind=[]; cum_mw=[]; pnus=[]; inds=[]
        for idx in order:
            p=parcels[idx]; cum_a+=p["area"]; cum_ai+=p["area"]*p["ind"]
            cum_ind.append(round(cum_ai/cum_a*100,1)); cum_mw.append(round(cum_a*PANEL_DENSITY,1))
            pnus.append(p["pnu"]); inds.append(p["ind"])
        cxs=defaultdict(float)
        for idx in members: cxs[parcels[idx]["cx"]]+=parcels[idx]["area"]
        clusters.append({
            "lat":round(sum(parcels[i]["lat"] for i in members)/len(members),5),
            "lon":round(sum(parcels[i]["lon"] for i in members)/len(members),5),
            "complex":max(cxs,key=cxs.get),"final_ind_pct":cum_ind[-1],"final_mw":cum_mw[-1],
            "n":len(members),"pnus":pnus,"inds":inds,"cum_ind":cum_ind,"cum_mw":cum_mw})
    # NMS 후 최저 개인% 우선 top개
    clusters.sort(key=lambda c:(c["final_ind_pct"],-c["final_mw"]))
    kept=[]
    for c in clusters:
        if all(hav_km(c["lat"],c["lon"],k["lat"],k["lon"])>nms_km for k in kept):
            kept.append(c)
        if len(kept)>=top: break
    return kept

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("geojson"); ap.add_argument("sgg")
    ap.add_argument("--scen",default="S3"); ap.add_argument("--sgg-code",default=None)
    ap.add_argument("--exclude",action="append",default=[])
    ap.add_argument("--target-mw",type=float,default=50); ap.add_argument("--adj",type=float,default=200)
    ap.add_argument("--top",type=int,default=8); ap.add_argument("--out")
    a=ap.parse_args()
    keys=S3_KEYS if a.scen=="S3" else S0_KEYS
    zones=[tuple(map(float,z.split(","))) for z in a.exclude]
    parcels=load(a.geojson,keys,a.sgg_code,zones)
    cl=grow(parcels,a.adj,a.target_mw,a.top)
    print(f"=== {a.sgg} 성장클러스터 {len(cl)}개 (적격필지 {len(parcels):,}, 목표 {a.target_mw:.0f}MW={a.target_mw/PANEL_DENSITY/1e4:.0f}ha) ===")
    for i,c in enumerate(cl):
        # cap별 prefix MW 보기
        def at(cap):
            k=-1
            for j,r in enumerate(c["cum_ind"]):
                if r<=cap: k=j
            return (c["cum_mw"][k], c["cum_ind"][k], k+1) if k>=0 else (0,0,0)
        m10=at(10); m30=at(30); m50=at(50)
        print(f"  #{i+1} 최종 개인{c['final_ind_pct']}% · {c['final_mw']}MW · {c['n']}필지 · {c['complex']}")
        print(f"      ≤10%→{m10[0]}MW({m10[2]}필지) | ≤30%→{m30[0]}MW({m30[2]}필지) | ≤50%→{m50[0]}MW({m50[2]}필지)")
    if a.out:
        json.dump({"sgg":a.sgg,"target_mw":a.target_mw,"req_ha":round(a.target_mw/PANEL_DENSITY/1e4,1),"clusters":cl},
                  open(a.out,"w",encoding="utf-8"),ensure_ascii=False)
        print("저장:",a.out)
