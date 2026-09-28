-- Minimal stand-in for the parts of Supabase the PartnerWAV SQL uses (for local testing only)
create role anon nologin; create role authenticated nologin;
create schema auth;
create table auth.users (id uuid primary key, email text);
create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
grant usage on schema auth to anon, authenticated;
grant execute on function auth.uid() to anon, authenticated;
grant usage on schema public to anon, authenticated;
alter default privileges in schema public grant select, insert, update, delete on tables to anon, authenticated;
create publication supabase_realtime;
insert into auth.users values
 ('00000000-0000-0000-0000-000000000001','ops@cloudwav.test'),
 ('00000000-0000-0000-0000-000000000002','vendor@intelsense.test'),
 ('00000000-0000-0000-0000-000000000003','partner@siamdigital.test'),
 ('00000000-0000-0000-0000-000000000004','partner@gulfcoast.test'),
 ('00000000-0000-0000-0000-000000000005','vendor@botnoi.test'),
 ('00000000-0000-0000-0000-000000000006','norole@example.test');
