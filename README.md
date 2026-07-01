# RE100 영농형 태양광 산업단지 입지 분석

## 실행 방법
- **Windows**: `run.bat` 더블클릭
- **Mac**: `run.app` 더블클릭 (첫 실행 시 "확인되지 않은 개발자" 경고가 뜨면
  파일을 **우클릭 → 열기 → 열기** 한 번만 허용하면 이후엔 더블클릭으로 바로 실행됩니다)
- **Mac 폴백**: `.app`이 동작하지 않을 때만 — 터미널에서 이 폴더로 이동 후
  `chmod +x run.command` 한 번 실행하고 `run.command` 더블클릭
- **수동**: 이 폴더에서 터미널 열고 `python3 -m http.server 8002` 실행 후
  브라우저에서 http://localhost:8002 접속

## 시군별 URL
충청남도:
  http://localhost:8002/chungnam/44270_dangjin/dangjin_map.html
  http://localhost:8002/chungnam/44210_seosan/seosan_map.html
  http://localhost:8002/chungnam/44200_asan/asan_map.html
  http://localhost:8002/chungnam/44130_cheonan/cheonan_map.html
  http://localhost:8002/chungnam/44810_yesan/yesan_map.html
  http://localhost:8002/chungnam/44800_hongseong/hongseong_map.html
  http://localhost:8002/chungnam/44180_boryeong/boryeong_map.html

경기도:
  http://localhost:8002/gyeonggi/41590_hwaseong/hwaseong_map.html
  http://localhost:8002/gyeonggi/41220_pyeongtaek/pyeongtaek_map.html
  http://localhost:8002/gyeonggi/41463_yongin/yongin_map.html
  http://localhost:8002/gyeonggi/41390_siheung_ansan/siheung_ansan_map.html
  http://localhost:8002/gyeonggi/41500_icheon/icheon_map.html
  http://localhost:8002/gyeonggi/41480_paju/paju_map.html
  http://localhost:8002/gyeonggi/41570_gimpo/gimpo_map.html

## 사전 요구사항
- Python 3 (https://python.org)
- Chrome 또는 Edge 브라우저

## 분석 개요
- 대상: 경기도 7개 + 충청남도 6개 = 13개 시군, 38개 산업단지
  + 산단 외 대형 소비처 13곳 (수요 전용 — 현대제철 당진, 삼성전자 평택·화성·기흥,
    삼성디스플레이 아산·천안, 삼성SDI 천안, 대산석화 4사, SK하이닉스 이천, LGD 파주)
- 대형 소비처 전력소비는 당진 현대제철·대산 일부를 제외하면 **사업장 단위 비공개**라
  전사 공시값(지속가능경영보고서 등)을 사업장 규모로 배분한 추정치임 —
  각 엔트리의 `elec_note`에 산출 근거와 신뢰도(직접공시/추정·확인필요)를 명시
- 발전공식: Power Density 0.045 kW/m2 (영농형 실증 기반, 보수적 추정)
- 설비이용률: 15% (한국전력거래소 EPSIS)
- 시나리오: 14개 정책 변수 (부처별 협의 단계)

## 시각화 주요 기능
- 산업단지 선택 + 반경 조절 (0.5~10km)
- 14개 정책 변수 토글 (부처별 그룹)
- 실시간 설비용량(MW) / 자급률(%) 계산
- 시나리오별 자급률 비교 (독립 효과)
- 농지 소유 현황
- 경사도 시각화

## 폴더 구조
gyeonggi_chungnam/
  gyeonggi/      (7개 시군)
  chungnam/      (6개 시군)
  metadata/      (엑셀)
  run.bat       (Windows)
  run.command   (Mac)
  README.md
