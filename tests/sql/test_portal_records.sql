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
insert into portal_records(collection,id,data,readers,writers) values ('deals','d1','{"id":"d1","status":"pending","pricingCheck":"","notes":"upserted","partnerId":"siam-digital"}','{partner:siam-digital,vendor:intelsense}','{partner:siam-digital}')
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
insert into portal_records(collection,id,data,readers,writers) values ('deals','d1','{"id":"d1","status":"approved","pricingCheck":"","notes":"seen","unreadPartner":false,"partnerId":"siam-digital"}','{partner:siam-digital,vendor:intelsense}','{partner:siam-digital}')
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
select t('vendor cannot plant its own return summary', fails($$insert into portal_records(collection,id,data,readers,writers,is_public) values ('houseSummaries','intelsense','{"id":"intelsense","roi":99999}','{vendor:intelsense}','{vendor:intelsense}',false)$$));
select t('vendor cannot award itself the Reseller Ready badge', fails($$update portal_records set data = data || '{"resellerReady":{"at":"2026-10-07","builtBy":"Us"}}' where collection='programs' and id='intelsense'$$));
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

-- ===== partner landing pages: the partner's own pages; public sign-ups become that partner's leads
select pg_temp.as_user('00000000-0000-0000-0000-000000000003'); set role authenticated;
insert into portal_records(collection,id,data,readers,writers,is_public) values
 ('partnerPages','pp-live','{"id":"pp-live","partnerId":"siam-digital","vendorId":"intelsense","template":"demo","status":"published","vendor":{"name":"Intelsense AI"}}','{*}','{partner:siam-digital}',true),
 ('partnerPages','pp-draft','{"id":"pp-draft","partnerId":"siam-digital","vendorId":"intelsense","template":"webinar","status":"draft"}','{partner:siam-digital}','{partner:siam-digital}',false);
select t('a partner saves its own landing pages', (select count(*) from portal_records where collection='partnerPages') = 2);
select t('a partner cannot save a page as another partner', fails($$insert into portal_records(collection,id,data,readers,writers,is_public) values ('partnerPages','pp-x','{"id":"pp-x","partnerId":"gulf-coast","status":"draft"}','{partner:siam-digital}','{partner:siam-digital}',false)$$));
reset role;
select pg_temp.as_user(''); set role anon;
select t('anon requests a demo on a published partner page', public.submit_partner_page_lead('pp-live', '{"name":"Ploy","email":"Ploy@Hotel.co.th","company":"Riverside Hotel","consent":true,"note":"Front desk bot"}') like 'lead-pp-%');
select t('page sign-up needs consent', fails($$select public.submit_partner_page_lead('pp-live', '{"name":"A","email":"a@b.co","consent":false}')$$));
select t('no sign-ups on a draft page', fails($$select public.submit_partner_page_lead('pp-draft', '{"name":"A","email":"a@b.co","consent":true}')$$));
select t('anon cannot add leads directly', fails($$insert into portal_records(collection,id,data,readers,writers) values ('leads','lead-x','{"partnerId":"siam-digital"}','{partner:siam-digital}','{partner:siam-digital}')$$));
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000003'); set role authenticated;
select t('the partner sees the request in its leads', (select count(*) from portal_records where collection='leads' and data->>'source'='landing page' and data->>'prospectName'='Riverside Hotel' and data->'contact'->>'email'='ploy@hotel.co.th') = 1);
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000004'); set role authenticated;
select t('other partners cannot see that lead', (select count(*) from portal_records where collection='leads' and data->>'source'='landing page') = 0);
select t('other partners cannot see a draft page', (select count(*) from portal_records where collection='partnerPages' and id='pp-draft') = 0);
reset role;

-- ===== spam protection on the public forms
select pg_temp.as_user(''); set role anon;
select t('a filled-in hidden field is dropped quietly', public.submit_partner_page_lead('pp-live', '{"name":"Bot","email":"bot@spam.test","company":"Spam Co","consent":true,"hp":"http://spam.test"}') like 'lead-pp-%');
select t('a form sent in under 1.5 seconds is dropped quietly', public.submit_partner_page_lead('pp-live', '{"name":"Fast","email":"fast@spam.test","company":"Fast Co","consent":true,"elapsedMs":300}') like 'lead-pp-%');
select t('a normal-speed form goes through', public.submit_partner_page_lead('pp-live', '{"name":"Ann","email":"ann@ok.test","company":"Ann Co","consent":true,"elapsedMs":9000}') like 'lead-pp-%');
select public.submit_partner_page_lead('pp-live', '{"name":"Ann","email":"ann@ok.test","company":"Ann Co","consent":true}');
select public.submit_partner_page_lead('pp-live', '{"name":"Ann","email":"ann@ok.test","company":"Ann Co","consent":true}');
select t('the same email can sign up on a form at most 3 times a day', fails($$select public.submit_partner_page_lead('pp-live', '{"name":"Ann","email":"ANN@ok.test","company":"Ann Co","consent":true}')$$));
select set_config('request.headers', '{"x-forwarded-for":"203.0.113.9, 10.0.0.1"}', false);
select public.submit_affiliate_signup('inv-live', '{"name":"I1","email":"i1@ip.test","consent":true}');
select public.submit_affiliate_signup('inv-live', '{"name":"I2","email":"i2@ip.test","consent":true}');
select public.submit_affiliate_signup('inv-live', '{"name":"I3","email":"i3@ip.test","consent":true}');
select public.submit_affiliate_signup('inv-live', '{"name":"I4","email":"i4@ip.test","consent":true}');
select t('five sign-ups from one connection are fine', public.submit_affiliate_signup('inv-live', '{"name":"I5","email":"i5@ip.test","consent":true}') like 'sg-%');
select t('a sixth from the same connection within 10 minutes is refused', fails($$select public.submit_affiliate_signup('inv-live', '{"name":"I6","email":"i6@ip.test","consent":true}')$$));
select set_config('request.headers', '', false);
select t('anon cannot read the submission log', fails($$select count(*) from public.portal_submit_log$$));
select t('anon cannot read the CAPTCHA secret', fails($$select value from public.portal_secrets$$));
select t('anon cannot call the spam check directly', fails($$select public.portal_spam_check('x', null, 'a@b.co', '{}')$$));
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000003'); set role authenticated;
select t('the partner gets only the real sign-ups', (select count(*) from portal_records where collection='leads' and data->>'source'='landing page') = 4);
select t('a signed-in member cannot read the CAPTCHA secret', fails($$select value from public.portal_secrets$$));
reset role;
-- CAPTCHA: once the secret is saved, a valid Turnstile answer is required (Cloudflare stubbed here)
create schema if not exists extensions;
create or replace function extensions.http_post(url text, body text, ctype text) returns table(status int, content text) language sql as $$
  select 200, case when body like '%response=good-token-12345%' and body like 'secret=test-secret%' then '{"success":true}' else '{"success":false}' end $$;
insert into public.portal_secrets(key, value) values ('turnstile_secret', 'test-secret') on conflict (key) do update set value = excluded.value;
select pg_temp.as_user(''); set role anon;
select t('with the CAPTCHA on, a sign-up without an answer is refused', fails($$select public.submit_partner_page_lead('pp-live', '{"name":"C1","email":"c1@cap.test","company":"C","consent":true}')$$));
select t('a wrong CAPTCHA answer is refused', fails($$select public.submit_partner_page_lead('pp-live', '{"name":"C2","email":"c2@cap.test","company":"C","consent":true,"captchaToken":"bad-token-12345"}')$$));
select t('a valid CAPTCHA answer goes through', public.submit_partner_page_lead('pp-live', '{"name":"C3","email":"c3@cap.test","company":"C","consent":true,"captchaToken":"good-token-12345"}') like 'lead-pp-%');
select t('the vendor assessment checks the CAPTCHA too', fails($$select public.submit_vendor_assessment('{"company":"X","contactName":"Y","email":"y@x.test","consent":true}')$$));
reset role;
delete from public.portal_secrets where key = 'turnstile_secret';

-- ===== vendor fit assessment from the public form
select pg_temp.as_user(''); set role anon;
select t('anon sends a vendor assessment', public.submit_vendor_assessment('{"company":"Acme AI","contactName":"Ann","email":"Ann@Acme.io","consent":true,"partners":"11-50","addons":["investor"],"status":"won","quote":{"total":1}}') like 'va-%');
select t('assessment needs consent', fails($$select public.submit_vendor_assessment('{"company":"A","contactName":"B","email":"a@b.co"}')$$));
select t('assessment needs company, name and email', fails($$select public.submit_vendor_assessment('{"company":"A","email":"a@b.co","consent":true}')$$));
select t('anon cannot read assessments', (select count(*) from portal_records where collection='vendorAssessments') = 0);
select t('anon cannot insert assessments directly', fails($$insert into portal_records(collection,id,data) values ('vendorAssessments','va-x','{}')$$));
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000002'); set role authenticated;
select t('vendors cannot read assessments or the pricing model', (select count(*) from portal_records where collection in ('vendorAssessments','pricingModel')) = 0);
select t('vendors cannot write the pricing model', fails($$insert into portal_records(collection,id,data,readers,writers) values ('pricingModel','default','{}','{}','{vendor:intelsense}')$$));
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000001'); set role authenticated;
select t('CloudWAV reads the assessment; public form could not set status or a quote', (select count(*) from portal_records where collection='vendorAssessments' and data->>'status'='new' and data->>'source'='vendor-link' and not (data ? 'quote') and data->>'email'='ann@acme.io' and data->>'partners'='11-50') = 1);
reset role;

-- ===== calendar events, bookings, and marking an assessment as booked
select pg_temp.as_user('00000000-0000-0000-0000-000000000002'); set role authenticated;
insert into portal_records(collection,id,data,readers,writers) values ('calendarEvents','ev-1','{"id":"ev-1","ownerKey":"vendor:intelsense","title":"Training"}','{*}','{vendor:intelsense}');
select t('vendor adds its own event', (select count(*) from portal_records where collection='calendarEvents') = 1);
select t('vendor cannot add an event as someone else', fails($$insert into portal_records(collection,id,data,readers,writers) values ('calendarEvents','ev-2','{"id":"ev-2","ownerKey":"vendor:botnoi"}','{*}','{vendor:intelsense}')$$));
select t('a booking cannot be recorded in someone else''s name', fails($$insert into portal_records(collection,id,data,readers,writers) values ('bookings','bk-1','{"id":"bk-1","bookedBy":"partner:siam-digital","ownerKey":"vendor:botnoi"}','{vendor:botnoi}','{vendor:intelsense}')$$));
insert into portal_records(collection,id,data,readers,writers) values ('bookings','bk-2','{"id":"bk-2","bookedBy":"vendor:intelsense","ownerKey":"vendor:botnoi"}','{vendor:botnoi,vendor:intelsense}','{vendor:intelsense}');
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000003'); set role authenticated;
update portal_records set data = data || '{"title":"x"}' where id='ev-1';
select t('everyone signed in sees the event; partners cannot edit it', (select data->>'title' from portal_records where collection='calendarEvents') = 'Training');
select t('a booking is seen only by the two sides', (select count(*) from portal_records where collection='bookings') = 0);
reset role;
select pg_temp.as_user(''); set role anon;
select t('anon marks their own assessment as booked', public.mark_assessment_booked((select public.submit_vendor_assessment('{"company":"Book Co","contactName":"Bo","email":"bo@book.co","consent":true}'))));
select t('unknown or malformed ids do nothing', not public.mark_assessment_booked('va-00000000000000000000000000000000') and not public.mark_assessment_booked('x'));
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000001'); set role authenticated;
select t('CloudWAV sees the booking on the assessment', (select count(*) from portal_records where collection='vendorAssessments' and data->>'company'='Book Co' and data ? 'bookedAt') = 1);
reset role;

-- ===== outside agreements: file storage and CloudWAV's private review notes
select pg_temp.as_user('00000000-0000-0000-0000-000000000001'); set role authenticated;
insert into portal_records(collection,id,data,readers,writers) values ('agreements','agr-out-1','{"id":"agr-out-1","kind":"vendor","partyKey":"vendor:intelsense","source":"outside","status":"draft"}','{vendor:intelsense}','{}');
insert into portal_records(collection,id,data,readers,writers) values ('agreementReviews','agr-out-1','{"id":"agr-out-1","note":"Their liability cap is lower than ours"}','{}','{}');
insert into storage.objects(bucket_id,name) values ('portal-files','agreements/agr-out-1/their-msa.pdf');
select t('CloudWAV uploads an outside agreement file', (select count(*) from storage.objects where name like 'agreements/%') = 1);
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000002'); set role authenticated;
select t('the vendor on the agreement can open its file', (select count(*) from storage.objects where name like 'agreements/%') = 1);
select t('the vendor cannot upload or replace agreement files', fails($$insert into storage.objects(bucket_id,name) values ('portal-files','agreements/agr-out-1/swap.pdf')$$));
select t('the vendor never sees CloudWAV''s review notes', (select count(*) from portal_records where collection='agreementReviews') = 0);
select t('a vendor cannot plant CloudWAV settings or vendor introductions', fails($$insert into portal_records(collection,id,data,readers,writers) values ('operatorSettings','legal','{"id":"legal","entity":"Fake LLC"}','{vendor:intelsense}','{vendor:intelsense}')$$) and fails($$insert into portal_records(collection,id,data,readers,writers) values ('vendorReferrals','botnoi','{"id":"botnoi"}','{vendor:intelsense}','{vendor:intelsense}')$$));
select t('the vendor cannot write review notes', fails($$insert into portal_records(collection,id,data,readers,writers) values ('agreementReviews','agr-out-1x','{}','{vendor:intelsense}','{vendor:intelsense}')$$));
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000005'); set role authenticated;
select t('another vendor cannot open the file', (select count(*) from storage.objects where name like 'agreements/%') = 0);
reset role;

-- ===== accounts set up by CloudWAV, and investment round details
insert into auth.users(id, email) values ('00000000-0000-0000-0000-000000000007', 'new@agentid.test');
select pg_temp.as_user('00000000-0000-0000-0000-000000000002'); set role authenticated;
select t('a vendor cannot set up accounts', fails($$select public.portal_setup_account('new@agentid.test','vendor','agentid','AgentID','TempPass123')$$));
select t('a vendor cannot list accounts', fails($$select public.portal_accounts()$$));
select t('a vendor cannot remove accounts', fails($$select public.portal_remove_account('00000000-0000-0000-0000-000000000003')$$));
insert into portal_records(collection,id,data,readers,writers) values ('fundingProfiles','vendor:intelsense','{"id":"vendor:intelsense","status":"raising","round":"Series A"}','{vendor:intelsense}','{vendor:intelsense}');
select t('a vendor saves its own investment round', (select count(*) from portal_records where collection='fundingProfiles') = 1);
select t('a vendor cannot save another company''s round', fails($$insert into portal_records(collection,id,data,readers,writers) values ('fundingProfiles','vendor:botnoi','{"id":"vendor:botnoi"}','{vendor:intelsense}','{vendor:intelsense}')$$));
insert into portal_records(collection,id,data,readers,writers,is_public) values ('brandKits','vendor:intelsense','{"id":"vendor:intelsense","primary":"#1e40af"}','{*}','{vendor:intelsense}',true);
select t('a vendor saves its own brand colours', (select count(*) from portal_records where collection='brandKits' and id='vendor:intelsense') = 1);
select t('a vendor cannot save another company''s brand colours', fails($$insert into portal_records(collection,id,data,readers,writers,is_public) values ('brandKits','vendor:botnoi','{"id":"vendor:botnoi","primary":"#000000"}','{*}','{vendor:intelsense}',true)$$));
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000003'); set role authenticated;
select t('a private round is hidden from other companies', (select count(*) from portal_records where collection='fundingProfiles') = 0);
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000001'); set role authenticated;
select t('CloudWAV sees the round', (select data->>'round' from portal_records where collection='fundingProfiles' and id='vendor:intelsense') = 'Series A');
insert into portal_records(collection,id,data,readers,writers,is_public) values ('programs','agentid','{"id":"agentid","name":"AgentID","needsProfile":true,"tiers":[{"tier":"Reseller","rate":"To be agreed"}]}','{*}','{vendor:agentid}',true);
select t('a login can only go to a company that exists', fails($$select public.portal_setup_account('new@agentid.test','vendor','agentid-lookalike','AgentID','TempPass123')$$));
select t('CloudWAV sets up a vendor login (an unused login is reused)', (select public.portal_setup_account(' New@AgentID.test','vendor','agentid','AgentID','TempPass123')->>'id') = '00000000-0000-0000-0000-000000000007');
select t('operator logins cannot be created here', fails($$select public.portal_setup_account('new@agentid.test','operator','x','X','TempPass123')$$));
select t('an operator login cannot be re-assigned', fails($$select public.portal_setup_account('ops@cloudwav.test','vendor','agentid','X','TempPass123')$$));
select t('a short temporary password is refused', fails($$select public.portal_setup_account('new@agentid.test','vendor','agentid','X','short')$$));
select t('a bad email is refused', fails($$select public.portal_setup_account('not-an-email','vendor','agentid','X','TempPass123')$$));
select t('a login cannot be moved to another company', fails($$select public.portal_setup_account('new@agentid.test','vendor','intelsense','X','TempPass123')$$));
select t('the list shows the new login waiting for its own password', (select count(*) from jsonb_array_elements(public.portal_accounts()) a where a->>'email'='new@agentid.test' and a->>'role'='vendor' and (a->>'must_change_password')::boolean) = 1);
-- finding 7: the login is created here, so public sign-up can stay off
select t('a brand-new email gets a login created', (select public.portal_setup_account('fresh@agentid.test','vendor','agentid','Second user','TempPass456')->>'email') = 'fresh@agentid.test');
reset role;
select t('...with an email identity, confirmed, and the password hashed', (select count(*) from auth.users u join auth.identities i on i.user_id = u.id and i.provider = 'email' and i.provider_id = u.id::text
  where u.email = 'fresh@agentid.test' and u.email_confirmed_at is not null and u.aud = 'authenticated' and u.encrypted_password = extensions.crypt('TempPass456', u.encrypted_password) and u.confirmation_token = '') = 1);
-- someone registered the email first and kept a session: refused, so they never get the company's access
insert into auth.users(id, email, last_sign_in_at) values ('00000000-0000-0000-0000-000000000008', 'grab@agentid.test', now());
insert into auth.users(id, email) values ('00000000-0000-0000-0000-000000000009', 'grab2@agentid.test');
insert into auth.sessions(user_id) values ('00000000-0000-0000-0000-000000000009');
select pg_temp.as_user('00000000-0000-0000-0000-000000000001'); set role authenticated;
select t('an email whose login has already been used is refused', fails($$select public.portal_setup_account('grab@agentid.test','vendor','agentid','X','TempPass123')$$));
select t('an email whose login has an open session is refused', fails($$select public.portal_setup_account('grab2@agentid.test','vendor','agentid','X','TempPass123')$$));
reset role;
select t('...and neither got a company', (select count(*) from public.portal_users where email like 'grab%') = 0);
select t('the temporary password is stored hashed and the email confirmed', (select encrypted_password = extensions.crypt('TempPass123', encrypted_password) and email_confirmed_at is not null from auth.users where email='new@agentid.test'));
-- finding 8: nothing is saved until the temporary password is replaced
select pg_temp.as_user('00000000-0000-0000-0000-000000000007'); set role authenticated;
select t('with the temporary password, nothing can be saved', fails($$update portal_records set data = data || '{"desc":"Identity for AI agents"}' where collection='programs' and id='agentid'$$));
select t('with the temporary password, no file can be uploaded', fails($$insert into storage.objects(bucket_id, name) values ('portal-files', 'resources/x/a.pdf')$$));
select t('the flag cannot be cleared without changing the password', fails($$select public.portal_password_changed()$$));
reset role;
update auth.users set encrypted_password = extensions.crypt('MyOwnPass789', extensions.gen_salt('bf')) where id = '00000000-0000-0000-0000-000000000007';   -- what Supabase does when they choose a password
select pg_temp.as_user('00000000-0000-0000-0000-000000000007'); set role authenticated;
select t('choosing a password clears the flag', public.portal_password_changed());
update portal_records set data = data || '{"desc":"Identity for AI agents","needsProfile":false}' where collection='programs' and id='agentid';
select t('the new vendor finishes the profile CloudWAV started', (select data->>'desc' = 'Identity for AI agents' and data->>'needsProfile' = 'false' from portal_records where collection='programs' and id='agentid'));
select t('the new vendor cannot change its own commission tiers', fails($$update portal_records set data = data || '{"tiers":[{"tier":"Reseller","rate":"90%"}]}' where collection='programs' and id='agentid'$$));
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000001'); set role authenticated;
select t('the flag is cleared in the list', (select count(*) from jsonb_array_elements(public.portal_accounts()) a where a->>'email'='new@agentid.test' and not (a->>'must_change_password')::boolean) = 1);
reset role;
-- resetting the same company's login signs it out everywhere
insert into auth.sessions(user_id) values ('00000000-0000-0000-0000-000000000007');
insert into auth.refresh_tokens(token, user_id, session_id) select 'rt-1', '00000000-0000-0000-0000-000000000007', id from auth.sessions where user_id = '00000000-0000-0000-0000-000000000007';
select pg_temp.as_user('00000000-0000-0000-0000-000000000001'); set role authenticated;
select t('CloudWAV can reset that company''s own login', (select public.portal_setup_account('new@agentid.test','vendor','agentid','AgentID','ResetPass123')->>'entity_id') = 'agentid');
reset role;
select t('...which signs it out everywhere', (select count(*) from auth.sessions where user_id = '00000000-0000-0000-0000-000000000007') = 0 and (select count(*) from auth.refresh_tokens where user_id = '00000000-0000-0000-0000-000000000007') = 0);
select pg_temp.as_user('00000000-0000-0000-0000-000000000001'); set role authenticated;
select t('CloudWAV removes the login''s access', public.portal_remove_account('00000000-0000-0000-0000-000000000007') and not public.portal_remove_account('00000000-0000-0000-0000-000000000001'));
reset role;
select t('...which signs it out everywhere and stops its password working', (select count(*) from auth.sessions where user_id = '00000000-0000-0000-0000-000000000007') = 0
  and (select encrypted_password <> extensions.crypt('ResetPass123', encrypted_password) from auth.users where id = '00000000-0000-0000-0000-000000000007'));
update auth.users set last_sign_in_at = now() where id = '00000000-0000-0000-0000-000000000007';
select pg_temp.as_user('00000000-0000-0000-0000-000000000001'); set role authenticated;
select t('a removed login can be given back to its company later', (select public.portal_setup_account('new@agentid.test','vendor','agentid','AgentID','BackAgain123')->>'entity_id') = 'agentid');
reset role;


-- ===== hardening (security review, fix 1): moved records, file folders, review bypass, owner checks
select pg_temp.as_user('00000000-0000-0000-0000-000000000004'); set role authenticated;   -- partner gulf-coast
insert into portal_records(collection,id,data,readers,writers) values ('scratch','d-x','{"id":"d-x","status":"approved","partnerId":"gulf-coast","programId":"intelsense"}','{partner:gulf-coast}','{partner:gulf-coast}');
select t('a record cannot be moved into another collection (e.g. an approved deal)', fails($$update portal_records set collection='deals' where collection='scratch' and id='d-x'$$));
select t('a record cannot be moved into a CloudWAV-only collection', fails($$update portal_records set collection='enrollments' where collection='scratch' and id='d-x'$$));
select t('a record cannot be renamed', fails($$update portal_records set id='d-y' where collection='scratch' and id='d-x'$$));
select t('no deal was created by moving', (select count(*) from portal_records where collection='deals' and id='d-x') = 0);
select t('a stored id must match the record key', fails($$insert into portal_records(collection,id,data,readers,writers) values ('leads','lead-a','{"id":"lead-b","partnerId":"gulf-coast"}','{partner:gulf-coast}','{partner:gulf-coast}')$$));
select t('members cannot publish resources directly', fails($$insert into portal_records(collection,id,data,readers,writers,is_public) values ('resources','evil','{"id":"evil","ownerKey":"partner:gulf-coast"}','{*}','{partner:gulf-coast}',true)$$));
select t('a pending resource must be submitted as yourself', fails($$insert into portal_records(collection,id,data,readers,writers) values ('pendingResources','res-x','{"id":"res-x","ownerKey":"partner:siam-digital"}','{partner:gulf-coast}','{partner:gulf-coast}')$$));
insert into portal_records(collection,id,data,readers,writers) values ('pendingResources','res-new','{"id":"res-new","status":"pending","ownerKey":"partner:gulf-coast"}','{partner:gulf-coast}','{partner:gulf-coast}');
select t('members can still submit their own resources for review', (select count(*) from portal_records where collection='pendingResources' and id='res-new') = 1);
select t('no hardware offering under another vendor''s name', fails($$insert into portal_records(collection,id,data,readers,writers,is_public) values ('hardwareOfferings','hw-x','{"id":"hw-x","vendorId":"intelsense"}','{*}','{partner:gulf-coast}',true)$$));
select t('no incentive under another vendor''s name', fails($$insert into portal_records(collection,id,data,readers,writers) values ('incentives','inc-x','{"id":"inc-x","vendorId":"intelsense"}','{partner:gulf-coast}','{partner:gulf-coast}')$$));
select t('no deal for another partner', fails($$insert into portal_records(collection,id,data,readers,writers) values ('deals','deal-x','{"id":"deal-x","partnerId":"siam-digital"}','{partner:gulf-coast}','{partner:gulf-coast}')$$));
select t('no lead for another partner', fails($$insert into portal_records(collection,id,data,readers,writers) values ('leads','lead-x2','{"id":"lead-x2","partnerId":"siam-digital"}','{partner:gulf-coast}','{partner:gulf-coast}')$$));
select t('no partner project for another partner', fails($$insert into portal_records(collection,id,data,readers,writers,is_public) values ('partnerProjects','pp-x','{"id":"pp-x","partnerId":"siam-digital"}','{*}','{partner:gulf-coast}',true)$$));
select t('a partner cannot create another partner''s profile', fails($$insert into portal_records(collection,id,data,readers,writers) values ('partnerProfiles','acme-msp','{"id":"acme-msp"}','{*}','{partner:gulf-coast}')$$));
select t('a partner cannot claim another company''s preferences', fails($$insert into portal_records(collection,id,data,readers,writers) values ('prefs','partner:siam-digital','{"id":"partner:siam-digital"}','{partner:gulf-coast}','{partner:gulf-coast}')$$));
insert into portal_records(collection,id,data,readers,writers) values ('leads','lead-own','{"id":"lead-own","partnerId":"gulf-coast"}','{partner:gulf-coast}','{partner:gulf-coast}');
insert into portal_records(collection,id,data,readers,writers) values ('prefs','partner:gulf-coast','{"id":"partner:gulf-coast"}','{partner:gulf-coast}','{partner:gulf-coast}');
select t('a partner still saves its own leads and preferences', (select count(*) from portal_records where (collection='leads' and id='lead-own') or (collection='prefs' and id='partner:gulf-coast')) = 2);
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000002'); set role authenticated;   -- vendor intelsense
insert into portal_records(collection,id,data,readers,writers,is_public) values ('hardwareOfferings','hw-own','{"id":"hw-own","vendorId":"intelsense"}','{*}','{vendor:intelsense}',true);
select t('a vendor still saves its own hardware offerings', (select count(*) from portal_records where collection='hardwareOfferings' and id='hw-own') = 1);
reset role;
-- files: a fake resource record no longer opens another folder (agreements)
select pg_temp.as_user('00000000-0000-0000-0000-000000000001'); set role authenticated;
insert into portal_records(collection,id,data,readers,writers) values ('agreements','agr-vendor-intelsense','{"id":"agr-vendor-intelsense"}','{vendor:intelsense}','{vendor:intelsense}') on conflict do nothing;
reset role;
insert into storage.objects(bucket_id, name, owner) values ('portal-files', 'agreements/agr-vendor-intelsense/signed.pdf', '00000000-0000-0000-0000-000000000001');
select pg_temp.as_user('00000000-0000-0000-0000-000000000004'); set role authenticated;
select t('a resource record with an agreement''s id does not open that agreement''s files', (select count(*) from storage.objects where name like 'agreements/agr-vendor-intelsense/%') = 0);
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000001'); set role authenticated;
select t('CloudWAV still opens the agreement file', (select count(*) from storage.objects where name like 'agreements/agr-vendor-intelsense/%') = 1);
insert into portal_records(collection,id,data,readers,writers,is_public) values ('resources','res-ok','{"id":"res-ok","ownerKey":"partner:gulf-coast"}','{*}','{partner:gulf-coast}',true);
select t('CloudWAV can still publish an approved resource', (select count(*) from portal_records where collection='resources' and id='res-ok') = 1);
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000004'); set role authenticated;
update portal_records set data = data || '{"title":"Edited"}' where collection='resources' and id='res-ok';
select t('the owner can still edit their published resource', (select data->>'title' from portal_records where collection='resources' and id='res-ok') = 'Edited');
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000004'); set role authenticated;
select t('a pending resource cannot reuse a published resource id', fails($$insert into portal_records(collection,id,data,readers,writers) values ('pendingResources','res-ok','{"id":"res-ok","status":"pending","ownerKey":"partner:gulf-coast"}','{partner:gulf-coast}','{partner:gulf-coast}')$$));
reset role;

-- ===== finding 11: partner applications only through the spam-checked route
set role anon;
select t('nobody can write straight into partner_applications any more', fails($$insert into public.partner_applications(company_name, work_email, status) values ('Spam Co','x@spam.test','approved')$$));
select t('an application through the spam-checked route still arrives', public.submit_partner_application('11111111-2222-3333-4444-555555555555', '{"companyName":"Real MSP","email":"Owner@RealMSP.co.th","firstName":"Somchai"}') = 'ok');
reset role;
select t('...saved as pending, with the email tidied', (select status = 'pending' and work_email = 'owner@realmsp.co.th' from public.partner_applications where company_name = 'Real MSP'));
select t('the old open insert rule is gone', (select count(*) from pg_policies where tablename = 'partner_applications' and cmd = 'INSERT') = 0);
select t('reading applications still works', (select count(*) from pg_policies where tablename = 'partner_applications' and cmd = 'SELECT') = 1);

-- ===== finding 10: a daily allowance for AI drafts
select pg_temp.as_user('00000000-0000-0000-0000-000000000002'); set role authenticated;   -- vendor intelsense
select t('a vendor gets an AI draft', (public.portal_ai_quota('flyer')->>'ok')::boolean);
reset role;
insert into public.portal_submit_log(kind, ref) select 'ai:flyer', '00000000-0000-0000-0000-000000000002' from generate_series(1, 18);
select pg_temp.as_user('00000000-0000-0000-0000-000000000002'); set role authenticated;
select t('the 20th draft of the day is allowed', (public.portal_ai_quota('flyer')->>'used')::int = 20);
select t('the 21st is refused', not (public.portal_ai_quota('flyer')->>'ok')::boolean and (public.portal_ai_quota('flyer')->>'limit')::int = 20);
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000005'); set role authenticated;   -- vendor botnoi
select t('another vendor has its own allowance', (public.portal_ai_quota('flyer')->>'ok')::boolean);
reset role;
update public.portal_submit_log set at = now() - interval '25 hours' where kind = 'ai:flyer' and ref = '00000000-0000-0000-0000-000000000002';
select pg_temp.as_user('00000000-0000-0000-0000-000000000002'); set role authenticated;
select t('the allowance comes back after a day', (public.portal_ai_quota('flyer')->>'ok')::boolean);
reset role;
insert into public.portal_secrets(key, value) values ('ai_daily_limit_vendor', '1') on conflict (key) do update set value = excluded.value;
select pg_temp.as_user('00000000-0000-0000-0000-000000000002'); set role authenticated;
select t('CloudWAV can change the allowance', not (public.portal_ai_quota('flyer')->>'ok')::boolean and (public.portal_ai_quota('flyer')->>'limit')::int = 1);
select t('a vendor cannot read or edit the allowance setting', fails($$update public.portal_secrets set value = '9999'$$));
select t('a vendor cannot clear its own usage', fails($$delete from public.portal_submit_log$$));
reset role;
set role anon;
select t('signed-out visitors get no AI drafts', fails($$select public.portal_ai_quota('flyer')$$));
reset role;
select pg_temp.as_user('00000000-0000-0000-0000-000000000006'); set role authenticated;   -- a login with no role
select t('a login without a role gets no AI drafts', fails($$select public.portal_ai_quota('flyer')$$));
reset role;

select case when ok then 'PASS ' else 'FAIL ' end || name from public.results;
