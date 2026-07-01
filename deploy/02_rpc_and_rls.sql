-- =====================================================================
-- 반경검색 RPC + 비공개(RLS) 설정
-- 01_schema.sql 실행 후 데이터 적재까지 끝낸 다음 실행해도 되고,
-- RPC/RLS만 먼저 만들어도 됩니다. (데이터와 독립)
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) 반경검색 RPC
--    프론트 loadParcels(lat, lon, radius_m) 와 1:1 대응.
--    중심점이 (lat,lon) 반경 radius_m(미터) 이내인 필지를
--    GeoJSON FeatureCollection 으로 반환.
--    프로퍼티 키는 프론트가 읽는 이름과 정확히 일치(needs_S0_clean 대문자 주의).
-- ---------------------------------------------------------------------
create or replace function public.parcels_within_radius(
  p_lat       double precision,
  p_lon       double precision,
  p_radius_m  double precision,
  p_sgg_code  text default null      -- 시군 한정(선택). 파일럿은 '44270'.
)
returns jsonb
language sql
stable
security invoker            -- 호출자(authenticated) 권한 → RLS 적용
set search_path = public, extensions
as $$
  with hits as (
    select *
    from public.parcels pa
    where (p_sgg_code is null or pa.sgg_code = p_sgg_code)
      and st_dwithin(
            (st_centroid(pa.geom))::geography,
            st_setsrid(st_makepoint(p_lon, p_lat), 4326)::geography,
            p_radius_m
          )
  )
  select jsonb_build_object(
    'type', 'FeatureCollection',
    'features', coalesce(jsonb_agg(
      jsonb_build_object(
        'type', 'Feature',
        'geometry', st_asgeojson(h.geom)::jsonb,
        'properties', jsonb_build_object(
          'pnu',             h.pnu,
          'area_m2',         h.area_m2,
          'slope_mean',      h.slope_mean,
          'ownership_name',  h.ownership_name,
          'category',        h.category,
          'subagpromo_name', h.subagpromo_name,
          'needs_S0_clean',  h.needs_s0_clean,
          'needs_agp_other', h.needs_agp_other,
          'needs_agp_protect', h.needs_agp_protect,
          'needs_agp_core',  h.needs_agp_core,
          'needs_facility',  h.needs_facility,
          'needs_jongchunji', h.needs_jongchunji,
          'needs_military',  h.needs_military,
          'needs_eco',       h.needs_eco,
          'needs_park',      h.needs_park,
          'needs_mining',    h.needs_mining,
          'needs_terrain',   h.needs_terrain,
          'needs_landuse',   h.needs_landuse,
          'needs_baekdu',    h.needs_baekdu,
          'needs_forest',    h.needs_forest,
          'needs_upper_law', h.needs_upper_law
        )
      )
    ), '[]'::jsonb)
  )
  from hits h;
$$;

-- ---------------------------------------------------------------------
-- 2) RLS — 비공개. 로그인(authenticated) 사용자만 read.
-- ---------------------------------------------------------------------
alter table public.parcels        enable row level security;
alter table public.clusters       enable row level security;
alter table public.cluster_parcels enable row level security;
alter table public.sgg_summary    enable row level security;

-- 기존 정책 정리 후 재생성(재실행 안전)
drop policy if exists parcels_read_auth on public.parcels;
drop policy if exists clusters_read_auth on public.clusters;
drop policy if exists cluster_parcels_read_auth on public.cluster_parcels;
drop policy if exists sgg_summary_read_auth on public.sgg_summary;

create policy parcels_read_auth        on public.parcels        for select to authenticated using (true);
create policy clusters_read_auth       on public.clusters       for select to authenticated using (true);
create policy cluster_parcels_read_auth on public.cluster_parcels for select to authenticated using (true);
create policy sgg_summary_read_auth    on public.sgg_summary    for select to authenticated using (true);

-- ---------------------------------------------------------------------
-- 3) 실행 권한 — 로그인 사용자만 RPC 호출 가능(anon 차단)
-- ---------------------------------------------------------------------
revoke execute on function public.parcels_within_radius(double precision,double precision,double precision,text) from anon, public;
grant  execute on function public.parcels_within_radius(double precision,double precision,double precision,text) to authenticated;

-- 테이블 직접 select 권한(RLS와 함께 동작)
grant select on public.parcels, public.clusters, public.cluster_parcels, public.sgg_summary to authenticated;
