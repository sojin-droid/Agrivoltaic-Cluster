#!/usr/bin/env python3
"""_patch_dong_pool.py — 시군 상세 _map.html 에 동-여유풀(KEPCO) 정보 반영(멱등).

<시군>_dong_pool.json(build_sigungu_dong_pool.py 산출물)을 로드해서:
  1) 필지 팝업에 소속 읍면동의 계통 여유용량 표시
  2) 결과 패널에 "계통 연계 여유(참고)"·"계통 제약 감안 시" MW 비교 지표 추가
  3) 사이드바에 선택 반경 내 동별 여유용량 목록 패널 추가
  4) 상한(vol1/vol2) 캡에 걸린 동 필지를 흐리게 표시하는 토글 추가
계산 함수(calcMW/annualGwh/calcRatio)와 기존 표시값 로직은 건드리지 않는다
(참고용 신규 지표만 옆에 추가).

멱등성: 파일에 마커 '/* DONGPOOL_PATCH */' 가 있으면 스킵.
각 치환은 정확 일치 문자열을 기대하며, 못 찾으면 해당 파일을 실패로 보고(부분패치 방지).
"""
import glob, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = sorted(glob.glob(os.path.join(ROOT, "chungnam", "*", "*_map.html")) +
               glob.glob(os.path.join(ROOT, "gyeonggi", "*", "*_map.html")))
MARKER = "/* DONGPOOL_PATCH */"

# ── 파일 공통 치환 (old, new) — 14개 파일에서 바이트 동일 ──
COMMON = []

# 1) 헬퍼 함수 + DONG_POOL 상태 변수 (slopeColor 다음에 추가)
COMMON.append((
    """function slopeColor(slope) {
  if (slope == null || isNaN(slope)) return "#e0e0e0";
  if (slope < 3) return "#ffffff";
  if (slope < 6) return "#fff9c4";
  if (slope < 10) return "#ffee58";
  if (slope < 15) return "#ff8f00";
  return "#d50000";
}""",
    """function slopeColor(slope) {
  if (slope == null || isNaN(slope)) return "#e0e0e0";
  if (slope < 3) return "#ffffff";
  if (slope < 6) return "#fff9c4";
  if (slope < 10) return "#ffee58";
  if (slope < 15) return "#ff8f00";
  return "#d50000";
}

// ── KEPCO 동-여유풀(참고용) — 계산값(mw/ratio)은 바꾸지 않고 옆에 표시만 ──  /* DONGPOOL_PATCH */
let DONG_POOL = {};
function dongPoolOf(pnu) { return pnu ? (DONG_POOL[pnu.substring(0, 8)] || null) : null; }
function dongPoolPopupLine(pnu) {
  var d = dongPoolOf(pnu);
  if (!d) return "";
  var warn = d[2] ? ' <span style="color:#b91c1c;">(상한 캡)</span>' : "";
  return "<br><b>계통 여유(동):</b> " + Math.round(d[1]).toLocaleString() + " kW" + warn;
}""",
))

# 2) 결과 패널: 계통 여유 지표 2행 + 동 목록 패널
# (r-ratio 앞 라벨 마크업은 파일마다 다름(dangjin만 id="r-ratio-label") — r-ratio 자체와
#  패널 닫는 태그만 공통 앵커로 사용, 라벨은 건드리지 않음)
COMMON.append((
    """      <span class="big" id="r-ratio">0%</span>
    </div>
  </div>""",
    """      <span class="big" id="r-ratio">0%</span>
    </div>
    <div class="result-row" title="선택 필지가 속한 읍면동의 KEPCO 배전선로 여유용량 합(동 전체 기준 근사값, 참고용)">
      <span>계통 연계 여유(참고)</span>
      <span class="big" id="r-grid-mw">0 MW</span>
    </div>
    <div class="result-row">
      <span>계통 제약 감안 시</span>
      <span class="big" id="r-grid-limited-mw">0 MW</span>
    </div>
  </div>

  <div id="dong-pool-panel" style="background:#fef3e2;border:1px solid #fcd9a8;border-radius:6px;padding:10px;margin:10px 0;font-size:11px;line-height:1.6;">
    <div style="font-weight:600;color:#92400e;margin-bottom:4px;">&#9889; 선택 반경 내 계통 여유용량 (읍면동 단위)</div>
    <div id="dong-pool-list" style="color:#78350f;">산단을 선택하면 표시됩니다.</div>
    <div style="font-size:10px;color:#a16207;margin-top:6px;">※ 동 전체 기준 근사값 — 반경 내 비율로 나누지 않았습니다. KEPCO 데이터 없는 동은 제외.</div>
  </div>"""
))

# 3) 상한 캡 시각화 토글 (상위법 제외 체크박스 다음에 추가)
COMMON.append((
    """  <div style="margin:12px 0;padding:10px;border:1px solid #e0e0e0;
              border-radius:6px;background:#fafafa;">
    <label style="display:flex;align-items:center;gap:8px;
                   cursor:pointer;font-size:12px;font-weight:500;">
      <input type="checkbox" id="chk-upper-law"
             onchange="updateMap()">
      상위법상 제한지역 제외 (문화재·생태·공원·군사 등 13종)
    </label>
    <div style="font-size:10px;color:#888;margin-top:4px;padding-left:24px;
                line-height:1.5;">
      갯벌·하천·산림·경사도 등 일부 규제는 미반영
    </div>
  </div>""",
    """  <div style="margin:12px 0;padding:10px;border:1px solid #e0e0e0;
              border-radius:6px;background:#fafafa;">
    <label style="display:flex;align-items:center;gap:8px;
                   cursor:pointer;font-size:12px;font-weight:500;">
      <input type="checkbox" id="chk-upper-law"
             onchange="updateMap()">
      상위법상 제한지역 제외 (문화재·생태·공원·군사 등 13종)
    </label>
    <div style="font-size:10px;color:#888;margin-top:4px;padding-left:24px;
                line-height:1.5;">
      갯벌·하천·산림·경사도 등 일부 규제는 미반영
    </div>
  </div>

  <div id="dong-pool-warn-box" style="margin:12px 0;padding:10px;border:1px solid #e0e0e0;
              border-radius:6px;background:#fafafa;">  <!-- DONGPOOL_PATCH -->
    <label style="display:flex;align-items:center;gap:8px;
                   cursor:pointer;font-size:12px;font-weight:500;">
      <input type="checkbox" id="chk-dong-pool-warn"
             onchange="updateMap()">
      계통 여유 부족(상한 캡) 읍면동 필지 흐리게 표시
    </label>
    <div style="font-size:10px;color:#888;margin-top:4px;padding-left:24px;
                line-height:1.5;">
      KEPCO 변전소·변압기 여유용량 상한에 걸린 동 — 동 전체 기준 근사치
    </div>
  </div>"""
))

# 4) computeSelection: r-ratio 갱신 직후 계통 여유 계산 + 패널 갱신 호출 삽입
COMMON.append((
    """  document.getElementById("r-ratio").textContent =
    Math.round(ratio).toLocaleString() + "%";
  updatePolicy(selected);""",
    """  document.getElementById("r-ratio").textContent =
    Math.round(ratio).toLocaleString() + "%";
  // ── 계통 연계 여유(KEPCO 동-풀, 참고용) — 선택 필지가 속한 동들의 여유용량 합 ──  /* DONGPOOL_PATCH */
  var dongSeen = {}, gridKw = 0;
  selected.forEach(function(f) {
    var code = f.properties.pnu ? f.properties.pnu.substring(0, 8) : null;
    var d = code ? DONG_POOL[code] : null;
    if (!d || dongSeen[code]) return;
    dongSeen[code] = true;
    gridKw += d[1];
  });
  var gridMw = gridKw / 1000;
  var gridLimitedMw = Math.min(mw, gridMw);
  var gmwEl = document.getElementById("r-grid-mw");
  if (gmwEl) gmwEl.textContent = Math.round(gridMw).toLocaleString() + " MW";
  var glEl = document.getElementById("r-grid-limited-mw");
  if (glEl) glEl.textContent = Math.round(gridLimitedMw).toLocaleString() + " MW";
  updateDongPoolPanel(dongSeen);
  updatePolicy(selected);"""
))

# 5) updateDongPoolPanel 함수 신규 정의 (updatePolicy 함수 앞에 추가)
COMMON.append((
    """function updatePolicy(selected) {""",
    """function updateDongPoolPanel(dongSeen) {  /* DONGPOOL_PATCH */
  var list = document.getElementById("dong-pool-list");
  if (!list) return;
  var rows = Object.keys(dongSeen).map(function(code) {
    var d = DONG_POOL[code];
    return d ? { name: d[0], kw: d[1], capped: d[2] } : null;
  }).filter(Boolean);
  if (rows.length === 0) {
    list.innerHTML = '<span style="color:#999;">이 반경 내 KEPCO 여유용량 데이터가 없습니다.</span>';
    return;
  }
  rows.sort(function(a, b) { return b.kw - a.kw; });
  list.innerHTML = rows.map(function(r) {
    var warn = r.capped ? ' <span style="color:#b91c1c;">&#9888;상한 캡</span>' : "";
    return r.name + ": <b>" + Math.round(r.kw).toLocaleString() + " kW</b>" + warn;
  }).join("<br>");
}

function updatePolicy(selected) {"""
))

# 6) renderMap: 캡 토글 상태를 루프 밖에서 1회만 조회(성능), 마커에 반영
COMMON.append((
    """  const selectedPnus = new Set(selected.map(f => f.properties.pnu));
  parcelLayer = L.layerGroup(inRange.map(function(feat) {  /* POINTS_PATCH */""",
    """  const selectedPnus = new Set(selected.map(f => f.properties.pnu));
  var _dpWarnEl = document.getElementById('chk-dong-pool-warn');  /* DONGPOOL_PATCH */
  var _dpWarnOn = !!(_dpWarnEl && _dpWarnEl.checked);
  parcelLayer = L.layerGroup(inRange.map(function(feat) {  /* POINTS_PATCH */"""
))
COMMON.append((
    """    var borderColor = isSel
      ? (isBase ? PARCEL_COLORS.base : PARCEL_COLORS.added)
      : PARCEL_COLORS.idle;
    var m = L.circleMarker([feat._lat, feat._lon], {
      radius: isSel ? 4 : 2.5,
      fillColor: slopeColor(p.slope_mean),
      fillOpacity: 0.55,
      color: borderColor,
      weight: isSel ? 2 : 0.5,
    });""",
    """    var borderColor = isSel
      ? (isBase ? PARCEL_COLORS.base : PARCEL_COLORS.added)
      : PARCEL_COLORS.idle;
    var _dp = _dpWarnOn ? dongPoolOf(p.pnu) : null;  /* DONGPOOL_PATCH */
    var _dpCapped = !!(_dp && _dp[2]);
    var m = L.circleMarker([feat._lat, feat._lon], {
      radius: isSel ? 4 : 2.5,
      fillColor: slopeColor(p.slope_mean),
      fillOpacity: _dpCapped ? 0.15 : 0.55,
      color: borderColor,
      weight: isSel ? 2 : 0.5,
      dashArray: _dpCapped ? "2,2" : null,
    });"""
))

# 7) 팝업: 소유/지목/진흥 다음에 계통 여유 줄 추가
COMMON.append((
    """      '<b>지목:</b> ' + (p.category || "?") + '<br>' +
      '<b>진흥:</b> ' + (p.subagpromo_name || "비진흥")
    );""",
    """      '<b>지목:</b> ' + (p.category || "?") + '<br>' +
      '<b>진흥:</b> ' + (p.subagpromo_name || "비진흥") +
      dongPoolPopupLine(p.pnu)  /* DONGPOOL_PATCH */
    );"""
))


def loader_pair(pfx):
    """파일별 로더 치환(파일명 다름) — PARCEL_POINTS 선언 다음에 dong_pool fetch 추가."""
    old = 'const PARCEL_POINTS = "%s_points.json";   /* POINTS_PATCH */' % pfx
    new = (
        'const PARCEL_POINTS = "%s_points.json";   /* POINTS_PATCH */\n'
        'const DONG_POOL_PATH = "%s_dong_pool.json";   /* DONGPOOL_PATCH */\n'
        'fetch(DONG_POOL_PATH).then(function(r){ return r.ok ? r.json() : {}; })'
        '.then(function(d){ DONG_POOL = d; }).catch(function(){});'
        % (pfx, pfx)
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
