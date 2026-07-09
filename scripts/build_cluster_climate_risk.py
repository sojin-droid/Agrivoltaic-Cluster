#!/usr/bin/env python3
"""S3 컴팩트 클러스터 40개의 기후 물리 리스크(태풍·하천범람) 평가 →
cluster_climate_risk.json(루트, Supabase 업로드 대상).

⚠️ 실행 환경: 이 저장소의 python이 아니라 **climaterisk 워커 conda env**로 실행할 것 —
   /Users/junsojin/Downloads/climaterisk-main/.climada-env/bin/python scripts/build_cluster_climate_risk.py

방법(기후변화영향평가의 IPCC 리스크 프레임: 리스크 = 위해 × 노출 × 취약성):
  위해(H)   CLIMADA Data API의 한국 태풍(tropical_cyclone)·하천범람(river_flood) 해저드.
            현재기후 + 미래 시나리오(가용한 RCP 중 4.5 우선, 없으면 6.0) 각각.
  노출(E)   클러스터 중심점, 자산가치 = MW × 20억 KRW/MW(agrivoltaic_economics.py CAPEX).
  취약성(V) 태풍 = Emanuel(2011) 피해곡선, 범람 = JRC 아시아 지역 피해곡선(climada_petals).
            ⚠️ 둘 다 일반 자산용 곡선 — 태양광 설비 전용 곡선이 아니므로 절대액보다
            클러스터 간 **상대 비교**용으로 해석할 것(json의 caveat에 명시).
산출: 클러스터별 연간기대손실(EAI, KRW)과 자산가치 대비 %(현재/미래), 시군 집계.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT, "cluster_climate_risk.json")
CAPEX_KRW_PER_MW = 2.0e9  # agrivoltaic_economics.py와 동일 가정

import numpy as np
import pandas as pd
from climada.entity import Exposures
from climada.engine import ImpactCalc
from climada.entity.impact_funcs import ImpactFuncSet
from climada.entity.impact_funcs.trop_cyclone import ImpfTropCyclone
from climada.util.api_client import Client


def load_clusters():
    cs = json.load(open(os.path.join(ROOT, "cluster_summary.json"), encoding="utf-8"))["S3"]
    rows = []
    for code, lst in cs.items():
        for c in lst:
            rows.append({"code": code, "smaa_rank": c["smaa_rank"], "lat": c["lat"],
                         "lon": c["lon"], "mw": c["mw"],
                         "value": c["mw"] * CAPEX_KRW_PER_MW})
    return rows


def make_exposures(rows, haz_type, impf_id):
    gdf = pd.DataFrame({
        "latitude": [r["lat"] for r in rows],
        "longitude": [r["lon"] for r in rows],
        "value": [r["value"] for r in rows],
        f"impf_{haz_type}": impf_id,
    })
    exp = Exposures(gdf)
    exp.set_geometry_points()
    return exp


def pick_dataset(client, data_type, base_props, scenario_keys, prefer):
    """가용 데이터셋 중 현재/미래 시나리오 속성 조합을 골라 (현재, 미래, 라벨) 반환."""
    infos = client.list_dataset_infos(data_type=data_type, properties=base_props)
    variants = {}
    for i in infos:
        p = i.properties
        key = tuple(str(p.get(k)) for k in scenario_keys)
        variants[key] = p
    return infos, variants


def eai_by_cluster(exp, impfset, haz):
    imp = ImpactCalc(exp, impfset, haz).impact(assign_centroids=True)
    return np.asarray(imp.eai_exp)


def main():
    rows = load_clusters()
    print(f"클러스터 {len(rows)}개 로드 (S3, 자산 = MW × {CAPEX_KRW_PER_MW/1e9}십억 KRW)")
    client = Client()
    result = {r_i: {} for r_i in range(len(rows))}
    scen_labels = {}

    # ── 태풍 ────────────────────────────────────────────────
    print("태풍 해저드 조회/다운로드 중 (CLIMADA Data API, 최초 1회는 수백 MB 가능)...")
    tc_props = {"country_iso3alpha": "KOR"}
    infos = client.list_dataset_infos(data_type="tropical_cyclone", properties=tc_props)
    print("  가용 태풍 데이터셋:", [(i.properties.get("climate_scenario"), i.properties.get("ref_year")) for i in infos])
    def get_tc(scenario, ref_year=None):
        props = dict(tc_props, climate_scenario=scenario)
        if ref_year:
            props["ref_year"] = str(ref_year)
        return client.get_hazard("tropical_cyclone", properties=props)

    tc_pres = get_tc("historical")
    tc_fut = None
    for scen, yr in (("rcp45", 2040), ("rcp45", 2060), ("rcp60", 2040), ("rcp85", 2040)):
        try:
            tc_fut = get_tc(scen, yr)
            scen_labels["tc_future"] = f"{scen.upper()} {yr}"
            break
        except Exception:
            continue
    if tc_fut is None:
        print("  ⚠ 미래 태풍 시나리오 미가용 — 현재기후로 대체")
        tc_fut = tc_pres
        scen_labels["tc_future"] = "historical(미래 미가용)"

    impf_tc = ImpfTropCyclone.from_emanuel_usa()
    impf_tc.id = 1
    tc_set = ImpactFuncSet([impf_tc])
    exp_tc = make_exposures(rows, "TC", 1)
    eai_tc_pres = eai_by_cluster(exp_tc, tc_set, tc_pres)
    eai_tc_fut = eai_by_cluster(exp_tc, tc_set, tc_fut)
    print(f"  태풍 EAI 합계: 현재 {eai_tc_pres.sum()/1e8:.2f}억, 미래 {eai_tc_fut.sum()/1e8:.2f}억 KRW/년")

    # ── 하천범람 ─────────────────────────────────────────────
    print("하천범람 해저드 조회/다운로드 중...")
    from climada_petals.entity.impact_funcs.river_flood import flood_imp_func_set
    rf_set = flood_imp_func_set()  # JRC 지역별 곡선(아시아 = id 21, "Flood Asia JRC Residential noPAA")
    ASIA_IMPF_ID = 21
    rf_props = {"country_iso3alpha": "KOR"}
    infos = client.list_dataset_infos(data_type="river_flood", properties=rf_props)
    print("  가용 범람 데이터셋:", [(i.properties.get("climate_scenario"), i.properties.get("year_range")) for i in infos])
    def get_rf(scenario, year_range=None):
        props = dict(rf_props, climate_scenario=scenario)
        if year_range:
            props["year_range"] = year_range
        return client.get_hazard("river_flood", properties=props)

    rf_pres = get_rf("historical")
    rf_fut = None
    # 범람은 rcp45 데이터셋이 없어 태풍(rcp45 2040)과 가장 가까운 rcp60을 우선 선택
    for scen, yr in (("rcp60", "2030_2050"), ("rcp26", "2030_2050"), ("rcp85", "2030_2050")):
        try:
            rf_fut = get_rf(scen, yr)
            scen_labels["rf_future"] = f"{scen.upper()} {yr.replace('_','–')}"
            break
        except Exception:
            continue
    if rf_fut is None:
        print("  ⚠ 미래 범람 시나리오 미가용 — 현재기후로 대체")
        rf_fut = rf_pres
        scen_labels["rf_future"] = "historical(미래 미가용)"

    exp_rf = make_exposures(rows, "RF", ASIA_IMPF_ID)
    eai_rf_pres = eai_by_cluster(exp_rf, rf_set, rf_pres)
    eai_rf_fut = eai_by_cluster(exp_rf, rf_set, rf_fut)
    print(f"  범람 EAI 합계: 현재 {eai_rf_pres.sum()/1e8:.2f}억, 미래 {eai_rf_fut.sum()/1e8:.2f}억 KRW/년")

    # ── 산출물 ───────────────────────────────────────────────
    clusters_out = []
    for i, r in enumerate(rows):
        pres = float(eai_tc_pres[i] + eai_rf_pres[i])
        fut = float(eai_tc_fut[i] + eai_rf_fut[i])
        clusters_out.append({
            "code": r["code"], "smaa_rank": r["smaa_rank"], "lat": r["lat"], "lon": r["lon"],
            "mw": r["mw"], "asset_krw": r["value"],
            "eai_tc_pres": float(eai_tc_pres[i]), "eai_tc_fut": float(eai_tc_fut[i]),
            "eai_rf_pres": float(eai_rf_pres[i]), "eai_rf_fut": float(eai_rf_fut[i]),
            "eai_pres": pres, "eai_fut": fut,
            "eai_fut_pct": round(fut / r["value"] * 100, 4),
        })
    by_code = {}
    for c in clusters_out:
        e = by_code.setdefault(c["code"], {"asset_krw": 0.0, "eai_pres": 0.0, "eai_fut": 0.0, "n": 0})
        e["asset_krw"] += c["asset_krw"]; e["eai_pres"] += c["eai_pres"]
        e["eai_fut"] += c["eai_fut"]; e["n"] += 1
    for code, e in by_code.items():
        e["eai_fut_pct"] = round(e["eai_fut"] / e["asset_krw"] * 100, 4)
        e["eai_pres_pct"] = round(e["eai_pres"] / e["asset_krw"] * 100, 4)
        for k in ("asset_krw", "eai_pres", "eai_fut"):
            e[k] = round(e[k], 0)

    out = {
        "method": "CLIMADA 리스크 = 위해(태풍·하천범람) × 노출(클러스터 중심점, MW×20억 KRW) × 취약성(태풍 Emanuel 2011, 범람 JRC 아시아 곡선)",
        "scenarios": {"present": "historical", **scen_labels},
        "caveat": ("일반 자산용 피해곡선 사용(태양광 설비 전용 아님) — 절대액이 아니라 "
                   "클러스터·시군 간 상대 비교용. 해저드 격자(~수 km)가 클러스터보다 거칠어 "
                   "미세 지형(제방 등) 미반영."),
        "clusters": clusters_out,
        "by_code": by_code,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"완료 -> {OUT_PATH}")
    for code, e in sorted(by_code.items(), key=lambda x: -x[1]["eai_fut_pct"]):
        print(f"  {code}: 미래 EAI {e['eai_fut']/1e8:.2f}억/년 (자산의 {e['eai_fut_pct']:.3f}%) 클러스터 {e['n']}개")


if __name__ == "__main__":
    sys.exit(main())
