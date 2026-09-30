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

-- ===== messages
select pg_temp.as_user('00000000-0000-0000-0000-000000000003'); set role authenticated;
insert into portal_records(collection,id,data,readers,writers) values ('conversations','partner:siam-digital__vendor:intelsense','{"participants":["partner:siam-digital","vendor:intelsense"]}','{partner:siam-digital,vendor:intelsense}','{partner:siam-digital,vendor:intelsense}');
insert into portal_records(collection,id,data,readers,writers) values ('messages','m1','{"from":"partner:siam-digital","text":"hi"}','{partner:siam-digital,vendor:intelsense}','{partner:siam-digital}');
select t('partner can message a vendor', (select count(*) from portal_records where collection='messages') = 1);
select t('cannot send a message as someone else', fails($$insert into portal_records(collection,id,data,readers,writers) values ('messages','m2','{"from":"vendor:intelsense","text":"fake"}','{partner:siam-digital,vendor:intelsense}','{partner:siam-digital}')$$));
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000002'); set role authenticated;
select t('the vendor sees the message', (select count(*) from portal_records where collection='messages') = 1);
insert into portal_records(collection,id,data,readers,writers) values ('messages','m3','{"from":"vendor:intelsense","text":"hello"}','{partner:siam-digital,vendor:intelsense}','{vendor:intelsense}');
select t('vendor replies', (select count(*) from portal_records where collection='messages') = 2);
select t('vendor cannot edit the partner''s message', (select count(*) from (select 1) x where not fails($$update portal_records set data='{"from":"partner:siam-digital","text":"edited"}' where id='m1'$$)) = 1 and (select data->>'text' from portal_records where id='m1') = 'hi');
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000004'); set role authenticated;
select t('a third partner cannot read the conversation', (select count(*) from portal_records where collection in ('messages','conversations')) = 0);
reset role;

-- ===== file storage
select pg_temp.as_user('00000000-0000-0000-0000-000000000002'); set role authenticated;
insert into portal_records(collection,id,data,readers,writers) values ('pendingResources','res-1','{"id":"res-1","status":"pending","ownerKey":"vendor:intelsense"}','{vendor:intelsense}','{vendor:intelsense}');
insert into storage.objects(bucket_id,name) values ('portal-files','resources/res-1/deck.pdf');
select t('submitter can upload the file for their resource', (select count(*) from storage.objects) = 1);
select t('cannot upload a file for someone else''s resource', fails($$insert into storage.objects(bucket_id,name) values ('portal-files','resources/i1/x.pdf')$$));
select t('cannot upload outside resources/', fails($$insert into storage.objects(bucket_id,name) values ('portal-files','other/res-1/x.pdf')$$));
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000004'); set role authenticated;
select t('other users cannot see the pending file', (select count(*) from storage.objects) = 0);
select t('other users cannot upload into it', fails($$insert into storage.objects(bucket_id,name) values ('portal-files','resources/res-1/evil.pdf')$$));
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000001'); set role authenticated;
select t('CloudWAV sees the pending file', (select count(*) from storage.objects) = 1);
insert into portal_records(collection,id,data,readers,writers) values ('resources','res-1','{"id":"res-1","status":"published","ownerKey":"vendor:intelsense"}','{*}','{vendor:intelsense}');
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000004'); set role authenticated;
select t('once published, every signed-in user can open the file', (select count(*) from storage.objects) = 1);
reset role;
set role anon;
select t('anonymous visitors cannot open files', (select count(*) from storage.objects) = 0);
reset role;

-- ===== software project referrals + agreements
select pg_temp.as_user('00000000-0000-0000-0000-000000000001'); set role authenticated;
insert into portal_records(collection,id,data,readers,writers) values ('softwareHouses','sh-1','{"id":"sh-1","status":"active"}','{*}','{}');
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000003'); set role authenticated;
select t('partner sees active software houses', (select count(*) from portal_records where collection='softwareHouses') = 1);
select t('partner cannot add a software house', fails($$insert into portal_records(collection,id,data,readers,writers) values ('softwareHouses','sh-2','{}','{*}','{partner:siam-digital}')$$));
insert into portal_records(collection,id,data,readers,writers) values ('projectReferrals','r1','{"id":"r1","houseId":"sh-1","referrerKey":"partner:siam-digital","status":"registered","payments":[],"payouts":[],"contractValue":null,"termsSnapshot":null,"acceptedAt":""}','{partner:siam-digital}','{partner:siam-digital}');
select t('partner registers a referral', (select count(*) from portal_records where collection='projectReferrals') = 1);
select t('partner cannot mark own referral won', fails($$update portal_records set data = jsonb_set(data,'{status}','"won"') where id='r1'$$));
select t('partner cannot add collected payments', fails($$update portal_records set data = jsonb_set(data,'{payments}','[{"amount":1000000}]') where id='r1'$$));
select t('partner cannot change the fee terms', fails($$update portal_records set data = jsonb_set(data,'{termsSnapshot}','{"referralRate":50}') where id='r1'$$));
update portal_records set data = jsonb_set(data,'{thread}','[{"text":"client wants a demo"}]') where id='r1';
select t('partner can add notes', (select data->'thread'->0->>'text' from portal_records where id='r1') = 'client wants a demo');
insert into portal_records(collection,id,data,readers,writers) values ('agreements','a1','{"id":"a1","kind":"partner","status":"requested","signers":[]}','{partner:siam-digital,vendor:intelsense}','{partner:siam-digital}');
select t('partner requests an agreement', (select count(*) from portal_records where collection='agreements') = 1);
select t('partner cannot mark an agreement signed', fails($$update portal_records set data = jsonb_set(jsonb_set(data,'{status}','"signed"'),'{signedAt}','"2026-10-01"') where id='a1'$$));
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000004'); set role authenticated;
select t('other partners cannot see the referral or agreement', (select count(*) from portal_records where collection in ('projectReferrals','agreements')) = 0);
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000001'); set role authenticated;
update portal_records set data = data || '{"status":"won","contractValue":1000000,"payments":[{"amount":500000}],"termsSnapshot":{"referralRate":10}}'::jsonb where id='r1';
update portal_records set data = data || '{"status":"signed","signedAt":"2026-10-01"}'::jsonb where id='a1';
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000003'); set role authenticated;
select t('partner sees CloudWAV''s updates', (select data->>'status' from portal_records where id='r1') = 'won' and (select data->>'status' from portal_records where id='a1') = 'signed');
update portal_records set data = jsonb_set(data,'{thread}','[{"text":"thanks"}]') where id='r1';
select t('partner can still add notes after it is won', (select data->'thread'->0->>'text' from portal_records where id='r1') = 'thanks');
reset role;

-- ===== invite-only affiliate offers: public sign-ups through submit_affiliate_signup()
select pg_temp.as_user('00000000-0000-0000-0000-000000000001'); set role authenticated;
insert into portal_records(collection,id,data,readers,writers,is_public) values
 ('affiliatePrograms','inv-live','{"id":"inv-live","vendorId":"botnoi","audience":"invite","status":"approved"}','{*}','{vendor:botnoi}',true),
 ('affiliatePrograms','inv-pending','{"id":"inv-pending","vendorId":"botnoi","audience":"invite","status":"pending"}','{vendor:botnoi}','{vendor:botnoi}',false),
 ('affiliatePrograms','mkt-live','{"id":"mkt-live","vendorId":"botnoi","status":"approved"}','{*}','{vendor:botnoi}',true);
reset role;
select pg_temp.as_user(''); set role anon;
select t('anon signs up on a live invite page', public.submit_affiliate_signup('inv-live', '{"name":"Nok","email":"Nok@Example.co.th","kind":"referrer","consent":true,"phone":"0812345678"}') like 'sg-%');
select t('anon business sign-up with a referrer', public.submit_affiliate_signup('inv-live', '{"name":"Som Shop","email":"som@shop.th","kind":"business","consent":true,"referredBy":"sg-abc"}') like 'sg-%');
select t('sign-up needs consent', fails($$select public.submit_affiliate_signup('inv-live', '{"name":"A","email":"a@b.co","consent":false}')$$));
select t('sign-up needs a valid email', fails($$select public.submit_affiliate_signup('inv-live', '{"name":"A","email":"nope","consent":true}')$$));
select t('no sign-ups on an unapproved invite', fails($$select public.submit_affiliate_signup('inv-pending', '{"name":"A","email":"a@b.co","consent":true}')$$));
select t('no sign-ups on a marketplace offer', fails($$select public.submit_affiliate_signup('mkt-live', '{"name":"A","email":"a@b.co","consent":true}')$$));
select t('anon cannot insert sign-ups directly', fails($$insert into portal_records(collection,id,data,readers,writers) values ('affiliateSignups','sg-x','{}','{vendor:botnoi}','{}')$$));
select t('anon cannot read sign-ups', (select count(*) from portal_records where collection='affiliateSignups') = 0);
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000005'); set role authenticated;
select t('the owning vendor reads its sign-ups', (select count(*) from portal_records where collection='affiliateSignups') = 2);
select t('sign-up is stored cleaned (email lower-cased, vendor set)', (select count(*) from portal_records where collection='affiliateSignups' and data->>'email'='nok@example.co.th' and data->>'vendorId'='botnoi') = 1);
select t('vendor cannot add fake sign-ups', fails($$insert into portal_records(collection,id,data,readers,writers) values ('affiliateSignups','sg-y','{"vendorId":"botnoi"}','{vendor:botnoi}','{vendor:botnoi}')$$));
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000002'); set role authenticated;
select t('other vendors cannot read the sign-ups', (select count(*) from portal_records where collection='affiliateSignups') = 0);
select t('signed-in members can use the invite page too', public.submit_affiliate_signup('inv-live', '{"name":"Ian","email":"ian@intelsense.ai","consent":true}') like 'sg-%');
reset role;

select case when ok then 'PASS ' else 'FAIL ' end || name from public.results;
