-- =====================================================================
-- PartnerWAV self sign-up: access requests (Member / Investor / Promoter)
--
-- Someone who creates a login from the portal gets an account with NO role, so
-- they see "Account not set up yet" and can't read any portal data. Their
-- Member / Investor / Promoter choice is stored here as a request. CloudWAV
-- (the operator) approves it, which gives the login its role. Roles are still
-- only ever assigned by the operator, never by the person signing up.
--
-- Run in: Supabase dashboard -> SQL Editor, AFTER supabase/portal_records.sql.
-- Safe to re-run.
--
-- ---------------------------------------------------------------------
-- TO DO BEFORE "Login with Google" WORKS (not done yet):
--   1. Google Cloud Console -> APIs & Services -> Credentials -> Create credentials ->
--      OAuth client ID -> Web application. Authorized redirect URI:
--        https://lnawgyaapcpyrvdtkarp.supabase.co/auth/v1/callback
--   2. Supabase -> Authentication -> Sign In / Providers -> Google: turn it on and paste
--      the Client ID and Client Secret from step 1.
--   3. Supabase -> Authentication -> URL Configuration -> Redirect URLs: add the portal's
--      address (the GitHub Pages URL the portal opens from).
--   Until these are done, the Google button shows "Login with Google isn't available yet".
--
-- Also in Supabase: Authentication -> Sign In / Providers -> "Allow new users to sign up" must be ON
-- for sign-up and Google sign-in. A new login has no role, so it sees only "not set up yet" until approved.
--
-- Approving a request (CloudWAV, SQL editor until an operator screen exists):
--   select id, email, name, kind, phone from portal_access_requests where status = 'pending';
--   select portal_approve_access('<request id>', '<company id>');
--   -- Member -> a memberProfiles id, Investor -> investorProfiles id, Promoter -> mediaProfiles id
--   select portal_decline_access('<request id>');   -- to turn a request down
-- =====================================================================

create table if not exists public.portal_access_requests (
  id          uuid primary key default gen_random_uuid(),
  email       text not null unique,
  name        text not null,
  phone       text,
  kind        text not null check (kind in ('member', 'investor', 'media')),   -- media = Promoter
  status      text not null default 'pending' check (status in ('pending', 'approved', 'declined')),
  entity_id   text,
  created_at  timestamptz not null default now(),
  decided_at  timestamptz
);

alter table public.portal_access_requests enable row level security;
revoke all on public.portal_access_requests from public, anon, authenticated;
grant select on public.portal_access_requests to authenticated;
drop policy if exists "access requests: operators read" on public.portal_access_requests;
create policy "access requests: operators read" on public.portal_access_requests
  for select to authenticated using (public.is_portal_operator());

-- The sign-up form calls this right after creating the login (anon key). It stores the
-- request only; it never gives a role. The same spam checks as the other public forms apply.
create or replace function public.portal_request_access(p_data jsonb)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  mail text := lower(trim(coalesce(p_data ->> 'email', '')));
  nm text := trim(coalesce(p_data ->> 'name', ''));
  ph text := trim(coalesce(p_data ->> 'phone', ''));
  kd text := coalesce(p_data ->> 'kind', '');
  cur_status text;
  rid uuid;
begin
  if not public.portal_spam_check('signup', kd, mail, p_data) then
    return jsonb_build_object('status', 'pending');   -- a bot is thanked but not saved
  end if;
  if nm = '' or length(nm) > 120 then raise exception 'Please enter your name'; end if;
  if mail !~ '^[^[:space:]@]+@[^[:space:]@]+[.][^[:space:]@]+$' or length(mail) > 254 then raise exception 'Please enter a valid email address'; end if;
  if kd not in ('member', 'investor', 'media') then raise exception 'Choose Member, Investor or Promoter'; end if;
  if length(ph) > 40 then raise exception 'That phone number is too long'; end if;

  select status into cur_status from public.portal_access_requests where email = mail;
  if cur_status = 'approved' then
    return jsonb_build_object('status', 'approved');   -- already has access; nothing to change
  end if;
  insert into public.portal_access_requests (email, name, phone, kind)
  values (mail, left(nm, 120), nullif(ph, ''), kd)
  on conflict (email) do update
    set name = excluded.name, phone = excluded.phone, kind = excluded.kind, status = 'pending', decided_at = null
    where public.portal_access_requests.status = 'pending'
  returning id into rid;
  return jsonb_build_object('status', 'pending', 'id', rid);
end $$;
revoke all on function public.portal_request_access(jsonb) from public;
grant execute on function public.portal_request_access(jsonb) to anon, authenticated;

-- CloudWAV approves a request: the person's own login (created at sign-up) gets the role
-- and the company it belongs to. The company must already exist in the portal.
create or replace function public.portal_approve_access(p_request uuid, p_entity text)
returns jsonb language plpgsql security definer set search_path = public, auth as $$
declare
  rq public.portal_access_requests%rowtype;
  u uuid;
  role_name text;
  coll text;
  ent text := trim(coalesce(p_entity, ''));
begin
  if not public.is_portal_operator() then raise exception 'Only CloudWAV can approve access'; end if;
  select * into rq from public.portal_access_requests where id = p_request and status = 'pending';
  if not found then raise exception 'That request is not waiting for a decision'; end if;
  if ent = '' then raise exception 'Choose the company or person this login belongs to'; end if;

  role_name := case rq.kind when 'media' then 'media' when 'investor' then 'investor' else 'member' end;
  coll := case role_name when 'investor' then 'investorProfiles' when 'media' then 'mediaProfiles' else 'memberProfiles' end;
  if not exists (select 1 from public.portal_records where collection = coll and id = ent and coalesce(data->>'_deleted', '') <> 'true') then
    raise exception 'That profile could not be found (%)', ent;
  end if;

  select id into u from auth.users where lower(email) = rq.email limit 1;
  if u is null then raise exception 'This person has not created their login yet'; end if;
  if exists (select 1 from public.portal_users x where x.id = u and x.role = 'operator') then
    raise exception 'That email belongs to a CloudWAV operator login';
  end if;

  insert into public.portal_users (id, email, role, entity_id, display_name)
  values (u, rq.email, role_name, ent, rq.name)
  on conflict (id) do update
    set role = excluded.role, entity_id = excluded.entity_id, display_name = excluded.display_name;
  update public.portal_access_requests set status = 'approved', entity_id = ent, decided_at = now() where id = rq.id;
  return jsonb_build_object('id', u, 'email', rq.email, 'role', role_name, 'entity_id', ent);
end $$;
revoke all on function public.portal_approve_access(uuid, text) from public;
grant execute on function public.portal_approve_access(uuid, text) to authenticated;

create or replace function public.portal_decline_access(p_request uuid)
returns boolean language plpgsql security definer set search_path = public as $$
declare n int;
begin
  if not public.is_portal_operator() then raise exception 'Only CloudWAV can decide access requests'; end if;
  update public.portal_access_requests set status = 'declined', decided_at = now() where id = p_request and status = 'pending';
  get diagnostics n = row_count;
  return n > 0;
end $$;
revoke all on function public.portal_decline_access(uuid) from public;
grant execute on function public.portal_decline_access(uuid) to authenticated;
