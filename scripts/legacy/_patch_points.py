#!/usr/bin/env python3
"""_patch_points.py — 시군 상세 _map.html 을 폴리곤 → 점(point) 렌더로 전환(멱등).

루트 chungnam/*·gyeonggi/* 14개만 대상(supagit 제외). build_points.py 가 만든
<시군>_points.json 을 로드하도록 로더를 바꾸고, 필지를 canvas circleMarker(점)로 렌더한다.
계산 함수(calcMW/annualGwh/calcRatio)와 표시값 로직은 건드리지 않는다.

멱등성: 파일에 마커 '/* POINTS_PATCH */' 가 있으면 스킵.
각 치환은 정확 일치 문자열을 기대하며, 못 찾으면 해당 파일을 실패로 보고(부분패치 방지).
"""
import glob, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = sorted(glob.glob(os.path.join(ROOT, "chungnam", "*", "*_map.html")) +
               glob.glob(os.path.join(ROOT, "gyeonggi", "*", "*_map.html")))
MARKER = "/* POINTS_PATCH */"

# ── 파일 공통 치환 (old, new) — 14개 파일에서 바이트 동일 ──
COMMON = []

# 1) 지도 canvas 렌더러
COMMON.append((
    "L.map('map').setView(",
    "L.map('map', { preferCanvas: true }).setView(",
))

# 2) computeSelection: 폴리곤 중간점 → 선계산 _lat/_lon
COMMON.append((
    """    var _coords = f.geometry.type === 'MultiPolygon'
      ? f.geometry.coordinates[0][0] : f.geometry.coordinates[0];
    var _pt = _coords[Math.floor(_coords.length / 2)];
    var _dist = haversineDist(_pt[1], _pt[0],
      currentComplex.lat, currentComplex.lon);""",
    """    var _dist = haversineDist(f._lat, f._lon,
      currentComplex.lat, currentComplex.lon);""",
))

# 3) renderMap: L.geoJSON 폴리곤 → canvas circleMarker(점), 팝업 소유=ownership_category
COMMON.append((
    """  parcelLayer = L.geoJSON({
    type: "FeatureCollection",
    features: inRange,
  }, {
    style: feat => {
      const pnu = feat.properties.pnu;
      const isSel = selectedPnus.has(pnu);
      const isBase = basePnus.has(pnu);
      // 테두리 색만 구분: base=보라, added=산호, idle=회색 (계산값 불변)
      const borderColor = isSel
        ? (isBase ? PARCEL_COLORS.base : PARCEL_COLORS.added)
        : PARCEL_COLORS.idle;
      return {
        fillColor: slopeColor(feat.properties.slope_mean),
        fillOpacity: 0.55,
        color: borderColor,
        weight: isSel ? 2 : 0.5,
      };
    },
    onEachFeature: (feat, layer) => {
      const p = feat.properties;
      layer.bindPopup(`
        <b>PNU:</b> ${p.pnu}<br>
        <b>면적:</b> ${Math.round(p.area_m2)} m²<br>
        <b>경사:</b> ${(p.slope_mean || 0).toFixed(1)}°<br>
        <b>소유:</b> ${p.ownership_name || "?"}<br>
        <b>지목:</b> ${p.category || "?"}<br>
        <b>진흥:</b> ${p.subagpromo_name || "비진흥"}
      `);
    }
  }).addTo(map);""",
    """  parcelLayer = L.layerGroup(inRange.map(function(feat) {  /* POINTS_PATCH */
    var p = feat.properties;
    var isSel = selectedPnus.has(p.pnu);
    var isBase = basePnus.has(p.pnu);
    // 테두리 색만 구분: base=보라, added=산호, idle=회색 (계산값 불변)
    var borderColor = isSel
      ? (isBase ? PARCEL_COLORS.base : PARCEL_COLORS.added)
      : PARCEL_COLORS.idle;
    var m = L.circleMarker([feat._lat, feat._lon], {
      radius: isSel ? 4 : 2.5,
      fillColor: slopeColor(p.slope_mean),
      fillOpacity: 0.55,
      color: borderColor,
      weight: isSel ? 2 : 0.5,
    });
    m.bindPopup(
      '<b>PNU:</b> ' + p.pnu + '<br>' +
      '<b>면적:</b> ' + Math.round(p.area_m2) + ' m²<br>' +
      '<b>경사:</b> ' + (p.slope_mean || 0).toFixed(1) + '°<br>' +
      '<b>소유:</b> ' + (p.ownership_category || "?") + '<br>' +
      '<b>지목:</b> ' + (p.category || "?") + '<br>' +
      '<b>진흥:</b> ' + (p.subagpromo_name || "비진흥")
    );
    return m;
  })).addTo(map);""",
))

# 4) 슬라이더: input 마다 즉시 updateMap → rAF 코얼레싱(드래그 중 1프레임 1회)
COMMON.append((
    """slider.addEventListener("input", e => {
  document.getElementById("radius-val").textContent =
    parseFloat(e.target.value).toFixed(1);
  updateMap();
});""",
    """slider.addEventListener("input", e => {
  document.getElementById("radius-val").textContent =
    parseFloat(e.target.value).toFixed(1);
  if (window.__updRaf) return;
  window.__updRaf = requestAnimationFrame(function() { window.__updRaf = 0; updateMap(); });
});""",
))

# 5) updateOwnership: ownership_category 직접 사용(파생 classifyOwnership 제거)
COMMON.append((
    "    var cat = classifyOwnership(f.properties.ownership_name||f.properties.ownership||'');",
    "    var cat = f.properties.ownership_category || '기타';",
))

# 6) ORDER/COLORS: '종중/종교' → 데이터 라벨 '종중·종교'(가운뎃점) 통일
COMMON.append((
    "  var ORDER=['개인','공공','국유','법인','종중/종교','기타'];",
    "  var ORDER=['개인','공공','국유','법인','종중·종교','기타'];",
))
COMMON.append((
    "'법인':'#BA7517','개인':'#3B6D11','종중/종교':'#534AB7'",
    "'법인':'#BA7517','개인':'#3B6D11','종중·종교':'#534AB7'",
))

# 7) 클러스터 fitBounds: 폴리곤 getBounds → 점 좌표 기반 bounds
COMMON.append((
    "      for (var j=0;j<c.pnus.length;j++){ var ft=pnuMap[c.pnus[j]]; if (ft){ var b=L.geoJSON(ft).getBounds(); bb = bb? bb.extend(b) : b; } }",
    "      for (var j=0;j<c.pnus.length;j++){ var ft=pnuMap[c.pnus[j]]; if (ft){ var ll=L.latLng(ft._lat, ft._lon); bb = bb? bb.extend(ll) : L.latLngBounds(ll, ll); } }",
))

# 8) 성장클러스터 멤버 렌더: 필지 폴리곤 fill → 점 circleMarker(pointToLayer)
COMMON.append((
    """          var feats=[];
          for (var j=0;j<=r.k;j++){
            var ft = pnuMap[r.c.pnus[j]];
            if (ft) feats.push({ type:"Feature", geometry: ft.geometry, properties:{ ind:r.c.inds[j] } });
          }
          if (!feats.length) return;
          var gj = L.geoJSON({type:"FeatureCollection",features:feats}, {
            renderer: liRenderer,
            style: function(f){ return { stroke:false, fillColor: f.properties.ind ? '#f59e0b' : '#15803d', fillOpacity: 0.62 }; }
          });""",
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
))


def loader_pair(pfx):
    """파일별 로더 치환(파일명 다름)."""
    old = (
        'const PARCEL_GEOJSON = "%s_parcels.geojson";\n'
        'function loadParcels(lat, lon, radiusM) {\n'
        '  return fetch(PARCEL_GEOJSON)\n'
        '    .then(r => r.json())\n'
        '    .then(data => data.features);\n'
        '}' % pfx
    )
    new = (
        'const PARCEL_POINTS = "%s_points.json";   /* POINTS_PATCH */\n'
        'function loadParcels(lat, lon, radiusM) {\n'
        '  return fetch(PARCEL_POINTS).then(r => r.json()).then(function(d) {\n'
        '    var NO = d.needs_order, OC = d.owncat, CAT = d.cat, PR = d.promo;\n'
        '    return d.rows.map(function(row) {\n'
        '      var props = {\n'
        '        pnu: row[0], area_m2: row[3], slope_mean: row[4],\n'
        '        ownership_category: OC[row[5]], category: CAT[row[6]], subagpromo_name: PR[row[7]]\n'
        '      };\n'
        '      var bits = row[8];\n'
        '      for (var i = 0; i < NO.length; i++) props[NO[i]] = (bits >> i) & 1;\n'
        '      return { properties: props, _lat: row[1], _lon: row[2] };\n'
        '    });\n'
        '  });\n'
        '}' % pfx
    )
    return (old, new)


def patch_file(path):
    pfx = os.path.basename(path).replace("_map.html", "")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if MARKER in src:
        return (pfx, "skip(already patched)")

    pairs = [loader_pair(pfx)] + COMMON
    missing = []
    out = src
    for old, new in pairs:
        n = out.count(old)
        if n != 1:
            missing.append((old.splitlines()[0][:60], n))
            continue
        out = out.replace(old, new)
    if missing:
        return (pfx, "FAIL missing/duplicate: " + "; ".join("%r x%d" % m for m in missing))
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)
    return (pfx, "patched")


def main():
    print(f"대상 {len(FILES)}개 _map.html (루트, supagit 제외)\n")
    ok = fail = skip = 0
    for path in FILES:
        pfx, status = patch_file(path)
        print(f"  {pfx:14s} {status}")
        if status == "patched": ok += 1
        elif status.startswith("skip"): skip += 1
        else: fail += 1
    print(f"\npatched={ok} skip={skip} fail={fail}")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
