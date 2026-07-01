#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""영농형 태양광 후보 클러스터 경제성(IRR/NPV/회수기간) 추정.

후보 4개 × 시나리오 3개(Base 8년 / Reform1 20년 / Reform2 23년).
가정 출처는 정책시사점_v2 §6. 자기자본(equity) IRR과 프로젝트(unlevered) IRR을 함께 산출.

수익 케이스 2종:
  - PPA-only : 매출 = PPA(=SMP×1.15) 만. 작업 B의 문자 그대로의 입력.
  - PPA+REC  : 매출 = PPA + REC(가중치 1.0 @ 71,500원/REC). RPS/REC 포함 — KREI P293 비교용.

검증 기준(KREI P293 [K1]): 후보 ①(평택 대추리) Base IRR이 4~6% 범위여야
"현행 8년 경제성 부족" 결론과 정합. KREI는 REC 포함(RPS) 기준이므로 PPA+REC 케이스로 검증.

모델링 주의: 차입은 사업기간(life)에 맞춰 상환(loan_term = min(20, life)) — 20년 만기
잔여부채를 8년차에 일시상환하는 가정은 8년 시나리오를 비현실적으로 악화시키므로 배제.

표준 라이브러리만 사용(numpy 미의존) — IRR은 이분법으로 해를 구함.
"""
import json

# ── 시장·비용 가정 (정책시사점_v2 §6) ──
SMP = 118.54              # 원/kWh
PPA = SMP * 1.15          # PPA 단가 = SMP × 1.15
REC_PRICE = 71500.0       # 원/REC (1 REC = 1 MWh)
REC_WEIGHT = 1.0          # 영농형 태양광 REC 가중치(보수적 1.0; 신설 논의 [N1])
CAPEX_PER_MW = 2.0e9      # 설치비 2.0 십억원/MW
OPEX_RATE = 0.05          # 운영비 = 매출의 5%
EQUITY = 0.30             # 자기자본 비중
DEBT = 0.70               # 차입 비중
RATE = 0.04               # 차입 금리
LOAN_TERM = 20            # 차입 만기(년) — 단, 사업기간보다 길면 사업기간으로 단축
DISCOUNT = 0.06           # NPV 할인율
CAP_FACTOR = 0.15         # 설비이용률(연 1,314h)
DEGRADATION = 0.005       # 연 0.5% 출력 저하(통상값)

SCENARIOS = {"Base": 8, "Reform1": 20, "Reform2": 23}

# 후보: 시나리오별 추진 가능 MW (정책시사점_v2 §2)
CANDIDATES = [
    {"id": "①", "name": "평택 대추리(국공유)", "mw": {"Base": 366, "Reform1": 373, "Reform2": 381}},
    {"id": "②", "name": "당진 송산(법인)",     "mw": {"Base": 15,  "Reform1": 652, "Reform2": 654}},
    {"id": "③", "name": "대호간척지(법인)",    "mw": {"Base": 1,   "Reform1": 337, "Reform2": 338}},
    {"id": "④", "name": "평택 서탄(국공유)",   "mw": {"Base": 50,  "Reform1": 90,  "Reform2": 99}},
]


def annual_generation_mwh(mw, year):
    """year년차(1-base) 발전량 MWh — 출력 저하 반영."""
    return mw * CAP_FACTOR * 8760 * ((1 - DEGRADATION) ** (year - 1))


def annuity_payment(principal, rate, n):
    """원리금균등 연상환액."""
    if rate == 0:
        return principal / n
    return principal * rate / (1 - (1 + rate) ** (-n))


def annual_revenue(mw, year, with_rec):
    """year년차 매출(원) = PPA 매출 (+ REC 매출)."""
    gen = annual_generation_mwh(mw, year)
    rev = gen * PPA * 1000.0
    if with_rec:
        rev += gen * REC_WEIGHT * REC_PRICE
    return rev


def project_cashflows(mw, life, with_rec):
    """프로젝트(unlevered) 현금흐름: 0년차 -CAPEX, 1..life 순영업현금(매출-운영비)."""
    flows = [-CAPEX_PER_MW * mw]
    for y in range(1, life + 1):
        rev = annual_revenue(mw, y, with_rec)
        flows.append(rev - rev * OPEX_RATE)
    return flows


def equity_cashflows(mw, life, with_rec):
    """자기자본 관점 현금흐름. 차입은 사업기간(min(LOAN_TERM, life))에 맞춰 원리금균등 상환.

    - 매출 = 발전량 × (PPA [+REC])
    - 운영비 = 매출 × 5%
    - 부채상환 = 원리금균등(만기 = min(LOAN_TERM, life)) → 사업 종료 시 부채 완납, 일시상환 없음
    """
    capex = CAPEX_PER_MW * mw
    debt0 = capex * DEBT
    equity0 = capex * EQUITY
    term = min(LOAN_TERM, life)
    pay = annuity_payment(debt0, RATE, term)
    balance = debt0
    flows = [-equity0]
    for y in range(1, life + 1):
        rev = annual_revenue(mw, y, with_rec)
        opex = rev * OPEX_RATE
        if y <= term and balance > 1:
            interest = balance * RATE
            principal_paid = min(pay - interest, balance)
            balance -= principal_paid
            debt_service = interest + principal_paid
        else:
            debt_service = 0.0
        flows.append(rev - opex - debt_service)
    return flows


def npv(flows, rate):
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(flows))


def irr(flows, lo=-0.95, hi=1.0, tol=1e-7):
    """이분법 IRR. 부호변화 없으면 None."""
    f_lo, f_hi = npv(flows, lo), npv(flows, hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = npv(flows, mid)
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def payback_year(flows):
    """할인 회수기간(년). 누적 NPV가 0을 넘는 연도. 미회수면 None."""
    cum = 0.0
    for t, cf in enumerate(flows):
        cum += cf / (1 + DISCOUNT) ** t
        if t > 0 and cum >= 0:
            return t
    return None


def compute(with_rec):
    rows = []
    for c in CANDIDATES:
        for sc, life in SCENARIOS.items():
            mw = c["mw"][sc]
            eq = equity_cashflows(mw, life, with_rec)
            pr = project_cashflows(mw, life, with_rec)
            er, prr = irr(eq), irr(pr)
            rows.append({
                "id": c["id"], "name": c["name"], "scenario": sc,
                "life": life, "mw": mw,
                "equity_irr_pct": None if er is None else round(er * 100, 1),
                "project_irr_pct": None if prr is None else round(prr * 100, 1),
                "npv_bil": round(npv(eq, DISCOUNT) / 1e9, 1),   # 자기자본 NPV(십억원)
                "payback": payback_year(eq),
            })
    return rows


def fmt_table(rows):
    out = ["| 후보 | 시나리오 | 기간(년) | 용량(MW) | 자기자본 IRR | 프로젝트 IRR | 자기자본 NPV(십억원) | 할인회수(년) |",
           "|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        e = "—" if r["equity_irr_pct"] is None else f"{r['equity_irr_pct']:.1f}%"
        p = "—" if r["project_irr_pct"] is None else f"{r['project_irr_pct']:.1f}%"
        pb = "미회수" if r["payback"] is None else f"{r['payback']}"
        out.append(f"| {r['id']} {r['name']} | {r['scenario']} | {r['life']} | "
                   f"{r['mw']:,} | {e} | {p} | {r['npv_bil']:,.1f} | {pb} |")
    return "\n".join(out)


def gross_payback_years(with_rec):
    """무차입·할인 미적용 단순 총회수기간(연) — 1MW 기준."""
    rev = annual_revenue(1, 1, with_rec) * (1 - OPEX_RATE)
    return CAPEX_PER_MW / rev


def solve_capex_for_target(mw, life, with_rec, target_irr=0.05):
    """주어진 사업조건에서 프로젝트 IRR이 target이 되는 CAPEX(원/MW)를 역산.

    프로젝트 IRR은 CAPEX에 단조감소 → 이분법. KREI P293 [K1] 정합성 점검용
    ("설치비가 수익성 지배 변수"인지 확인)."""
    global CAPEX_PER_MW
    saved = CAPEX_PER_MW
    lo, hi = 0.5e9, 4.0e9
    for _ in range(80):
        mid = (lo + hi) / 2
        CAPEX_PER_MW = mid
        r = irr(project_cashflows(mw, life, with_rec))
        if r is None:
            hi = mid
            continue
        if r > target_irr:
            lo = mid  # capex 더 키워도 됨
        else:
            hi = mid
    CAPEX_PER_MW = saved
    return (lo + hi) / 2


if __name__ == "__main__":
    for with_rec, label in [(False, "PPA-only (작업 B 문자 그대로)"),
                            (True, "PPA+REC (RPS 포함 — KREI P293 비교 기준)")]:
        rows = compute(with_rec)
        print(f"### 수익 케이스: {label}")
        print(fmt_table(rows))
        b1 = next(r for r in rows if r["id"] == "①" and r["scenario"] == "Base")
        gp = gross_payback_years(with_rec)
        print(f"  · 후보① 대추리 Base — 자기자본 IRR {b1['equity_irr_pct']}% / 프로젝트 IRR {b1['project_irr_pct']}% "
              f"(단순 총회수 {gp:.1f}년 vs 사업 8년)")
        print()

    # ── 검증: KREI 비교는 REC 포함 기준 ──
    rows_rec = compute(True)
    b = next(r for r in rows_rec if r["id"] == "①" and r["scenario"] == "Base")
    v = b["project_irr_pct"]
    status = "PASS (4~6%)" if (v is not None and 4.0 <= v <= 6.0) else "OUT OF RANGE"
    print(f"[검증] 후보① 대추리 Base 프로젝트 IRR(REC 포함, CAPEX 2.0) = {v}% → {status}")
    cx5 = solve_capex_for_target(381, 8, True, 0.05)
    print(f"[역산] Base 프로젝트 IRR=5% 달성 CAPEX = {cx5/1e9:.2f} 십억원/MW "
          f"(현행 2.0 대비 {(1-cx5/2e9)*100:.0f}% 절감 필요 — KREI P293 '설치비 지배변수' 정합)")

    # ── KREI-정합 케이스: CAPEX 1.65 + REC ──
    CAPEX_PER_MW = 1.65e9
    print()
    print("### 수익 케이스: KREI-정합 (PPA+REC, CAPEX 1.65 십억/MW)")
    print(fmt_table(compute(True)))
    print(f"[가정] SMP={SMP} PPA={PPA:.1f}원/kWh, REC={REC_PRICE:,.0f}원×가중치{REC_WEIGHT}, "
          f"CAPEX={CAPEX_PER_MW/1e9:.1f}십억/MW, OPEX={OPEX_RATE:.0%}, "
          f"부채{DEBT:.0%}@{RATE:.0%}/min({LOAN_TERM},life)년, 할인율{DISCOUNT:.0%}, "
          f"이용률{CAP_FACTOR:.0%}, 저하{DEGRADATION:.1%}/년")
    print(json.dumps(rows_rec, ensure_ascii=False))
