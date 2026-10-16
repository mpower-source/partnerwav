-- Behaviour tests for supabase/portal_access_requests.sql. Run by tests/test_sql.sh after portal_records.sql.
-- Uses its own names (ar_*) because it shares a database with test_portal_records.sql.
\set ON_ERROR_STOP off
\pset tuples_only on
create table public.ar_results(name text, ok boolean);
grant insert on public.ar_results to anon, authenticated;
create or replace function public.ar_t(name text, ok boolean) returns void language sql security definer as $$ insert into public.ar_results values (name, coalesce(ok,false)) $$;
grant execute on function public.ar_t(text, boolean) to anon, authenticated;
create or replace function public.ar_fails(sql text) returns boolean language plpgsql as $$
begin execute sql; return false; exception when others then return true; end $$;
grant execute on function public.ar_fails(text) to anon, authenticated;
create or replace function pg_temp.ar_as(uid text) returns void language plpgsql as $$
begin perform set_config('request.jwt.claim.sub', uid, false); end $$;

-- the newcomer's login exists (created at sign-up, no role yet); the operator is the harness's operator login
insert into auth.users (id,email) values ('00000000-0000-0000-0000-0000000000a1','newbie@example.test') on conflict do nothing;
select pg_temp.ar_as('00000000-0000-0000-0000-000000000001');
set role authenticated;
insert into portal_records(collection,id,data,readers,writers,is_public) values
 ('memberProfiles','mem-bangkok','{"id":"mem-bangkok","name":"Bangkok members"}','{}','{}',false),
 ('investorProfiles','inv-one','{"id":"inv-one","name":"Investor one"}','{}','{}',false);
reset role;

-- a visitor (anon) asks for access; the spam fields are clean and the form took over 1.5s
set role anon;
select public.ar_t('sign-up request is stored as pending', (public.portal_request_access('{"name":"New Person","email":"Newbie@Example.test","phone":"","kind":"member","hp":"","elapsedMs":5000}'::jsonb) ->> 'status') = 'pending');
select public.ar_t('the request gives no role yet', not exists (select 1 from public.portal_users where email = 'newbie@example.test'));
select public.ar_t('Promoter is stored as media', (public.portal_request_access('{"name":"Promo","email":"promo@example.test","kind":"media","elapsedMs":5000}'::jsonb) ->> 'status') = 'pending');
select public.ar_t('a honeypot-filled request is thanked but not stored', (public.portal_request_access('{"name":"Bot","email":"bot@example.test","kind":"member","hp":"x","elapsedMs":5000}'::jsonb) ->> 'status') = 'pending');
select public.ar_t('an unknown kind is refused', public.ar_fails('select public.portal_request_access(''{"name":"X","email":"x@example.test","kind":"operator","elapsedMs":5000}''::jsonb)'));
select public.ar_t('a bad email is refused', public.ar_fails('select public.portal_request_access(''{"name":"X","email":"nope","kind":"member","elapsedMs":5000}''::jsonb)'));
select public.ar_t('a visitor cannot read the requests', public.ar_fails('select count(*) from public.portal_access_requests'));
select public.ar_t('a visitor cannot approve', public.ar_fails('select public.portal_approve_access((select id from public.portal_access_requests where email = ''newbie@example.test''), ''mem-bangkok'')'));
reset role;

-- a person who has a login but no role cannot approve their own request
select pg_temp.ar_as('00000000-0000-0000-0000-0000000000a1');
set role authenticated;
select public.ar_t('a person without a role cannot approve their own request', public.ar_fails('select public.portal_approve_access((select id from public.portal_access_requests where email = ''newbie@example.test''), ''mem-bangkok'')'));
select public.ar_t('a person without a role sees no requests', (select count(*) = 0 from public.portal_access_requests));
reset role;

-- the operator approves: the login gets the Member role for the company given
select pg_temp.ar_as('00000000-0000-0000-0000-000000000001');
set role authenticated;
select public.ar_t('the operator approves a Member request into a company', (public.portal_approve_access((select id from public.portal_access_requests where email = 'newbie@example.test'), 'mem-bangkok') ->> 'role') = 'member');
select public.ar_t('the approved login has the role and company', exists (select 1 from public.portal_users where id = '00000000-0000-0000-0000-0000000000a1' and role = 'member' and entity_id = 'mem-bangkok'));
select public.ar_t('the request is marked approved', (select status = 'approved' from public.portal_access_requests where email = 'newbie@example.test'));
select public.ar_t('approval for an unknown company is refused', public.ar_fails('select public.portal_approve_access((select id from public.portal_access_requests where email = ''promo@example.test''), ''no-such-company'')'));
select public.ar_t('approving someone who never created a login is refused', public.ar_fails('select public.portal_approve_access((select id from public.portal_access_requests where email = ''promo@example.test''), ''inv-one'')'));
select public.ar_t('the operator can decline a request', public.portal_decline_access((select id from public.portal_access_requests where email = 'promo@example.test')));
reset role;

-- the honeypot request was not stored (checked as the owner, since visitors can't read the table)
select public.ar_t('a honeypot-filled request is not stored', not exists (select 1 from public.portal_access_requests where email = 'bot@example.test'));

-- the operator is told about each new request (as a notification addressed to 'operator')
select public.ar_t('a new request tells the operator', exists (select 1 from public.portal_records where collection = 'notifications' and data ->> 'kind' = 'request' and data -> 'to' = '["operator"]' and data ->> 'title' like 'New access request%' and data ->> 'ref' = (select id::text from public.portal_access_requests where email = 'newbie@example.test')));
-- a declined person can ask again (the request goes back to pending for the operator)
set role anon;
select public.ar_t('a declined person can ask again', (public.portal_request_access('{"name":"Promo","email":"promo@example.test","kind":"media","elapsedMs":5000}'::jsonb) ->> 'status') = 'pending');
reset role;
select public.ar_t('the re-request is pending again', (select status = 'pending' from public.portal_access_requests where email = 'promo@example.test'));

-- once approved, signing up again does not change the role or the request
set role anon;
select public.ar_t('an approved person signing up again keeps their approval', (public.portal_request_access('{"name":"New Person","email":"newbie@example.test","kind":"investor","elapsedMs":5000}'::jsonb) ->> 'status') = 'approved');
reset role;
select 'PASS ' || name from public.ar_results where ok order by name;
select 'FAIL ' || name from public.ar_results where not ok order by name;
drop table public.ar_results;
