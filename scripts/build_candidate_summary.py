#!/usr/bin/env python3
"""build_candidate_summary.py — 전국 index.html 용 시나리오별 특구 후보 요약.

<시군>_candidate_clusters_{scen}.json(경량본, build_candidate_clusters.py 산출물)을
시군×시나리오별로 집계해 단일 경량 파일로 묶는다(cluster_summary.json과 동일한
"1회 fetch+메모리 캐싱" 소비 패턴을 index_template.html이 그대로 씀).

grid_ok_pct 규칙(확정, 2026-07-04): grid_ok_pct = true / (true + false).
null(pool_incomplete, 계통 데이터 일부 없음)은 분모에서 제외하고 grid_ok_null로
별도 집계 — null을 fail로 세면 화성·평택처럼 데이터 공백이 큰 시군이 계통 여유가
실제로 부족한 게 아닌데도 부당하게 나빠 보인다.

출력: candidate_summary.json — {scen: {sgg_code: {n, total_mw, avg_indiv_ratio,
  grid_ok_pct(int|null), grid_ok_denom, grid_ok_null}}}
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENARIOS = ["S0", "S3", "SMAX"]
OUT_PATH = os.path.join(ROOT, "candidate_summary.json")


def sgg_code_of(path):
    folder = os.path.basename(os.path.dirname(path))
    return folder.split("_", 1)[0]


def summarize(clusters):
    n = len(clusters)
    total_mw = sum(c["total_mw"] for c in clusters)
    avg_indiv = sum(c["indiv_ratio"] for c in clusters) / n if n else 0.0
    n_true = sum(1 for c in clusters if c["grid_ok"] is True)
    n_false = sum(1 for c in clusters if c["grid_ok"] is False)
    n_null = sum(1 for c in clusters if c["grid_ok"] is None)
    denom = n_true + n_false
    return {
        "n": n,
        "total_mw": round(total_mw, 1),
        "avg_indiv_ratio": round(avg_indiv, 4),
        "grid_ok_pct": round(n_true / denom * 100) if denom else None,
        "grid_ok_denom": denom,
        "grid_ok_null": n_null,
    }


def main():
    out = {s: {} for s in SCENARIOS}
    for scen in SCENARIOS:
        files = sorted(glob.glob(os.path.join(ROOT, "chungnam", "*", f"*_candidate_clusters_{scen}.json")) +
                        glob.glob(os.path.join(ROOT, "gyeonggi", "*", f"*_candidate_clusters_{scen}.json")))
        for path in files:
            code = sgg_code_of(path)
            with open(path, encoding="utf-8") as f:
                clusters = json.load(f)
            out[scen][code] = summarize(clusters)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(OUT_PATH) / 1024
    print(f"candidate_summary.json 생성: {size_kb:.1f} KB")
    print(f"\n{'sgg_code':10s} {'S0':>18} {'S3':>18} {'SMAX':>18}")
    codes = sorted(set().union(*[out[s].keys() for s in SCENARIOS]))
    for code in codes:
        cells = []
        for s in SCENARIOS:
            a = out[s].get(code)
            cells.append(f"{a['n']}개/{a['total_mw']:.0f}MW" if a else "-")
        print(f"{code:10s} {cells[0]:>18} {cells[1]:>18} {cells[2]:>18}")


if __name__ == "__main__":
    main()
