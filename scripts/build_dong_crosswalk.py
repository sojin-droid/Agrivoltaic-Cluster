#!/usr/bin/env python3
"""build_dong_crosswalk.py — 법정동(우리 PNU 8자리) -> SGIS 읍면동(다른 숫자 체계)
크로스워크. 1차 이름 매칭 + 2차 point-in-polygon 폴백.

SGIS와 우리 코드는 자릿수만 같고 숫자가 무관해 직접 조인 불가(CLAUDE.md "읍면동
경계 파이프라인" 참조). 도심 "OO동" 다수가 여러 법정동 → 행정동 하나로 통합돼
있어(2026-07-03 실측: 실패 155개 중 152개가 이 케이스) 이름 매칭만으론 안 되고,
그 법정동의 S3 적격 필지 대표점들을 SGIS 폴리곤에 공간 포함 판정(다수결)해서
배정한다.

같은 폴리곤을 여러 법정동이 공유하게 되는 경우(도심 통합 케이스), 각 법정동의
dong_pool_kw를 그냥 더하면 그 사이에 걸친 DL이 이중계상된다. 대신 폴리곤에 속한
모든 법정동의 dl_dong_index.csv 원본 행을 모아 dl_id 유니크 기준으로 재집계 후
build_dong_pool.py와 동일한 2단(vol2→vol1) 캡 로직을 다시 적용한다(전체 vol3
그대로 — equal_split 아님, 이미 하나의 행정단위로 합쳐지는 것이므로 분할 불필요).

산출:
  crosswalk.csv — beopjeongdong_code, sgis_code, sido, sigungu_name, dong_name,
    match_type(name|pip|none), confidence, pip_hit_pct, note
  <시군>_dong_boundary.json — {"polygons": {sgis_code: {sgis_name, geometry(4326),
    pool_kw|null, member_dongs:[...], no_pool_data}}, "dong_to_polygon":
    {beopjeongdong_code: sgis_code}}  (미매칭 동은 dong_to_polygon에 키 자체가 없음
    — 뷰어는 조회 실패를 "데이터 없음" 해칭으로 처리, CLAUDE.md 방침)
"""
import csv
import glob
import json
import os
import sys
from collections import defaultdict

from shapely.geometry import shape, Point
from shapely.prepared import prep

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_candidate_clusters as bcc  # eligible_parcels() 재사용

DONG_LIST_PATH = os.path.join(ROOT, "scripts", "dong_list.csv")
BOUNDARY_PATH = os.path.join(ROOT, "boundary_dong_4326.json")
DL_INDEX_PATH = os.path.join(ROOT, "dl_dong_index.csv")
UNRESOLVED_PATH = os.path.join(ROOT, "cache", "dong_list_unresolved.json")
CROSSWALK_PATH = os.path.join(ROOT, "crosswalk.csv")

SIDO_PREFIX = {"41": "경기", "44": "충남"}


def parse_sgis_name(sgis_name):
    tokens = sgis_name.split()
    return tokens[0], " ".join(tokens[1:-1]), tokens[-1]


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_all_points():
    """전 시군 points.json 1회 로드(재사용) -> [(city_pfx, points_dict), ...]."""
    out = []
    for path in sorted(glob.glob(os.path.join(ROOT, "chungnam", "*", "*_points.json")) +
                        glob.glob(os.path.join(ROOT, "gyeonggi", "*", "*_points.json"))):
        pfx = os.path.basename(path).replace("_points.json", "")
        with open(path, encoding="utf-8") as f:
            out.append((pfx, os.path.dirname(path), json.load(f)))
    return out


def s3_parcels_by_dong(all_points):
    """dong_code -> [(lat,lon), ...] (S3 적격, 시군 파일 간 중복 동은 이어붙임)."""
    out = defaultdict(list)
    for pfx, folder, d in all_points:
        for p in bcc.eligible_parcels(d, "S3"):
            out[p["dong"]].append((p["lat"], p["lon"]))
    return out


def build_sgis_candidates_by_sigungu(features):
    """our sigungu_name -> [(sgis_code, sgis_name, prepared_geom, geom), ...]."""
    out = defaultdict(list)
    for ft in features:
        _, sigungu, _dong = parse_sgis_name(ft["sgis_name"])
        geom = shape(ft["geometry"])
        out[sigungu].append((ft["sgis_code"], ft["sgis_name"], prep(geom), geom))
    return out


def pip_assign(points, candidates):
    """points: [(lat,lon),...], candidates: [(code,name,prepared,geom),...].
    다수결로 1개 sgis_code 배정 + 분산 비율(dict) 리턴."""
    hits = defaultdict(int)
    for lat, lon in points:
        pt = Point(lon, lat)
        matched = None
        for code, name, pgeom, geom in candidates:
            if pgeom.contains(pt):
                matched = code
                break
        hits[matched if matched else "_no_match"] += 1
    total = len(points)
    if total == 0:
        return None, {}
    winner = max(hits.items(), key=lambda kv: kv[1])
    dist_pct = {k: round(v / total * 100, 1) for k, v in hits.items()}
    winner_code = winner[0] if winner[0] != "_no_match" else None
    return winner_code, dist_pct


def compute_polygon_pool_kw(dong_codes, dl_index_by_dong):
    """폴리곤이 물고 있는 법정동들의 dl_dong_index 원본 행을 dl_id 유니크 기준
    재집계 후 build_dong_pool.py와 동일한 2단(vol2->vol1) 캡 적용. equal_split
    아님 — 이미 하나의 행정단위로 합쳐지는 것이므로 vol3 전체를 그대로 쓴다."""
    seen_dl = {}
    for code in dong_codes:
        for row in dl_index_by_dong.get(code, []):
            if row["dl_id"] not in seen_dl:
                seen_dl[row["dl_id"]] = row

    by_subst = defaultdict(list)
    for row in seen_dl.values():
        by_subst[row["substCd"]].append(row)

    total = 0.0
    for subst_key, rows in by_subst.items():
        by_mtr = defaultdict(list)
        for r in rows:
            by_mtr[(r["substCd"], r["mtrNo"])].append(r)
        subst_total = 0.0
        for mtr_key, mrows in by_mtr.items():
            mtr_sum = sum(num(r["vol3"]) or 0.0 for r in mrows)
            vol2 = num(mrows[0]["vol2"])
            subst_total += min(mtr_sum, vol2) if vol2 is not None else mtr_sum
        vol1 = num(rows[0]["vol1"])
        total += min(subst_total, vol1) if vol1 is not None else subst_total

    return round(total, 1), len(seen_dl)


def main():
    with open(DONG_LIST_PATH, encoding="utf-8") as f:
        dong_rows = list(csv.DictReader(f))

    with open(BOUNDARY_PATH, encoding="utf-8") as f:
        boundary_features = json.load(f)
    sgis_by_name = {}
    for ft in boundary_features:
        _, sigungu, dong = parse_sgis_name(ft["sgis_name"])
        sgis_by_name[(sigungu, dong)] = ft
    sgis_candidates_by_sigungu = build_sgis_candidates_by_sigungu(boundary_features)

    with open(DL_INDEX_PATH, encoding="utf-8") as f:
        dl_rows = list(csv.DictReader(f))
    dl_index_by_dong = defaultdict(list)
    for r in dl_rows:
        dl_index_by_dong[r["dong_code"]].append(r)

    print("전 시군 points.json 로딩(S3 적격 필지 좌표 집계용)...")
    all_points = load_all_points()
    parcels_by_dong = s3_parcels_by_dong(all_points)

    # ── 1차: 이름 매칭 ──
    crosswalk = []
    name_matched, name_failed = [], []
    for row in dong_rows:
        key = (row["sigungu_name"], row["addrLidong"])
        ft = sgis_by_name.get(key)
        if ft is not None:
            crosswalk.append({"beopjeongdong_code": row["code"], "sgis_code": ft["sgis_code"],
                               "sido": ft["sido"], "sigungu_name": row["sigungu_name"],
                               "dong_name": row["addrLidong"], "match_type": "name",
                               "confidence": "high", "pip_hit_pct": "", "note": ""})
            name_matched.append(row)
        else:
            name_failed.append(row)

    # ── 2차: point-in-polygon 폴백 ──
    print(f"이름매칭 실패 {len(name_failed)}개 point-in-polygon 폴백 시도...")
    pip_matched, pip_failed = [], []
    for row in name_failed:
        code = row["code"]
        candidates = sgis_candidates_by_sigungu.get(row["sigungu_name"], [])
        points = parcels_by_dong.get(code, [])
        winner, dist = pip_assign(points, candidates)
        if winner is None:
            crosswalk.append({"beopjeongdong_code": code, "sgis_code": "", "sido": "",
                               "sigungu_name": row["sigungu_name"], "dong_name": row["addrLidong"],
                               "match_type": "none", "confidence": "",
                               "pip_hit_pct": "", "note": f"S3필지 {len(points)}개, 매칭 폴리곤 없음"})
            pip_failed.append((row, len(points)))
        else:
            win_name = next(n for c, n, *_ in candidates if c == winner)
            pct = dist.get(winner, 0.0)
            conf = "high" if pct >= 90 else "medium" if pct >= 70 else "low"
            crosswalk.append({"beopjeongdong_code": code, "sgis_code": winner, "sido": row["code"][:2],
                               "sigungu_name": row["sigungu_name"], "dong_name": row["addrLidong"],
                               "match_type": "pip", "confidence": conf,
                               "pip_hit_pct": pct, "note": f"-> {win_name} | 분산={dist}"})
            pip_matched.append((row, winner, pct, dist))

    # ── A그룹(신설, dong_list.csv에도 없음): pip만 시도, 성공해도 pool 데이터 없음 ──
    a_group_results = []
    if os.path.exists(UNRESOLVED_PATH):
        with open(UNRESOLVED_PATH, encoding="utf-8") as f:
            a_group_codes = json.load(f)["codes"]
        for code in a_group_codes:
            sido_2 = code[:2]
            sido_name = SIDO_PREFIX.get(sido_2, "?")
            # 소속 시군구를 모름(dong_list.csv에 없으므로) -> 그 시도 전체 폴리곤 대상
            candidates = [c for c in
                          [item for sub in sgis_candidates_by_sigungu.values() for item in sub]]
            candidates = [c for c in candidates if c[0].startswith("31" if sido_name == "경기" else "34")]
            points = parcels_by_dong.get(code, [])
            winner, dist = pip_assign(points, candidates)
            if winner is None:
                crosswalk.append({"beopjeongdong_code": code, "sgis_code": "", "sido": sido_name,
                                   "sigungu_name": "(A그룹/신설)", "dong_name": "",
                                   "match_type": "none", "confidence": "",
                                   "pip_hit_pct": "", "note": f"S3필지 {len(points)}개, 매칭 폴리곤 없음"})
            else:
                win_name = next(n for c, n, *_ in candidates if c == winner)
                pct = dist.get(winner, 0.0)
                crosswalk.append({"beopjeongdong_code": code, "sgis_code": winner, "sido": sido_name,
                                   "sigungu_name": "(A그룹/신설)", "dong_name": win_name.split()[-1],
                                   "match_type": "pip", "confidence": "n/a(no_pool_data)",
                                   "pip_hit_pct": pct, "note": f"-> {win_name} | KEPCO 미조회(풀 데이터 없음)"})
            a_group_results.append((code, winner, len(points)))

    with open(CROSSWALK_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["beopjeongdong_code", "sgis_code", "sido", "sigungu_name",
                                           "dong_name", "match_type", "confidence", "pip_hit_pct", "note"])
        w.writeheader()
        w.writerows(crosswalk)

    # ── 리포트 ──
    n_name, n_pip, n_none = (sum(1 for r in crosswalk if r["match_type"] == t)
                              for t in ("name", "pip", "none"))
    total_dongs = len(crosswalk)
    print(f"\n=== 최종 매칭률(동 수 기준) ===")
    print(f"  name={n_name}  pip={n_pip}  none={n_none}  전체={total_dongs} "
          f"(매칭률 {(n_name+n_pip)/total_dongs*100:.1f}%)")

    # 필지 수/pool_kw 기준 매칭률
    matched_codes = {r["beopjeongdong_code"] for r in crosswalk if r["sgis_code"]}
    all_codes = {r["beopjeongdong_code"] for r in crosswalk}
    n_parcels_matched = sum(len(parcels_by_dong.get(c, [])) for c in matched_codes)
    n_parcels_total = sum(len(parcels_by_dong.get(c, [])) for c in all_codes)
    print(f"  필지 수 기준: 매칭 {n_parcels_matched} / 전체 {n_parcels_total} "
          f"({n_parcels_matched/n_parcels_total*100:.1f}%)" if n_parcels_total else "  필지 수 0")

    with open(os.path.join(ROOT, "dong_pool.json"), encoding="utf-8") as f:
        dong_pool_rows = json.load(f)
    dong_pool_kw = {r["dong_code"]: r["pool_capacity_kw"] for r in dong_pool_rows}
    kw_matched = sum(dong_pool_kw.get(c, 0.0) for c in matched_codes)
    kw_total = sum(dong_pool_kw.get(c, 0.0) for c in all_codes)
    print(f"  dong_pool_kw 기준: 매칭 {kw_matched:,.1f} / 전체 {kw_total:,.1f} "
          f"({kw_matched/kw_total*100:.1f}%)" if kw_total else "  pool_kw 0")

    print(f"\n=== 여전히 실패(none) {n_none}개 ===")
    for row, n in pip_failed:
        print(f"  {row['code']} {row['sigungu_name']} {row['addrLidong']}: S3필지 {n}개")
    for code, winner, n in a_group_results:
        if winner is None:
            print(f"  {code} (A그룹): S3필지 {n}개, 매칭 안 됨")

    print(f"\n=== pip 매칭 {len(pip_matched)}건 분산 비율(confidence 낮은 것 위주) ===")
    for row, winner, pct, dist in sorted(pip_matched, key=lambda x: x[2])[:20]:
        print(f"  {row['code']} {row['addrLidong']}: 1위 {pct}% (분산={dist})")

    # ── 폴리곤별 pool_kw 재집계(dl_id 유니크 dedup) ──
    print("\n폴리곤별 pool_kw 재집계 중(dl_id dedup)...")
    sgis_to_dongs = defaultdict(list)
    for r in crosswalk:
        if r["sgis_code"]:
            sgis_to_dongs[r["sgis_code"]].append(r["beopjeongdong_code"])

    polygon_pool = {}
    for sgis_code, codes in sgis_to_dongs.items():
        has_any_dl_data = any(dl_index_by_dong.get(c) for c in codes)
        if has_any_dl_data:
            kw, n_dl = compute_polygon_pool_kw(codes, dl_index_by_dong)
            polygon_pool[sgis_code] = {"pool_kw": kw, "n_unique_dl": n_dl, "no_pool_data": False}
        else:
            polygon_pool[sgis_code] = {"pool_kw": None, "n_unique_dl": 0, "no_pool_data": True}

    shared = {c: ds for c, ds in sgis_to_dongs.items() if len(ds) > 1}
    print(f"여러 법정동이 공유하는 폴리곤: {len(shared)}개 (dedup 재집계 대상)")
    for code, ds in list(shared.items())[:10]:
        print(f"  {code}: 법정동 {len(ds)}개 -> pool_kw={polygon_pool[code]['pool_kw']} "
              f"(unique DL {polygon_pool[code]['n_unique_dl']}개)")

    # ── 시군별 <시군>_dong_boundary.json ──
    geom_by_sgis = {ft["sgis_code"]: ft for ft in boundary_features}
    n_written = 0
    for pfx, folder, d in all_points:
        codes_in_city = {row[0][:8] for row in d["rows"] if row[0]}
        cw_for_city = [r for r in crosswalk if r["beopjeongdong_code"] in codes_in_city and r["sgis_code"]]
        used_sgis = {r["sgis_code"] for r in cw_for_city}
        polygons = {}
        for sgis_code in used_sgis:
            ft = geom_by_sgis[sgis_code]
            pp = polygon_pool[sgis_code]
            polygons[sgis_code] = {
                "sgis_name": ft["sgis_name"], "geometry": ft["geometry"],
                "pool_kw": pp["pool_kw"], "no_pool_data": pp["no_pool_data"],
                "member_dongs": sorted(sgis_to_dongs[sgis_code]),
            }
        dong_to_polygon = {r["beopjeongdong_code"]: r["sgis_code"] for r in cw_for_city}
        out = {"polygons": polygons, "dong_to_polygon": dong_to_polygon}
        out_path = os.path.join(folder, f"{pfx}_dong_boundary.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        n_written += 1
    print(f"\n<시군>_dong_boundary.json {n_written}개 생성 완료")


if __name__ == "__main__":
    main()
