#!/usr/bin/env python3
"""fetch_dong_boundaries.py — SGIS(행정안전부 국가데이터처) 행정구역경계 API로
경기·충남 읍면동 경계를 받아 EPSG:4326으로 변환한다.

⚠️ 코드 체계(2026-07-03 실측 확정): SGIS는 우리 PNU/법정동 8자리와 **다른**
통계청 옛 시도코드를 쓴다 — 경기=31, 충남=34(41/44 아님, 서울=11만 두 체계가
우연히 같음). 시군구 5자리, 읍면동 8자리지만 숫자 자체가 법정동 코드와 다르므로
직접 조인 불가 — 이름 기반 크로스워크가 필요하다(→ build_dong_crosswalk.py).

응답 좌표계는 EPSG:5179(UTM-K) — pyproj로 4326 변환. year 파라미터는 2000~2025만
허용(2026 불가, 최신 신설 법정동은 여기도 없을 수 있음 — crosswalk 단계에서 확인).

사용법:
  python3 scripts/fetch_dong_boundaries.py --verify     # 인증 + 당진(34080) 1건 대조, 저장 안 함
  python3 scripts/fetch_dong_boundaries.py               # 경기(31)+충남(34) 전체 읍면동 fetch
                                                           # + 4326 변환 -> boundary_dong_4326.json
  python3 scripts/fetch_dong_boundaries.py --force        # 캐시 무시하고 재호출
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from pyproj import Transformer

AUTH_URL = "https://sgisapi.mods.go.kr/OpenAPI3/auth/authentication.json"
BOUNDARY_URL = "https://sgisapi.mods.go.kr/OpenAPI3/boundary/hadmarea.geojson"
RAW_DIR = "boundary_raw"
OUT_PATH = "boundary_dong_4326.json"
YEAR = "2025"           # API 허용 범위 2000~2025(2026 불가)
SLEEP_SEC = 0.3
SIDO_CODES = {"경기": "31", "충남": "34"}   # SGIS 고유 시도코드(법정동 41/44 아님)

VERIFY_SIGUNGU = "34080"        # 당진(SGIS 코드)
VERIFY_EXPECT_NAME = "합덕읍"


def load_env():
    env = {}
    with open(".env", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k] = v
    missing = [k for k in ("SGIS_CONSUMER_KEY", "SGIS_CONSUMER_SECRET") if k not in env]
    if missing:
        raise RuntimeError(f".env에 {', '.join(missing)} 없음 — 두 값 다 있어야 인증 가능")
    return env["SGIS_CONSUMER_KEY"], env["SGIS_CONSUMER_SECRET"]


def get_access_token(consumer_key, consumer_secret):
    params = {"consumer_key": consumer_key, "consumer_secret": consumer_secret}
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=20) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    token = (body.get("result") or {}).get("accessToken")
    if not token:
        raise RuntimeError(f"accessToken 발급 실패: {body}")
    return token


def fetch_hadmarea(access_token, adm_cd, low_search=1):
    params = {"accessToken": access_token, "year": YEAR, "adm_cd": adm_cd, "low_search": low_search}
    url = f"{BOUNDARY_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def verify(token):
    print(f"검증 호출: adm_cd={VERIFY_SIGUNGU}(당진, SGIS코드), low_search=1 ...")
    data = fetch_hadmarea(token, VERIFY_SIGUNGU, low_search=1)
    feats = data.get("features", [])
    print(f"errCd={data.get('errCd')} errMsg={data.get('errMsg')} features={len(feats)}")
    for ft in feats:
        p = ft["properties"]
        mark = "  <-- 대조 대상" if VERIFY_EXPECT_NAME in p["adm_nm"] else ""
        print(f"  {p['adm_cd']}  {p['adm_nm']}{mark}")


def reproject_geometry(geom, transformer):
    def conv_ring(ring):
        return [list(transformer.transform(x, y)) for x, y in ring]

    if geom["type"] == "Polygon":
        return {"type": "Polygon", "coordinates": [conv_ring(r) for r in geom["coordinates"]]}
    if geom["type"] == "MultiPolygon":
        return {"type": "MultiPolygon",
                "coordinates": [[conv_ring(r) for r in poly] for poly in geom["coordinates"]]}
    raise ValueError(f"미지원 geometry type: {geom['type']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    consumer_key, consumer_secret = load_env()
    print("accessToken 발급 중...")
    token = get_access_token(consumer_key, consumer_secret)
    print("발급 완료.")

    if args.verify:
        verify(token)
        return

    os.makedirs(RAW_DIR, exist_ok=True)
    transformer = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)

    out_features = []
    for name, sido_cd in SIDO_CODES.items():
        raw_path = os.path.join(RAW_DIR, f"{sido_cd}.json")
        if os.path.exists(raw_path) and not args.force:
            print(f"{name}({sido_cd}): 캐시 있음")
            with open(raw_path, encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = fetch_hadmarea(token, sido_cd, low_search=2)
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            print(f"{name}({sido_cd}): fetch 완료, errCd={data.get('errCd')}, "
                  f"features={len(data.get('features', []))}")
            time.sleep(SLEEP_SEC)

        for ft in data.get("features", []):
            p = ft["properties"]
            geom4326 = reproject_geometry(ft["geometry"], transformer)
            out_features.append({
                "sgis_code": p["adm_cd"],
                "sgis_name": p["adm_nm"],
                "sido": name,
                "geometry": geom4326,
            })

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out_features, f, ensure_ascii=False, separators=(",", ":"))

    size_mb = os.path.getsize(OUT_PATH) / 1e6
    print(f"\n{OUT_PATH}: {len(out_features)}개 읍면동, {size_mb:.2f} MB (EPSG:4326)")


if __name__ == "__main__":
    main()
