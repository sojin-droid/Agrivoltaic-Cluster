-- 영농형 특구 후보 클러스터 DB (앵커기반, 개인소유 ≤50%, ≥50MW)
-- 가중치 임의성 제거: Pareto 비지배 + SMAA rank-acceptability (선호중립)

DROP TABLE IF EXISTS cluster_parcels;
DROP TABLE IF EXISTS clusters;

CREATE TABLE clusters (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  sgg_code        TEXT NOT NULL,          -- 법정동 시군코드 (당진 44270)
  sgg_name        TEXT NOT NULL,
  scenario        TEXT NOT NULL,          -- S0 / S3 / SMAX (정책 적격 시나리오)
  cluster_id      INTEGER NOT NULL,       -- 시나리오 내 클러스터 번호(MW 내림차순)
  mw              REAL NOT NULL,          -- 설비용량(MW) = 면적 × 0.045 / 1000
  area_ha         REAL NOT NULL,
  n_parcels       INTEGER NOT NULL,
  individual_ratio_pct REAL NOT NULL,     -- 면적가중 개인소유 비율(%) — 앵커 제약 ≤50
  nearest_complex TEXT,                   -- 최근접 산단/대형소비처
  dist_km         REAL,                   -- 클러스터 중심→최근접 산단 거리
  demand_gwh      REAL,                   -- 최근접 산단 연간 전력수요(GWh)
  pareto_layer    INTEGER,                -- 비지배 층(1=비지배 프런트)
  smaa_rank1_pct  REAL,                   -- SMAA 1위 획득 확률(%) — 가중치 강건성
  smaa_rank       INTEGER,                -- 최종 순위(rank1% 내림차순)
  centroid_lon    REAL,
  centroid_lat    REAL,
  geojson_file    TEXT,                   -- 폴리곤이 들어있는 geojson 파일명
  UNIQUE(sgg_code, scenario, cluster_id)
);

CREATE TABLE cluster_parcels (
  sgg_code        TEXT NOT NULL,
  scenario        TEXT NOT NULL,
  cluster_id      INTEGER NOT NULL,
  pnu             TEXT NOT NULL,
  area_m2         REAL,
  ownership_name  TEXT,
  is_individual   INTEGER,                -- 1=개인, 0=비개인(앵커/공공/법인 등)
  FOREIGN KEY(sgg_code,scenario,cluster_id) REFERENCES clusters(sgg_code,scenario,cluster_id)
);
CREATE INDEX ix_cp ON cluster_parcels(sgg_code,scenario,cluster_id);
CREATE INDEX ix_cp_pnu ON cluster_parcels(pnu);

-- 시나리오별 요약 뷰 (S0 vs S3 vs SMAX 비교)
DROP VIEW IF EXISTS scenario_summary;
CREATE VIEW scenario_summary AS
SELECT sgg_code, sgg_name, scenario,
       COUNT(*)              AS n_clusters,
       ROUND(SUM(mw),1)      AS total_mw,
       ROUND(SUM(area_ha),1) AS total_ha,
       MIN(dist_km)          AS min_dist_km,
       ROUND(AVG(individual_ratio_pct),1) AS avg_individual_pct
FROM clusters
GROUP BY sgg_code, sgg_name, scenario;
