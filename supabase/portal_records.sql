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

-- Logins can be partner, vendor, affiliate, investor, member (people CloudWAV invites to the community),
-- media (Media & Events partners: PR agencies, media outlets, creators, event organizers, venues) or operator (CloudWAV)
do $$ begin
  if to_regclass('public.portal_users') is not null then
    alter table public.portal_users drop constraint if exists portal_users_role_check;
    alter table public.portal_users add constraint portal_users_role_check check (role in ('partner','vendor','affiliate','investor','member','media','operator'));
  end if;
end $$;

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
          or public.portal_key() = any(writers)
          or ('investors' = any(readers) and public.portal_key() like 'investor:%')
          or ('members' = any(readers) and public.portal_key() like 'member:%')))
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
  -- the "Reseller Ready" badge is CloudWAV's verification; a vendor cannot award it to itself
  ('programs',         'resellerReady','[null]'),
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
  ('projectReferrals', 'rejectReason', '[null, ""]'),
  -- a software house's own dev leads: the guard above lets it move them forward; these fields are never set by anyone else
  ('projectReferrals', 'source',       '["", null]'),
  -- an investor asks for an introduction (or withdraws); only CloudWAV marks it introduced or answers
  ('introRequests',    'status',       '["requested", "withdrawn"]'),
  ('introRequests',    'reply',        '["", null]'),
  -- a company's investor-readiness check: it sends it for review; only CloudWAV approves it or asks for changes
  ('investorReadiness','status',       '["draft", "submitted"]'),
  ('investorReadiness','reviewNote',   '["", null]'),
  ('investorReadiness','reviewedAt',   '["", null]'),
  -- Media & Events partners: CloudWAV approves them and sets PartnerWAV's fee; sponsorships are confirmed by CloudWAV
  ('mediaProfiles',    'status',       '["pending", null]'),
  ('mediaProfiles',    'feePct',       '[null]'),
  ('mediaProfiles',    'approvedAt',   '["", null]'),
  ('mediaSponsorships','status',       '["applied", "withdrawn"]'),
  ('mediaSponsorships','reply',        '["", null]'),
  -- requests for an MVP Builder package or a Media & Events service: CloudWAV tracks them and the fee
  ('serviceRequests',  'status',       '["new", "withdrawn"]'),
  ('serviceRequests',  'value',        '[null]'),
  ('serviceRequests',  'fee',          '[null]'),
  ('serviceRequests',  'houseId',      '["", null]'),
  ('serviceRequests',  'opNote',       '["", null]'),
  -- marketing videos: a requester asks for one and can withdraw it; only the Operator makes it, sends it for approval, approves it or sends it back
  ('marketingVideos',  'status',       '["requested", "withdrawn"]'),
  ('marketingVideos',  'videoUrl',     '[null, ""]'),
  ('marketingVideos',  'reviewNotes',  '[[], null]'),
  ('marketingVideos',  'reviewedAt',   '["", null]')
on conflict (collection, field) do update set allowed = excluded.allowed;

-- Collections only CloudWAV can add records to (members may still edit where they're a writer)
create or replace function public.portal_operator_only(c text)
returns boolean language sql immutable as $$
  select c = any (array['mspProspects','mspEngagements','landingPages','resources','enrollmentNotes',
                        'shopProducts','shopAccess','levelRules','enrollments','softwareHouses',
                        'programFees','platformFees','affiliateSignups',
                        'vendorAssessments','pricingModel','agreementReviews',
                        'operatorSettings','vendorReferrals','houseSummaries',
                        'eventPages','eventConnections','communityOrgs','communityEvents','investorDb','startupPerks','meetInvites','mvpPackages'])
$$;

-- ---------------------------------------------------------------------------
-- 5. Guard trigger: enforces the rules above on every insert/update
-- ---------------------------------------------------------------------------
alter table public.portal_users add column if not exists must_change_password boolean not null default false;
-- True while the signed-in person still has the temporary password CloudWAV gave them (finding 8).
create or replace function public.portal_password_pending()
returns boolean language sql stable security definer set search_path = public as $$
  select coalesce((select must_change_password from public.portal_users where id = auth.uid()), false);
$$;
revoke all on function public.portal_password_pending() from public;
grant execute on function public.portal_password_pending() to anon, authenticated;

create or replace function public.portal_records_guard()
returns trigger language plpgsql security definer set search_path = public as $$
declare
  k text := public.portal_key();
  r record;
  v jsonb;
  ov jsonb;
  prev public.portal_records%rowtype;
  is_new boolean;
  house_lead boolean := false;   -- a software house working its own Dev Lead (see below)
  product_price numeric;
  st jsonb;
  fkey text;
  i int;
  empty_vals jsonb[] := array['null', '""', '[]', '{}']::jsonb[];
begin
  -- finding 8: nothing is saved until the person has replaced CloudWAV's temporary password
  if public.portal_password_pending() then raise exception 'Choose your own password before saving anything'; end if;
  new.updated_at := now();
  new.updated_by := auth.uid();
  -- A record keeps its collection and id for life. Moving one would carry values past every check below
  -- (e.g. a scratch record holding "status":"approved" edited into deals), so nobody may do it.
  if tg_op = 'UPDATE' and (new.collection is distinct from old.collection or new.id is distinct from old.id) then
    raise exception 'A record cannot be moved to another collection or renamed';
  end if;
  if public.is_portal_operator() then return new; end if;
  -- public sign-ups on a vendor's invite page arrive through submit_affiliate_signup() below
  if new.collection = 'affiliateSignups' and tg_op = 'INSERT'
     and current_setting('portal.affiliate_signup', true) = 'on' then return new; end if;
  -- a sign-up on a partner's public landing page arrives through submit_partner_page_lead() below
  if new.collection = 'leads' and tg_op = 'INSERT'
     and current_setting('portal.page_lead', true) = 'on' then return new; end if;
  -- someone CloudWAV met at an event connects through submit_event_connection() below
  if new.collection = 'eventConnections' and tg_op = 'INSERT'
     and current_setting('portal.event_connect', true) = 'on' then return new; end if;
  -- an organizer sends an event in for the public Thailand calendar through submit_community_event() below
  if new.collection = 'communityEvents' and tg_op = 'INSERT'
     and current_setting('portal.community_event', true) = 'on' then return new; end if;
  -- events found on Luma, Meetup and Eventbrite feeds come in for review through import_community_events() below
  if current_setting('portal.event_import', true) = 'on'
     and ((new.collection = 'communityEvents' and tg_op = 'INSERT')
       or (new.collection = 'operatorSettings' and new.id = 'eventSourcesRun')) then return new; end if;
  -- a vendor's fit assessment sent from the public form arrives through submit_vendor_assessment() below
  if new.collection = 'vendorAssessments'
     and current_setting('portal.vendor_assessment', true) = 'on' then return new; end if;
  -- a notification is written only by post_notification() or submit_vendor_assessment() (below), which set this flag
  if new.collection = 'notifications' and current_setting('portal.notification', true) = 'on' then return new; end if;
  -- a Dev Lead made from a bigger MVP Builder request, by portal_make_devlead() below
  if new.collection = 'projectReferrals' and current_setting('portal.system', true) = 'on' then return new; end if;
  if k is null then raise exception 'This account has no PartnerWAV role'; end if;

  -- The portal saves with upsert (INSERT ... ON CONFLICT DO UPDATE). The insert trigger sees
  -- those too, so compare against the stored row whenever there is one.
  if tg_op = 'UPDATE' then
    prev := old; is_new := false;
  else
    select * into prev from public.portal_records where collection = new.collection and id = new.id;
    is_new := not found;
  end if;

  -- A software house works its own Dev Leads: a project referral with source 'mvp' that CloudWAV sent to it from an MVP
  -- Builder request. It accepts or declines, quotes, marks won or delivered, and logs progress. It can't change the lead's
  -- client, dates, house or sender, and can only move a lead forward through the stages below.
  if new.collection = 'projectReferrals' and not is_new and coalesce(prev.data ->> 'source', '') = 'mvp' then
    select exists (select 1 from public.portal_records h where h.collection = 'softwareHouses' and h.id = prev.data ->> 'houseId'
      and k in ('partner:' || coalesce(h.data ->> 'partnerId', '-'), 'vendor:' || coalesce(h.data ->> 'programId', '-'))) into house_lead;
  end if;
  if house_lead then
    if exists (select 1 from jsonb_object_keys(prev.data || new.data) f
        where f not in ('status', 'acceptedAt', 'quoteBy', 'quotedAt', 'quoteValue', 'wonAt', 'contractValue', 'rejectReason', 'deliveredAt', 'progress', 'thread', 'unreadPartner', 'unreadVendor', 'unreadOperator', 'unreadAffiliate')
          and coalesce(new.data -> f, 'null'::jsonb) is distinct from coalesce(prev.data -> f, 'null'::jsonb)) then
      raise exception 'A software house can only update the progress of its own dev leads';
    end if;
    if new.data ->> 'status' is distinct from prev.data ->> 'status' and not (
         (prev.data ->> 'status' = 'registered' and new.data ->> 'status' in ('accepted', 'rejected'))
      or (prev.data ->> 'status' = 'accepted' and new.data ->> 'status' in ('proposal', 'lost'))
      or (prev.data ->> 'status' = 'proposal' and new.data ->> 'status' in ('won', 'lost'))) then
      raise exception 'That change to the dev lead isn''t allowed';
    end if;
  end if;

  -- affiliate offers (and their private terms) come only from CloudWAV or the vendor that owns them
  if new.collection in ('affiliatePrograms', 'affiliateTerms')
     and (k not like 'vendor:%' or 'vendor:' || coalesce(new.data ->> 'vendorId', '') <> k) then
    raise exception 'Only CloudWAV or the owning vendor can save affiliate offers';
  end if;

  -- WhatsApp / LINE: your own contact details, groups and share log only
  if new.collection in ('contactChannels', 'integrationRequests') and new.id <> k then
    raise exception 'You can only save your own WhatsApp and LINE details';
  end if;
  -- investment round details: each company saves only its own
  -- the id stored inside a record must be the record's own id (the portal shows and links by it)
  if new.data ? 'id' and new.data ->> 'id' is distinct from new.id then
    raise exception 'A record''s id must match its key';
  end if;
  -- records that belong to one company can only be saved by that company
  if new.collection in ('incentives', 'flyers', 'hardwareOfferings')
     and 'vendor:' || coalesce(new.data ->> 'vendorId', '') <> k then
    raise exception 'You can only save your own company''s %', new.collection;
  end if;
  if new.collection in ('deals', 'leads', 'partnerProjects')
     and 'partner:' || coalesce(new.data ->> 'partnerId', '') <> k then
    raise exception 'You can only save your own company''s %', new.collection;
  end if;
  if (new.collection = 'partnerProfiles' and 'partner:' || new.id <> k)
     or (new.collection = 'affiliateProfiles' and 'affiliate:' || new.id <> k)
     or (new.collection = 'prefs' and new.id <> k) then
    raise exception 'You can only save your own profile and settings';
  end if;
  -- resources: members submit their own for review; the id can't reuse a published resource's id
  if new.collection in ('resources', 'pendingResources') and coalesce(new.data ->> 'ownerKey', '') <> k then
    raise exception 'You can only submit resources as yourself';
  end if;
  if new.collection = 'pendingResources' and tg_op = 'INSERT'
     and exists (select 1 from public.portal_records x where x.collection = 'resources' and x.id = new.id) then
    raise exception 'That resource id is already in use';
  end if;
  -- partner landing pages: a partner saves only its own
  if new.collection = 'partnerPages' and 'partner:' || coalesce(new.data ->> 'partnerId', '') <> k then
    raise exception 'You can only save your own landing pages';
  end if;
  -- brand colours: each company saves only its own (CloudWAV can set them up for anyone)
  if new.collection = 'brandKits' and new.id <> k then
    raise exception 'You can only save your own brand colours';
  end if;
  if new.collection = 'fundingProfiles' and new.id <> k then
    raise exception 'You can only save your own investment round details';
  end if;
  if new.collection in ('socialGroups', 'broadcasts') and (new.data ->> 'ownerKey') is distinct from k then
    raise exception 'You can only save your own groups';
  end if;
  -- investors: each saves only its own profile and its own introduction requests; a company's investor card
  -- (what investors see of its round) is saved only by that vendor or partner, and is read by investor logins
  if new.collection = 'investorProfiles' and 'investor:' || new.id <> k then
    raise exception 'You can only save your own investor profile';
  end if;
  if new.collection = 'introRequests' and 'investor:' || coalesce(new.data ->> 'investorId', '') <> k then
    raise exception 'You can only ask for introductions as yourself';
  end if;
  if new.collection = 'investorListings' and (new.id <> k or k !~ '^(vendor|partner|affiliate):') then
    raise exception 'Only the company itself can show its round to investors';
  end if;
  -- investors only see companies whose investor-readiness check CloudWAV has approved
  if new.collection = 'investorListings' and not exists (select 1 from public.portal_records x
       where x.collection = 'investorReadiness' and x.id = k and x.data ->> 'status' = 'approved') then
    raise exception 'Your investor-readiness check needs to be approved by PartnerWAV first';
  end if;
  if new.collection = 'investorReadiness' and (new.id <> k or k !~ '^(vendor|partner|affiliate):') then
    raise exception 'You can only save your own investor-readiness check';
  end if;
  if new.collection = 'investorListings' and exists (select 1 from unnest(new.readers) x where x not in ('investors', k)) then
    raise exception 'A company''s investor card is only for investors';
  end if;
  -- members (people CloudWAV invites to the community): each saves only its own profile, which members can read
  -- (never public); WhatsApp and LINE sit in memberContacts, shared only with the member's connections
  if new.collection in ('memberProfiles', 'memberContacts') and 'member:' || new.id <> k then
    raise exception 'You can only save your own member profile';
  end if;
  if new.collection = 'memberProfiles' and (new.is_public or exists (select 1 from unnest(new.readers) x where x not in ('members', k))) then
    raise exception 'A member profile is only for other members';
  end if;
  if new.collection = 'memberContacts' and (new.is_public or exists (select 1 from unnest(new.readers) x where x <> k and x !~ '^member:.')) then
    raise exception 'Contact details are only shared with your connections';
  end if;
  -- connections between members: the person asking sends it; only the person asked accepts or declines
  if new.collection = 'memberConnections' then
    if k not in (new.data ->> 'from', new.data ->> 'to') or new.data ->> 'from' = new.data ->> 'to'
       or coalesce(new.data ->> 'from', '') !~ '^member:.' or coalesce(new.data ->> 'to', '') !~ '^member:.' then
      raise exception 'Connections are between two members, one of them you';
    end if;
    if new.readers is distinct from array[new.data ->> 'from', new.data ->> 'to'] or new.is_public then
      raise exception 'A connection is only seen by the two members';
    end if;
    if tg_op = 'INSERT' and not exists (select 1 from public.portal_records x where x.collection = 'memberConnections' and x.id = new.id) then
      if new.data ->> 'from' <> k or coalesce(new.data ->> 'status', '') <> 'pending' then raise exception 'A connection starts as a request from you'; end if;
    else
      select * into prev from public.portal_records where collection = new.collection and id = new.id;
      if prev.data ->> 'from' is distinct from new.data ->> 'from' or prev.data ->> 'to' is distinct from new.data ->> 'to' then
        raise exception 'A connection can''t be moved to other people';
      end if;
      if (new.data ->> 'status') is distinct from (prev.data ->> 'status') and not (
           (k = new.data ->> 'to' and prev.data ->> 'status' = 'pending' and new.data ->> 'status' in ('accepted', 'declined'))
        or (k = new.data ->> 'from' and prev.data ->> 'status' = 'pending' and new.data ->> 'status' = 'withdrawn')
        or (k = new.data ->> 'from' and prev.data ->> 'status' in ('withdrawn', 'declined') and new.data ->> 'status' = 'pending')
        or (prev.data ->> 'status' = 'accepted' and new.data ->> 'status' = 'removed')) then
        raise exception 'Only the person asked can accept a connection';
      end if;
    end if;
  end if;
  -- Media & Events partners: each saves its own profile; it is shown to everyone signed in only once CloudWAV approves it
  if new.collection = 'mediaProfiles' then
    if 'media:' || new.id <> k then raise exception 'You can only save your own Media & Events profile'; end if;
    if new.is_public or exists (select 1 from unnest(new.readers) x where x not in ('*', k)) then raise exception 'A Media & Events profile is for signed-in PartnerWAV users only'; end if;
    if '*' = any(new.readers) and coalesce(new.data ->> 'status', '') <> 'approved' then raise exception 'Your profile is listed once PartnerWAV approves it'; end if;
  end if;
  if new.collection in ('mediaOffers', 'mediaSponsorships', 'mediaOfferCodes') and 'media:' || coalesce(new.data ->> 'mediaId', '') <> k then
    raise exception 'You can only save your own offers and sponsorships';
  end if;
  if new.collection in ('mediaSponsorships', 'mediaOfferCodes') and (new.is_public or exists (select 1 from unnest(new.readers) x where x <> k)) then
    raise exception 'This is only for you and PartnerWAV';
  end if;
  if new.collection = 'mediaOffers' then
    if new.is_public or exists (select 1 from unnest(new.readers) x where x not in ('*', k)) then raise exception 'Offers are for signed-in PartnerWAV users only'; end if;
    if '*' = any(new.readers) and not exists (select 1 from public.portal_records x where x.collection = 'mediaProfiles' and 'media:' || x.id = k and x.data ->> 'status' = 'approved') then
      raise exception 'Offers are listed once PartnerWAV approves your profile';
    end if;
  end if;
  -- a request for an MVP Builder package or a Media & Events service: sent by the company or member itself, seen only by
  -- them, the Media & Events partner it is for, and CloudWAV
  if new.collection = 'serviceRequests' then
    if coalesce(new.data ->> 'requesterKey', '') <> k then raise exception 'You can only send requests as yourself'; end if;
    if coalesce(new.data ->> 'kind', '') not in ('mvp', 'media', 'fractional') then raise exception 'Unknown kind of request'; end if;
    if new.is_public or exists (select 1 from unnest(new.readers) x where x <> k and x <> 'media:' || coalesce(new.data ->> 'mediaId', '')) then
      raise exception 'A request is only seen by you, the partner it is for and PartnerWAV';
    end if;
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
    exit when house_lead;
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

  -- Second review, finding 2: once CloudWAV has approved, declined, signed, paid or accepted a record, its owner
  -- can't quietly change it. They can still mark messages read, add to its thread, or send it back for review
  -- (a status they are allowed to set, which takes the approval away).
  if not is_new then
    select allowed into st from public.portal_field_rules where collection = new.collection and field = 'status'
       and collection in ('deals', 'incentives', 'flyers', 'pendingResources', 'shopOrders', 'affiliatePrograms', 'agreements', 'projectReferrals', 'investorReadiness');
    if found and not house_lead and coalesce(prev.data -> 'status', 'null'::jsonb) <> 'null'::jsonb
       and not (st @> jsonb_build_array(prev.data -> 'status')) and prev.data ->> 'status' <> 'changes'
       and (new.data -> 'status') is not distinct from (prev.data -> 'status') then
      for fkey in select jsonb_object_keys(prev.data || new.data) loop
        continue when fkey in ('unreadPartner', 'unreadVendor', 'unreadOperator', 'unreadAffiliate', 'thread', 'archivedAt', 'listed');
        continue when coalesce(new.data -> fkey, 'null'::jsonb) = any(empty_vals) and coalesce(prev.data -> fkey, 'null'::jsonb) = any(empty_vals);
        if (new.data -> fkey) is distinct from (prev.data -> fkey) then
          raise exception 'This record is % by CloudWAV, so "%" can''t be changed. Send it back for review to edit it', prev.data ->> 'status', fkey;
        end if;
      end loop;
    end if;
    -- a record's message thread only grows: earlier messages can't be edited or removed
    if jsonb_typeof(prev.data -> 'thread') = 'array' and jsonb_array_length(prev.data -> 'thread') > 0 then
      if jsonb_typeof(new.data -> 'thread') is distinct from 'array' or jsonb_array_length(new.data -> 'thread') < jsonb_array_length(prev.data -> 'thread') then
        raise exception 'Messages already sent can''t be removed';
      end if;
      for i in 0 .. jsonb_array_length(prev.data -> 'thread') - 1 loop
        if (new.data -> 'thread' -> i) is distinct from (prev.data -> 'thread' -> i) then raise exception 'Messages already sent can''t be changed'; end if;
      end loop;
    end if;
    -- shop orders: the product, price and buyer are fixed once the order exists
    if new.collection = 'shopOrders' and ((new.data -> 'productId') is distinct from (prev.data -> 'productId')
        or (new.data -> 'price') is distinct from (prev.data -> 'price') or (new.data -> 'buyer') is distinct from (prev.data -> 'buyer')) then
      raise exception 'An order''s product, price and buyer can''t be changed';
    end if;
    -- finding 3: a published resource is CloudWAV's copy. Its owner may archive it; changes go through review.
    if new.collection = 'resources' then
      for fkey in select jsonb_object_keys(prev.data || new.data) loop
        continue when fkey = 'archivedAt';
        if (new.data -> fkey) is distinct from (prev.data -> fkey) then
          raise exception 'A published resource can''t be changed directly. Submit your changes for review';
        end if;
      end loop;
    end if;
  end if;
  -- only CloudWAV writes as CloudWAV in a thread
  if jsonb_typeof(new.data -> 'thread') = 'array' and exists (
       select 1 from jsonb_array_elements(new.data -> 'thread') with ordinality as m(msg, n)
        where m.n > coalesce(case when is_new or jsonb_typeof(prev.data -> 'thread') <> 'array' then 0 else jsonb_array_length(prev.data -> 'thread') end, 0)
          and m.msg ->> 'from' = 'operator') then
    raise exception 'Only CloudWAV can post as CloudWAV';
  end if;
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
  if not public.portal_spam_check('invite', p_offer, p_data ->> 'email', p_data) then return new_id; end if;
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
-- ---------------------------------------------------------------------------
-- A visitor on a partner's published landing page asks for a demo or registers for a webinar (no sign-in).
-- The request becomes a lead that only that partner can see and edit.
-- ---------------------------------------------------------------------------
create or replace function public.submit_partner_page_lead(p_page text, p_data jsonb)
returns text language plpgsql security definer set search_path = public as $$
declare
  page jsonb;
  partner text;
  new_id text := 'lead-pp-' || replace(gen_random_uuid()::text, '-', '');
  web boolean;
  who text;
begin
  select data into page from public.portal_records
   where collection = 'partnerPages' and id = p_page and is_public;
  if page is null or page ->> 'status' is distinct from 'published' or page ? 'deletedAt' and page ->> 'deletedAt' <> '' then
    raise exception 'This page is not available';
  end if;
  partner := page ->> 'partnerId';
  if coalesce(partner, '') = '' then raise exception 'This page is not available'; end if;
  if p_data is null or jsonb_typeof(p_data) <> 'object' or length(p_data::text) > 4000 then
    raise exception 'Sign-up details are missing or too long';
  end if;
  if coalesce(trim(p_data ->> 'name'), '') = '' or coalesce(p_data ->> 'email', '') !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' then
    raise exception 'Please give your name and a valid email address';
  end if;
  if coalesce((p_data ->> 'consent')::boolean, false) is not true then
    raise exception 'Please agree to be contacted';
  end if;
  if not public.portal_spam_check('page', p_page, p_data ->> 'email', p_data) then return new_id; end if;
  web := page ->> 'template' = 'webinar';
  who := left(trim(p_data ->> 'name'), 120) || ' · ' || left(lower(trim(p_data ->> 'email')), 160)
         || case when coalesce(p_data ->> 'phone', '') <> '' then ' · ' || left(p_data ->> 'phone', 60) else '' end
         || case when coalesce(p_data ->> 'company', '') <> '' then ' · ' || left(p_data ->> 'company', 160) else '' end;
  perform set_config('portal.page_lead', 'on', true);
  insert into public.portal_records (collection, id, data, readers, writers, is_public)
  values ('leads', new_id, jsonb_build_object(
    'id', new_id, 'partnerId', partner, 'status', 'prospect', 'value', '', 'convertedDeal', null,
    'prospectName', left(coalesce(nullif(trim(p_data ->> 'company'), ''), trim(p_data ->> 'name')), 160),
    'notes', case when web then 'Registered for the webinar "' || left(coalesce(page ->> 'headline', ''), 160) || '" from your landing page. '
                  else 'Asked for a ' || left(coalesce(page -> 'vendor' ->> 'name', page ->> 'vendorId', ''), 120) || ' demo from your landing page. ' end
             || who || case when coalesce(p_data ->> 'note', '') <> '' then '. Note: ' || left(p_data ->> 'note', 500) else '' end,
    'source', 'landing page', 'pageId', p_page, 'vendorId', page ->> 'vendorId',
    'contact', jsonb_build_object('name', left(trim(p_data ->> 'name'), 120), 'email', left(lower(trim(p_data ->> 'email')), 160), 'phone', left(coalesce(p_data ->> 'phone', ''), 60)),
    'createdDate', to_char(now() at time zone 'Asia/Bangkok', 'YYYY-MM-DD'),
    'createdAt', to_char(now() at time zone 'Asia/Bangkok', 'YYYY-MM-DD HH24:MI')),
    array['partner:' || partner], array['partner:' || partner], false);
  perform set_config('portal.page_lead', 'off', true);
  return new_id;
end $$;
revoke all on function public.submit_partner_page_lead(text, jsonb) from public;
grant execute on function public.submit_partner_page_lead(text, jsonb) to anon, authenticated;

-- ---------------------------------------------------------------------------
-- Event Connect: someone CloudWAV met at an event scans the QR code and leaves their name,
-- company and WhatsApp number or LINE ID (no sign-in). Only CloudWAV can read the connection.
-- ---------------------------------------------------------------------------
create or replace function public.submit_event_connection(p_event text, p_data jsonb)
returns text language plpgsql security definer set search_path = public as $$
declare
  page jsonb;
  new_id text := 'evc-' || replace(gen_random_uuid()::text, '-', '');
  ch text;
  contact text;
  interest jsonb;
begin
  select data into page from public.portal_records
   where collection = 'eventPages' and id = p_event and is_public;
  if page is null or page ->> 'status' is distinct from 'published' then
    raise exception 'This page is not available';
  end if;
  if p_data is null or jsonb_typeof(p_data) <> 'object' or length(p_data::text) > 3000 then
    raise exception 'Details are missing or too long';
  end if;
  if coalesce(trim(p_data ->> 'name'), '') = '' then raise exception 'Please add your name'; end if;
  ch := p_data ->> 'channel';
  if ch is null or ch not in ('whatsapp', 'line') then raise exception 'Please choose WhatsApp or LINE'; end if;
  contact := trim(coalesce(p_data ->> 'contact', ''));
  if ch = 'line' and contact !~ '^@?[A-Za-z0-9._-]{2,40}$' then raise exception 'Please add your LINE ID'; end if;
  if ch = 'whatsapp' and (contact !~ '^\+?[0-9 ().-]{7,20}$' or length(regexp_replace(contact, '[^0-9]', '', 'g')) < 7) then
    raise exception 'Please add your WhatsApp number, with the country code';
  end if;
  select coalesce(jsonb_agg(distinct v), '[]'::jsonb) into interest
    from jsonb_array_elements_text(case when jsonb_typeof(p_data -> 'interest') = 'array' then p_data -> 'interest' else '[]'::jsonb end) v
   where v in ('vendor', 'partner', 'affiliate', 'investor', 'member');
  if not public.portal_spam_check('meet', p_event, ch || ':' || lower(contact), p_data) then return new_id; end if;
  perform set_config('portal.event_connect', 'on', true);
  insert into public.portal_records (collection, id, data, readers, writers, is_public)
  values ('eventConnections', new_id, jsonb_build_object(
    'id', new_id, 'eventId', p_event, 'eventName', left(coalesce(page ->> 'name', ''), 160),
    'name', left(trim(p_data ->> 'name'), 120), 'company', left(trim(coalesce(p_data ->> 'company', '')), 160),
    'channel', ch, 'contact', left(contact, 60), 'interest', interest, 'status', 'new',
    'createdAt', to_char(now() at time zone 'Asia/Bangkok', 'YYYY-MM-DD HH24:MI')),
    '{}', '{}', false);
  perform set_config('portal.event_connect', 'off', true);
  return new_id;
end $$;
revoke all on function public.submit_event_connection(text, jsonb) from public;
grant execute on function public.submit_event_connection(text, jsonb) to anon, authenticated;

-- ---------------------------------------------------------------------------
-- Thailand event calendar: anyone running a community can send an event in (no sign-in). It waits,
-- unlisted, until CloudWAV approves it; only CloudWAV sees the organizer's contact details.
-- ---------------------------------------------------------------------------
create or replace function public.submit_community_event(p_data jsonb)
returns text language plpgsql security definer set search_path = public as $$
declare
  new_id text := 'ce-' || replace(gen_random_uuid()::text, '-', '');
  st timestamptz;
  dur int;
  link text;
  city text;
begin
  if p_data is null or jsonb_typeof(p_data) <> 'object' or length(p_data::text) > 5000 then
    raise exception 'The event details are missing or too long';
  end if;
  if coalesce(trim(p_data ->> 'orgName'), '') = '' or coalesce(trim(p_data ->> 'title'), '') = '' then
    raise exception 'Please add the community and the event name';
  end if;
  if coalesce(trim(p_data ->> 'name'), '') = '' or coalesce(trim(p_data ->> 'contact'), '') = '' then
    raise exception 'Please add your name and a LINE, WhatsApp or email';
  end if;
  begin
    st := (p_data ->> 'start')::timestamptz;
  exception when others then st := null;
  end;
  if st is null or st < now() or st > now() + interval '2 years' then raise exception 'Please choose a date in the future'; end if;
  link := trim(coalesce(p_data ->> 'link', ''));
  if link !~ '^https://[^\s"<>]+\.[^\s"<>]+$' or length(link) > 400 then raise exception 'Please add the registration link (https://...)'; end if;
  dur := case when coalesce(p_data ->> 'durationMin', '') ~ '^[0-9]{1,5}$' then (p_data ->> 'durationMin')::int else 120 end;
  if dur < 15 or dur > 10080 then dur := 120; end if;
  city := coalesce(p_data ->> 'city', '');
  if city not in ('Bangkok', 'Chiang Mai', 'Phuket', 'Pattaya', 'Khon Kaen', 'Hua Hin', 'Online', 'Other') then city := 'Other'; end if;
  if not public.portal_spam_check('tec', 'calendar', lower(trim(p_data ->> 'contact')), p_data) then return new_id; end if;
  perform set_config('portal.community_event', 'on', true);
  insert into public.portal_records (collection, id, data, readers, writers, is_public)
  values ('communityEvents', new_id, jsonb_build_object(
    'id', new_id, 'status', 'pending', 'orgName', left(trim(p_data ->> 'orgName'), 120), 'title', left(trim(p_data ->> 'title'), 160),
    'category', case when p_data ->> 'category' in ('pitch', 'hackathon', 'opencall', 'conference', 'government') then p_data ->> 'category' else 'community' end,
    'start', to_char(st at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS".000Z"'), 'durationMin', dur, 'city', city,
    'venue', left(trim(coalesce(p_data ->> 'venue', '')), 160), 'price', left(trim(coalesce(p_data ->> 'price', '')), 60),
    'link', link, 'desc', left(trim(coalesce(p_data ->> 'desc', '')), 800),
    'submitter', jsonb_build_object('name', left(trim(p_data ->> 'name'), 120), 'contact', left(trim(p_data ->> 'contact'), 160)),
    'createdAt', to_char(now() at time zone 'Asia/Bangkok', 'YYYY-MM-DD HH24:MI')),
    '{}', '{}', false);
  perform set_config('portal.community_event', 'off', true);
  return new_id;
end $$;
revoke all on function public.submit_community_event(jsonb) from public;
grant execute on function public.submit_community_event(jsonb) to anon, authenticated;

-- Events found on public feeds (Luma and Meetup iCal links, Eventbrite organizers) or pasted in from the
-- weekly Saturday check. Called by the events-sync Edge Function (service role) or by CloudWAV. Each event
-- waits for review, unlisted. The id comes from the feed's own event id, so an event is only ever added once,
-- and one CloudWAV removed stays removed (the portal keeps it as declined).
create or replace function public.import_community_events(p_rows jsonb, p_run jsonb default null)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  r jsonb; added int := 0; skipped int := 0; seen int := 0; n int;
  st timestamptz; dur int; link text; city text; uid text; src text; ttl text; cat text; new_id text;
  claims jsonb;
begin
  begin claims := nullif(current_setting('request.jwt.claims', true), '')::jsonb; exception when others then claims := null; end;
  if not public.is_portal_operator() and coalesce(claims ->> 'role', '') <> 'service_role' then
    raise exception 'Only CloudWAV can bring events in';
  end if;
  if p_rows is null or jsonb_typeof(p_rows) <> 'array' or jsonb_array_length(p_rows) > 500 then
    raise exception 'Send a list of up to 500 events';
  end if;
  perform set_config('portal.event_import', 'on', true);
  for r in select value from jsonb_array_elements(p_rows) loop
    seen := seen + 1;
    if jsonb_typeof(r) <> 'object' or length(r::text) > 6000 then skipped := skipped + 1; continue; end if;
    src := lower(coalesce(r ->> 'source', ''));
    if src not in ('luma', 'meetup', 'eventbrite', 'zipevent', 'ical', 'manual') then src := 'other'; end if;
    ttl := left(trim(coalesce(r ->> 'title', '')), 160);
    link := trim(coalesce(r ->> 'link', ''));
    uid := left(trim(coalesce(nullif(r ->> 'uid', ''), link)), 400);
    begin st := (r ->> 'start')::timestamptz; exception when others then st := null; end;
    if ttl = '' or uid = '' or st is null or st < now() or st > now() + interval '2 years'
       or link !~ '^https://[^\s"<>]+\.[^\s"<>]+$' or length(link) > 400 then
      skipped := skipped + 1; continue;
    end if;
    dur := case when coalesce(r ->> 'durationMin', '') ~ '^[0-9]{1,5}$' then (r ->> 'durationMin')::int else 120 end;
    if dur < 15 or dur > 10080 then dur := 120; end if;
    city := coalesce(r ->> 'city', '');
    if city not in ('Bangkok', 'Chiang Mai', 'Phuket', 'Pattaya', 'Khon Kaen', 'Hua Hin', 'Online', 'Other') then city := 'Other'; end if;
    cat := case when r ->> 'category' in ('pitch', 'hackathon', 'opencall', 'conference', 'government') then r ->> 'category' else 'community' end;
    new_id := 'ce-ext-' || left(md5(src || '|' || uid), 20);
    insert into public.portal_records (collection, id, data, readers, writers, is_public)
    values ('communityEvents', new_id, jsonb_build_object(
      'id', new_id, 'status', 'pending', 'source', src, 'extUid', uid,
      'orgName', left(trim(coalesce(r ->> 'orgName', '')), 120), 'title', ttl, 'category', cat,
      'start', to_char(st at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS".000Z"'), 'durationMin', dur, 'city', city,
      'venue', left(trim(coalesce(r ->> 'venue', '')), 160), 'price', left(trim(coalesce(r ->> 'price', '')), 60),
      'link', link, 'desc', left(trim(coalesce(r ->> 'desc', '')), 800),
      'createdAt', to_char(now() at time zone 'Asia/Bangkok', 'YYYY-MM-DD HH24:MI')),
      '{}', '{}', false)
    on conflict (collection, id) do nothing;
    get diagnostics n = row_count;
    if n > 0 then added := added + 1; end if;
  end loop;
  if p_run is not null and jsonb_typeof(p_run) = 'object' and length(p_run::text) < 20000 then
    insert into public.portal_records (collection, id, data, readers, writers, is_public)
    values ('operatorSettings', 'eventSourcesRun', jsonb_build_object('id', 'eventSourcesRun',
      'at', to_char(now() at time zone 'Asia/Bangkok', 'YYYY-MM-DD HH24:MI'), 'added', added, 'skipped', skipped, 'seen', seen,
      'sources', case when jsonb_typeof(p_run -> 'sources') = 'array' then p_run -> 'sources' else '[]'::jsonb end), '{}', '{}', false)
    on conflict (collection, id) do update set data = excluded.data;
  end if;
  perform set_config('portal.event_import', 'off', true);
  return jsonb_build_object('added', added, 'skipped', skipped, 'seen', seen);
end $$;
revoke all on function public.import_community_events(jsonb, jsonb) from public;
grant execute on function public.import_community_events(jsonb, jsonb) to authenticated;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'service_role') then
    grant execute on function public.import_community_events(jsonb, jsonb) to service_role;
  end if;
end $$;

create or replace function public.submit_vendor_assessment(p_data jsonb)
returns text language plpgsql security definer set search_path = public as $$
declare
  new_id text := 'va-' || replace(gen_random_uuid()::text, '-', '');
  clean jsonb;
  kept jsonb := '{}'::jsonb;
  fk text;
  -- the public form's own fields (VA_STEPS in the page); anything else a caller sends is dropped
  text_fields text[] := array['budget','companyStage','contactRole','dealSize','hq','lineId','notes','partners','phone','productCount',
                              'productSummary','programStage','raiseAmount','raising','support','timeline','website','introducedBy'];
  list_fields text[] := array['addons','markets','needs','partnerTypes','productTypes'];
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
  if not public.portal_spam_check('assess', null, p_data ->> 'email', p_data) then return new_id; end if;
  -- Second review, finding 1: keep only the form's own answers, as plain text or short lists of plain values.
  -- CloudWAV-only fields (quote, plan, notes, ROI) and anything else a caller adds are never stored.
  foreach fk in array text_fields loop
    if jsonb_typeof(p_data -> fk) = 'string' then
      kept := kept || jsonb_build_object(fk, left(p_data ->> fk, case when fk in ('notes', 'productSummary') then 2000 else 300 end));
    end if;
  end loop;
  foreach fk in array list_fields loop
    if jsonb_typeof(p_data -> fk) = 'array' then
      kept := kept || jsonb_build_object(fk, coalesce((
        select jsonb_agg(x.v) from (select v from jsonb_array_elements_text(p_data -> fk) as v limit 30) x
         where x.v ~ '^[^<>"''`\\]{1,80}$'), '[]'::jsonb));
    end if;
  end loop;
  clean := kept
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
  perform set_config('portal.notification', 'on', true);
  insert into public.portal_records (collection, id, data, readers, writers, is_public)
  values ('notifications', 'n-' || replace(gen_random_uuid()::text, '-', ''),
    jsonb_build_object('kind', 'assessment', 'title', 'New vendor assessment: ' || left(trim(p_data ->> 'company'), 120),
      'body', 'Contact: ' || left(trim(p_data ->> 'contactName'), 80) || ' -- ' || left(lower(trim(p_data ->> 'email')), 120),
      'screen', 'operator-assessments', 'to', jsonb_build_array('operator'), 'from', 'vendor-link',
      'at', to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'id', 'n-' || replace(gen_random_uuid()::text, '-', '')),
    array[]::text[], array[]::text[], false);
  perform set_config('portal.notification', 'off', true);
  return new_id;
end $$;
create or replace function public.post_notification(p_to text[], p_kind text, p_title text, p_body text, p_screen text)
returns text language plpgsql security definer set search_path = public as $$
declare
  k text := public.portal_key();
  op boolean := public.is_portal_operator();
  new_id text := 'n-' || replace(gen_random_uuid()::text, '-', '');
  to_keys text[];
begin
  if k is null then raise exception 'Sign in to send a notification'; end if;
  if p_to is null or cardinality(p_to) < 1 or cardinality(p_to) > 10 then raise exception 'Choose who to tell'; end if;
  if p_kind not in ('assessment', 'mvp', 'fractional', 'media', 'referral', 'deal', 'devlead', 'request', 'sponsor', 'marketing') then
    raise exception 'Unknown kind of notification';
  end if;
  -- companies, members, partners and software houses only tell CloudWAV; CloudWAV can tell any login
  if not op and p_to <> array['operator'] then raise exception 'You can only send a notification to PartnerWAV'; end if;
  to_keys := array(select t from unnest(p_to) t where t <> 'operator');
  if exists (select 1 from unnest(to_keys) t where t !~ '^(partner|vendor|affiliate|investor|member|media):[^\s]{1,120}$') then
    raise exception 'Unknown recipient';
  end if;
  perform set_config('portal.notification', 'on', true);
  insert into public.portal_records (collection, id, data, readers, writers, is_public)
  values ('notifications', new_id,
    jsonb_build_object('id', new_id, 'kind', p_kind, 'title', left(coalesce(p_title, ''), 160), 'body', left(coalesce(p_body, ''), 400),
      'screen', left(coalesce(p_screen, ''), 60), 'to', to_jsonb(p_to), 'from', k,
      'at', to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
    to_keys, array[k], false);
  perform set_config('portal.notification', 'off', true);
  return new_id;
end $$;
revoke all on function public.post_notification(text[], text, text, text, text) from public;
grant execute on function public.post_notification(text[], text, text, text, text) to authenticated;

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

alter table public.portal_users add column if not exists temp_password_hash text;
-- Logins CloudWAV took access away from: these may be given to their company again later
create table if not exists public.portal_removed_logins (id uuid primary key, removed_at timestamptz not null default now());
alter table public.portal_removed_logins enable row level security;
revoke all on public.portal_removed_logins from anon, authenticated;

-- Creates (or resets) a company's login. Security review findings 7 and 9:
--   * the login is created here, so "Allow new users to sign up" can stay OFF in Supabase
--   * an email that already has a used login is refused, unless it is this same company's login being reset
--     (someone could have registered it first and kept a session open)
--   * the login goes to exactly the company id given, which must exist -- never matched by name
--   * every setup or reset signs the login out everywhere
create or replace function public.portal_setup_account(p_email text, p_role text, p_entity text, p_name text, p_password text)
returns jsonb language plpgsql security definer set search_path = public, extensions as $$
declare u uuid; used_at timestamptz; cur_role text; cur_entity text; mail text := lower(trim(coalesce(p_email, ''))); ent text := trim(coalesce(p_entity, ''));
        hash text; coll text;
begin
  if not public.is_portal_operator() then raise exception 'Only CloudWAV can set up accounts'; end if;
  if p_role is null or p_role not in ('partner', 'vendor', 'affiliate', 'investor', 'member', 'media') then raise exception 'Choose partner, vendor, affiliate, investor, member or media'; end if;
  if ent = '' then raise exception 'The account needs a company'; end if;
  if mail !~ '^[^[:space:]@]+@[^[:space:]@]+[.][^[:space:]@]+$' then raise exception 'Enter a valid email address'; end if;
  if p_password is null or length(p_password) < 8 then raise exception 'The temporary password needs at least 8 characters'; end if;
  coll := case p_role when 'vendor' then 'programs' when 'partner' then 'partnerProfiles' when 'investor' then 'investorProfiles' when 'member' then 'memberProfiles' when 'media' then 'mediaProfiles' else 'affiliateProfiles' end;
  if not exists (select 1 from public.portal_records where collection = coll and id = ent and coalesce(data->>'_deleted', '') <> 'true') then
    raise exception 'That company could not be found (%). It needs to be saved before it can have a login.', ent;
  end if;

  select id, last_sign_in_at into u, used_at from auth.users where lower(email) = mail limit 1;
  hash := crypt(p_password, gen_salt('bf'));
  if u is not null then
    select role, entity_id into cur_role, cur_entity from public.portal_users where id = u;
    if cur_role = 'operator' then raise exception 'That email belongs to a CloudWAV operator login'; end if;
    if cur_role is not null and (cur_role <> p_role or cur_entity <> ent) then
      raise exception 'That email already has a login for another company (% %). Remove that login first.', cur_role, cur_entity;
    end if;
    if cur_role is null and not exists (select 1 from public.portal_removed_logins x where x.id = u)
       and (used_at is not null or exists (select 1 from auth.sessions s where s.user_id = u)) then
      raise exception 'That email already has a login that has been used, so it can''t be given to a company. Use another email, or delete that login under Authentication > Users in Supabase first.';
    end if;
    update auth.users set encrypted_password = hash, email_confirmed_at = coalesce(email_confirmed_at, now()), updated_at = now() where id = u;
  else
    u := gen_random_uuid();
    insert into auth.users (instance_id, id, aud, role, email, encrypted_password, email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
                            created_at, updated_at, confirmation_token, recovery_token, email_change_token_new, email_change,
                            email_change_token_current, phone_change, phone_change_token, reauthentication_token)
    values ('00000000-0000-0000-0000-000000000000', u, 'authenticated', 'authenticated', mail, hash, now(),
            '{"provider":"email","providers":["email"]}'::jsonb, '{}'::jsonb, now(), now(), '', '', '', '', '', '', '', '');
    insert into auth.identities (id, user_id, provider_id, provider, identity_data, created_at, updated_at)
    values (gen_random_uuid(), u, u::text, 'email', jsonb_build_object('sub', u::text, 'email', mail, 'email_verified', true, 'phone_verified', false), now(), now());
  end if;
  -- sign the login out everywhere: any session someone already holds stops working
  delete from auth.sessions where user_id = u;
  delete from auth.refresh_tokens where user_id = u::text;
  delete from public.portal_removed_logins where id = u;

  insert into public.portal_users (id, email, role, entity_id, display_name, must_change_password, temp_password_hash)
  values (u, mail, p_role, ent, nullif(trim(coalesce(p_name, '')), ''), true, hash)
  on conflict (id) do update
    set email = excluded.email, role = excluded.role, entity_id = excluded.entity_id,
        display_name = coalesce(excluded.display_name, public.portal_users.display_name),
        must_change_password = true, temp_password_hash = excluded.temp_password_hash;
  return jsonb_build_object('id', u, 'email', mail, 'role', p_role, 'entity_id', ent);
end $$;
revoke all on function public.portal_setup_account(text, text, text, text, text) from public;
grant execute on function public.portal_setup_account(text, text, text, text, text) to authenticated;

-- Called by the person themselves once they have chosen their own password.
-- Only clears the flag if the password really is no longer the temporary one.
create or replace function public.portal_password_changed()
returns boolean language plpgsql security definer set search_path = public as $$
declare n int;
begin
  update public.portal_users p set must_change_password = false, temp_password_hash = null
   where p.id = auth.uid()
     and (p.temp_password_hash is null
          or exists (select 1 from auth.users u where u.id = p.id and u.encrypted_password is distinct from p.temp_password_hash));
  get diagnostics n = row_count;
  if n = 0 and public.portal_password_pending() then raise exception 'Choose your own password first'; end if;
  return n > 0;
end $$;
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
  if n > 0 then
    -- signed out everywhere, and the old password stops working
    insert into public.portal_removed_logins (id) values (p_user) on conflict (id) do update set removed_at = now();
    delete from auth.sessions where user_id = p_user;
    delete from auth.refresh_tokens where user_id = p_user::text;
    update auth.users set encrypted_password = extensions.crypt(gen_random_uuid()::text, extensions.gen_salt('bf')) where id = p_user;
  end if;
  return n > 0;
end $$;
revoke all on function public.portal_remove_account(uuid) from public;
grant execute on function public.portal_remove_account(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- 5b. Spam protection for the public forms (invite pages, partner landing pages, the vendor
--     assessment and the partner application). Every public submit function calls portal_spam_check():
--       * a hidden "hp" field that people never see; if a bot fills it in, the submission is dropped quietly
--       * a form sent faster than a person could type (under 1.5 seconds) is dropped quietly
--       * a CAPTCHA (Cloudflare Turnstile), checked here on the server, once its secret key is saved below
--       * limits: 5 submissions per connection per 10 minutes, 3 per email per form per day,
--         100 per form per hour
--     To turn the CAPTCHA on: create a free Turnstile widget at dash.cloudflare.com (Turnstile -> Add widget,
--     add your portal's domain), put its SITE key in the portal (Integrations -> Spam protection, as the
--     operator), and save its SECRET key here, in the SQL editor:
--       insert into public.portal_secrets(key, value) values ('turnstile_secret', 'YOUR-SECRET-KEY')
--         on conflict (key) do update set value = excluded.value;
--     The secret never goes into the portal page. Nobody can read portal_secrets through the API.
-- ---------------------------------------------------------------------------
create table if not exists public.portal_secrets (key text primary key, value text not null);
alter table public.portal_secrets enable row level security;
revoke all on public.portal_secrets from anon, authenticated;

create table if not exists public.portal_submit_log (
  id bigserial primary key, kind text not null, ref text, ip_hash text, email_hash text,
  at timestamptz not null default now());
create index if not exists portal_submit_log_at on public.portal_submit_log (at);
alter table public.portal_submit_log enable row level security;
revoke all on public.portal_submit_log from anon, authenticated;

-- the http extension lets the database ask Cloudflare whether a CAPTCHA answer is valid
do $$ begin
  create extension if not exists http with schema extensions;
exception when others then raise notice 'http extension not available: %', sqlerrm;
end $$;

create or replace function public.portal_client_ip()
returns text language sql stable as $$
  select nullif(trim(split_part(coalesce(
    (nullif(current_setting('request.headers', true), '')::json ->> 'x-forwarded-for'), ''), ',', 1)), '')
$$;

-- true = looks like a person; false = drop it quietly (the visitor still sees "thank you").
-- Raises an error the visitor sees for a failed CAPTCHA or when a limit is reached.
create or replace function public.portal_spam_check(p_kind text, p_ref text, p_email text, p_data jsonb)
returns boolean language plpgsql security definer set search_path = public as $$
declare
  secret text;
  token text := coalesce(p_data ->> 'captchaToken', '');
  ip text := public.portal_client_ip();
  iph text;
  emh text := md5(lower(coalesce(p_email, '')));
  st int;
  body text;
  ok boolean := false;
begin
  if coalesce(p_data ->> 'hp', '') <> '' then return false; end if;
  if coalesce(p_data ->> 'elapsedMs', '') ~ '^[0-9]{1,12}$' and (p_data ->> 'elapsedMs')::bigint < 1500 then return false; end if;

  select value into secret from public.portal_secrets where key = 'turnstile_secret';
  if coalesce(secret, '') <> '' then
    if length(token) not between 10 and 4096 or token !~ '^[A-Za-z0-9._:-]+$' then raise exception 'Please complete the security check'; end if;
    begin
      execute 'select status, content::text from extensions.http_post($1, $2, $3)' into st, body
        using 'https://challenges.cloudflare.com/turnstile/v0/siteverify',
              'secret=' || secret || '&response=' || token
                || case when length(ip) <= 64 and ip ~ '^[0-9a-fA-F:.]+$' then '&remoteip=' || ip else '' end,
              'application/x-www-form-urlencoded';
      ok := st = 200 and coalesce((body::json ->> 'success')::boolean, false);
    exception when others then ok := false;
    end;
    if not ok then raise exception 'The security check did not pass. Please try again'; end if;
  end if;

  iph := case when ip is null then null else md5('partnerwav:' || ip) end;
  delete from public.portal_submit_log where at < now() - interval '2 days';
  if iph is not null and (select count(*) from public.portal_submit_log
                          where ip_hash = iph and at > now() - interval '10 minutes') >= 5 then
    raise exception 'Too many sign-ups from this connection. Please wait a few minutes and try again';
  end if;
  if (select count(*) from public.portal_submit_log
      where email_hash = emh and kind = p_kind and ref is not distinct from p_ref and at > now() - interval '1 day') >= 3 then
    raise exception 'You have already signed up with this email address';
  end if;
  if (select count(*) from public.portal_submit_log
      where kind = p_kind and ref is not distinct from p_ref and at > now() - interval '1 hour') >= 100 then
    raise exception 'This form is getting a lot of sign-ups right now. Please try again a little later';
  end if;
  insert into public.portal_submit_log (kind, ref, ip_hash, email_hash) values (p_kind, p_ref, iph, emh);
  return true;
end $$;
revoke all on function public.portal_spam_check(text, text, text, jsonb) from public, anon, authenticated;
revoke all on function public.portal_client_ip() from public, anon, authenticated;

-- The public partner application (?apply=vendor). Goes through the same spam check, then into
-- partner_applications. Once this is in place, remove any policy that lets anon insert into
-- partner_applications directly, so this is the only way in.
create or replace function public.submit_partner_application(p_vendor uuid, p_data jsonb)
returns text language plpgsql security definer set search_path = public as $$
begin
  if p_data is null or jsonb_typeof(p_data) <> 'object' or length(p_data::text) > 6000 then
    raise exception 'The application is empty or too long';
  end if;
  if coalesce(trim(p_data ->> 'companyName'), '') = '' or coalesce(p_data ->> 'email', '') !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' then
    raise exception 'Please give your company name and a valid email address';
  end if;
  if not public.portal_spam_check('apply', p_vendor::text, p_data ->> 'email', p_data) then return 'ok'; end if;
  insert into public.partner_applications (vendor_id, first_name, last_name, company_name, country_code, phone_number,
      region, work_email, website, years_in_business, annual_revenue, num_employees, num_sales_people,
      vertical_markets, geographic_markets, status)
  values (p_vendor, left(p_data ->> 'firstName', 120), left(p_data ->> 'lastName', 120), left(p_data ->> 'companyName', 160),
      left(p_data ->> 'countryCode', 10), left(p_data ->> 'phone', 60), left(p_data ->> 'region', 120),
      left(lower(trim(p_data ->> 'email')), 160), left(p_data ->> 'website', 300), left(p_data ->> 'yearsInBusiness', 20),
      left(p_data ->> 'revenue', 60), left(p_data ->> 'numEmployees', 60), left(p_data ->> 'numSalesPeople', 20),
      left(p_data ->> 'verticalMarkets', 300), left(p_data ->> 'geographicMarkets', 300), 'pending');
  return 'ok';
end $$;
revoke all on function public.submit_partner_application(uuid, jsonb) from public;
grant execute on function public.submit_partner_application(uuid, jsonb) to anon, authenticated;

-- Finding 11: applications only arrive through submit_partner_application (spam-checked).
-- Nobody can write straight into the table any more; CloudWAV can still read and update them.
-- Second review, finding 1: applicants' names, emails and phone numbers are for CloudWAV only. Every other
-- rule on the table is replaced (the partner map reads approved applicants through its own view).
do $$ declare p record; begin
  if to_regclass('public.partner_applications') is not null then
    alter table public.partner_applications enable row level security;
    revoke all on public.partner_applications from public, anon;
    revoke insert on public.partner_applications from authenticated;
    grant select, update, delete on public.partner_applications to authenticated;
    for p in select policyname from pg_policies where schemaname = 'public' and tablename = 'partner_applications' loop
      execute format('drop policy %I on public.partner_applications', p.policyname);
    end loop;
    create policy "CloudWAV reads applications" on public.partner_applications
      for select to authenticated using (public.is_portal_operator());
    create policy "CloudWAV reviews applications" on public.partner_applications
      for update to authenticated using (public.is_portal_operator()) with check (public.is_portal_operator());
    create policy "CloudWAV removes applications" on public.partner_applications
      for delete to authenticated using (public.is_portal_operator());
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- 5c. Daily allowance for AI drafts (finding 10). Each AI flyer draft costs CloudWAV money, so the
--     flyer-assist function asks here first. 20 a day per person (200 for CloudWAV); to change it:
--       insert into public.portal_secrets(key, value) values ('ai_daily_limit_vendor', '40')
--         on conflict (key) do update set value = excluded.value;
-- ---------------------------------------------------------------------------
create or replace function public.portal_ai_quota(p_kind text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare who uuid := auth.uid(); r text; lim int; used int;
begin
  if who is null then raise exception 'Sign in first'; end if;
  select role into r from public.portal_users where id = who;
  if r is null then raise exception 'This login has no PartnerWAV role'; end if;
  if public.portal_password_pending() then raise exception 'Choose your own password first'; end if;
  if coalesce(p_kind, '') !~ '^[a-z-]{1,30}$' then raise exception 'Unknown AI feature'; end if;
  lim := coalesce((select value::int from public.portal_secrets where key = 'ai_daily_limit_' || r and value ~ '^[0-9]{1,6}$'),
                  case when r = 'operator' then 200 else 20 end);
  perform pg_advisory_xact_lock(hashtext('portal-ai:' || who::text));   -- two clicks at once can't both slip under the limit
  select count(*) into used from public.portal_submit_log
   where kind = 'ai:' || p_kind and ref = who::text and at > now() - interval '24 hours';
  if used >= lim then return jsonb_build_object('ok', false, 'limit', lim, 'used', used); end if;
  insert into public.portal_submit_log (kind, ref) values ('ai:' || p_kind, who::text);
  return jsonb_build_object('ok', true, 'limit', lim, 'used', used + 1);
end $$;
revoke all on function public.portal_ai_quota(text) from public;
grant execute on function public.portal_ai_quota(text) to authenticated;

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

-- A member may change or remove a resource file only while it is waiting for review, in a folder of their own
-- pending submission, and never a file a published resource uses (second review, finding 3).
create or replace function public.portal_member_can_change_file(p_name text)
returns boolean language sql stable security definer set search_path = public as $$
  select (storage.foldername(p_name))[1] = 'resources'
     and exists (select 1 from public.portal_records r where r.collection = 'pendingResources'
                  and r.id = (storage.foldername(p_name))[2] and public.portal_key() = any(r.writers))
     and not exists (select 1 from public.portal_records r where r.collection = 'resources'
                      and (r.id = (storage.foldername(p_name))[2] or r.data ->> 'filePath' = p_name));
$$;
revoke all on function public.portal_member_can_change_file(text) from public;
grant execute on function public.portal_member_can_change_file(text) to authenticated;

create policy "portal-files read" on storage.objects
  for select to authenticated using (
    bucket_id = 'portal-files'
    and (((storage.foldername(name))[1] = 'resources'                -- a resource's files: only under resources/
          and exists (select 1 from public.portal_records r           -- RLS on portal_records applies here
                      where r.collection in ('resources', 'pendingResources')
                        and r.id = (storage.foldername(name))[2]))
         -- an approved change to a resource keeps the file it was reviewed with (only CloudWAV writes resources)
         or ((storage.foldername(name))[1] = 'resources'
             and exists (select 1 from public.portal_records r where r.collection = 'resources' and r.data ->> 'filePath' = name))
         -- an uploaded outside agreement: whoever can see the agreement record can open its file
         or ((storage.foldername(name))[1] = 'agreements'
             and exists (select 1 from public.portal_records r
                         where r.collection = 'agreements' and r.id = (storage.foldername(name))[2])))
  );

create policy "portal-files upload" on storage.objects
  for insert to authenticated with check (
    bucket_id = 'portal-files'
    and not public.portal_password_pending()
    and (((storage.foldername(name))[1] = 'resources'
          and (public.is_portal_operator() or public.portal_member_can_change_file(name)))
         -- outside agreements are uploaded by CloudWAV only
         or ((storage.foldername(name))[1] = 'agreements' and public.is_portal_operator()))
  );

create policy "portal-files update" on storage.objects
  for update to authenticated
  using (bucket_id = 'portal-files' and (public.is_portal_operator() or (owner = auth.uid() and public.portal_member_can_change_file(name))))
  with check (bucket_id = 'portal-files' and (public.is_portal_operator() or (owner = auth.uid() and public.portal_member_can_change_file(name))));

create policy "portal-files delete" on storage.objects
  for delete to authenticated using (bucket_id = 'portal-files' and (public.is_portal_operator() or (owner = auth.uid() and public.portal_member_can_change_file(name))));

-- ---------------------------------------------------------------------------
-- 8. Check (optional): after signing in to the portal as the operator and clicking
--    Cloud Data -> "Save all starter records to Supabase", this should list the collections.
-- ---------------------------------------------------------------------------
-- select collection, count(*) from public.portal_records group by 1 order by 1;

-- ---------------------------------------------------------------------------
-- 8b. A bigger MVP Builder request (route 'devlead') becomes a Dev Lead in the database as soon as it is sent, from
--     any login: a Dev Lead is a project referral for CloudWAV to route, so it never waits for a browser to save it.
--     It is unassigned (status 'new') until CloudWAV sends it to a software house. Re-running this file adds any that
--     were sent before this rule existed.
-- ---------------------------------------------------------------------------
create or replace function public.portal_make_devlead(p_req_id text, p_req jsonb)
returns void language plpgsql security definer set search_path = public as $$
begin
  if p_req ->> 'route' is distinct from 'devlead' or p_req ->> 'kind' is distinct from 'mvp' then return; end if;
  perform set_config('portal.system', 'on', true);
  insert into public.portal_records (collection, id, data, readers, writers, is_public)
  values ('projectReferrals', 'dl-' || p_req_id, jsonb_build_object(
      'id', 'dl-' || p_req_id, 'source', 'mvp', 'mvpRequestId', p_req_id, 'movedFrom', '', 'houseId', '',
      'referrerKey', 'operator:', 'level', 'referral', 'cosellLead', 'cloudwav',
      'client', jsonb_build_object('company', left(coalesce(p_req ->> 'requesterName', ''), 160), 'contact', '', 'email', '', 'phone', ''),
      'need', left(coalesce(p_req ->> 'details', ''), 1500), 'budget', 0, 'currency', 'USD',
      'timeline', left(coalesce(p_req ->> 'timeline', ''), 60), 'disclosed', true,
      'status', 'new', 'registeredAt', to_char(now() at time zone 'Asia/Bangkok', 'YYYY-MM-DD'),
      'respondBy', '', 'quoteBy', '', 'closeBy', to_char((now() at time zone 'Asia/Bangkok') + interval '30 days', 'YYYY-MM-DD'),
      'acceptedAt', '', 'protectedUntil', '', 'contractValue', null, 'wonAt', '', 'quoteValue', null, 'rejectReason', '',
      'payments', '[]'::jsonb, 'payouts', '[]'::jsonb, 'thread', '[]'::jsonb, 'termsSnapshot', null,
      'progress', jsonb_build_array(jsonb_build_object('at', to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
          'stage', 'Waiting for a software house', 'note', ''))),
    array['operator:'], array['operator:'], false)
  on conflict (collection, id) do nothing;
  perform set_config('portal.system', 'off', true);
end $$;
revoke all on function public.portal_make_devlead(text, jsonb) from public, anon, authenticated;

create or replace function public.portal_devlead_trigger()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  perform public.portal_make_devlead(new.id, new.data);
  return new;
end $$;
revoke all on function public.portal_devlead_trigger() from public, anon, authenticated;

drop trigger if exists portal_devlead_from_request on public.portal_records;
create trigger portal_devlead_from_request after insert on public.portal_records
  for each row when (new.collection = 'serviceRequests') execute function public.portal_devlead_trigger();

-- add the Dev Leads for bigger requests that were sent before this (safe to run again)
do $$
declare r record;
begin
  for r in select id, data from public.portal_records where collection = 'serviceRequests' and data ->> 'route' = 'devlead' loop
    perform public.portal_make_devlead(r.id, r.data);
  end loop;
end $$;

-- ---------------------------------------------------------------------------
-- 9. Tell the Supabase API about the new table and functions right away
--    (otherwise the portal can say "Could not find the table 'public.portal_records' in the schema cache")
-- ---------------------------------------------------------------------------
notify pgrst, 'reload schema';
