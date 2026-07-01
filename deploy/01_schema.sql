-- =====================================================================
-- 영농형 태양광 RE100 — Supabase(PostGIS) 백엔드 스키마
-- 파일럿: 당진(44270). 이후 동일 구조로 13개 시군 확장.
-- 실행: Supabase 대시보드 → SQL Editor 에 붙여넣고 RUN.
-- =====================================================================

-- 1) PostGIS 확장 (Supabase는 extensions 스키마에 설치)
create extension if not exists postgis with schema extensions;

-- =====================================================================
-- 2) 필지(parcels) — 프론트엔드가 쓰는 속성만 컬럼화 + 지오메트리
--    (geojson의 반복 키가 사라져 저장 용량이 크게 줄어듦)
-- =====================================================================
drop table if exists public.parcels cascade;
create table public.parcels (
  id              bigint generated always as identity primary key,
  sgg_code        text not null,                 -- 시군코드 (당진 44270)
  pnu             text,
  area_m2         double precision,
  slope_mean      double precision,
  ownership_name  text,
  category        text,                          -- 지목
  subagpromo_name text,                          -- 진흥구분
  -- 정책 변수 플래그 (0/1) — 프론트 토글과 1:1
  needs_s0_clean    smallint,
  needs_agp_other   smallint,
  needs_agp_protect smallint,
  needs_agp_core    smallint,
  needs_facility    smallint,
  needs_jongchunji  smallint,
  needs_military    smallint,
  needs_eco         smallint,
  needs_park        smallint,
  needs_mining      smallint,
  needs_terrain     smallint,
  needs_landuse     smallint,
  needs_baekdu      smallint,
  needs_forest      smallint,
  needs_upper_law   smallint,
  geom            geometry(MultiPolygon, 4326) not null
);

-- 공간 인덱스 + 시군 필터 인덱스
create index parcels_geom_gix on public.parcels using gist (geom);
create index parcels_sgg_idx  on public.parcels (sgg_code);
-- 반경 검색은 중심점(centroid) 기준이므로 centroid GIST도 둠
create index parcels_centroid_gix on public.parcels using gist ( (st_centroid(geom)) );

-- =====================================================================
-- 3) 클러스터 (기존 cluster_db/schema.sql 이식)
-- =====================================================================
drop table if exists public.cluster_parcels cascade;
drop table if exists public.clusters cascade;

create table public.clusters (
  id              bigint generated always as identity primary key,
  sgg_code        text not null,
  sgg_name        text not null,
  scenario        text not null,        -- S0 / S3 / SMAX
  cluster_id      integer not null,     -- 시나리오 내 클러스터 번호(MW 내림차순)
  mw              double precision not null,
  area_ha         double precision not null,
  n_parcels       integer not null,
  individual_ratio_pct double precision not null,  -- 면적가중 개인소유 비율(%) ≤50
  nearest_complex text,
  dist_km         double precision,
  demand_gwh      double precision,
  pareto_layer    integer,              -- 비지배 층(1=프런트)
  smaa_rank1_pct  double precision,     -- SMAA 1위 획득 확률(%)
  smaa_rank       integer,
  centroid_lon    double precision,
  centroid_lat    double precision,
  geojson_file    text,
  unique (sgg_code, scenario, cluster_id)
);
create index clusters_sgg_idx on public.clusters (sgg_code, scenario);

create table public.cluster_parcels (
  sgg_code        text not null,
  scenario        text not null,
  cluster_id      integer not null,
  pnu             text not null,
  area_m2         double precision,
  ownership_name  text,
  is_individual   smallint              -- 1=개인, 0=비개인(앵커/공공/법인)
);
create index cluster_parcels_idx on public.cluster_parcels (sgg_code, scenario, cluster_id);

-- =====================================================================
-- 4) 시군 종합 잠재량 사전계산 테이블
--    (프론트 renderSggSummary()가 전체 필지를 순회하던 것을 대체 —
--     반경검색 RPC만으로는 전수 집계가 안 되므로 사전계산값을 둠)
-- =====================================================================
drop table if exists public.sgg_summary cascade;
create table public.sgg_summary (
  sgg_code   text primary key,
  sgg_name   text,
  mw_s0      double precision,   -- 현행법
  mw_s3      double precision,   -- 농지법 개정(진흥구역 포함)
  mw_max     double precision,   -- 이론적 최대
  demand_gwh double precision    -- 분석대상 전력수요 합산
);
