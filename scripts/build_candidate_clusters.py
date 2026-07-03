#!/usr/bin/env python3
"""build_candidate_clusters.py — 특구 후보 클러스터 "메뉴" 생성(예산 사전컷 없음).

이전 build_budget_clusters.py(그리디 예산배분 + 동적 개인비율 게이트)는 폐기.
전 필지 설치를 가정한 사전 예산컷은 잘못된 질문이었다는 판단에 따라, 예산
검증은 클러스터를 다 뽑은 *뒤에* 그 클러스터가 실행 가능한지 보는
post-clustering 참고지표(grid_ok/grid_margin_kw)로만 남긴다.

절차:
  1. 시군별 적격 필지(needs_upper_law==0 & S3 키 중 하나 이상) 전체에 DBSCAN
     1회(eps=200m, minPts=3, 위경도→로컬미터 투영 + 격자 인덱스 이웃탐색).
     t는 여기 관여하지 않음 — 재클러스터링 없음.
  2. 클러스터별 지표: indiv_ratio(면적가중 개인소유 비율, ownership_category=='개인'
     단독 판정 — own_cd/ownership_cd 계열 필드는 데이터에 없음, 2026-07-03 확인),
     total_kw/total_mw, annual_gwh(CLAUDE.md 공식 그대로), 걸친 동 목록,
     grid_ok/grid_margin_kw/usable_mw(=min(total_mw, 걸친 동 pool_kw합/1000)).
     한계: grid_ok/usable_mw는 클러스터 단위 독립 가정 — 여러 후보가 같은 동을
     걸치면 각자 그 동 용량을 온전히 있다고 계산(dong_pool.py의 vol1/vol2 캡과
     동일한 성격의 비-독점 가정). "메뉴 제시"가 목적이라 의도된 한계.
     걸친 동 중 하나라도 그 시군의 dong_pool.json에 없으면(KEPCO 응답 자체가
     없거나 build_dong_list.py가 법정동코드를 못 찾은 경우) grid_ok를 False로
     단정하지 않고 pool_incomplete=true + grid_ok=null 처리. grid_margin_kw/
     usable_mw는 알려진 동만으로 계산한 **하한값**을 그대로 둔다(보수적 방향
     으로만 틀림 — pool_incomplete로 불완전성을 별도 표시). missing_dong_log에
     기록 후 콘솔에 원인 분류까지 출력한다.
  3. 대형 클러스터(total_mw > CAP_MW=50) 용량 제약 영역성장(region growing)으로
     무손실 분할:
       - 멤버 필지로 200m 인접 그래프 구성(다른 시군 셀과 동일한 격자 이웃탐색
         재사용).
       - 시드 = 미배속 필지 중 가장 가까운 산단(<시군>_complexes.json, haversine)
         까지 거리 최소(tie=pnu 오름차순). 매번 전체 스캔하면 대형 클러스터에서
         O(n²)라 (거리,pnu) 기준 1회 정렬 후 포인터 전진으로 상환.
       - 시드에서 BFS(프론티어는 시드와의 거리 오름차순 min-heap, tie=pnu)로
         인접 미배속 필지를 흡수, 다음 필지를 넣으면 CAP(kW) 초과 시 그 필지는
         넣지 않고 덩어리를 그 자리에서 확정(스킵 후 계속 채우기 아님).
       - 배속 안 된 필지는 다음 시드로 새 덩어리 시작, 전부 배속될 때까지 반복.
       - eps 사다리(200→100→50) 방식은 폐기됨: 밀도 균일한 준연속 농지에서
         eps 축소가 자연 경계 분할이 아니라 전역 파편화를 낳았음(조각 75%가
         1MW 이하, 커버리지 손실 25~42%). region growing은 필지를 버리지 않는
         무손실 분할이라 커버리지 손실이 항상 0이어야 한다(콘솔에서 검증).
  4. t∈{10,20,30,40,50}는 클러스터링과 무관한 **사후 표시 필터**
     (indiv_ratio ≤ t/100)일 뿐 — 저장 시점엔 전부 포함(분할된 조각 기준),
     콘솔 요약에서만 사용.

시나리오: S0(현행법)/S3(특별법·법개정)/SMAX(이론최대, needs_* 15개 전부 OR) 3세트를
--scenario로 반복 실행(생략 시 3개 전부). 로직은 동일 — eligible_parcels()에 넘기는
scen만 바뀐다.

산출(전부 gitignore 대상 build artifact, 시나리오별 3세트):
  <시군>_candidate_clusters_{scen}.json — [{cluster_id, hull:[[lon,lat],...], n,
    indiv_ratio, total_kw, total_mw, annual_gwh, dongs:[code,...],
    grid_ok(bool|null), grid_margin_kw, usable_mw, pool_incomplete,
    split_method("none"|"region_grow"), isolated}, ...]  — 뷰어용 경량본,
    members 없음(members가 파일 용량의 94.8% 차지, 2026-07-04 확인).
    (필터 없이 전체 클러스터 — 대형 클러스터는 분할된 조각들로 대체됨)
  <시군>_candidate_members_{scen}.json — {cluster_id: [pnu,...]} — 뷰어 미사용,
    특구 확정 시 필지 명세 조회용.
  <시군>_candidate_dong_summary_{scen}.json — {dong_code: {dong_name, pool_kw,
    demand_kw, n_clusters, capped}}  (demand_kw = 그 동을 걸치는 모든
    클러스터/조각의 total_kw 합 — 위와 동일한 비-독점 가정)
"""
import csv, glob, heapq, json, math, os
from collections import defaultdict, deque

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POINTS_FILES = sorted(glob.glob(os.path.join(ROOT, "chungnam", "*", "*_points.json")) +
                       glob.glob(os.path.join(ROOT, "gyeonggi", "*", "*_points.json")))

THRESHOLDS = [10, 20, 30, 40, 50]
EPS_M = 200.0              # 최초 DBSCAN 클러스터링 eps
GROW_ADJ_M = 200.0         # region growing 인접 그래프 판정 거리(동일 기준)
MIN_PTS = 3
KW_PER_M2 = 0.045          # 설비용량 kW = area_m2 * 0.045 (CLAUDE.md 공식)
CAP_FACTOR = 8760 * 0.15   # annual kWh = kW * CAP_FACTOR (설비이용률 15%)
CAP_MW = 50                # 이 MW 초과 클러스터는 영역성장으로 분할(추후 수요 연동 예정)
CAP_KW = CAP_MW * 1000

NEEDS_ORDER_15 = [
    "needs_S0_clean", "needs_agp_other", "needs_agp_protect", "needs_agp_core",
    "needs_facility", "needs_jongchunji", "needs_military", "needs_eco",
    "needs_park", "needs_mining", "needs_terrain", "needs_landuse",
    "needs_baekdu", "needs_forest", "needs_upper_law",
]
SCEN_KEYS = {
    "S0": ["needs_S0_clean"],
    "S3": ["needs_S0_clean", "needs_agp_other", "needs_agp_protect", "needs_facility", "needs_agp_core"],
    # 이론최대: needs_* 15개 전부 OR(모든 정책 카테고리 조건부 해제). needs_upper_law는
    # 이 OR 집합에 들어있어도 eligible_parcels()의 별도 하드 제외(문화재·생태·공원·군사 등
    # 13종)가 그대로 적용돼 실질적으로는 "그 13종 제외 + 나머지 14개 카테고리 중 하나"와
    # 동일하게 동작한다 — SMAX도 하드 법적 제한지역까지 풀지는 않는다는 의미.
    # 확정: 2026-07-03. 과거 cluster_db(외부 생성기, 유실)의 SMAX와 결과가 달라도 정상 —
    # 그 DB는 재현 대상이 아니다.
    "SMAX": NEEDS_ORDER_15,
}


def eligible_parcels(d, scen):
    """정책 적격(needs_upper_law==0 & scen 키 중 하나 이상)만 뽑는다."""
    order = d["needs_order"]
    key_bits = [order.index(k) for k in SCEN_KEYS[scen]]
    upper_law_bit = order.index("needs_upper_law")
    owncat = d["owncat"]
    ind_idx = owncat.index("개인") if "개인" in owncat else None

    out = []
    for row in d["rows"]:
        pnu, lat, lon, area, slope, owncat_i, cat_i, promo_i, bits = row
        if (bits >> upper_law_bit) & 1:
            continue
        if not any((bits >> b) & 1 for b in key_bits):
            continue
        if not pnu or len(pnu) < 8:
            continue
        out.append({
            "pnu": pnu, "lat": lat, "lon": lon, "area_m2": area,
            "dong": pnu[:8], "is_individual": (owncat_i == ind_idx),
        })
    return out


def project(parcels):
    lat0 = sum(p["lat"] for p in parcels) / len(parcels)
    lon0 = sum(p["lon"] for p in parcels) / len(parcels)
    kx = 111320 * math.cos(math.radians(lat0))
    ky = 111320
    for p in parcels:
        p["_x"] = (p["lon"] - lon0) * kx
        p["_y"] = (p["lat"] - lat0) * ky
    return parcels


def make_neighbor_finder(parcels, eps_m):
    """격자 인덱스 기반 이웃탐색(공용) — dbscan()과 region_grow_partition() 둘 다 재사용."""
    grid = defaultdict(list)
    for i, p in enumerate(parcels):
        grid[(int(p["_x"] // eps_m), int(p["_y"] // eps_m))].append(i)

    def neighbors_of(i):
        p = parcels[i]
        gx, gy = int(p["_x"] // eps_m), int(p["_y"] // eps_m)
        out = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((gx + dx, gy + dy), ()):
                    if j == i:
                        continue
                    ddx = parcels[j]["_x"] - p["_x"]
                    ddy = parcels[j]["_y"] - p["_y"]
                    if ddx * ddx + ddy * ddy <= eps_m * eps_m:
                        out.append(j)
        return out

    return neighbors_of


def dbscan(parcels, eps_m, min_pts):
    """순수 Python DBSCAN. 격자 인덱스로 이웃탐색."""
    n = len(parcels)
    neighbors_of = make_neighbor_finder(parcels, eps_m)

    labels = [None] * n
    cluster_id = 0
    for i in range(n):
        if labels[i] is not None:
            continue
        neighbors = neighbors_of(i)
        if len(neighbors) < min_pts:
            labels[i] = -1
            continue
        cluster_id += 1
        labels[i] = cluster_id
        seeds = deque(neighbors)
        while seeds:
            j = seeds.popleft()
            if labels[j] == -1:
                labels[j] = cluster_id
            if labels[j] is not None:
                continue
            labels[j] = cluster_id
            j_neighbors = neighbors_of(j)
            if len(j_neighbors) >= min_pts:
                seeds.extend(k for k in j_neighbors if labels[k] is None)
    return labels


def convex_hull(points):
    """monotone chain. points: [(lon,lat), ...]"""
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    t = math.pi / 180
    return 2 * R * math.asin(math.sqrt(
        math.sin((lat2 - lat1) * t / 2) ** 2 +
        math.cos(lat1 * t) * math.cos(lat2 * t) * math.sin((lon2 - lon1) * t / 2) ** 2))


def load_complexes(path):
    """<시군>_complexes.json 스키마 2종 대응: 단일 dict({complexes:[...]})와
    구 합산 시군(천안 서북/동남구 등)의 list([{complexes:[...]}, ...])."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        out = []
        for item in data:
            out.extend(item.get("complexes", []))
        return out
    return data.get("complexes", [])


def nearest_complex_dist_m(lat, lon, complexes):
    if not complexes:
        return float("inf")
    return min(haversine_m(lat, lon, c["lat"], c["lon"]) for c in complexes)


def compute_cluster_metrics(members, dong_pool, split_method, city, missing_log):
    """members: project()된 필지 dict 리스트(1개 클러스터/조각). 최초 클러스터링과
    영역성장 분할 양쪽에서 공용으로 쓴다."""
    total_area = sum(m["area_m2"] for m in members)
    total_kw = total_area * KW_PER_M2
    total_mw = total_kw / 1000
    ind_area = sum(m["area_m2"] for m in members if m["is_individual"])
    dongs = sorted({m["dong"] for m in members})

    pool_sum = 0.0
    pool_incomplete = False
    for dcode in dongs:
        row = dong_pool.get(dcode)
        if row is None:
            missing_log[dcode].append({"city": city, "mw": round(total_mw, 1), "n": len(members)})
            pool_incomplete = True
            continue
        pool_sum += row[1]

    hull = convex_hull([(m["lon"], m["lat"]) for m in members])
    return {
        "members": [m["pnu"] for m in members],
        "hull": [[lon, lat] for lon, lat in hull],
        "n": len(members),
        "indiv_ratio": round(ind_area / total_area, 4) if total_area else 0.0,
        "total_kw": round(total_kw, 1),
        "total_mw": round(total_mw, 3),
        "annual_gwh": round(total_kw * CAP_FACTOR / 1e6, 3),
        "dongs": dongs,
        "grid_ok": None if pool_incomplete else (pool_sum >= total_kw),
        "grid_margin_kw": round(pool_sum - total_kw, 1),
        "usable_mw": round(min(total_mw, pool_sum / 1000), 3),
        "pool_incomplete": pool_incomplete,
        "split_method": split_method,
        "isolated": len(members) < MIN_PTS,
    }


def build_clusters(parcels_raw, dong_pool, city, missing_log):
    if not parcels_raw:
        return []
    parcels = project([dict(p) for p in parcels_raw])
    labels = dbscan(parcels, EPS_M, MIN_PTS)

    by_cluster = defaultdict(list)
    for p, lab in zip(parcels, labels):
        if lab == -1:
            continue
        by_cluster[lab].append(p)

    clusters = []
    for members in by_cluster.values():
        metrics = compute_cluster_metrics(members, dong_pool, "none", city, missing_log)
        # 분할 필요 여부 판단 후 pop — PNU가 유일키가 아니라서(같은 PNU가 정책구역
        # 경계로 잘려 면적이 다른 여러 행으로 존재, 2026-07-03 확인) PNU로 재조회하면
        # 면적을 잃는다. 분할 시 이 원본 멤버 dict를 그대로 재사용해 그 문제를 피한다.
        metrics["_raw_members"] = members
        clusters.append(metrics)
    clusters.sort(key=lambda c: -c["total_mw"])
    return clusters


def region_grow_partition(raw_members, dong_pool, city, missing_log, complexes):
    """total_mw > CAP_MW 클러스터를 무손실 영역성장으로 CAP 이하 조각들로 분할.
    raw_members는 build_clusters()가 만든 실제 멤버 dict(이미 _x/_y 투영됨)를
    그대로 받는다 — PNU로 재조회하지 않는다(PNU 비유일 문제 회피)."""
    members = [dict(m) for m in raw_members]
    n = len(members)
    for m in members:
        m["_dist_complex"] = nearest_complex_dist_m(m["lat"], m["lon"], complexes)
    neighbors_of = make_neighbor_finder(members, GROW_ADJ_M)

    # 시드 순서: 산단까지 거리 오름차순, tie=pnu — 1회 정렬 후 포인터 전진(스캔 상환)
    order = sorted(range(n), key=lambda i: (members[i]["_dist_complex"], members[i]["pnu"]))

    assigned = [False] * n
    fragments = []
    ptr = 0
    while ptr < n:
        seed = order[ptr]
        if assigned[seed]:
            ptr += 1
            continue

        blob = [seed]
        assigned[seed] = True
        cum_kw = members[seed]["area_m2"] * KW_PER_M2
        sx, sy = members[seed]["_x"], members[seed]["_y"]
        heap = []

        def push_frontier(i):
            for j in neighbors_of(i):
                if not assigned[j]:
                    dx = members[j]["_x"] - sx
                    dy = members[j]["_y"] - sy
                    heapq.heappush(heap, (dx * dx + dy * dy, members[j]["pnu"], j))

        push_frontier(seed)
        while heap:
            _, _, j = heapq.heappop(heap)
            if assigned[j]:
                continue  # 다른 경로로 이미 프론티어에 중복 등록됐던 항목
            cost = members[j]["area_m2"] * KW_PER_M2
            if cum_kw + cost > CAP_KW:
                break  # 다음 필지를 넣으면 CAP 초과 -> 넣지 않고 덩어리 확정
            assigned[j] = True
            blob.append(j)
            cum_kw += cost
            push_frontier(j)

        frag_members = [members[i] for i in blob]
        fragments.append(compute_cluster_metrics(frag_members, dong_pool, "region_grow", city, missing_log))
        ptr += 1

    return fragments


def dong_summary(clusters, dong_pool):
    demand = defaultdict(float)
    touch_count = defaultdict(int)
    for c in clusters:
        for d in c["dongs"]:
            demand[d] += c["total_kw"]
            touch_count[d] += 1

    out = {}
    for code, row in dong_pool.items():
        name, pool_kw, capped = row
        out[code] = {
            "dong_name": name,
            "pool_kw": pool_kw,
            "demand_kw": round(demand.get(code, 0.0), 1),
            "n_clusters": touch_count.get(code, 0),
            "capped": capped,
        }
    return out


def histogram(values, n_bins=10):
    bins = [0] * n_bins
    for v in values:
        idx = min(int(v * n_bins), n_bins - 1)
        bins[idx] += 1
    return bins


def mw_size_bins(clusters):
    bins = {"<=1MW": 0, "1-10MW": 0, "10-30MW": 0, "30-50MW": 0, ">50MW": 0}
    for c in clusters:
        mw = c["total_mw"]
        if mw <= 1: bins["<=1MW"] += 1
        elif mw <= 10: bins["1-10MW"] += 1
        elif mw <= 30: bins["10-30MW"] += 1
        elif mw <= 50: bins["30-50MW"] += 1
        else: bins[">50MW"] += 1
    return bins


def classify_missing_dong(code, dong_list_codes):
    """누락 동 코드의 원인 분류(리포트 전용, 매 실행마다 최신 캐시 상태로 재분류)."""
    if code not in dong_list_codes:
        return "A_미해석(dong_list.csv에 없음 — beopjeongdong_raw.txt 미해석 추정)"
    raw_path = os.path.join(ROOT, "addr_lidong_raw", f"{code}.json")
    if not os.path.exists(raw_path):
        return "D_dong_list엔 있으나 kepco_client 호출 캐시 없음"
    with open(raw_path, encoding="utf-8") as f:
        rec = json.load(f)
    err = (rec.get("response") or {}).get("errCd")
    if err == "404":
        return "B_KEPCO 404(정상적인 결과없음)"
    return "C_원본 캐시엔 데이터 있으나 dong_pool 단계에서 탈락(dl_dong_index/build_dong_pool 확인 필요)"


def run_scenario(scen):
    print(f"\n{'#'*70}\n# 시나리오 {scen}\n{'#'*70}")
    print(f"대상 {len(POINTS_FILES)}개 시군 (scen={scen}, eps={EPS_M:.0f}m, minPts={MIN_PTS}, "
          f"CAP_MW={CAP_MW}, split=region_grow adj={GROW_ADJ_M:.0f}m)\n")

    all_clusters_by_city = {}
    all_ratios = []
    missing_log = defaultdict(list)   # dong_code -> [{city, mw, n}, ...]
    split_report = []                 # 분할된 원 클러스터 기록(원삼 상세 포함)
    n_clusters_before = n_clusters_after = 0

    for points_path in POINTS_FILES:
        pfx = os.path.basename(points_path).replace("_points.json", "")
        folder = os.path.dirname(points_path)
        dong_pool_path = os.path.join(folder, pfx + "_dong_pool.json")
        complexes_path = os.path.join(folder, pfx + "_complexes.json")
        if not os.path.exists(dong_pool_path):
            print(f"  [스킵] {pfx}: {pfx}_dong_pool.json 없음(build_sigungu_dong_pool.py 먼저 실행 필요)")
            continue
        if not os.path.exists(complexes_path):
            print(f"  [스킵] {pfx}: {pfx}_complexes.json 없음(region growing 시드 계산 불가)")
            continue

        with open(points_path, encoding="utf-8") as f:
            d = json.load(f)
        with open(dong_pool_path, encoding="utf-8") as f:
            dong_pool = json.load(f)
        complexes = load_complexes(complexes_path)

        parcels = eligible_parcels(d, scen)
        clusters = build_clusters(parcels, dong_pool, pfx, missing_log)
        n_clusters_before += len(clusters)

        final_clusters = []
        for c in clusters:
            raw_members = c.pop("_raw_members")
            if c["total_mw"] <= CAP_MW:
                final_clusters.append(c)
                continue
            orig_mw, orig_n, orig_dongs = c["total_mw"], c["n"], c["dongs"]
            frags = region_grow_partition(raw_members, dong_pool, pfx, missing_log, complexes)
            frag_mw = sum(f["total_mw"] for f in frags)
            frag_n = sum(f["n"] for f in frags)
            split_report.append({
                "city": pfx, "orig_mw": orig_mw, "orig_n": orig_n, "orig_dongs": orig_dongs,
                "n_fragments": len(frags), "frag_mw": frag_mw, "frag_n": frag_n,
                "mw_loss_pct": (orig_mw - frag_mw) / orig_mw * 100 if orig_mw else 0.0,
                "n_loss_pct": (orig_n - frag_n) / orig_n * 100 if orig_n else 0.0,
                "fragments": frags,
            })
            final_clusters.extend(frags)

        n_clusters_after += len(final_clusters)
        all_clusters_by_city[pfx] = final_clusters
        all_ratios.extend(c["indiv_ratio"] for c in final_clusters)

        # cluster_id 부여(0부터, 현재 정렬 순서 그대로 — 결정적) 후 members 분리.
        # 뷰어는 경량본(members 없음)만 쓰고, members는 특구 확정 시 필지 명세용
        # 별도 파일로 뺀다(평택 S3 기준 members가 파일 용량의 94.8% 차지, 2026-07-04 확인).
        members_by_id = {}
        light_clusters = []
        for i, c in enumerate(final_clusters):
            c["cluster_id"] = i
            members_by_id[i] = c["members"]
            light_clusters.append({k: v for k, v in c.items() if k != "members"})

        out_clusters_path = os.path.join(folder, f"{pfx}_candidate_clusters_{scen}.json")
        with open(out_clusters_path, "w", encoding="utf-8") as f:
            json.dump(light_clusters, f, ensure_ascii=False, separators=(",", ":"))

        out_members_path = os.path.join(folder, f"{pfx}_candidate_members_{scen}.json")
        with open(out_members_path, "w", encoding="utf-8") as f:
            json.dump(members_by_id, f, ensure_ascii=False, separators=(",", ":"))

        summary = dong_summary(final_clusters, dong_pool)
        out_summary_path = os.path.join(folder, f"{pfx}_candidate_dong_summary_{scen}.json")
        with open(out_summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, separators=(",", ":"))

        n_ok = sum(1 for c in final_clusters if c["grid_ok"])
        total_mw = sum(c["total_mw"] for c in final_clusters)
        print(f"  {pfx:16s} 적격 {len(parcels):7d} -> 클러스터 {len(final_clusters):4d}개 "
              f"({total_mw:8.1f}MW, grid_ok {n_ok}/{len(final_clusters)})")

    # (1) 교체 후 전국 클러스터 수 · 크기분포
    print(f"\n=== (1) 분할 전/후 전국 클러스터 수 ===")
    print(f"  분할 전: {n_clusters_before}개 (CAP={CAP_MW}MW 초과 {len(split_report)}개 포함)")
    print(f"  분할 후: {n_clusters_after}개")
    all_final = [c for cs in all_clusters_by_city.values() for c in cs]
    print("  크기분포(분할 후 전체):", mw_size_bins(all_final))

    # (2) 커버리지 검증 — region growing은 무손실이어야 함(손실 0 확인)
    print(f"\n=== (2) 분할 커버리지 검증({len(split_report)}건, region_grow는 손실 0이 정상) ===")
    print(f"{'시군':14s} {'원본MW':>10} {'분할후MW':>10} {'MW차이':>9} {'원본필지':>8} {'분할후필지':>9} {'필지일치':>7}")
    n_mismatch = 0
    for r in sorted(split_report, key=lambda r: -r["orig_mw"]):
        n_match = "OK" if r["orig_n"] == r["frag_n"] else "MISMATCH"
        if n_match != "OK":
            n_mismatch += 1
        print(f"{r['city']:14s} {r['orig_mw']:>10.1f} {r['frag_mw']:>10.1f} "
              f"{r['orig_mw']-r['frag_mw']:>9.3f} {r['orig_n']:>8} {r['frag_n']:>9} {n_match:>7}")
    print(f"  필지수 불일치: {n_mismatch}건 (0이어야 무손실 확인)")

    # (3) 원삼(용인) 대형 클러스터 분할 결과 상세
    wonsam = next((r for r in split_report if r["city"] == "yongin" and "41461340" in r["orig_dongs"]), None)
    print("\n=== (3) 용인 원삼 대형 클러스터 분할 상세 ===")
    if wonsam is None:
        print("  [경고] 원삼면(41461340)을 포함하는 분할 대상 클러스터를 찾지 못함")
    else:
        print(f"  원본: {wonsam['orig_mw']:.1f}MW, {wonsam['orig_n']}필지, 동 {len(wonsam['orig_dongs'])}개")
        print(f"  분할 후: {wonsam['n_fragments']}개 조각, 합계 {wonsam['frag_mw']:.1f}MW "
              f"(MW차이 {wonsam['orig_mw']-wonsam['frag_mw']:.3f}, 필지 {wonsam['orig_n']}->{wonsam['frag_n']})")
        print("  크기분포:", mw_size_bins(wonsam["fragments"]))
        print(f"  {'MW':>10} {'필지수':>8} {'indiv_ratio':>11} {'usable_mw':>10} {'isolated':>8} {'pool_incomplete':>15}  동")
        for f in sorted(wonsam["fragments"], key=lambda f: -f["total_mw"])[:15]:
            print(f"  {f['total_mw']:>10.1f} {f['n']:>8} {f['indiv_ratio']:>11.3f} {f['usable_mw']:>10.1f} "
                  f"{str(f['isolated']):>8} {str(f['pool_incomplete']):>15}  "
                  f"{f['dongs'][:5]}{'...' if len(f['dongs']) > 5 else ''}")
        print(f"  (최대 15개만 표시, 전체 {wonsam['n_fragments']}개)")

    # (5) 누락 동 코드 원인 분류
    dong_list_codes = set()
    dong_list_path = os.path.join(ROOT, "scripts", "dong_list.csv")
    if os.path.exists(dong_list_path):
        with open(dong_list_path, encoding="utf-8") as f:
            dong_list_codes = {row["code"] for row in csv.DictReader(f)}

    print(f"\n=== (5) 누락 동 코드(dong_pool에 없음) 원인 분류 — {len(missing_log)}개 ===")
    by_cause = defaultdict(list)
    for dcode in sorted(missing_log):
        cause = classify_missing_dong(dcode, dong_list_codes)
        by_cause[cause].append(dcode)
    for cause, codes in sorted(by_cause.items()):
        print(f"\n  [{cause}] {len(codes)}개")
        for dcode in codes:
            entries = missing_log[dcode]
            cities = sorted({e["city"] for e in entries})
            print(f"    {dcode}: {len(entries)}개 조각이 참조, 시군={cities}")

    # (6) 시군별 pool_incomplete 조각 수
    print("\n=== (6) 시군별 pool_incomplete 조각 수 ===")
    print(f"{'시군':16s} {'pool_incomplete':>15} {'전체':>8}")
    for pfx, clusters in all_clusters_by_city.items():
        n_inc = sum(1 for c in clusters if c["pool_incomplete"])
        print(f"{pfx:16s} {n_inc:>15} {len(clusters):>8}")

    # (4) 분할 후 t별 요약
    print("\n=== (4) t별(사후 표시 필터, 분할 후 기준) 시군별 잔존 클러스터 ===")
    for t in THRESHOLDS:
        print(f"\n-- t={t}% (indiv_ratio <= {t/100:.2f}) --")
        print(f"{'시군':16s} {'클러스터수':>8} {'합계MW':>10} {'grid_ok비율':>12}")
        tot_n = tot_mw = tot_ok = tot_null = 0
        for pfx, clusters in all_clusters_by_city.items():
            kept = [c for c in clusters if c["indiv_ratio"] <= t / 100]
            n_ok = sum(1 for c in kept if c["grid_ok"] is True)
            n_null = sum(1 for c in kept if c["grid_ok"] is None)
            mw = sum(c["total_mw"] for c in kept)
            tot_n += len(kept); tot_mw += mw; tot_ok += n_ok; tot_null += n_null
            ok_pct = f"{n_ok}/{len(kept)}(null{n_null})" if kept else "0/0"
            print(f"{pfx:16s} {len(kept):>8} {mw:>10.1f} {ok_pct:>12}")
        ok_pct_total = f"{tot_ok}/{tot_n}(null{tot_null})" if tot_n else "0/0"
        print(f"{'전국합계':16s} {tot_n:>8} {tot_mw:>10.1f} {ok_pct_total:>12}")

    print("\n=== indiv_ratio 분포(전국, 10%p 구간, t 무관, 분할 후 기준) ===")
    bins = histogram(all_ratios, 10)
    for i, c in enumerate(bins):
        lo, hi = i * 10, (i + 1) * 10
        bar = "#" * min(c, 80)
        print(f"  {lo:3d}-{hi:3d}%: {c:5d} {bar}")

    n_ok_total = sum(1 for c in all_final if c["grid_ok"] is True)
    return {
        "scenario": scen,
        "n_candidates": len(all_final),
        "total_mw": round(sum(c["total_mw"] for c in all_final), 1),
        "grid_ok": n_ok_total,
        "grid_ok_pct": round(n_ok_total / len(all_final) * 100, 1) if all_final else 0.0,
    }


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=sorted(SCEN_KEYS), action="append",
                     help="반복 가능(예: --scenario S0 --scenario S3). 생략 시 S0/S3/SMAX 전부 실행")
    args = ap.parse_args()
    scenarios = args.scenario or ["S0", "S3", "SMAX"]

    results = [run_scenario(scen) for scen in scenarios]

    print(f"\n{'#'*70}\n# 시나리오별 비교\n{'#'*70}")
    print(f"{'시나리오':10s} {'후보 수':>8} {'합계MW':>12} {'grid_ok':>10} {'grid_ok%':>9}")
    for r in results:
        print(f"{r['scenario']:10s} {r['n_candidates']:>8} {r['total_mw']:>12.1f} "
              f"{r['grid_ok']:>10} {r['grid_ok_pct']:>8.1f}%")


if __name__ == "__main__":
    main()
