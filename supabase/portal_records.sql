-- PartnerWAV: all portal data in one table, with row-level security.
-- Run this ONCE in the Supabase SQL editor, AFTER supabase/portal_users.sql.
-- Safe to re-run: it replaces the functions, policies and rules it creates.
--
-- Each row is one record of one "collection" (deals, incentives, shop products...).
-- readers / writers hold "role:entity" keys from portal_users, e.g. 'partner:siam-digital',
-- 'vendor:intelsense'. '*' means any signed-in portal user. CloudWAV operators can do everything.

-- ---------------------------------------------------------------------------
-- 1. Table
-- ---------------------------------------------------------------------------
create table if not exists public.portal_records (
  collection  text        not null,
  id          text        not null,
  data        jsonb       not null,
  readers     text[]      not null default '{}',
  writers     text[]      not null default '{}',
  is_public   boolean     not null default false,   -- readable without signing in (published landing pages, vendor profiles)
  updated_at  timestamptz not null default now(),
  updated_by  uuid        default auth.uid(),
  primary key (collection, id)
);
create index if not exists portal_records_readers_idx on public.portal_records using gin (readers);
alter table public.portal_records enable row level security;

-- ---------------------------------------------------------------------------
-- 2. Who is calling: "role:entity" from portal_users (NOT from user-editable metadata)
-- ---------------------------------------------------------------------------
create or replace function public.portal_key()
returns text language sql stable security definer set search_path = public as $$
  select role || ':' || coalesce(entity_id, '') from public.portal_users where id = auth.uid()
$$;
revoke all on function public.portal_key() from public;
grant execute on function public.portal_key() to authenticated, anon;

-- ---------------------------------------------------------------------------
-- 3. Row-level security
-- ---------------------------------------------------------------------------
drop policy if exists "portal_records public read"  on public.portal_records;
drop policy if exists "portal_records member read"  on public.portal_records;
drop policy if exists "portal_records insert"       on public.portal_records;
drop policy if exists "portal_records update"       on public.portal_records;
drop policy if exists "portal_records delete"       on public.portal_records;

create policy "portal_records public read" on public.portal_records
  for select to anon using (is_public);

create policy "portal_records member read" on public.portal_records
  for select to authenticated using (
    is_public
    or public.is_portal_operator()
    or (public.portal_key() is not null and (
          '*' = any(readers)
          or public.portal_key() = any(readers)
          or public.portal_key() = any(writers)))
  );

create policy "portal_records insert" on public.portal_records
  for insert to authenticated with check (
    public.is_portal_operator()
    or (public.portal_key() is not null and (public.portal_key() = any(writers) or '*' = any(writers)))
  );

create policy "portal_records update" on public.portal_records
  for update to authenticated
  using (
    public.is_portal_operator()
    or (public.portal_key() is not null and (public.portal_key() = any(writers) or '*' = any(writers)))
  )
  with check (
    public.is_portal_operator()
    or (public.portal_key() is not null and (public.portal_key() = any(writers) or '*' = any(writers)))
  );

create policy "portal_records delete" on public.portal_records
  for delete to authenticated using (
    public.is_portal_operator()
    or (public.portal_key() is not null and public.portal_key() = any(writers))
  );

-- ---------------------------------------------------------------------------
-- 4. Fields only CloudWAV may set. For everyone else a listed field may only take one of
--    the allowed values (or stay unchanged). Empty list = locked.
--    e.g. partners submit deals as "pending"; only CloudWAV can approve them.
-- ---------------------------------------------------------------------------
create table if not exists public.portal_field_rules (
  collection text  not null,
  field      text  not null,
  allowed    jsonb not null default '[]',
  primary key (collection, field)
);
alter table public.portal_field_rules enable row level security;  -- no policies: only the guard (security definer) reads it

insert into public.portal_field_rules (collection, field, allowed) values
  ('deals',            'status',       '["pending"]'),
  ('deals',            'pricingCheck', '["", null]'),
  ('incentives',       'status',       '["pending"]'),
  ('incentives',       'checks',       '[{}, null]'),
  ('incentives',       'approvedBy',   '[null]'),
  ('flyers',           'status',       '["draft", "pending"]'),
  ('flyers',           'checks',       '[{}, null]'),
  ('pendingResources', 'status',       '["pending"]'),
  ('shopOrders',       'status',       '["awaiting", "cancelled"]'),
  ('shopOrders',       'paidAt',       '["", null]'),
  -- affiliate offers: vendors add their own affiliate program; CloudWAV reviews it
  ('affiliatePrograms','status',       '["pending", "withdrawn"]'),
  ('affiliatePrograms','direct',       '[false, null]'),
  ('affiliatePrograms','rejectReason', '["", null]'),
  ('affiliatePrograms','reviewedAt',   '["", null]'),
  ('programs',         'tiers',        '[]'),
  ('programs',         'relationships','[]'),
  ('programs',         'agreement',    '[]'),
  ('programs',         'status',       '[]'),
  ('programs',         'terms',        '[]'),
  -- agreements: partners can only request one; CloudWAV sends it and records signatures
  ('agreements',       'status',       '["requested"]'),
  ('agreements',       'signers',      '[[], null]'),
  ('agreements',       'sentAt',       '["", null]'),
  ('agreements',       'signedAt',     '["", null]'),
  -- software project referrals: partners register; CloudWAV records the software house's
  -- answer, the contract, collected payments and payouts (these drive the fee)
  ('projectReferrals', 'status',       '["registered"]'),
  ('projectReferrals', 'acceptedAt',   '["", null]'),
  ('projectReferrals', 'protectedUntil','["", null]'),
  ('projectReferrals', 'contractValue','[null]'),
  ('projectReferrals', 'wonAt',        '["", null]'),
  ('projectReferrals', 'payments',     '[[], null]'),
  ('projectReferrals', 'payouts',      '[[], null]'),
  ('projectReferrals', 'termsSnapshot','[null]'),
  ('projectReferrals', 'rejectReason', '[null, ""]')
on conflict (collection, field) do update set allowed = excluded.allowed;

-- Collections only CloudWAV can add records to (members may still edit where they're a writer)
create or replace function public.portal_operator_only(c text)
returns boolean language sql immutable as $$
  select c = any (array['mspProspects','mspEngagements','landingPages',
                        'shopProducts','shopAccess','levelRules','enrollments','softwareHouses',
                        'programFees','platformFees','affiliateSignups',
                        'vendorAssessments','pricingModel','agreementReviews',
                        'operatorSettings','vendorReferrals'])
$$;

-- ---------------------------------------------------------------------------
-- 5. Guard trigger: enforces the rules above on every insert/update
-- ---------------------------------------------------------------------------
create or replace function public.portal_records_guard()
returns trigger language plpgsql security definer set search_path = public as $$
declare
  k text := public.portal_key();
  r record;
  v jsonb;
  ov jsonb;
  prev public.portal_records%rowtype;
  is_new boolean;
  product_price numeric;
begin
  new.updated_at := now();
  new.updated_by := auth.uid();
  if public.is_portal_operator() then return new; end if;
  -- public sign-ups on a vendor's invite page arrive through submit_affiliate_signup() below
  if new.collection = 'affiliateSignups' and tg_op = 'INSERT'
     and current_setting('portal.affiliate_signup', true) = 'on' then return new; end if;
  -- a vendor's fit assessment sent from the public form arrives through submit_vendor_assessment() below
  if new.collection = 'vendorAssessments'
     and current_setting('portal.vendor_assessment', true) = 'on' then return new; end if;
  if k is null then raise exception 'This account has no PartnerWAV role'; end if;

  -- The portal saves with upsert (INSERT ... ON CONFLICT DO UPDATE). The insert trigger sees
  -- those too, so compare against the stored row whenever there is one.
  if tg_op = 'UPDATE' then
    prev := old; is_new := false;
  else
    select * into prev from public.portal_records where collection = new.collection and id = new.id;
    is_new := not found;
  end if;

  -- affiliate offers (and their private terms) come only from CloudWAV or the vendor that owns them
  if new.collection in ('affiliatePrograms', 'affiliateTerms')
     and (k not like 'vendor:%' or 'vendor:' || coalesce(new.data ->> 'vendorId', '') <> k) then
    raise exception 'Only CloudWAV or the owning vendor can save affiliate offers';
  end if;

  -- WhatsApp / LINE: your own contact details, groups and share log only
  if new.collection = 'contactChannels' and new.id <> k then
    raise exception 'You can only save your own WhatsApp and LINE details';
  end if;
  -- investment round details: each company saves only its own
  if new.collection = 'fundingProfiles' and new.id <> k then
    raise exception 'You can only save your own investment round details';
  end if;
  if new.collection in ('socialGroups', 'broadcasts') and (new.data ->> 'ownerKey') is distinct from k then
    raise exception 'You can only save your own groups';
  end if;
  -- calendar events belong to whoever created them; a booking is recorded by the person who booked
  if new.collection = 'calendarEvents' and (new.data ->> 'ownerKey') is distinct from k then
    raise exception 'You can only save your own events';
  end if;
  if new.collection = 'bookings' and (new.data ->> 'bookedBy') is distinct from k then
    raise exception 'A booking is recorded by the person who made it';
  end if;

  -- nobody can post a message as someone else
  if new.collection = 'messages' and (new.data ->> 'from') is distinct from k then
    raise exception 'Messages must be sent as yourself';
  end if;

  if is_new then
    if public.portal_operator_only(new.collection) then
      raise exception 'Only CloudWAV can add % records', new.collection;
    end if;
    -- a vendor may create only their own program profile
    if new.collection = 'programs' and k <> 'vendor:' || new.id then
      raise exception 'Vendors can only save their own profile';
    end if;
    -- '*' (anyone can edit) is only for community threads and groups
    if '*' = any(new.writers) and new.collection not in ('threads', 'groups') then
      raise exception 'Shared editing is only allowed for community posts';
    end if;
    if not ('*' = any(new.writers) or k = any(new.writers)) then
      raise exception 'You must be an editor of records you create';
    end if;
  else
    if not ('*' = any(prev.writers) or k = any(prev.writers)) then
      raise exception 'You can''t edit this record';
    end if;
    if new.writers is distinct from prev.writers then
      raise exception 'Only CloudWAV can change who edits a record';
    end if;
  end if;

  for r in select field, allowed from public.portal_field_rules where collection = new.collection loop
    v := coalesce(new.data -> r.field, 'null'::jsonb);
    if not is_new then
      ov := coalesce(prev.data -> r.field, 'null'::jsonb);
      if v = ov then continue; end if;
    end if;
    -- free shop products are "paid" straight away
    if new.collection = 'shopOrders' and is_new and r.field in ('status', 'paidAt') then
      select coalesce((data ->> 'price')::numeric, 0) into product_price
        from public.portal_records where collection = 'shopProducts' and id = new.data ->> 'productId';
      if found and product_price = 0 and coalesce((new.data ->> 'price')::numeric, 0) = 0 then continue; end if;
    end if;
    if not (r.allowed @> jsonb_build_array(v)) then
      raise exception 'Only CloudWAV can set "%" on %', r.field, new.collection;
    end if;
  end loop;
  return new;
end $$;

drop trigger if exists portal_records_guard on public.portal_records;
create trigger portal_records_guard
  before insert or update on public.portal_records
  for each row execute function public.portal_records_guard();

-- ---------------------------------------------------------------------------
-- 5b. Invite-only affiliate offers: anyone with the vendor's invite link can sign up without
--     an account. Only the vendor that owns the offer (and CloudWAV) can read the sign-ups.
-- ---------------------------------------------------------------------------
create or replace function public.submit_affiliate_signup(p_offer text, p_data jsonb)
returns text language plpgsql security definer set search_path = public as $$
declare
  offer jsonb;
  vendor text;
  new_id text := 'sg-' || replace(gen_random_uuid()::text, '-', '');
  clean jsonb;
begin
  select data into offer from public.portal_records
   where collection = 'affiliatePrograms' and id = p_offer and is_public;
  if offer is null or offer ->> 'audience' is distinct from 'invite'
     or coalesce(offer ->> 'status', 'approved') not in ('approved', 'active') then
    raise exception 'This invitation is not available';
  end if;
  vendor := offer ->> 'vendorId';
  if coalesce(vendor, '') = '' then raise exception 'This invitation is not available'; end if;
  if p_data is null or jsonb_typeof(p_data) <> 'object' or length(p_data::text) > 4000 then
    raise exception 'Sign-up details are missing or too long';
  end if;
  if coalesce(trim(p_data ->> 'name'), '') = '' or coalesce(p_data ->> 'email', '') !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' then
    raise exception 'Please give your name and a valid email address';
  end if;
  if coalesce((p_data ->> 'consent')::boolean, false) is not true then
    raise exception 'Please agree to be contacted about this offer';
  end if;
  clean := jsonb_build_object(
    'id', new_id, 'offerId', p_offer, 'vendorId', vendor,
    'kind',      case when p_data ->> 'kind' = 'business' then 'business' else 'referrer' end,
    'name',      left(trim(p_data ->> 'name'), 120),
    'email',     left(lower(trim(p_data ->> 'email')), 160),
    'phone',     left(coalesce(p_data ->> 'phone', ''), 60),
    'lineId',    left(coalesce(p_data ->> 'lineId', ''), 60),
    'company',   left(coalesce(p_data ->> 'company', ''), 160),
    'role',      left(coalesce(p_data ->> 'role', ''), 80),
    'note',      left(coalesce(p_data ->> 'note', ''), 500),
    'referredBy',left(coalesce(p_data ->> 'referredBy', ''), 60),
    'consent',   true,
    'createdAt', to_char(now() at time zone 'Asia/Bangkok', 'YYYY-MM-DD HH24:MI'));
  perform set_config('portal.affiliate_signup', 'on', true);
  insert into public.portal_records (collection, id, data, readers, writers, is_public)
  values ('affiliateSignups', new_id, clean, array['vendor:' || vendor], array[]::text[], false);
  perform set_config('portal.affiliate_signup', 'off', true);
  return new_id;
end $$;
revoke all on function public.submit_affiliate_signup(text, jsonb) from public;
grant execute on function public.submit_affiliate_signup(text, jsonb) to anon, authenticated;

-- ---------------------------------------------------------------------------
-- 5c. Vendor fit assessment: a prospective vendor fills in the public form (no account).
--     Only CloudWAV can read what they sent; CloudWAV then contacts them about pricing.
-- ---------------------------------------------------------------------------
create or replace function public.submit_vendor_assessment(p_data jsonb)
returns text language plpgsql security definer set search_path = public as $$
declare
  new_id text := 'va-' || replace(gen_random_uuid()::text, '-', '');
  clean jsonb;
begin
  if p_data is null or jsonb_typeof(p_data) <> 'object' or length(p_data::text) > 12000 then
    raise exception 'The form is empty or too long';
  end if;
  if coalesce(trim(p_data ->> 'company'), '') = '' or coalesce(trim(p_data ->> 'contactName'), '') = ''
     or coalesce(p_data ->> 'email', '') !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' then
    raise exception 'Please give your company, your name and a valid email address';
  end if;
  if coalesce((p_data ->> 'consent')::boolean, false) is not true then
    raise exception 'Please agree to be contacted about PartnerWAV';
  end if;
  -- keep the answers, but CloudWAV-only fields can never be set from the public form
  clean := (p_data - 'quote' - 'plan' - 'notesInternal' - 'statusLog')
    || jsonb_build_object('id', new_id, 'source', 'vendor-link', 'status', 'new',
         'email', left(lower(trim(p_data ->> 'email')), 160),
         'company', left(trim(p_data ->> 'company'), 160),
         'contactName', left(trim(p_data ->> 'contactName'), 120),
         'consent', true,
         'createdAt', to_char(now() at time zone 'Asia/Bangkok', 'YYYY-MM-DD HH24:MI'));
  perform set_config('portal.vendor_assessment', 'on', true);
  insert into public.portal_records (collection, id, data, readers, writers, is_public)
  values ('vendorAssessments', new_id, clean, array[]::text[], array[]::text[], false);
  perform set_config('portal.vendor_assessment', 'off', true);
  return new_id;
end $$;
revoke all on function public.submit_vendor_assessment(jsonb) from public;
grant execute on function public.submit_vendor_assessment(jsonb) to anon, authenticated;

-- A vendor who books a call from the assessment's thank-you page (not signed in): note it on their assessment.
-- Only the assessment's own id (a long random value they were just given) can mark it, and only for a week.
create or replace function public.mark_assessment_booked(p_id text)
returns boolean language plpgsql security definer set search_path = public as $$
declare n int;
begin
  if p_id is null or p_id !~ '^va-[0-9a-f]{32}$' then return false; end if;
  perform set_config('portal.vendor_assessment', 'on', true);
  update public.portal_records
     set data = data || jsonb_build_object('bookedAt', to_char(now() at time zone 'Asia/Bangkok', 'YYYY-MM-DD HH24:MI'))
   where collection = 'vendorAssessments' and id = p_id and not (data ? 'bookedAt')
     and updated_at > now() - interval '7 days';
  get diagnostics n = row_count;
  perform set_config('portal.vendor_assessment', 'off', true);
  return n > 0;
end $$;
revoke all on function public.mark_assessment_booked(text) from public;
grant execute on function public.mark_assessment_booked(text) to anon, authenticated;

-- ---------------------------------------------------------------------------
-- 5b. Accounts set up by CloudWAV from inside the portal
--     The operator enters a company name and an email; the portal creates the login with a
--     temporary password and calls portal_setup_account() to give it a role. The person is
--     asked to choose their own password the first time they sign in.
--     Operator logins are never created or changed here -- only in portal_users.sql.
-- ---------------------------------------------------------------------------
create extension if not exists pgcrypto with schema extensions;
alter table public.portal_users add column if not exists must_change_password boolean not null default false;

create or replace function public.portal_setup_account(p_email text, p_role text, p_entity text, p_name text, p_password text)
returns jsonb language plpgsql security definer set search_path = public, extensions as $$
declare u uuid; existing text;
begin
  if not public.is_portal_operator() then raise exception 'Only CloudWAV can set up accounts'; end if;
  if p_role is null or p_role not in ('partner', 'vendor', 'affiliate') then raise exception 'Choose vendor, partner or affiliate'; end if;
  if coalesce(trim(p_entity), '') = '' then raise exception 'The account needs a company'; end if;
  if p_password is null or length(p_password) < 8 then raise exception 'The temporary password needs at least 8 characters'; end if;
  select id into u from auth.users where lower(email) = lower(trim(p_email)) limit 1;
  if u is null then raise exception 'No login exists for % yet', trim(p_email); end if;
  select role into existing from public.portal_users where id = u;
  if existing = 'operator' then raise exception 'That email belongs to a CloudWAV operator login'; end if;
  update auth.users
     set encrypted_password = crypt(p_password, gen_salt('bf')),
         email_confirmed_at = coalesce(email_confirmed_at, now())
   where id = u;
  insert into public.portal_users (id, email, role, entity_id, display_name, must_change_password)
  values (u, lower(trim(p_email)), p_role, trim(p_entity), nullif(trim(coalesce(p_name, '')), ''), true)
  on conflict (id) do update
    set email = excluded.email, role = excluded.role, entity_id = excluded.entity_id,
        display_name = coalesce(excluded.display_name, public.portal_users.display_name), must_change_password = true;
  return jsonb_build_object('id', u, 'email', lower(trim(p_email)), 'role', p_role, 'entity_id', trim(p_entity));
end $$;
revoke all on function public.portal_setup_account(text, text, text, text, text) from public;
grant execute on function public.portal_setup_account(text, text, text, text, text) to authenticated;

-- Called by the person themselves once they have chosen their own password.
create or replace function public.portal_password_changed()
returns boolean language sql security definer set search_path = public as $$
  update public.portal_users set must_change_password = false where id = auth.uid() returning true;
$$;
revoke all on function public.portal_password_changed() from public;
grant execute on function public.portal_password_changed() to authenticated;

-- Every login and the company it belongs to (CloudWAV only).
create or replace function public.portal_accounts()
returns jsonb language plpgsql stable security definer set search_path = public as $$
begin
  if not public.is_portal_operator() then raise exception 'Only CloudWAV can list accounts'; end if;
  return coalesce((
    select jsonb_agg(jsonb_build_object('id', p.id, 'email', p.email, 'role', p.role, 'entity_id', p.entity_id,
             'display_name', p.display_name, 'must_change_password', p.must_change_password,
             'last_sign_in_at', u.last_sign_in_at, 'created_at', p.created_at) order by p.role, p.email)
    from public.portal_users p join auth.users u on u.id = p.id), '[]'::jsonb);
end $$;
revoke all on function public.portal_accounts() from public;
grant execute on function public.portal_accounts() to authenticated;

-- Take away a login's access to the portal (the login itself stays in Supabase Auth, without a role).
create or replace function public.portal_remove_account(p_user uuid)
returns boolean language plpgsql security definer set search_path = public as $$
declare n int;
begin
  if not public.is_portal_operator() then raise exception 'Only CloudWAV can remove accounts'; end if;
  delete from public.portal_users where id = p_user and role <> 'operator';
  get diagnostics n = row_count;
  return n > 0;
end $$;
revoke all on function public.portal_remove_account(uuid) from public;
grant execute on function public.portal_remove_account(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- 6. Live updates: other people's changes show up without reloading
-- ---------------------------------------------------------------------------
do $$ begin
  alter publication supabase_realtime add table public.portal_records;
exception when duplicate_object then null; when undefined_object then null; end $$;

-- ---------------------------------------------------------------------------
-- 7. File storage for resource uploads (bucket "portal-files", private, 50 MB per file)
--    Files live at resources/<record id>/<file name>. Whoever can read the resource record
--    can read its file; only the submitter (or CloudWAV) can upload it.
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit)
values ('portal-files', 'portal-files', false, 52428800)
on conflict (id) do update set public = false, file_size_limit = excluded.file_size_limit;

drop policy if exists "portal-files read"   on storage.objects;
drop policy if exists "portal-files upload" on storage.objects;
drop policy if exists "portal-files update" on storage.objects;
drop policy if exists "portal-files delete" on storage.objects;

create policy "portal-files read" on storage.objects
  for select to authenticated using (
    bucket_id = 'portal-files'
    and (exists (select 1 from public.portal_records r            -- RLS on portal_records applies here
                 where r.collection in ('resources', 'pendingResources')
                   and r.id = (storage.foldername(name))[2])
         -- an uploaded outside agreement: whoever can see the agreement record can open its file
         or ((storage.foldername(name))[1] = 'agreements'
             and exists (select 1 from public.portal_records r
                         where r.collection = 'agreements' and r.id = (storage.foldername(name))[2])))
  );

create policy "portal-files upload" on storage.objects
  for insert to authenticated with check (
    bucket_id = 'portal-files'
    and (((storage.foldername(name))[1] = 'resources'
          and (public.is_portal_operator()
               or exists (select 1 from public.portal_records r
                          where r.collection in ('resources', 'pendingResources')
                            and r.id = (storage.foldername(name))[2]
                            and public.portal_key() = any(r.writers))))
         -- outside agreements are uploaded by CloudWAV only
         or ((storage.foldername(name))[1] = 'agreements' and public.is_portal_operator()))
  );

create policy "portal-files update" on storage.objects
  for update to authenticated
  using (bucket_id = 'portal-files' and (owner = auth.uid() or public.is_portal_operator()))
  with check (bucket_id = 'portal-files' and (owner = auth.uid() or public.is_portal_operator()));

create policy "portal-files delete" on storage.objects
  for delete to authenticated using (bucket_id = 'portal-files' and (owner = auth.uid() or public.is_portal_operator()));

-- ---------------------------------------------------------------------------
-- 8. Check (optional): after signing in to the portal as the operator and clicking
--    Cloud Data -> "Save all starter records to Supabase", this should list the collections.
-- ---------------------------------------------------------------------------
-- select collection, count(*) from public.portal_records group by 1 order by 1;

-- ---------------------------------------------------------------------------
-- 9. Tell the Supabase API about the new table and functions right away
--    (otherwise the portal can say "Could not find the table 'public.portal_records' in the schema cache")
-- ---------------------------------------------------------------------------
notify pgrst, 'reload schema';
