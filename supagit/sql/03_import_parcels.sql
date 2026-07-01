-- =====================================================================
-- 필지 적재 (data/dangjin_parcels.csv, 96,837행)
-- 순서: ①staging 생성 SQL 실행 → ②대시보드 CSV Import → ③변환+요약 SQL 실행
-- =====================================================================

-- ① staging
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
-- ↑ 실행 후 Table Editor → parcels_staging → Import data from CSV → dangjin_parcels.csv

-- ② 변환 + 본 테이블 적재
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
  st_multi(st_setsrid(st_geomfromtext(geom_wkt),4326))
from public.parcels_staging where geom_wkt is not null;

select count(*) as parcels_loaded from public.parcels;
-- drop table public.parcels_staging;   -- 정리(선택)

-- ③ 시군 종합 잠재량
insert into public.sgg_summary (sgg_code, sgg_name, mw_s0, mw_s3, mw_max, demand_gwh)
select '44270','당진',
  sum(case when needs_upper_law=1 then 0 when needs_s0_clean=1 then area_m2 else 0 end)*0.225*0.20/1000,
  sum(case when needs_upper_law=1 then 0
           when (needs_s0_clean=1 or needs_agp_other=1 or needs_agp_protect=1
                 or needs_facility=1 or needs_agp_core=1) then area_m2 else 0 end)*0.225*0.20/1000,
  sum(case when needs_upper_law=1 then 0 else area_m2 end)*0.225*0.20/1000,
  3904.2 + 388.9 + 7126.6 + 1710
from public.parcels where sgg_code='44270'
on conflict (sgg_code) do update set
  mw_s0=excluded.mw_s0, mw_s3=excluded.mw_s3, mw_max=excluded.mw_max, demand_gwh=excluded.demand_gwh;
select * from public.sgg_summary;
