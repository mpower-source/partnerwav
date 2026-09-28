-- Behaviour tests for supabase/portal_records.sql. Run by tests/test_sql.sh against a local Postgres.
\set ON_ERROR_STOP off
\pset tuples_only on
insert into public.portal_users (id,email,role,entity_id,display_name) values
 ('00000000-0000-0000-0000-000000000001','ops@cloudwav.test','operator',null,'Ops'),
 ('00000000-0000-0000-0000-000000000002','vendor@intelsense.test','vendor','intelsense','Intelsense'),
 ('00000000-0000-0000-0000-000000000003','partner@siamdigital.test','partner','siam-digital','Siam'),
 ('00000000-0000-0000-0000-000000000004','partner@gulfcoast.test','partner','gulf-coast','Gulf'),
 ('00000000-0000-0000-0000-000000000005','vendor@botnoi.test','vendor','botnoi','Botnoi');

create or replace function pg_temp.as_user(uid text) returns void language plpgsql as $$
begin perform set_config('request.jwt.claim.sub', uid, false); end $$;
create table public.results(name text, ok boolean);
grant insert on public.results to anon, authenticated;
create or replace function public.t(name text, ok boolean) returns void language sql security definer as $$ insert into public.results values (name, coalesce(ok,false)) $$;
grant execute on function public.t(text, boolean) to anon, authenticated;
-- run an statement expecting failure
create or replace function public.fails(sql text) returns boolean language plpgsql as $$
begin execute sql; return false; exception when others then return true; end $$;
grant execute on function public.fails(text) to anon, authenticated;

-- ===== operator seeds starter data
select pg_temp.as_user('00000000-0000-0000-0000-000000000001');
set role authenticated;
insert into portal_records(collection,id,data,readers,writers,is_public) values
 ('programs','intelsense','{"id":"intelsense","name":"Intelsense AI","tiers":[1],"status":"active"}','{*}','{vendor:intelsense}',true),
 ('programs','botnoi','{"id":"botnoi","name":"Botnoi","tiers":[1],"status":"active"}','{*}','{vendor:botnoi}',true),
 ('shopProducts','shop-free','{"id":"shop-free","price":0}','{*}','{}',false),
 ('shopProducts','shop-paid','{"id":"shop-paid","price":149}','{*}','{}',false),
 ('mspProspects','apl-x','{"id":"apl-x"}','{}','{}',false),
 ('landingPages','lp-pub','{"id":"lp-pub","status":"published"}','{vendor:botnoi}','{}',true),
 ('landingPages','lp-draft','{"id":"lp-draft","status":"draft"}','{vendor:botnoi}','{}',false);
select t('operator can seed', (select count(*) from portal_records) = 7);
reset role;

-- ===== anonymous visitors see only public rows
set role anon;
select t('anon sees only public rows (2 programs + published page)', (select count(*) from portal_records) = 3);
select t('anon cannot insert', fails($$insert into portal_records(collection,id,data) values ('deals','x','{}')$$));
reset role;

-- ===== partner Siam
select pg_temp.as_user('00000000-0000-0000-0000-000000000003');
set role authenticated;
select t('partner sees programs + published shop items, not prospects/drafts', (select count(*) from portal_records) = 5);
select t('partner cannot see MSP prospects', (select count(*) from portal_records where collection='mspProspects') = 0);
insert into portal_records(collection,id,data,readers,writers) values ('deals','d1','{"id":"d1","status":"pending","pricingCheck":"","partnerId":"siam-digital","programId":"intelsense"}','{partner:siam-digital,vendor:intelsense}','{partner:siam-digital}');
select t('partner can register a pending deal', (select count(*) from portal_records where id='d1') = 1);
select t('partner cannot approve their own deal', fails($$update portal_records set data = jsonb_set(data,'{status}','"approved"') where id='d1'$$));
select t('partner cannot insert a deal already approved', fails($$insert into portal_records(collection,id,data,readers,writers) values ('deals','d2','{"id":"d2","status":"approved"}','{partner:siam-digital}','{partner:siam-digital}')$$));
select t('partner cannot set the pricing check', fails($$update portal_records set data = jsonb_set(data,'{pricingCheck}','"fair"') where id='d1'$$));
update portal_records set data = jsonb_set(data,'{notes}','"hi"') where id='d1';
select t('partner can edit other deal fields', (select data->>'notes' from portal_records where id='d1') = 'hi');
select t('partner cannot hand the deal to someone else', fails($$update portal_records set writers='{partner:gulf-coast}' where id='d1'$$));
select t('partner cannot create records for another partner', fails($$insert into portal_records(collection,id,data,readers,writers) values ('leads','l9','{}','{partner:gulf-coast}','{partner:gulf-coast}')$$));
select t('partner cannot add shop products', fails($$insert into portal_records(collection,id,data,readers,writers) values ('shopProducts','sp9','{}','{*}','{partner:siam-digital}')$$));
select t('partner cannot edit a vendor profile', (select count(*) from (select 1) x where not fails($$update portal_records set data='{"hacked":true}' where collection='programs' and id='intelsense'$$)) = 1 and (select data->>'name' from portal_records where collection='programs' and id='intelsense') = 'Intelsense AI');
select t('partner cannot create a program', fails($$insert into portal_records(collection,id,data,readers,writers,is_public) values ('programs','siam-digital','{}','{*}','{vendor:siam-digital}',true)$$));
select t('partner cannot make shared-edit records outside community', fails($$insert into portal_records(collection,id,data,readers,writers) values ('leads','l8','{}','{*}','{*}')$$));
insert into portal_records(collection,id,data,readers,writers) values ('threads','t1','{"id":"t1","posts":[]}','{*}','{*}');
select t('anyone can start a community thread', (select count(*) from portal_records where id='t1') = 1);
-- shop orders
insert into portal_records(collection,id,data,readers,writers) values ('shopOrders','o-free','{"id":"o-free","productId":"shop-free","price":0,"status":"paid","paidAt":"now","buyer":"partner:siam-digital"}','{partner:siam-digital}','{partner:siam-digital}');
select t('free product order can be paid straight away', (select count(*) from portal_records where id='o-free') = 1);
select t('paid product cannot be self-marked paid', fails($$insert into portal_records(collection,id,data,readers,writers) values ('shopOrders','o-paid','{"id":"o-paid","productId":"shop-paid","price":0,"status":"paid","paidAt":"now","buyer":"partner:siam-digital"}','{partner:siam-digital}','{partner:siam-digital}')$$));
insert into portal_records(collection,id,data,readers,writers) values ('shopOrders','o-paid','{"id":"o-paid","productId":"shop-paid","price":149,"status":"awaiting","paidAt":"","buyer":"partner:siam-digital"}','{partner:siam-digital}','{partner:siam-digital}');
select t('paid product order starts awaiting payment', (select data->>'status' from portal_records where id='o-paid') = 'awaiting');
-- upsert path (what the portal uses)
insert into portal_records(collection,id,data,readers,writers) values ('deals','d1','{"id":"d1","status":"pending","pricingCheck":"","notes":"upserted"}','{partner:siam-digital,vendor:intelsense}','{partner:siam-digital}')
  on conflict (collection,id) do update set data = excluded.data, readers = excluded.readers, writers = excluded.writers;
select t('upsert of own deal works', (select data->>'notes' from portal_records where id='d1') = 'upserted');
reset role;

-- ===== operator approves; partner can then upsert other fields of the approved deal
select pg_temp.as_user('00000000-0000-0000-0000-000000000001'); set role authenticated;
update portal_records set data = jsonb_set(data,'{status}','"approved"') where id='d1';
update portal_records set data = jsonb_set(jsonb_set(data,'{status}','"paid"'),'{paidAt}','"x"') where id='o-paid';
select t('operator sees everything (11 rows)', (select count(*) from portal_records) = 11);
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000003'); set role authenticated;
insert into portal_records(collection,id,data,readers,writers) values ('deals','d1','{"id":"d1","status":"approved","pricingCheck":"","notes":"seen","unreadPartner":false}','{partner:siam-digital,vendor:intelsense}','{partner:siam-digital}')
  on conflict (collection,id) do update set data = excluded.data, readers = excluded.readers, writers = excluded.writers;
select t('partner can upsert an approved deal without changing its status', (select data->>'notes' from portal_records where id='d1') = 'seen');
reset role;

-- ===== other partner and vendors
select pg_temp.as_user('00000000-0000-0000-0000-000000000004'); set role authenticated;
select t('another partner cannot see Siam deals or orders', (select count(*) from portal_records where collection in ('deals','shopOrders')) = 0);
select t('another partner cannot delete Siam deal', (select count(*) from (select 1) x where not fails($$delete from portal_records where id='d1'$$)) = 1);
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000003'); set role authenticated;
select t('deal still there after the other partner tried to delete it', (select count(*) from portal_records where id='d1') = 1);
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000002'); set role authenticated;
select t('vendor sees deals in their program', (select count(*) from portal_records where collection='deals') = 1);
select t('vendor cannot edit partner deals', (select count(*) from (select 1) x where not fails($$update portal_records set data='{}' where id='d1'$$)) = 1 and (select data->>'notes' from portal_records where id='d1') = 'seen');
update portal_records set data = jsonb_set(data,'{name}','"Intelsense AI (edited)"') where collection='programs' and id='intelsense';
select t('vendor can edit their own profile', (select data->>'name' from portal_records where collection='programs' and id='intelsense') = 'Intelsense AI (edited)');
select t('vendor cannot change their commission tiers', fails($$update portal_records set data = jsonb_set(data,'{tiers}','[99]') where collection='programs' and id='intelsense'$$));
select t('vendor cannot edit another vendor', (select count(*) from (select 1) x where not fails($$update portal_records set data='{}' where collection='programs' and id='botnoi'$$)) = 1 and (select data->>'name' from portal_records where collection='programs' and id='botnoi') = 'Botnoi');
insert into portal_records(collection,id,data,readers,writers) values ('incentives','i1','{"id":"i1","status":"pending","vendorId":"intelsense"}','{vendor:intelsense}','{vendor:intelsense}');
select t('vendor submits an incentive for review', (select count(*) from portal_records where id='i1') = 1);
select t('vendor cannot approve own incentive', fails($$update portal_records set data = jsonb_set(data,'{status}','"approved"') where id='i1'$$));
select t('vendor cannot see draft landing pages of other vendors', (select count(*) from portal_records where collection='landingPages') = 1);
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000005'); set role authenticated;
select t('botnoi vendor sees its landing pages (both)', (select count(*) from portal_records where collection='landingPages') = 2);
select t('botnoi cannot see Intelsense pending incentive', (select count(*) from portal_records where id='i1') = 0);
reset role;

-- ===== account with no role sees nothing but public
select pg_temp.as_user('00000000-0000-0000-0000-000000000006'); set role authenticated;
select t('login without a portal role sees only public rows', (select count(*) from portal_records where not is_public) = 0);
select t('login without a portal role cannot write', fails($$insert into portal_records(collection,id,data,readers,writers) values ('threads','t9','{}','{*}','{*}')$$));
reset role;

select case when ok then 'PASS ' else 'FAIL ' end || name from public.results;
