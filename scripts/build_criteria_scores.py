#!/usr/bin/env python3
"""14개 시군의 "영농형 특구 필요도" 점수화 → criteria_scores.json(루트, 커밋 대상).

5개 지표(균등 가중치 초안, 필요시 아래 WEIGHTS만 조정):
  growth_pct   산단 생산실적 증감률(전분기대비, %) — 한국산업단지공단 국가산단 CSV.
               국가산단이 없거나(대다수 일반/농공단지 시군) 값이 빈 문자열인 시군은
               "데이터없음" — 나머지 4개 지표로 25%씩 재정규화(0점 처리 아님, 확정 사항).
  demand_cnt   RE100 대형 수요처 존재(<시군>_complexes.json의 is_demand_only 개수 —
               index.html 매칭선 기능과 동일한 실시간 소스, sggs_data.json 스냅샷 아님).
  grid_ok_pct  계통 여유 비율(candidate_summary.json, S3 기준).
  total_mw     특구 후보 클러스터 합계 MW(candidate_summary.json, S3 기준).
  indiv_ratio  평균 개인소유 비율(candidate_summary.json, S3 기준) — 높을수록 특별법 필요성 큼.

정규화는 min-max(0~1), 지표별로 "값이 있는 시군들 사이에서만" 계산한다(growth_pct는
4개 시군끼리만). 최종 점수 = sum(정규화값 × 가중치). 상위 5개=gold, 다음 5개=silver,
나머지 4개=bronze(14개를 3등분, 나머지는 상위 그룹에 배분).
"""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "metadata", "한국산업단지공단_국가산업단지 산업동향정보_생산실적_20260331.csv")
SGGS_PATH = os.path.join(ROOT, "scripts", "sggs_data.json")
SUMMARY_PATH = os.path.join(ROOT, "candidate_summary.json")
OUT_PATH = os.path.join(ROOT, "criteria_scores.json")


def load_complexes(path):
    """<시군>_complexes.json 스키마 2종 대응(build_viewer.py의 동명 함수와 동일 로직).

    sggs_data.json의 "complexes"(1회 추출해 고정, demand 필드)는 재생성 스크립트가
    없는 스냅샷이라 demand_cnt에 쓰지 않는다 — index.html의 산단-특구 매칭선
    (build_viewer.py의 gather_demand_complexes)과 같은 이 실시간 파일을 읽어야
    두 기능이 같은 시군에 대해 서로 다른 수요처 개수를 보여주는 불일치를 피한다."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        out = []
        for item in data:
            out.extend(item.get("complexes", []))
        return out
    return data.get("complexes", [])


def count_demand_complexes(s):
    rel_path = s["url"]
    folder = os.path.dirname(os.path.join(ROOT, rel_path))
    pfx = os.path.basename(rel_path).replace("_map.html", "")
    complexes_path = os.path.join(folder, f"{pfx}_complexes.json")
    if not os.path.exists(complexes_path):
        return 0
    return sum(1 for c in load_complexes(complexes_path) if c.get("is_demand_only"))

SCENARIO_BASIS = "S3"  # candidate_summary.json 중 어떤 시나리오를 기준으로 쓸지
RISK_PATH = os.path.join(ROOT, "cluster_climate_risk.json")  # build_cluster_climate_risk.py 산출물

# 균등 가중치 초안(합계 1.0). 어떤 지표든 값이 없는 시군은 그 지표를 빼고 나머지를
# 비례 재정규화한다(growth_pct의 기존 확정 규칙을 전 지표로 일반화). 조정은 여기만.
# climate_risk는 CLIMADA 기반 미래(RCP) 연간기대손실률(%) — **낮을수록 좋음(역방향)**,
# 정규화 시 1-minmax로 뒤집는다(INVERTED_KEYS).
WEIGHTS = {
    "growth_pct": 1 / 6,
    "demand_cnt": 1 / 6,
    "grid_ok_pct": 1 / 6,
    "total_mw": 1 / 6,
    "indiv_ratio": 1 / 6,
    "climate_risk": 1 / 6,
}
INVERTED_KEYS = {"climate_risk"}
MISSING_NOTES = {
    "growth_pct": "국가산단 생산실적 데이터 없음",
    "climate_risk": "기후 리스크 미평가(cluster_climate_risk.json 없음)",
}

# 산업단지명(CSV) -> 카드 코드. 국가산단만 존재하는 CSV라 절반 이상의 시군은 매핑이 없음(정상).
COMPLEX_TO_CODE = {
    "석문": "44270", "아산": "44200", "파주탄현": "41480",
    "시화": "41390", "시화MTV": "41390", "반월": "41390",
    "용인첨단시스템반도체": "41463", "송산그린시티": "41590",
}


def load_growth_by_code():
    """국가산단 생산실적 증감률을 카드 코드 단위로 생산액(당분기) 가중평균."""
    weighted = {}
    with open(CSV_PATH, encoding="cp949") as f:
        for row in csv.DictReader(f):
            code = COMPLEX_TO_CODE.get(row["산업단지"])
            if not code:
                continue
            try:
                cur = float(row["당분기(억원)"])
                rate = float(row["증감률(전분기대비)(퍼센트)"])
            except ValueError:
                continue  # 빈 문자열(용인첨단시스템반도체/송산그린시티 — 아직 가동실적 없음)
            e = weighted.setdefault(code, {"num": 0.0, "den": 0.0})
            e["num"] += cur * rate
            e["den"] += cur
    return {code: e["num"] / e["den"] for code, e in weighted.items() if e["den"] > 0}


def minmax_norm(values_by_code):
    vals = list(values_by_code.values())
    if not vals:
        return {}
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return {code: 0.5 for code in values_by_code}
    return {code: (v - lo) / (hi - lo) for code, v in values_by_code.items()}


def main():
    sggs = json.load(open(SGGS_PATH, encoding="utf-8"))
    summary = json.load(open(SUMMARY_PATH, encoding="utf-8"))
    bysgg = summary[SCENARIO_BASIS]

    growth = load_growth_by_code()
    demand_cnt = {s["code"]: count_demand_complexes(s) for s in sggs}
    grid_ok = {s["code"]: bysgg.get(s["code"], {}).get("grid_ok_pct") for s in sggs}
    grid_ok = {c: v for c, v in grid_ok.items() if v is not None}
    total_mw = {s["code"]: bysgg.get(s["code"], {}).get("total_mw", 0) for s in sggs}
    indiv_ratio = {s["code"]: bysgg.get(s["code"], {}).get("avg_indiv_ratio", 0) for s in sggs}

    climate_risk = {}
    if os.path.exists(RISK_PATH):
        risk = json.load(open(RISK_PATH, encoding="utf-8"))
        climate_risk = {c: e["eai_fut_pct"] for c, e in risk["by_code"].items()}
    else:
        print("  [주의] cluster_climate_risk.json 없음 — climate_risk 지표 제외하고 점수화")

    raw = {
        "growth_pct": growth, "demand_cnt": demand_cnt, "grid_ok_pct": grid_ok,
        "total_mw": total_mw, "indiv_ratio": indiv_ratio, "climate_risk": climate_risk,
    }
    norm = {}
    for key, values in raw.items():
        n = minmax_norm(values)
        if key in INVERTED_KEYS:  # 낮을수록 좋은 지표는 뒤집기
            n = {c: 1 - v for c, v in n.items()}
        norm[key] = n

    scored = []
    by_code_out = {}
    for s in sggs:
        code = s["code"]
        # 값이 있는 지표만으로 가중치 비례 재정규화(지표 누락 시군 페널티 없음 — 확정 규칙)
        avail = [k for k in WEIGHTS if code in raw[k]]
        w_sum = sum(WEIGHTS[k] for k in avail)
        score = 0.0
        indicators = {}
        for key in WEIGHTS:
            if key in avail:
                w = WEIGHTS[key] / w_sum
                n = norm[key].get(code)
                indicators[key] = {"value": raw[key][code], "norm": n, "weight": round(w, 4)}
                score += (n or 0) * w
            else:
                indicators[key] = {"value": None, "norm": None, "weight": 0,
                                   "note": MISSING_NOTES.get(key, "데이터 없음")}
        by_code_out[code] = {"score": round(score, 4), "indicators": indicators}
        scored.append((code, score))

    scored.sort(key=lambda x: -x[1])
    n = len(scored)
    gold_cut = -(-n // 3)  # ceil(n/3)
    silver_cut = gold_cut + (-(-n // 3))
    for i, (code, _) in enumerate(scored):
        badge = "gold" if i < gold_cut else ("silver" if i < silver_cut else "bronze")
        by_code_out[code]["badge"] = badge
        by_code_out[code]["rank"] = i + 1

    out = {
        "scenario_basis": SCENARIO_BASIS,
        "weights_default": {k: round(w, 4) for k, w in WEIGHTS.items()},
        "renorm_rule": "값이 없는 지표는 그 시군에서 제외하고 나머지 가중치를 비례 재정규화",
        "indicator_labels": {
            "growth_pct": "산단 생산실적 증감률(%)",
            "demand_cnt": "RE100 대형 수요처 수",
            "grid_ok_pct": "계통 여유 비율(%)",
            "total_mw": "특구 후보 합계(MW)",
            "indiv_ratio": "평균 개인소유 비율",
            "climate_risk": "기후 리스크(연간기대손실률 %·낮을수록 좋음)",
        },
        "by_code": by_code_out,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"완료: {n}개 시군 -> {OUT_PATH}")
    for code, score in scored:
        b = by_code_out[code]["badge"]
        name = next(s["name"] for s in sggs if s["code"] == code)
        print(f"  {b:6s} {name:10s} score={score:.3f}")


if __name__ == "__main__":
    main()
