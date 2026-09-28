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
  select c = any (array['affiliatePrograms','mspProspects','mspEngagements','landingPages',
                        'shopProducts','shopAccess','levelRules','enrollments','softwareHouses',
                        'programFees','platformFees'])
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
  if k is null then raise exception 'This account has no PartnerWAV role'; end if;

  -- The portal saves with upsert (INSERT ... ON CONFLICT DO UPDATE). The insert trigger sees
  -- those too, so compare against the stored row whenever there is one.
  if tg_op = 'UPDATE' then
    prev := old; is_new := false;
  else
    select * into prev from public.portal_records where collection = new.collection and id = new.id;
    is_new := not found;
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
    and exists (select 1 from public.portal_records r            -- RLS on portal_records applies here
                where r.collection in ('resources', 'pendingResources')
                  and r.id = (storage.foldername(name))[2])
  );

create policy "portal-files upload" on storage.objects
  for insert to authenticated with check (
    bucket_id = 'portal-files'
    and (storage.foldername(name))[1] = 'resources'
    and (public.is_portal_operator()
         or exists (select 1 from public.portal_records r
                    where r.collection in ('resources', 'pendingResources')
                      and r.id = (storage.foldername(name))[2]
                      and public.portal_key() = any(r.writers)))
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
