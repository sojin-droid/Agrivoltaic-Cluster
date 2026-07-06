#!/usr/bin/env python3
"""build_viewer.py — viewer_template.html/index_template.html에서 14개
<시군>_map.html + 전국 index.html을 재생성한다.

기존 _patch_*.py(정확 문자열 치환 + 멱등 가드, scripts/legacy/로 이동됨) 방식을
폐기하고, 매번 템플릿에서 전체를 새로 찍어낸다 — 멱등 가드가 필요 없다(템플릿이
항상 진실이므로). 뷰어를 고칠 땐 scripts/templates/*.html을 고치고 이 스크립트를
재실행할 것 — 생성된 <시군>_map.html/index.html을 직접 손으로 편집하지 말 것.

시군 메타(이름·좌표·산단 URL)는 scripts/sggs_data.json(과거 index.html의 SGGS
배열을 1회 추출해 고정한 것)에서 읽는다. 산단 상세(elec_gwh 등)는 그 트림된
데이터에 없어 각 시군 폴더의 <시군>_complexes.json에서 별도로 읽는다.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(ROOT, "scripts", "templates")
SGGS_DATA_PATH = os.path.join(ROOT, "scripts", "sggs_data.json")


def load_complexes(path):
    """<시군>_complexes.json 스키마 2종 대응(build_candidate_clusters.py와 동일 로직):
    단일 dict({complexes:[...]})와 구 합산 시군(천안 등)의 list([{complexes:[...]}, ...])."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        out = []
        for item in data:
            out.extend(item.get("complexes", []))
        return out
    return data.get("complexes", [])


def build_city_pages(sggs):
    with open(os.path.join(TEMPLATE_DIR, "viewer_template.html"), encoding="utf-8") as f:
        template = f.read()

    n_ok = 0
    for s in sggs:
        rel_path = s["url"]  # 예: chungnam/44270_dangjin/dangjin_map.html
        abs_path = os.path.join(ROOT, rel_path)
        folder = os.path.dirname(abs_path)
        pfx = os.path.basename(rel_path).replace("_map.html", "")

        complexes_path = os.path.join(folder, f"{pfx}_complexes.json")
        complexes = load_complexes(complexes_path) if os.path.exists(complexes_path) else []
        complexes_view = [
            {"name": c.get("name"), "lat": c.get("lat"), "lon": c.get("lon"),
             "elec_gwh": c.get("elec_gwh"), "is_demand_only": bool(c.get("is_demand_only"))}
            for c in complexes
        ]

        out = (template
               .replace("{{PFX}}", pfx)
               .replace("{{SGG_NAME}}", s["name"])
               .replace("{{SGG_CODE}}", s["code"])
               .replace("{{CENTER_LAT}}", str(s["lat"]))
               .replace("{{CENTER_LON}}", str(s["lon"]))
               .replace("{{COMPLEXES_JSON}}", json.dumps(complexes_view, ensure_ascii=False)))

        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(out)
        n_ok += 1
        print(f"  {pfx:16s} -> {rel_path} ({len(complexes_view)}개 산단)")

    return n_ok


def gather_demand_complexes(sggs):
    """②(산단-특구 매칭선)용: 14개 시군 <시군>_complexes.json 전체에서 is_demand_only만
    모아 소속 시군 코드와 함께 반환 — 자기 시군 외 인근 시군과도 매칭선을 그리기 위해
    index 레벨에서 전체를 한 번에 들고 있는다(개별 크기가 작아 무리 없음)."""
    out = []
    for s in sggs:
        rel_path = s["url"]
        folder = os.path.dirname(os.path.join(ROOT, rel_path))
        pfx = os.path.basename(rel_path).replace("_map.html", "")
        complexes_path = os.path.join(folder, f"{pfx}_complexes.json")
        if not os.path.exists(complexes_path):
            continue
        for c in load_complexes(complexes_path):
            if c.get("is_demand_only"):
                out.append({"name": c.get("name"), "lat": c.get("lat"), "lon": c.get("lon"),
                            "elec_gwh": c.get("elec_gwh"), "home_code": s["code"]})
    return out


def build_index(sggs):
    with open(os.path.join(TEMPLATE_DIR, "index_template.html"), encoding="utf-8") as f:
        template = f.read()
    # index 카드+지도엔 complexes 불필요 — 트림해서 용량 절약. lat/lon은 지도 마커용.
    sggs_view = [{"name": s["name"], "sido": s["sido"], "url": s["url"], "code": s["code"],
                  "lat": s["lat"], "lon": s["lon"]} for s in sggs]
    demands = gather_demand_complexes(sggs)
    out = (template
           .replace("{{SGGS_JSON}}", json.dumps(sggs_view, ensure_ascii=False))
           .replace("{{DEMAND_COMPLEXES_JSON}}", json.dumps(demands, ensure_ascii=False)))
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(out)
    print(f"  RE100 대형 수요처 {len(demands)}개(매칭선용)")


def main():
    with open(SGGS_DATA_PATH, encoding="utf-8") as f:
        sggs = json.load(f)

    print(f"시군 상세 {len(sggs)}개 생성 중...")
    n = build_city_pages(sggs)
    print(f"\nindex.html 생성 중...")
    build_index(sggs)
    print(f"\n완료: 시군 상세 {n}개 + index.html 1개")


if __name__ == "__main__":
    main()
