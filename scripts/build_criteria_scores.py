#!/usr/bin/env python3
"""14개 시군의 "영농형 특구 필요도" 점수화 → criteria_scores.json(루트, 커밋 대상).

5개 지표(균등 가중치 초안, 필요시 아래 WEIGHTS만 조정):
  growth_pct   산단 생산실적 증감률(전분기대비, %) — 한국산업단지공단 국가산단 CSV.
               국가산단이 없거나(대다수 일반/농공단지 시군) 값이 빈 문자열인 시군은
               "데이터없음" — 나머지 4개 지표로 25%씩 재정규화(0점 처리 아님, 확정 사항).
  demand_cnt   RE100 대형 수요처 존재(<시군>_complexes.json의 demand:true 개수).
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

SCENARIO_BASIS = "S3"  # candidate_summary.json 중 어떤 시나리오를 기준으로 쓸지

# 5개 지표 균등 가중치 초안(합계 1.0). growth_pct 데이터 없는 시군은 이 키를 빼고
# 나머지 4개를 25%씩으로 재정규화(RENORM_WITHOUT_GROWTH)한다 — 값을 조정하려면 여기만 고치면 됨.
WEIGHTS = {
    "growth_pct": 0.20,
    "demand_cnt": 0.20,
    "grid_ok_pct": 0.20,
    "total_mw": 0.20,
    "indiv_ratio": 0.20,
}
RENORM_WITHOUT_GROWTH = {
    "demand_cnt": 0.25,
    "grid_ok_pct": 0.25,
    "total_mw": 0.25,
    "indiv_ratio": 0.25,
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
    demand_cnt = {s["code"]: sum(1 for c in s.get("complexes", []) if c.get("demand")) for s in sggs}
    grid_ok = {s["code"]: bysgg.get(s["code"], {}).get("grid_ok_pct") for s in sggs}
    grid_ok = {c: v for c, v in grid_ok.items() if v is not None}
    total_mw = {s["code"]: bysgg.get(s["code"], {}).get("total_mw", 0) for s in sggs}
    indiv_ratio = {s["code"]: bysgg.get(s["code"], {}).get("avg_indiv_ratio", 0) for s in sggs}

    norm = {
        "growth_pct": minmax_norm(growth),
        "demand_cnt": minmax_norm(demand_cnt),
        "grid_ok_pct": minmax_norm(grid_ok),
        "total_mw": minmax_norm(total_mw),
        "indiv_ratio": minmax_norm(indiv_ratio),
    }
    raw = {
        "growth_pct": growth, "demand_cnt": demand_cnt, "grid_ok_pct": grid_ok,
        "total_mw": total_mw, "indiv_ratio": indiv_ratio,
    }

    scored = []
    by_code_out = {}
    for s in sggs:
        code = s["code"]
        has_growth = code in growth
        weights = WEIGHTS if has_growth else RENORM_WITHOUT_GROWTH
        score = 0.0
        indicators = {}
        for key, w in weights.items():
            n = norm[key].get(code)
            v = raw[key].get(code)
            contrib = (n or 0) * w
            score += contrib
            indicators[key] = {"value": v, "norm": n, "weight": w}
        if not has_growth:
            indicators["growth_pct"] = {"value": None, "norm": None, "weight": 0, "note": "국가산단 생산실적 데이터 없음"}
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
        "weights_default": WEIGHTS,
        "weights_without_growth": RENORM_WITHOUT_GROWTH,
        "indicator_labels": {
            "growth_pct": "산단 생산실적 증감률(%)",
            "demand_cnt": "RE100 대형 수요처 수",
            "grid_ok_pct": "계통 여유 비율(%)",
            "total_mw": "특구 후보 합계(MW)",
            "indiv_ratio": "평균 개인소유 비율",
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
