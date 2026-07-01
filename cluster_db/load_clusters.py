#!/usr/bin/env python3
"""영농형 특구 후보 클러스터를 clusters.db에 적재.
사용: python3 load_clusters.py <sgg_code> <sgg_name> <region_dir> <file_prefix> [scenarios...]
예:   python3 load_clusters.py 44270 당진 ../chungnam/44270_dangjin dangjin S0 S3 SMAX
입력(영구 파일): {prefix}_clusters_ranked_{scen}.json, {prefix}_clusters_members_{scen}.json,
                {prefix}_clusters_{scen}.geojson
"""
import sqlite3, json, os, sys
HERE=os.path.dirname(os.path.abspath(__file__))
DB=os.path.join(HERE,"clusters.db")
def main(sgg_code,sgg_name,region_dir,prefix,scenarios):
    region_dir=os.path.join(HERE,region_dir) if not os.path.isabs(region_dir) else region_dir
    con=sqlite3.connect(DB)
    con.executescript(open(os.path.join(HERE,"schema.sql"),encoding="utf-8").read())
    for scen in scenarios:
        rp=os.path.join(region_dir,f"{prefix}_clusters_ranked_{scen}.json")
        mp=os.path.join(region_dir,f"{prefix}_clusters_members_{scen}.json")
        if not os.path.exists(rp): print("skip",scen,"(no ranked file)"); continue
        ranked=json.load(open(rp,encoding="utf-8"))["clusters"]
        members=json.load(open(mp,encoding="utf-8")) if os.path.exists(mp) else {}
        gj=f"{prefix}_clusters_{scen}.geojson"
        for i,c in enumerate(ranked):
            cid=i+1
            con.execute("""INSERT OR REPLACE INTO clusters
              (sgg_code,sgg_name,scenario,cluster_id,mw,area_ha,n_parcels,individual_ratio_pct,
               nearest_complex,dist_km,demand_gwh,pareto_layer,smaa_rank1_pct,smaa_rank,
               centroid_lon,centroid_lat,geojson_file)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (sgg_code,sgg_name,scen,cid,round(c["mw"],2),round(c["area"]/1e4,2),c["n"],
               round(c["ratio"]*100,2),c.get("nearest_complex"),c.get("dist_km"),c.get("demand_gwh"),
               c.get("pareto_layer"),c.get("smaa_rank1_pct"),c.get("smaa_rank"),
               c.get("lon"),c.get("lat"),gj))
            for p in members.get(str(cid),[]):
                con.execute("""INSERT INTO cluster_parcels
                  (sgg_code,scenario,cluster_id,pnu,area_m2,ownership_name,is_individual)
                  VALUES (?,?,?,?,?,?,?)""",
                  (sgg_code,scen,cid,p["pnu"],p["area_m2"],p["ownership_name"],p["is_individual"]))
        print(f"loaded {scen}: {len(ranked)} clusters, {sum(len(members.get(str(i+1),[])) for i in range(len(ranked)))} parcels")
    con.commit(); con.close()
if __name__=="__main__":
    a=sys.argv
    main(a[1],a[2],a[3],a[4],a[5:] if len(a)>5 else ["S0","S3","SMAX"])
