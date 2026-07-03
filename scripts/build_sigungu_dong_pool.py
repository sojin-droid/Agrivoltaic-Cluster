"""
동-여유풀 파이프라인 6단계: 전국 dong_pool.json → 시군별 <시군>_dong_pool.json.

<시군>_points.json(필지 경량 점)에 실제 등장하는 PNU 앞 8자리(읍면동코드)만
추려 dong_pool.json에서 필터링, 시군 상세 뷰어가 로드하는 경량 파일로 저장한다.
build_points.py 산출물처럼 완전히 재생성 가능한 build artifact — gitignore 대상.

출력 포맷(경량, 컬럼형): {"<dong_code>": ["<dong_name>", pool_capacity_kw, capped(0/1)], ...}
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POINTS = sorted(glob.glob(os.path.join(ROOT, "chungnam", "*", "*_points.json")) +
                glob.glob(os.path.join(ROOT, "gyeonggi", "*", "*_points.json")))
DONG_POOL_PATH = os.path.join(ROOT, "dong_pool.json")


def main():
    with open(DONG_POOL_PATH, encoding="utf-8") as f:
        dong_pool = {row["dong_code"]: row for row in json.load(f)}

    for path in POINTS:
        pfx = os.path.basename(path).replace("_points.json", "")
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        codes = {row[0][:8] for row in d["rows"] if row[0]}
        out = {}
        for code in codes:
            row = dong_pool.get(code)
            if row is None:
                continue
            out[code] = [row["dong_name"], row["pool_capacity_kw"], int(row["capped_by_upper_hierarchy"])]

        out_path = os.path.join(os.path.dirname(path), pfx + "_dong_pool.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

        missing = len(codes) - len(out)
        print(f"  {pfx:16s} 동 {len(codes):3d}개 중 {len(out):3d}개 매칭"
              + (f" (미매칭 {missing}개)" if missing else ""))


if __name__ == "__main__":
    main()
