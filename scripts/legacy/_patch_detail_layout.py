#!/usr/bin/env python3
"""14개 detail map 사이드바 위계 재배분 일괄 패치.

변경:
  A. 사이드바 sgg-summary 다음에 「공공·법인 주도형 특구 후보」 패널 신규 삽입(요약·필터·리스트·CSV).
  B. 기존 H2 "1. 산단 선택" ~ 시나리오 차트 영역 → <details> 로 감싸기(기본 닫힘).
  C. 우측 #control-panel 의 H2 "설치 가능 조건 선택" ~ 끝 영역 → <details> 로 감싸기(기본 열림).
  D. 기존 우상단 floating "공공·법인 주도형 후보" IIFE 제거.
  E. loadClusters() 직후 사이드바 패널 동작 JS 신규 삽입.
"""
import glob, sys

# ── 변경 마커들 ─────────────────────────────────────────
# B 산단 영역 시작/끝 마커 (14개 동일)
B_START = '<h2>1. 산단 선택</h2>'
B_END_BEFORE = '<h2 style="margin-top:20px;font-size:11px;color:#999;">'  # formula-card 시작 직전
# C 우측 정책 영역
C_START = '<div id="control-panel">\n  <h2>설치 가능 조건 선택</h2>'
C_END = '</div>\n\n<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
# D 기존 IIFE — 시작/끝
D_START_LINE = '  // ═══ 공공·법인 주도형 특구 후보 레이어 (개인소유 ≤상한, ≥50MW · 14개 시군 통합) ═══'
D_END_LINE = '  })();\n\n})();'                                  # IIFE 끝 + 바깥 IIFE 끝

# ── A 새 사이드바 패널 ──────────────────────────────────
NEW_SIDE_PANEL = '''<div id="li-panel" style="background:#f0fdf4;border:1px solid #86efac;border-radius:6px;padding:12px;margin-bottom:12px;font-size:12px;">
  <div style="font-weight:600;color:#166534;margin-bottom:6px;font-size:13px;">⭐ 공공·법인 주도형 특구 후보</div>
  <div id="li-summary" style="line-height:1.6;color:#374151;">데이터 로드 중…</div>
  <div style="margin-top:8px;padding-top:8px;border-top:1px solid #bbf7d0;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
    <span style="font-size:11px;color:#555;">개인 ≤</span>
    <select id="li-cap-side" style="font-size:11px;padding:2px 4px;">
      <option value="10">10%</option><option value="20">20%</option><option value="30" selected>30%</option><option value="50">50%</option>
    </select>
    <label style="cursor:pointer;font-size:11px;color:#555;"><input type="checkbox" id="li-show-side" checked style="vertical-align:middle;margin-right:3px"> 지도 표시</label>
    <button id="li-csv-side" type="button" style="margin-left:auto;font-size:11px;border:1px solid #16a34a;color:#16a34a;background:#fff;border-radius:4px;padding:2px 8px;cursor:pointer;">CSV</button>
  </div>
  <div id="li-list" style="margin-top:8px;max-height:260px;overflow:auto;"></div>
</div>

'''

# ── E 새 사이드바 동작 JS ──────────────────────────────
NEW_SIDE_JS = r'''  loadClusters(lsGet("cl_scen","S3"));

  // ═══ 공공·법인 주도형 후보 사이드바 동작 (필터·요약·카드·CSV·지도원) ═══
  (function(){
    if (typeof map === "undefined" || typeof INFO === "undefined") return;
    if (!document.getElementById("li-panel")) return;
    var liLayer = L.layerGroup();
    var DATA = null;
    function indColor(p){ if (p<=0) return '#15803d'; if (p<=10) return '#4ade80'; if (p<=20) return '#facc15'; if (p<=30) return '#fb923c'; return '#ef4444'; }
    function render(){
      var cap = parseFloat(document.getElementById("li-cap-side").value);
      var show = document.getElementById("li-show-side").checked;
      liLayer.clearLayers();
      var rows = (DATA||[]).filter(function(c){ return c.ind_pct <= cap; });
      rows.sort(function(a,b){ return (a.ind_pct - b.ind_pct) || (a.n_ind - b.n_ind); });

      var n0 = rows.filter(function(c){return c.ind_pct<=0;}).length;
      var n10 = rows.filter(function(c){return c.ind_pct<=10;}).length;
      var n30 = rows.filter(function(c){return c.ind_pct<=30;}).length;
      var totalAll = (DATA||[]).length;
      var best = rows.length ? rows[0] : null;
      var s = "이 시군 후보 <b>" + totalAll + "곳</b> · 필터 적용 <b>" + rows.length + "곳</b>";
      if (best) {
        s += "<br>최저 개인소유 <b style='color:" + indColor(best.ind_pct) + "'>" + best.ind_pct + "%</b> · ";
        s += Math.round(best.mw) + "MW · " + best.complex;
        s += "<br><span style='font-size:11px;color:#888'>0% " + n0 + "곳 · ≤10% " + n10 + "곳 · ≤30% " + n30 + "곳</span>";
      } else if (totalAll === 0) {
        s += "<br><span style='color:#999'>이 시군은 컴팩트 ≥50MW 후보가 없습니다.</span>";
      } else {
        s += "<br><span style='color:#999'>현재 필터로 표시할 후보 없음 — 상한을 올려보세요.</span>";
      }
      document.getElementById("li-summary").innerHTML = s;

      var listEl = document.getElementById("li-list");
      listEl.innerHTML = rows.slice(0,30).map(function(c){
        var col = indColor(c.ind_pct);
        var consent = c.ind_pct <= 0 ? '동의 불필요' : ('동의 ' + c.n_ind + '필지');
        return '<div data-lat="'+c.lat+'" data-lon="'+c.lon+'" class="li-card" style="cursor:pointer;background:#fff;border-left:3px solid '+col+';padding:6px 8px;margin-bottom:4px;font-size:11px;border-radius:3px;">' +
          '<b>#'+c.rank+'</b> 개인 <b style="color:'+col+'">'+c.ind_pct+'%</b> · '+Math.round(c.mw)+'MW · '+c.area_ha+'ha' +
          (c.pareto?' <span style="color:#b45309" title="Pareto 최적">★</span>':'') +
          '<br><span style="color:#666">'+consent+' / '+c.complex+'</span></div>';
      }).join('') + (rows.length>30 ? '<div style="color:#888;font-size:11px;text-align:center;padding:4px">… +'+(rows.length-30)+'곳 더(CSV로 전체 받기)</div>' : '');
      listEl.querySelectorAll(".li-card").forEach(function(el){
        el.addEventListener("click", function(){
          var lat=parseFloat(this.dataset.lat), lon=parseFloat(this.dataset.lon);
          map.flyTo([lat,lon], 15, {duration:0.8});
        });
      });

      if (show) {
        rows.forEach(function(c){
          var col = indColor(c.ind_pct);
          var ring = L.circle([c.lat,c.lon], { radius: c.radius_m, stroke: false, fillColor: col, fillOpacity: 0.55 });
          var consent = c.ind_pct <= 0 ? '<b style="color:#15803d">개인 동의 불필요</b>' : ('동의 개인필지 <b>' + c.n_ind + '개</b>');
          ring.bindTooltip('개인 ' + c.ind_pct + '% · ' + Math.round(c.mw) + 'MW · R~' + c.radius_m + 'm', {sticky:true});
          ring.bindPopup('<div style="min-width:200px"><b>공공·법인 주도형 #' + c.rank + '</b>' + (c.pareto?' <span style="color:#b45309">★Pareto</span>':'') +
            '<br>개인 <b style="color:' + col + '">' + c.ind_pct + '%</b>' + (c.unknown_pct>0?(' (불명 ' + c.unknown_pct + '%)'):'') +
            (c.data_warn?' <span style="color:#b91c1c;font-size:11px">⚠ 결측많음</span>':'') +
            '<br>' + consent + ' · 총 ' + c.n_parcels + '필지' +
            '<br>설비 <b>' + Math.round(c.mw) + 'MW</b> · ' + Math.round(c.area_ha) + 'ha · 반경 ~' + c.radius_m + 'm' +
            '<br>최근접 산단: ' + c.complex + '</div>');
          liLayer.addLayer(ring);
        });
        if (!map.hasLayer(liLayer)) map.addLayer(liLayer);
      } else {
        map.removeLayer(liLayer);
      }
    }
    function csv(){
      var cap = parseFloat(document.getElementById("li-cap-side").value);
      var rows = (DATA||[]).filter(function(c){ return c.ind_pct <= cap; });
      var hdr = ['시군','후보순위','개인소유_pct','소유불명_pct','동의_개인필지수','총필지수','설비MW','면적ha','반경m','최근접산단','Pareto','lat','lon'];
      var out = '﻿' + hdr.join(',') + '\n' + rows.map(function(c){
        return [c.sgg, c.rank, c.ind_pct, c.unknown_pct, c.n_ind, c.n_parcels, c.mw, c.area_ha, c.radius_m, c.complex, c.pareto?'Y':'', c.lat, c.lon]
          .map(function(x){ return '"' + String(x).replace(/"/g,'""') + '"'; }).join(',');
      }).join('\n');
      var a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([out], {type:'text/csv'}));
      a.download = '공공법인주도형_' + (INFO.sgg_name||'sgg') + '_개인' + cap + '이하.csv';
      a.click();
    }
    fetch("../../lowindiv_candidates_S3.json").then(function(r){return r.json();}).then(function(d){
      var code = INFO && INFO.sgg_code;
      DATA = d.filter(function(c){ return code && c.url && c.url.indexOf("/" + code + "_") >= 0; });
      render();
    }).catch(function(){
      document.getElementById("li-summary").innerHTML = '<span style="color:#b91c1c">데이터 로드 실패</span>';
    });
    document.getElementById("li-cap-side").addEventListener("change", render);
    document.getElementById("li-show-side").addEventListener("change", render);
    document.getElementById("li-csv-side").addEventListener("click", csv);
  })();
'''

# ── B 산단 영역 wrap ──────────────────────────────────
B_DETAILS_OPEN = '<details id="complex-analysis" style="margin-bottom:12px;">\n<summary style="cursor:pointer;font-weight:600;color:#4b5563;font-size:13px;padding:8px 12px;background:#f3f4f6;border-radius:6px;list-style:none;">▾ 산단별 자급률 분석 (반경 기반, 보조)</summary>\n<div style="padding-top:10px;">\n  ' + B_START
B_DETAILS_CLOSE = '</div>\n</details>\n\n  ' + B_END_BEFORE

# ── C 우측 정책 wrap ──────────────────────────────────
C_DETAILS_OPEN = '<div id="control-panel">\n  <details open style="margin-bottom:0;">\n  <summary style="cursor:pointer;font-weight:600;color:#374151;font-size:14px;padding:6px 0;list-style:none;">▾ 설치 가능 조건 선택 (정책·규제)</summary>\n  <div style="padding-top:8px;">'
C_DETAILS_CLOSE = '  </div>\n  </details>\n</div>\n\n<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'


def patch(path):
    s = open(path, encoding="utf-8").read()
    msgs = []

    # 0) IIFE(D) 제거
    # 시작 마커 인덱스
    i = s.find(D_START_LINE)
    if i < 0:
        return False, "D 시작 마커 없음"
    # 시작부터 가장 가까운 '\n  })();\n\n})();' 까지 — 정확히 외부 IIFE 종료 직전
    end_marker = D_END_LINE
    j = s.find(end_marker, i)
    if j < 0:
        return False, "D 끝 마커 없음"
    # 제거 범위: i 직전 빈줄까지 포함하여 깔끔히
    # 패턴: loadClusters(...);\n\n  // ═══ ...\n  (function(){ ... })();\n\n})();
    # 보존: loadClusters(...);\n + (외부 IIFE 끝)
    s = s[:i].rstrip("\n") + "\n\n" + s[j + len("  })();\n\n"):]
    msgs.append("D 제거")

    # 1) A 사이드바 신규 패널 — sgg-summary 닫는 </div> 다음에 삽입
    sgg_marker = '시군 전체 잠재량 계산 중&hellip;</div>\n'
    if sgg_marker in s:
        s = s.replace(sgg_marker, sgg_marker + "\n  " + NEW_SIDE_PANEL, 1)
        msgs.append("A 패널 삽입")
    else:
        return False, "A sgg-summary 마커 없음"

    # 2) B 산단 영역 wrap
    if s.count(B_START) != 1 or s.count(B_END_BEFORE) != 1:
        return False, f"B 마커 카운트 이상 (start={s.count(B_START)}, end={s.count(B_END_BEFORE)})"
    s = s.replace(B_START, B_DETAILS_OPEN, 1).replace(B_END_BEFORE, B_DETAILS_CLOSE, 1)
    msgs.append("B 산단 details")

    # 3) C 우측 정책 wrap
    if s.count(C_START) != 1 or s.count(C_END) != 1:
        return False, f"C 마커 카운트 이상 (start={s.count(C_START)}, end={s.count(C_END)})"
    s = s.replace(C_START, C_DETAILS_OPEN, 1).replace(C_END, C_DETAILS_CLOSE, 1)
    msgs.append("C 정책 details")

    # 4) E 사이드바 JS 동작 — 기존 loadClusters() 직후 anchor 사용
    e_anchor = '  loadClusters(lsGet("cl_scen","S3"));'
    if s.count(e_anchor) != 1:
        return False, f"E anchor count {s.count(e_anchor)}"
    s = s.replace(e_anchor, NEW_SIDE_JS.rstrip(), 1)
    msgs.append("E 사이드바 JS")

    open(path, "w", encoding="utf-8").write(s)
    return True, ", ".join(msgs)


if __name__ == "__main__":
    files = sorted(glob.glob("chungnam/*/*_map.html") + glob.glob("gyeonggi/*/*_map.html"))
    if len(sys.argv) > 1:
        only = sys.argv[1]
        files = [f for f in files if only in f]
    for f in files:
        ok, msg = patch(f)
        print(("✓" if ok else "✗"), f, "|", msg)
