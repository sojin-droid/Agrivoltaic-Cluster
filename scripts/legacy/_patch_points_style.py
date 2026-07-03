#!/usr/bin/env python3
"""_patch_points_style.py — 점(point) 렌더 시각 개선(멱등). 계산값·dong-pool 로직 불변.

배경: 폴리곤→점 전환 후 낮은 줌에서 점 수천 개가 뭉쳐 덩어리로 보임.
  ① 주 필지 점: 반경↓·투명도↓·비선택 테두리 제거 → 덜 뭉치게. (dong-pool _dpCapped 스타일은 보존)
  ② 성장클러스터 멤버: 필지 점 수천 개 → '클러스터별 볼록껍질(convex hull) 외곽선 1개'로.

멱등: 마커 '/* POINTS_STYLE_PATCH */'(convexHull 헬퍼에 포함) 있으면 스킵.
대상: 루트 chungnam/*·gyeonggi/* 14개(supagit 제외). 각 치환 정확 1회 매칭 아니면 실패 보고.
"""
import glob, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = sorted(glob.glob(os.path.join(ROOT, "chungnam", "*", "*_map.html")) +
               glob.glob(os.path.join(ROOT, "gyeonggi", "*", "*_map.html")))
MARKER = "/* POINTS_STYLE_PATCH */"

PAIRS = []

# ① 주 필지 circleMarker 스타일 튜닝 (_dpCapped/dashArray 보존)
PAIRS.append((
    """    var m = L.circleMarker([feat._lat, feat._lon], {
      radius: isSel ? 4 : 2.5,
      fillColor: slopeColor(p.slope_mean),
      fillOpacity: _dpCapped ? 0.15 : 0.55,
      color: borderColor,
      weight: isSel ? 2 : 0.5,
      dashArray: _dpCapped ? "2,2" : null,
    });""",
    """    var m = L.circleMarker([feat._lat, feat._lon], {
      radius: isSel ? 3 : 1.5,
      fillColor: slopeColor(p.slope_mean),
      fillOpacity: _dpCapped ? 0.12 : (isSel ? 0.7 : 0.28),
      color: borderColor,
      weight: _dpCapped ? 1 : (isSel ? 1 : 0),
      dashArray: _dpCapped ? "2,2" : null,
    });""",
))

# ② 성장클러스터 멤버: 점 수천 개 → 클러스터별 convex hull 외곽선 1개
PAIRS.append((
    """          var feats=[];
          for (var j=0;j<=r.k;j++){
            var ft = pnuMap[r.c.pnus[j]];
            if (ft) feats.push({ type:"Feature", geometry:{ type:"Point", coordinates:[ft._lon, ft._lat] }, properties:{ ind:r.c.inds[j] } });
          }
          if (!feats.length) return;
          var gj = L.geoJSON({type:"FeatureCollection",features:feats}, {
            renderer: liRenderer,
            pointToLayer: function(f, latlng){ return L.circleMarker(latlng, { renderer: liRenderer, radius: 3, stroke:false, fillColor: f.properties.ind ? '#f59e0b' : '#15803d', fillOpacity: 0.62 }); }
          });""",
    """          var _pts=[];
          for (var j=0;j<=r.k;j++){
            var ft = pnuMap[r.c.pnus[j]];
            if (ft) _pts.push([ft._lon, ft._lat]);
          }
          if (!_pts.length) return;
          var _ip = (r.c.final_ind_pct!=null ? r.c.final_ind_pct : 50);
          var _col = _ip<=0?'#15803d':_ip<=20?'#4ade80':_ip<=40?'#facc15':'#f59e0b';
          var _hull = convexHull(_pts).map(function(pt){ return [pt[1], pt[0]]; });
          var gj = (_hull.length>=3)
            ? L.polygon(_hull, { renderer: liRenderer, color:_col, weight:2, fillColor:_col, fillOpacity:0.20 })
            : L.geoJSON({type:"FeatureCollection",features:_pts.map(function(pt){return {type:"Feature",geometry:{type:"Point",coordinates:pt},properties:{}};})}, { renderer: liRenderer, pointToLayer:function(f,ll){return L.circleMarker(ll,{renderer:liRenderer,radius:3,stroke:false,fillColor:_col,fillOpacity:0.6});} });""",
))

# ③ convexHull 헬퍼 삽입(전역) + 멱등 마커. haversineDist 앞에 prepend.
PAIRS.append((
    "function haversineDist(lat1, lon1, lat2, lon2) {",
    """function convexHull(points) {  """ + MARKER + """
  var pts = points.slice().sort(function(a,b){ return a[0]-b[0] || a[1]-b[1]; });
  if (pts.length < 3) return pts;
  function cross(o,a,b){ return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0]); }
  var lo=[], i;
  for (i=0;i<pts.length;i++){ while(lo.length>=2 && cross(lo[lo.length-2],lo[lo.length-1],pts[i])<=0) lo.pop(); lo.push(pts[i]); }
  var up=[];
  for (i=pts.length-1;i>=0;i--){ while(up.length>=2 && cross(up[up.length-2],up[up.length-1],pts[i])<=0) up.pop(); up.push(pts[i]); }
  lo.pop(); up.pop();
  return lo.concat(up);
}

function haversineDist(lat1, lon1, lat2, lon2) {""",
))


def patch_file(path):
    pfx = os.path.basename(path).replace("_map.html", "")
    src = open(path, encoding="utf-8").read()
    if MARKER in src:
        return (pfx, "skip(already styled)")
    miss = []
    out = src
    for old, new in PAIRS:
        if out.count(old) != 1:
            miss.append((old.splitlines()[0][:50], out.count(old)))
            continue
        out = out.replace(old, new)
    if miss:
        return (pfx, "FAIL: " + "; ".join("%r x%d" % m for m in miss))
    open(path, "w", encoding="utf-8").write(out)
    return (pfx, "styled")


def main():
    print("대상 %d개 (supagit 제외)\n" % len(FILES))
    ok = fail = skip = 0
    for p in FILES:
        pfx, st = patch_file(p)
        print("  %-14s %s" % (pfx, st))
        ok += st == "styled"; skip += st.startswith("skip"); fail += st.startswith("FAIL")
    print("\nstyled=%d skip=%d fail=%d" % (ok, skip, fail))
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
