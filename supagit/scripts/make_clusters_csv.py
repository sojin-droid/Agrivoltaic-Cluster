import json, csv, os
BASE="/sessions/funny-affectionate-wozniak/mnt/gyeonggi_chungnam/chungnam/44270_dangjin"
OUT="/sessions/funny-affectionate-wozniak/mnt/gyeonggi_chungnam/supagit/data/dangjin_clusters.csv"
SGG="44270"
def ring(r): return "("+", ".join("%s %s"%(c[0],c[1]) for c in r)+")"
def wkt(g):
    t=g["type"]; c=g["coordinates"]
    polys=[c] if t=="Polygon" else (c if t=="MultiPolygon" else None)
    if polys is None: return None
    return "MULTIPOLYGON("+", ".join("("+", ".join(ring(r) for r in poly)+")" for poly in polys)+")"
rows=[]
for scen in ["S0","S3","SMAX"]:
    fp=os.path.join(BASE,f"dangjin_clusters_{scen}.geojson")
    gj=json.load(open(fp,encoding="utf-8"))
    for ft in gj.get("features",[]):
        p=ft["properties"]; cid=p.get("cluster_id")
        rows.append([SGG,scen,cid,json.dumps(p,ensure_ascii=False),wkt(ft["geometry"])])
with open(OUT,"w",newline="",encoding="utf-8") as fo:
    w=csv.writer(fo); w.writerow(["sgg_code","scenario","cluster_id","props","geom_wkt"])
    for r in rows: w.writerow(r)
print("clusters rows:",len(rows),"->",OUT)
