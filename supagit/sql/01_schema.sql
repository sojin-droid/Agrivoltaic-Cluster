-- =====================================================================
-- 영농형 태양광 RE100 — Supabase 백엔드 스키마 (supagit 배포용)
-- 모든 백엔드 데이터(필지·클러스터·저개인후보)를 Supabase에 보관.
-- 공개 정책(RLS)은 02_rpc_rls.sql 에서 설정:
--   · 개요(클러스터·저개인후보·시군요약) = 누구나(anon) 읽기
--   · 필지 상세(parcels)             = 로그인(authenticated) 만
-- 실행: Supabase 대시보드 → SQL Editor 에 붙여넣고 RUN.
-- =====================================================================

create extension if not exists postgis with schema extensions;

-- ── 1) 필지 (상세 — 로그인 전용) ──────────────────────
drop table if exists public.parcels cascade;
create table public.parcels (
  id              bigint generated always as identity primary key,
  sgg_code        text not null,
  pnu             text,
  area_m2         double precision,
  slope_mean      double precision,
  ownership_name  text,
  category        text,
  subagpromo_name text,
  needs_s0_clean    smallint, needs_agp_other smallint, needs_agp_protect smallint,
  needs_agp_core    smallint, needs_facility  smallint, needs_jongchunji  smallint,
  needs_military    smallint, needs_eco       smallint, needs_park        smallint,
  needs_mining      smallint, needs_terrain   smallint, needs_landuse     smallint,
  needs_baekdu      smallint, needs_forest    smallint, needs_upper_law   smallint,
  geom            geometry(MultiPolygon, 4326) not null
);
create index parcels_geom_gix     on public.parcels using gist (geom);
create index parcels_sgg_idx      on public.parcels (sgg_code);
create index parcels_centroid_gix on public.parcels using gist ( (st_centroid(geom)) );

-- ── 2) 클러스터(특구 후보) 폴리곤 + 풍부한 속성 (개요 — 공개) ──
--    properties 가 중첩(ownership/nearby_complexes 배열)이라 jsonb 로 보관.
drop table if exists public.clusters_geo cascade;
create table public.clusters_geo (
  sgg_code   text not null,
  scenario   text not null,            -- S0 / S3 / SMAX
  cluster_id integer not null,
  props      jsonb not null,           -- geojson feature.properties 그대로
  geom       geometry(MultiPolygon, 4326) not null,
  primary key (sgg_code, scenario, cluster_id)
);
create index clusters_geo_gix on public.clusters_geo using gist (geom);
create index clusters_geo_idx on public.clusters_geo (sgg_code, scenario);

-- ── 3) 클러스터 구성 필지 (상세 — 로그인 전용, 선택적) ──
drop table if exists public.cluster_parcels cascade;
create table public.cluster_parcels (
  sgg_code text not null, scenario text not null, cluster_id integer not null,
  pnu text not null, area_m2 double precision, ownership_name text, is_individual smallint
);
create index cluster_parcels_idx on public.cluster_parcels (sgg_code, scenario, cluster_id);

-- ── 4) 시군 종합 잠재량 (개요 — 공개) ───────────────────
drop table if exists public.sgg_summary cascade;
create table public.sgg_summary (
  sgg_code text primary key, sgg_name text,
  mw_s0 double precision, mw_s3 double precision, mw_max double precision,
  demand_gwh double precision
);

-- ── 5) 저개인 특구 후보(전국, 개요 — 공개) ──────────────
--    index.html 의 LOWINDIV 배열을 시나리오별 jsonb 1행으로 보관.
drop table if exists public.lowindiv_candidates cascade;
create table public.lowindiv_candidates (
  scenario text primary key,
  data     jsonb not null
);
