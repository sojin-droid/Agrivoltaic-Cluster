-- =====================================================================
-- 데이터 적재 (CSV Import 방식)
-- 순서:
--   1) 아래 staging 테이블 생성 SQL 실행
--   2) Supabase 대시보드 → Table Editor → parcels_staging →
--      "Import data from CSV" 로 dangjin_parcels.csv 업로드
--   3) 그 다음 아래 "변환 + 적재" SQL 실행
-- =====================================================================

-- 1) staging (geom은 일단 WKT 텍스트로 받음)
drop table if exists public.parcels_staging;
create table public.parcels_staging (
  sgg_code text, pnu text, area_m2 double precision, slope_mean double precision,
  ownership_name text, category text, subagpromo_name text,
  needs_s0_clean smallint, needs_agp_other smallint, needs_agp_protect smallint,
  needs_agp_core smallint, needs_facility smallint, needs_jongchunji smallint,
  needs_military smallint, needs_eco smallint, needs_park smallint, needs_mining smallint,
  needs_terrain smallint, needs_landuse smallint, needs_baekdu smallint, needs_forest smallint,
  needs_upper_law smallint, geom_wkt text
);

-- ↑ 여기까지 실행 후, 대시보드에서 CSV Import 하세요. ↑

-- =====================================================================
-- 2) 변환 + 본 테이블 적재 (CSV Import 끝난 뒤 실행)
-- =====================================================================
insert into public.parcels (
  sgg_code, pnu, area_m2, slope_mean, ownership_name, category, subagpromo_name,
  needs_s0_clean, needs_agp_other, needs_agp_protect, needs_agp_core, needs_facility,
  needs_jongchunji, needs_military, needs_eco, needs_park, needs_mining, needs_terrain,
  needs_landuse, needs_baekdu, needs_forest, needs_upper_law, geom)
select
  sgg_code, pnu, area_m2, slope_mean, ownership_name, category, subagpromo_name,
  needs_s0_clean, needs_agp_other, needs_agp_protect, needs_agp_core, needs_facility,
  needs_jongchunji, needs_military, needs_eco, needs_park, needs_mining, needs_terrain,
  needs_landuse, needs_baekdu, needs_forest, needs_upper_law,
  st_multi(st_setsrid(st_geomfromtext(geom_wkt), 4326))
from public.parcels_staging
where geom_wkt is not null;

-- 적재 확인
select count(*) as parcels_loaded from public.parcels;

-- staging 정리(선택)
-- drop table public.parcels_staging;

-- =====================================================================
-- 3) 시군 종합 잠재량 사전계산 (parcels 적재 후 1회)
--    프론트 renderSggSummary()가 읽는 값. demand_gwh는 산단 4곳 연수요 합.
-- =====================================================================
insert into public.sgg_summary (sgg_code, sgg_name, mw_s0, mw_s3, mw_max, demand_gwh)
select '44270', '당진',
  sum(case when needs_upper_law=1 then 0 when needs_s0_clean=1 then area_m2 else 0 end) * 0.225*0.20/1000,
  sum(case when needs_upper_law=1 then 0
           when (needs_s0_clean=1 or needs_agp_other=1 or needs_agp_protect=1
                 or needs_facility=1 or needs_agp_core=1) then area_m2 else 0 end) * 0.225*0.20/1000,
  sum(case when needs_upper_law=1 then 0 else area_m2 end) * 0.225*0.20/1000,
  3904.2 + 388.9 + 7126.6 + 1710          -- 당진송산2 + 당진일반 + 석문 + 현대제철
from public.parcels
on conflict (sgg_code) do update set
  mw_s0=excluded.mw_s0, mw_s3=excluded.mw_s3, mw_max=excluded.mw_max, demand_gwh=excluded.demand_gwh;

select * from public.sgg_summary;
