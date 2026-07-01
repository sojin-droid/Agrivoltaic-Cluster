-- =====================================================================
-- RPC + RLS  (01_schema.sql 실행 후)
--   공개(anon): 클러스터·저개인후보·시군요약  → 개요 지도
--   로그인(authenticated): 필지(parcels)        → 시군 상세 줌인
-- =====================================================================

-- ── RPC 1) 필지 반경검색 (로그인 전용) ─────────────────
create or replace function public.parcels_within_radius(
  p_lat double precision, p_lon double precision,
  p_radius_m double precision, p_sgg_code text default null
) returns jsonb
language sql stable security invoker
set search_path = public, extensions
as $$
  with hits as (
    select * from public.parcels pa
    where (p_sgg_code is null or pa.sgg_code = p_sgg_code)
      and st_dwithin((st_centroid(pa.geom))::geography,
                     st_setsrid(st_makepoint(p_lon, p_lat),4326)::geography, p_radius_m)
  )
  select jsonb_build_object('type','FeatureCollection','features',
    coalesce(jsonb_agg(jsonb_build_object(
      'type','Feature','geometry', st_asgeojson(h.geom)::jsonb,
      'properties', jsonb_build_object(
        'pnu',h.pnu,'area_m2',h.area_m2,'slope_mean',h.slope_mean,
        'ownership_name',h.ownership_name,'category',h.category,'subagpromo_name',h.subagpromo_name,
        'needs_S0_clean',h.needs_s0_clean,'needs_agp_other',h.needs_agp_other,
        'needs_agp_protect',h.needs_agp_protect,'needs_agp_core',h.needs_agp_core,
        'needs_facility',h.needs_facility,'needs_jongchunji',h.needs_jongchunji,
        'needs_military',h.needs_military,'needs_eco',h.needs_eco,'needs_park',h.needs_park,
        'needs_mining',h.needs_mining,'needs_terrain',h.needs_terrain,'needs_landuse',h.needs_landuse,
        'needs_baekdu',h.needs_baekdu,'needs_forest',h.needs_forest,'needs_upper_law',h.needs_upper_law)
    )), '[]'::jsonb))
  from hits h;
$$;

-- ── RPC 2) 클러스터 GeoJSON (공개) ────────────────────
--    프론트의 dangjin_clusters_<scen>.geojson 을 대체.
create or replace function public.clusters_geojson(
  p_sgg_code text, p_scenario text
) returns jsonb
language sql stable security invoker
set search_path = public, extensions
as $$
  select jsonb_build_object('type','FeatureCollection','features',
    coalesce(jsonb_agg(jsonb_build_object(
      'type','Feature','geometry', st_asgeojson(c.geom)::jsonb, 'properties', c.props
    ) order by (c.props->>'smaa_rank')::int nulls last), '[]'::jsonb))
  from public.clusters_geo c
  where c.sgg_code = p_sgg_code and c.scenario = p_scenario;
$$;

-- =====================================================================
-- RLS
-- =====================================================================
alter table public.parcels             enable row level security;
alter table public.clusters_geo        enable row level security;
alter table public.cluster_parcels     enable row level security;
alter table public.sgg_summary         enable row level security;
alter table public.lowindiv_candidates enable row level security;

drop policy if exists parcels_auth        on public.parcels;
drop policy if exists cluster_parcels_auth on public.cluster_parcels;
drop policy if exists clusters_pub        on public.clusters_geo;
drop policy if exists sgg_pub             on public.sgg_summary;
drop policy if exists lowindiv_pub        on public.lowindiv_candidates;

-- 상세: 로그인만
create policy parcels_auth         on public.parcels         for select to authenticated using (true);
create policy cluster_parcels_auth on public.cluster_parcels for select to authenticated using (true);
-- 개요: 누구나(비로그인 포함)
create policy clusters_pub on public.clusters_geo        for select to anon, authenticated using (true);
create policy sgg_pub      on public.sgg_summary         for select to anon, authenticated using (true);
create policy lowindiv_pub on public.lowindiv_candidates for select to anon, authenticated using (true);

-- =====================================================================
-- 실행/조회 권한
-- =====================================================================
-- 필지 RPC: 로그인만
revoke execute on function public.parcels_within_radius(double precision,double precision,double precision,text) from anon, public;
grant  execute on function public.parcels_within_radius(double precision,double precision,double precision,text) to authenticated;
-- 클러스터 RPC: 누구나
grant  execute on function public.clusters_geojson(text,text) to anon, authenticated;

grant select on public.parcels, public.cluster_parcels to authenticated;
grant select on public.clusters_geo, public.sgg_summary, public.lowindiv_candidates to anon, authenticated;
