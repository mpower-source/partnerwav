-- =====================================================================
-- PartnerWAV sign-in: portal_users
-- Maps each Supabase Auth login to a portal role and the company it
-- belongs to. The portal reads this after sign-in to decide which
-- workspace to open (Partner / Vendor / Affiliate / Operator).
--
-- Run in: Supabase dashboard -> SQL Editor. Safe to re-run.
-- =====================================================================

create table if not exists public.portal_users (
  id           uuid primary key references auth.users(id) on delete cascade,
  email        text not null,
  role         text not null check (role in ('partner','vendor','affiliate','operator')),
  -- Which company this login acts for. Must match the ids in partnerwav-v11-merged.html:
  --   vendor    -> vendor program id   (intelsense, crossconnect, botnoi, zipevent, portonics-dev, unisense)
  --   partner   -> partner profile id  (siam-digital, gulf-coast, portonics, riverside)
  --   affiliate -> affiliate id        (techbridge-aff, asian-connect-aff)
  --   operator  -> null
  entity_id    text,
  display_name text,
  created_at   timestamptz not null default now(),
  constraint portal_users_entity_required check (role = 'operator' or entity_id is not null)
);

alter table public.portal_users enable row level security;

-- Operator check that doesn't recurse through RLS
create or replace function public.is_portal_operator()
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.portal_users where id = auth.uid() and role = 'operator');
$$;

drop policy if exists "portal_users: read own row" on public.portal_users;
create policy "portal_users: read own row" on public.portal_users
  for select to authenticated using (id = auth.uid());

drop policy if exists "portal_users: operators read all" on public.portal_users;
create policy "portal_users: operators read all" on public.portal_users
  for select to authenticated using (public.is_portal_operator());

-- Deliberately NO insert/update/delete policies: roles can only be assigned
-- here in the SQL editor (or with the service-role key on a server), never
-- from the browser. A user can't promote themselves to operator.


-- =====================================================================
-- STEP 1 (dashboard): create the logins
--   Authentication -> Users -> Add user -> "Create new user"
--   Enter email + password, tick "Auto Confirm User".
--   Create one for each row you keep in the list below.
--
-- STEP 2: edit the emails below (replace the example.com addresses with
-- the real ones, delete rows you don't need), then run this block.
-- =====================================================================

with wanted(email, role, entity_id, display_name) as (values
  -- Program Operator (CloudWAV)
  ('cto@cloudwavconsulting.com',        'operator',  null,                'Peter Phelan'),
  -- Vendors
  ('intelsense@example.com',            'vendor',    'intelsense',        'Intelsense AI'),
  ('crossconnect@example.com',          'vendor',    'crossconnect',      'Cross Connect'),
  ('botnoi@example.com',                'vendor',    'botnoi',            'Botnoi Voice'),
  ('zipevent@example.com',              'vendor',    'zipevent',          'ZipEvent'),
  ('portonics-vendor@example.com',      'vendor',    'portonics-dev',     'Portonics Ltd. (Vendor)'),
  ('unisense@example.com',              'vendor',    'unisense',          'Unisense'),
  -- Partners
  ('siamdigital@example.com',           'partner',   'siam-digital',      'Siam Digital MSP'),
  ('gulfcoast@example.com',             'partner',   'gulf-coast',        'Gulf Coast VAR'),
  ('portonics-partner@example.com',     'partner',   'portonics',         'Portonics Ltd.'),
  ('riverside@example.com',             'partner',   'riverside',         'Riverside Telco'),
  -- Affiliates
  ('techbridge@example.com',            'affiliate', 'techbridge-aff',    'TechBridge Solutions'),
  ('asianconnect@example.com',          'affiliate', 'asian-connect-aff', 'Asian Connect Services')
)
insert into public.portal_users (id, email, role, entity_id, display_name)
select u.id, u.email, w.role, w.entity_id, w.display_name
from wanted w
join auth.users u on lower(u.email) = lower(w.email)
on conflict (id) do update
  set email = excluded.email, role = excluded.role,
      entity_id = excluded.entity_id, display_name = excluded.display_name;


-- =====================================================================
-- STEP 3: check. Lists every login and its role; "NO ROLE" rows can
-- sign in but will see "Account not set up yet".
-- =====================================================================

select u.email,
       coalesce(p.role, 'NO ROLE') as role,
       p.entity_id,
       p.display_name,
       u.email_confirmed_at is not null as confirmed
from auth.users u
left join public.portal_users p on p.id = u.id
order by p.role nulls first, u.email;
