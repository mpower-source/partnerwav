-- Minimal stand-in for the parts of Supabase the PartnerWAV SQL uses (for local testing only)
create role anon nologin; create role authenticated nologin;
create schema auth;
create schema extensions; grant usage on schema extensions to anon, authenticated;
create table auth.users (id uuid primary key, email text, encrypted_password text, email_confirmed_at timestamptz, last_sign_in_at timestamptz,
  instance_id uuid, aud varchar(255), role varchar(255), raw_app_meta_data jsonb, raw_user_meta_data jsonb,
  created_at timestamptz default now(), updated_at timestamptz default now(),
  confirmation_token varchar(255), recovery_token varchar(255), email_change_token_new varchar(255), email_change varchar(255),
  email_change_token_current varchar(255), phone_change text, phone_change_token varchar(255), reauthentication_token varchar(255));
-- as in Supabase: an email login needs an identity; sessions and refresh tokens keep people signed in
create table auth.identities (id uuid primary key, provider_id text not null, user_id uuid not null references auth.users(id) on delete cascade,
  identity_data jsonb not null, provider text not null, last_sign_in_at timestamptz, created_at timestamptz, updated_at timestamptz,
  email text generated always as (lower(identity_data->>'email')) stored, unique (provider_id, provider));
create table auth.sessions (id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade, created_at timestamptz default now());
create table auth.refresh_tokens (id bigserial primary key, token varchar(255), user_id varchar(255), revoked boolean default false,
  session_id uuid references auth.sessions(id) on delete cascade);
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

-- Storage stand-in: buckets, objects (RLS on), storage.foldername()
create schema storage;
create table storage.buckets (id text primary key, name text, public boolean default false, file_size_limit bigint);
create table storage.objects (id uuid default gen_random_uuid() primary key, bucket_id text references storage.buckets(id), name text, owner uuid default auth.uid(), created_at timestamptz default now(), unique (bucket_id, name));
alter table storage.objects enable row level security;
create function storage.foldername(name text) returns text[] language sql immutable as $$
  select (string_to_array(name, '/'))[1:array_length(string_to_array(name, '/'), 1) - 1]
$$;
grant usage on schema storage to anon, authenticated;
grant select, insert, update, delete on storage.objects to anon, authenticated;
grant select on storage.buckets to anon, authenticated;
grant execute on function storage.foldername(text) to anon, authenticated;
