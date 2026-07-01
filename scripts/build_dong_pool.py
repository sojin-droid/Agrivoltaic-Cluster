"""
동-여유풀 파이프라인 5단계(최종): dl_dong_index -> dong_pool.

안분(apportion): 기본은 균등분할(equal_split) —
  dl_share_per_dong = dl.vol3 / (그 dl_id가 걸치는 동 개수)
다른 가중치(필지수/면적)로 바꿀 수 있게 APPORTION_METHOD 를 함수 레지스트리로
분리해둔다. equal_split 외 가중치를 쓰려면 apportion_weighted()에 동별 가중치
딕셔너리를 넘기면 된다(현재는 미사용, config 자리만 마련).

동-풀 합산 후 상위 계층(vol2=변압기, vol1=변전소) 캡을 적용한다. 캡은 "이 동이
그 변압기/변전소를 통해 받는 몫이 변압기/변전소 전체 여유용량을 넘을 수 없다"는
동(dong) 단위 로컬 min() 클램프다 — 같은 변압기/변전소를 공유하는 여러 동에
vol1/vol2를 다시 나눠 배분하는 로직은 아니다(스펙에 명시되지 않은 확장이라
안 함). 즉 같은 상위 설비를 공유하는 동들의 캡이 서로 독립적으로 같은
상한을 참조할 수 있어, 동별 합계를 전부 더하면 실제 계통 여유보다 과대평가될
수 있다는 한계가 있음 — capped_by_upper_hierarchy 플래그로 어느 동이 캡에
걸렸는지는 남기지만, 동간 재분배는 하지 않는다.

출력: dong_pool.csv / dong_pool.json
  dong_code, dong_name, sigungu_code, sigungu_name,
  pool_capacity_kw, raw_capacity_kw, contributing_dl_ids, capped_by_upper_hierarchy,
  apportion_method
"""
import argparse
import csv
import json
from collections import defaultdict

INDEX_PATH = "dl_dong_index.csv"
OUT_CSV = "dong_pool.csv"
OUT_JSON = "dong_pool.json"


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def equal_split(dl_rows_for_dl_id):
    """dl_id 하나가 걸치는 동 개수로 vol3를 균등분할."""
    n = len(dl_rows_for_dl_id)
    return {r["dong_code"]: r["vol3"] / n for r in dl_rows_for_dl_id if r["vol3"] is not None}


APPORTION_METHODS = {
    "equal_split": equal_split,
    # 추후: "parcel_weighted": apportion_by_parcel_count, "area_weighted": ...
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sigungu", help="특정 시군구코드만 (샘플 검증용)")
    ap.add_argument("--method", default="equal_split", choices=list(APPORTION_METHODS))
    args = ap.parse_args()

    with open(INDEX_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["vol1"], r["vol2"], r["vol3"] = num(r["vol1"]), num(r["vol2"]), num(r["vol3"])

    if args.sigungu:
        rows = [r for r in rows if r["sigungu_code"] == args.sigungu]

    by_dl = defaultdict(list)
    for r in rows:
        by_dl[r["dl_id"]].append(r)

    apportion_fn = APPORTION_METHODS[args.method]

    # dong_code -> [(dl_id, share, mtr_key, subst_key, vol2, vol1)]
    dong_contribs = defaultdict(list)
    dong_names = {}
    for dl_id, dl_rows in by_dl.items():
        shares = apportion_fn(dl_rows)
        for r in dl_rows:
            dong_code = r["dong_code"]
            dong_names[dong_code] = (r["dong_name"], r["sigungu_code"], r["sigungu_name"])
            share = shares.get(dong_code)
            if share is None:
                continue
            mtr_key = f"{r['substCd']}:{r['mtrNo']}"
            subst_key = r["substCd"]
            dong_contribs[dong_code].append({
                "dl_id": dl_id, "share": share,
                "mtr_key": mtr_key, "vol2": r["vol2"],
                "subst_key": subst_key, "vol1": r["vol1"],
            })

    results = []
    for dong_code, contribs in dong_contribs.items():
        dong_name, sgg_code, sgg_name = dong_names[dong_code]
        raw_total = sum(c["share"] for c in contribs)

        # subst(변전소) -> mtr(변압기) 2단 그룹핑 후 안쪽(vol2)부터 바깥쪽(vol1) 순으로 캡
        capped = False
        by_subst = defaultdict(list)
        for c in contribs:
            by_subst[c["subst_key"]].append(c)

        final_total = 0.0
        for subst_key, subst_contribs in by_subst.items():
            by_mtr = defaultdict(list)
            for c in subst_contribs:
                by_mtr[c["mtr_key"]].append(c)

            subst_after_mtr_cap = 0.0
            for mtr_key, g in by_mtr.items():
                mtr_sum = sum(c["share"] for c in g)
                vol2 = g[0]["vol2"]
                if vol2 is not None and mtr_sum > vol2:
                    capped = True
                    subst_after_mtr_cap += vol2
                else:
                    subst_after_mtr_cap += mtr_sum

            vol1 = subst_contribs[0]["vol1"]
            if vol1 is not None and subst_after_mtr_cap > vol1:
                capped = True
                final_total += vol1
            else:
                final_total += subst_after_mtr_cap

        results.append({
            "dong_code": dong_code,
            "dong_name": dong_name,
            "sigungu_code": sgg_code,
            "sigungu_name": sgg_name,
            "raw_capacity_kw": round(raw_total, 1),
            "pool_capacity_kw": round(final_total, 1),
            "capped_by_upper_hierarchy": capped,
            "contributing_dl_ids": sorted({c["dl_id"] for c in contribs}),
            "apportion_method": args.method,
        })

    results.sort(key=lambda r: r["dong_code"])

    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "dong_code", "dong_name", "sigungu_code", "sigungu_name",
            "raw_capacity_kw", "pool_capacity_kw", "capped_by_upper_hierarchy",
            "contributing_dl_ids", "apportion_method",
        ])
        for r in results:
            row = dict(r)
            row["contributing_dl_ids"] = ",".join(r["contributing_dl_ids"])
            writer.writerow(row)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    capped_n = sum(1 for r in results if r["capped_by_upper_hierarchy"])
    print(f"동 {len(results)}개, 캡 적용 {capped_n}개")
    print(f"-> {OUT_CSV}, {OUT_JSON}")
    for r in results[:5]:
        print(f"  {r['dong_name']}({r['dong_code']}): raw={r['raw_capacity_kw']} -> pool={r['pool_capacity_kw']} capped={r['capped_by_upper_hierarchy']}")


if __name__ == "__main__":
    main()
