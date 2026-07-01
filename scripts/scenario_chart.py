#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""정책시사점_v2 §6 시나리오 적층 막대그래프 → charts/scenario_comparison.png.

x축: Base / Reform1 / Reform2  ·  y축: 잠재 용량(MW)  ·  스택: 후보 4개.

데이터 정합성 주의(2종 MW 정의):
  - 본 차트의 MW = **배치 시나리오**(Bardach 매핑 5.3 / 프롬프트 3-2):
        Base = 시범 배치(대추리 50ha=22.5MW 등), Reform2 = 확장 포함 최대.
        합계 Base 33 / Reform1 680 / Reform2 1,592 MW.
  - 경제성 모듈(agrivoltaic_economics.CANDIDATES)의 MW = **가용 면적** 기준
        (v2 §2 클러스터 면적, Reform2 합계 1,472). IRR 산출에만 사용.
  → MW는 배치 시나리오, IRR은 경제성 모듈에서 가져와 결합한다.

IRR(프로젝트, KREI-정합 케이스: REC 포함·CAPEX 1.65)은 단위경제성이라
후보 규모와 무관(scale-invariant) → 시나리오별 1개 값을 x축에 병기.
"""
import os
import sys
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "charts", "scenario_comparison.png")

# ── 1. 한글 폰트: NanumGothic 우선 탐색, 없으면 시스템 폰트 fallback ──
def pick_korean_font():
    for name in ("NanumGothic", "NanumBarunGothic"):
        try:
            path = font_manager.findfont(name, fallback_to_default=False)
            if path and os.path.exists(path):
                font_manager.fontManager.addfont(path)
                return font_manager.FontProperties(fname=path).get_name(), True
        except Exception:
            pass
    # fallback: 시스템 한글 폰트 파일 직접 등록
    for cand in ("/System/Library/Fonts/AppleSDGothicNeo.ttc",
                 "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
                 "/Library/Fonts/AppleGothic.ttf"):
        if os.path.exists(cand):
            try:
                font_manager.fontManager.addfont(cand)
                nm = font_manager.FontProperties(fname=cand).get_name()
                warnings.warn(f"NanumGothic 미발견 → 시스템 폰트 '{nm}'로 대체")
                return nm, False
            except Exception:
                continue
    warnings.warn("한글 폰트 미발견 — 기본 폰트 사용(한글 깨질 수 있음)")
    return None, False

font_name, is_nanum = pick_korean_font()
if font_name:
    plt.rcParams["font.family"] = font_name
plt.rcParams["axes.unicode_minus"] = False

# ── 2. 배치 시나리오 MW (Bardach 5.3 / 프롬프트 3-2) ──
SCENARIOS = ["Base", "Reform1", "Reform2"]
SCEN_LABEL = {"Base": "Base\n(현행법·시범)",
              "Reform1": "Reform1\n(진흥지역外 20년)",
              "Reform2": "Reform2\n(영농형 특별법)"}
CANDS = [
    ("평택 대추리", "#0072B2", [23, 381, 420]),   # 파랑
    ("당진 송산",   "#E69F00", [0,  200, 654]),   # 주황
    ("당진 대호",   "#009E73", [0,    0, 338]),   # 초록
    ("평택 서탄",   "#CC79A7", [10,  99, 180]),   # 분홍
]  # Wong colorblind-safe 팔레트

# ── 3. IRR(프로젝트, KREI-정합)을 경제성 모듈에서 ──
def load_irr():
    try:
        sys.path.insert(0, HERE)
        import agrivoltaic_economics as econ
        econ.CAPEX_PER_MW = 1.65e9  # KREI-정합 케이스
        rows = econ.compute(with_rec=True)
        by = {r["scenario"]: r["project_irr_pct"] for r in rows if r["id"] == "①"}
        return {sc: by.get(sc) for sc in SCENARIOS}
    except Exception as e:  # 모듈 실패해도 차트는 그림
        warnings.warn(f"경제성 모듈 IRR 로드 실패({e}) — IRR 주석 생략")
        return {sc: None for sc in SCENARIOS}

IRR = load_irr()


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    totals = [sum(c[2][i] for c in CANDS) for i in range(len(SCENARIOS))]

    # 1000px 폭 우선: figsize 8in × dpi 125 = 1000px (300dpi는 3.3in로 과밀)
    fig, ax = plt.subplots(figsize=(8, 5.0))
    x = range(len(SCENARIOS))
    bottoms = [0.0] * len(SCENARIOS)
    for name, color, mws in CANDS:
        ax.bar(x, mws, bottom=bottoms, color=color, width=0.62,
               label=name, edgecolor="white", linewidth=0.6)
        bottoms = [b + m for b, m in zip(bottoms, mws)]

    # 합계 라벨(굵게)
    for i, t in enumerate(totals):
        txt = f"{t/1000:.2f} GW" if t >= 1000 else f"{int(round(t))} MW"
        ax.text(i, t + max(totals) * 0.02, txt, ha="center", va="bottom",
                fontweight="bold", fontsize=12)

    # x축 라벨 + 시나리오 IRR 병기
    ax.set_xticks(list(x))
    labels = []
    for sc in SCENARIOS:
        irr = IRR.get(sc)
        irr_s = f"IRR {irr:.1f}%" if irr is not None else "IRR n/a"
        labels.append(f"{SCEN_LABEL[sc]}\n{irr_s}")
    ax.set_xticklabels(labels, fontsize=10)

    ax.set_ylabel("잠재 용량 (MW)", fontsize=11)
    ax.set_ylim(0, max(totals) * 1.16)
    ax.set_title("영농형 태양광 후보지 — 입법 시나리오별 보급 잠재량",
                 fontsize=14, fontweight="bold", pad=26)
    # 부제
    ax.text(0.5, 1.045,
            "현행법 33MW  vs  영농형 특별법 통과 시 1.6GW — 약 50배 차이",
            transform=ax.transAxes, ha="center", va="bottom",
            fontsize=10.5, color="#444444")

    ax.legend(title="후보 클러스터", loc="upper left", fontsize=9,
              title_fontsize=9, frameon=True, framealpha=0.9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", linestyle=":", alpha=0.4)

    # 가정 박스(좌측 중단 — 막대와 겹치지 않는 위치)
    ax.text(0.018, 0.66,
            "가정\nSMP 118.5 원/kWh\nCAPEX 1.65 십억/MW\n할인율 6% · REC 포함",
            transform=ax.transAxes, ha="left", va="top", fontsize=8,
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#F4F4F4",
                      edgecolor="#BBBBBB", linewidth=0.6))
    # 데이터 주석
    fig.text(0.012, 0.012,
             "MW=배치 시나리오(Bardach 5.3) · IRR=프로젝트 기준(KREI-정합) · "
             "IRR은 단위경제성이라 후보 공통",
             fontsize=6.8, color="#888888")

    fig.tight_layout(rect=[0, 0.03, 1, 1])
    fig.savefig(OUT, dpi=125)  # 8in × 125dpi = 1000px 폭
    plt.close(fig)
    return totals


if __name__ == "__main__":
    totals = main()
    print(f"저장: {OUT}")
    print(f"합계 MW — Base {totals[0]:.0f} / Reform1 {totals[1]:.0f} / Reform2 {totals[2]:.0f}")
    ok = abs(totals[2] - 1592) <= 5
    print(f"[검증] Reform2 합계 = {totals[2]:.0f} MW → {'PASS (~1,592)' if ok else 'CHECK'}")
    print(f"[폰트] {'NanumGothic' if (font_name and 'Nanum' in font_name) else font_name} "
          f"({'정상' if font_name else '미발견'})")
