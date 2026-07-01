"""
동-여유풀 파이프라인 2단계: KEPCO 분산전원연계정보 API(addrLidong 단위) 호출.

scripts/dong_list.csv 의 각 읍면동에 대해
  https://bigdata.kepco.co.kr/openapi/v1/dispersedGeneration.do
    ?metroCd=..&cityCd=..&addrLidong=<읍면동명>&apiKey=..&returnType=json
을 호출하고 원본 응답을 addr_lidong_raw/<code>.json 에 캐시한다. addrLi는 주지
않는다 — 실측 결과 addrLidong 단독 호출이 그 읍면동에 걸친 모든 DL을 이미
합쳐서 돌려준다(2026-07-01 합덕읍 검증: addrLi 없이 18건, 기존 리 탐침 캐시의
8리 union보다 많음 — 미탐침 리의 DL까지 포함).

이미 캐시된 코드는 재호출하지 않는다(재실행 방지). --sigungu 로 특정 시군구만
필터링해 샘플 실행 가능(예: --sigungu 44270 당진 샘플).

사용법:
  python3 scripts/kepco_client.py --sigungu 44270      # 당진만(샘플)
  python3 scripts/kepco_client.py                       # 전체 306개
  python3 scripts/kepco_client.py --force               # 캐시 무시하고 재호출
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = "https://bigdata.kepco.co.kr/openapi/v1/dispersedGeneration.do"
DONG_LIST_PATH = "scripts/dong_list.csv"
RAW_DIR = "addr_lidong_raw"
SLEEP_SEC = 0.3


def load_api_key():
    with open(".env", encoding="utf-8") as f:
        for line in f:
            if line.startswith("KEPCO_API_KEY="):
                return line.strip().split("=", 1)[1]
    raise RuntimeError(".env 에 KEPCO_API_KEY 없음")


def call_api(api_key, metro_cd, city_cd, addr_lidong):
    params = {
        "metroCd": metro_cd,
        "cityCd": city_cd,
        "addrLidong": addr_lidong,
        "apiKey": api_key,
        "returnType": "json",
    }
    url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body)
    except urllib.error.HTTPError as e:
        # KEPCO는 "이 주소로 매칭되는 DL 데이터 없음"도 HTTP 404 +
        # {"errCd":"404","errMsg":"NotFound"} 로 응답한다(존재하지 않는 동네 이름으로도
        # 동일하게 재현됨, 2026-07-01 확인). 호출 실패가 아니라 빈 결과로 취급한다.
        body = e.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except ValueError:
            raise
        if parsed.get("errCd") == "404":
            return e.code, {"data": [], "errCd": parsed.get("errCd"), "errMsg": parsed.get("errMsg")}
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sigungu", help="특정 시군구코드만 (샘플 실행용, 예: 44270)")
    ap.add_argument("--force", action="store_true", help="캐시 무시하고 재호출")
    ap.add_argument("--limit", type=int, help="최대 호출 건수 (디버그용)")
    args = ap.parse_args()

    os.makedirs(RAW_DIR, exist_ok=True)
    api_key = load_api_key()

    with open(DONG_LIST_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if args.sigungu:
        rows = [r for r in rows if r["sigungu_code"] == args.sigungu]

    if args.limit:
        rows = rows[: args.limit]

    print(f"대상 {len(rows)}건")

    called, skipped, failed = 0, 0, 0
    for i, row in enumerate(rows, 1):
        code = row["code"]
        out_path = os.path.join(RAW_DIR, f"{code}.json")
        if os.path.exists(out_path) and not args.force:
            skipped += 1
            continue

        try:
            status, body = call_api(api_key, row["metroCd"], row["cityCd"], row["addrLidong"])
        except Exception as e:
            print(f"  [{i}/{len(rows)}] {code} {row['addrLidong']} FAIL: {e}", file=sys.stderr)
            failed += 1
            continue

        record = {
            "code": code,
            "sigungu_code": row["sigungu_code"],
            "sigungu_name": row["sigungu_name"],
            "addrLidong": row["addrLidong"],
            "metroCd": row["metroCd"],
            "cityCd": row["cityCd"],
            "http_status": status,
            "response": body,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        n = len(body.get("data") or [])
        print(f"  [{i}/{len(rows)}] {code} {row['sigungu_name']} {row['addrLidong']}: {n}건")
        called += 1
        time.sleep(SLEEP_SEC)

    print(f"완료: 호출 {called}, 캐시스킵 {skipped}, 실패 {failed}")


if __name__ == "__main__":
    main()
