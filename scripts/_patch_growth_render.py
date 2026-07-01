#!/usr/bin/env python3
"""detail map의 공공·법인 주도형 후보를 '원(버퍼)' → '실제 필지 폴리곤 + 개인상한 슬라이더'로 교체.
- 패널 HTML: select → range 슬라이더(0~50% step5) + 값표시 + 범례
- JS: {pfx}_growth_S3.json 로드, parcels(pnu)에서 geometry 조회, prefix(누적개인%≤상한)만 그림(canvas)
"""
import glob

OLD_PANEL = '''  <div id="li-panel" style="background:#f0fdf4;border:1px solid #86efac;border-radius:6px;padding:12px;margin-bottom:12px;font-size:12px;">
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
</div>'''

NEW_PANEL = '''  <div id="li-panel" style="background:#f0fdf4;border:1px solid #86efac;border-radius:6px;padding:12px;margin-bottom:12px;font-size:12px;">
  <div style="font-weight:600;color:#166534;margin-bottom:6px;font-size:13px;">⭐ 공공·법인 주도형 특구 후보 <span style="font-weight:400;font-size:10px;color:#888">(필지 합산 · 목표 50MW)</span></div>
  <div id="li-summary" style="line-height:1.6;color:#374151;">데이터 로드 중…</div>
  <div style="margin-top:8px;padding-top:8px;border-top:1px solid #bbf7d0;">
    <div style="display:flex;align-items:center;gap:6px;font-size:11px;color:#555;">
      <span style="white-space:nowrap;">개인소유 상한</span>
      <input type="range" id="li-cap-side" min="0" max="50" step="5" value="30" style="flex:1;">
      <b id="li-cap-val" style="color:#166534;min-width:34px;text-align:right;">30%</b>
    </div>
    <div style="display:flex;align-items:center;gap:10px;margin-top:6px;">
      <label style="cursor:pointer;font-size:11px;color:#555;"><input type="checkbox" id="li-show-side" checked style="vertical-align:middle;margin-right:3px"> 지도에 필지 표시</label>
      <button id="li-csv-side" type="button" style="margin-left:auto;font-size:11px;border:1px solid #16a34a;color:#16a34a;background:#fff;border-radius:4px;padding:2px 8px;cursor:pointer;">CSV</button>
    </div>
    <div style="font-size:10px;color:#888;margin-top:5px;line-height:1.5;"><span style="display:inline-block;width:9px;height:9px;background:#15803d;border-radius:2px;vertical-align:middle"></span> 비개인(공공·법인) &nbsp; <span style="display:inline-block;width:9px;height:9px;background:#f59e0b;border-radius:2px;vertical-align:middle"></span> 개인 — 상한을 올리면 개인 필지가 더 합쳐져 클러스터가 커집니다</div>
  </div>
  <div id="li-list" style="margin-top:8px;max-height:240px;overflow:auto;"></div>
</div>'''

OLD_JS = '''  // ═══ 공공·법인 주도형 후보 사이드바 동작 (필터·요약·카드·CSV·지도원) ═══
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
      var out = '\\ufeff' + hdr.join(',') + '\\n' + rows.map(function(c){
        return [c.sgg, c.rank, c.ind_pct, c.unknown_pct, c.n_ind, c.n_parcels, c.mw, c.area_ha, c.radius_m, c.complex, c.pareto?'Y':'', c.lat, c.lon]
          .map(function(x){ return '"' + String(x).replace(/"/g,'""') + '"'; }).join(',');
      }).join('\\n');
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
  })();'''

NEW_JS = r'''  // ═══ 공공·법인 주도형 후보 — 실제 필지 성장 렌더링 (개인상한 슬라이더로 shrink/grow) ═══
  (function(){
    if (typeof map === "undefined" || typeof INFO === "undefined") return;
    if (!document.getElementById("li-panel")) return;
    var pfx = location.pathname.split("/").pop().replace("_map.html","");
    var DATA = null, pnuMap = null, _t = null;
    var DENS = 0.045/1000;                 // MW/m²
    var liRenderer = L.canvas({ padding: 0.4 });
    var liLayer = L.layerGroup();
    function indColor(p){ if (p<=0) return '#15803d'; if (p<=10) return '#4ade80'; if (p<=20) return '#facc15'; if (p<=30) return '#fb923c'; return '#ef4444'; }
    function fmt(n){ return Math.round(n).toLocaleString(); }
    function prefixK(c, cap){ var k=-1; for (var j=0;j<c.cum_ind.length;j++){ if (c.cum_ind[j] <= cap) k=j; } return k; }
    function buildPnu(){ pnuMap={}; (parcels||[]).forEach(function(f){ var pn=f.properties && f.properties.pnu; if (pn) pnuMap[pn]=f; }); }
    function focusCluster(cid){
      var c = DATA.clusters[cid]; if (!c) return;
      if (!pnuMap) buildPnu();
      var bb=null;
      for (var j=0;j<c.pnus.length;j++){ var ft=pnuMap[c.pnus[j]]; if (ft){ var b=L.geoJSON(ft).getBounds(); bb = bb? bb.extend(b) : b; } }
      if (bb) map.fitBounds(bb,{padding:[40,40]}); else map.flyTo([c.lat,c.lon],14);
    }
    function render(){
      var cap = parseFloat(document.getElementById("li-cap-side").value);
      var show = document.getElementById("li-show-side").checked;
      liLayer.clearLayers();
      if (!DATA) return;
      if (!parcels || !parcels.length){ setTimeout(render, 400); return; }   // 필지 로드 대기
      if (!pnuMap) buildPnu();
      var clusters = DATA.clusters || [];
      var reqHa = DATA.req_ha, reqM2 = Math.round(reqHa*10000), tgt = DATA.target_mw;
      var rows = clusters.map(function(c,i){
        var k = prefixK(c, cap);
        return { c:c, i:i, k:k, mw:(k>=0?c.cum_mw[k]:0), n:(k+1) };
      });
      var nReach = rows.filter(function(r){ return r.mw >= tgt*0.99; }).length;
      var s = "이 시군 성장클러스터 <b>"+clusters.length+"곳</b> · 상한 <b>"+cap+"%</b>에서 50MW 달성 <b>"+nReach+"곳</b>";
      s += "<br><span style='font-size:11px;color:#555'>50MW 필요면적 = <b>"+fmt(reqM2)+"㎡ ("+reqHa+"ha)</b> · 영농형 0.045kW/㎡</span>";
      if (clusters.length===0) s += "<br><span style='color:#999'>이 시군은 ≥50MW 성장 후보가 없습니다.</span>";
      document.getElementById("li-summary").innerHTML = s;

      var listEl = document.getElementById("li-list");
      listEl.innerHTML = rows.map(function(r){
        var c=r.c, col=indColor(c.final_ind_pct);
        var curM2 = Math.round(r.mw/DENS);
        var bar = Math.min(100, Math.round(r.mw/tgt*100));
        var reachTxt = r.mw>=tgt*0.99 ? '<span style="color:#15803d;font-weight:600">50MW 달성</span>' : ('현재 <b>'+Math.round(r.mw)+'MW</b>');
        return '<div data-cid="'+r.i+'" class="li-card" style="cursor:pointer;background:#fff;border-left:3px solid '+col+';padding:6px 8px;margin-bottom:4px;font-size:11px;border-radius:3px;">' +
          '<b>#'+(r.i+1)+'</b> '+c.complex+' · 최종 개인 <b style="color:'+col+'">'+c.final_ind_pct+'%</b>' +
          '<br><span style="color:#444">상한 '+cap+'% → '+reachTxt+' · '+r.n+'필지 · '+fmt(curM2)+'㎡</span>' +
          '<div style="height:5px;background:#e5e7eb;border-radius:3px;margin-top:3px;overflow:hidden"><div style="height:100%;width:'+bar+'%;background:'+col+'"></div></div>' +
          '</div>';
      }).join('');
      listEl.querySelectorAll(".li-card").forEach(function(el){
        el.addEventListener("click", function(){ focusCluster(parseInt(this.dataset.cid)); });
      });

      if (show){
        rows.forEach(function(r){
          if (r.k < 0) return;
          var feats=[];
          for (var j=0;j<=r.k;j++){
            var ft = pnuMap[r.c.pnus[j]];
            if (ft) feats.push({ type:"Feature", geometry: ft.geometry, properties:{ ind:r.c.inds[j] } });
          }
          if (!feats.length) return;
          var gj = L.geoJSON({type:"FeatureCollection",features:feats}, {
            renderer: liRenderer,
            style: function(f){ return { stroke:false, fillColor: f.properties.ind ? '#f59e0b' : '#15803d', fillOpacity: 0.62 }; }
          });
          gj.bindTooltip('#'+(r.i+1)+' '+r.c.complex+' · 상한 '+cap+'% · '+Math.round(r.mw)+'MW · '+r.n+'필지', {sticky:true});
          liLayer.addLayer(gj);
        });
        if (!map.hasLayer(liLayer)) map.addLayer(liLayer);
      } else {
        map.removeLayer(liLayer);
      }
    }
    function onCap(){
      document.getElementById("li-cap-val").textContent = document.getElementById("li-cap-side").value + "%";
      clearTimeout(_t); _t = setTimeout(render, 130);     // 슬라이더 드래그 디바운스
    }
    function csv(){
      if (!DATA) return;
      var cap = parseFloat(document.getElementById("li-cap-side").value);
      var hdr = ['시군','클러스터','최종개인pct','최종MW','상한적용MW','상한적용필지수','최근접산단','중심lat','중심lon'];
      var out = '﻿' + hdr.join(',') + '\n' + (DATA.clusters||[]).map(function(c,i){
        var k = prefixK(c, cap);
        return [DATA.sgg, i+1, c.final_ind_pct, c.final_mw, (k>=0?c.cum_mw[k]:0), (k+1), c.complex, c.lat, c.lon]
          .map(function(x){ return '"' + String(x).replace(/"/g,'""') + '"'; }).join(',');
      }).join('\n');
      var a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([out], {type:'text/csv'}));
      a.download = '공공법인주도형_' + (INFO.sgg_name||'sgg') + '_상한' + cap + '.csv';
      a.click();
    }
    fetch(pfx + "_growth_S3.json").then(function(r){ return r.json(); }).then(function(d){ DATA=d; render(); })
      .catch(function(){ document.getElementById("li-summary").innerHTML = '<span style="color:#b91c1c">성장클러스터 데이터 없음</span>'; });
    document.getElementById("li-cap-side").addEventListener("input", onCap);
    document.getElementById("li-show-side").addEventListener("change", render);
    document.getElementById("li-csv-side").addEventListener("click", csv);
  })();'''

JS_START = '  // ═══ 공공·법인 주도형 후보 사이드바 동작 (필터·요약·카드·CSV·지도원) ═══'
JS_END   = '    document.getElementById("li-csv-side").addEventListener("click", csv);\n  })();'

n=0; bad=[]
for f in sorted(glob.glob("chungnam/*/*_map.html")+glob.glob("gyeonggi/*/*_map.html")):
    s=open(f,encoding="utf-8").read()
    if OLD_PANEL not in s: bad.append((f,"panel")); continue
    i=s.find(JS_START)
    if i<0: bad.append((f,"js-start")); continue
    j=s.find(JS_END, i)
    if j<0: bad.append((f,"js-end")); continue
    j_end=j+len(JS_END)
    s=s.replace(OLD_PANEL,NEW_PANEL,1)
    # panel 교체로 인덱스가 바뀌므로 JS는 다시 찾기
    i=s.find(JS_START); j=s.find(JS_END,i); j_end=j+len(JS_END)
    s=s[:i]+NEW_JS+s[j_end:]
    open(f,"w",encoding="utf-8").write(s); n+=1
print(f"{n}개 패치 완료")
for b in bad: print("  ✗", b)
