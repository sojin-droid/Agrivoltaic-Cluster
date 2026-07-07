-- supabase/storage_setup.sql
-- Supabase 대시보드 → SQL Editor에서 실행.
-- agrivoltaic-data 버킷을 만들고 "읽기는 전체 공개, 쓰기는 service_role만" 정책을 건다.
-- (anon/authenticated는 절대 쓰기 불가 — service_role 키로 올린 migrate_to_supabase.py만 업로드 가능)

insert into storage.buckets (id, name, public)
values ('agrivoltaic-data', 'agrivoltaic-data', true)
on conflict (id) do update set public = true;

-- 공개 읽기: 누구나(anon 포함) SELECT 가능
drop policy if exists "agrivoltaic-data public read" on storage.objects;
create policy "agrivoltaic-data public read"
  on storage.objects for select
  using (bucket_id = 'agrivoltaic-data');

-- 쓰기/수정/삭제는 service_role만 (기본적으로 service_role은 RLS를 우회하므로
-- anon/authenticated에 대한 insert/update/delete 정책은 만들지 않는다 = 곧 차단).
