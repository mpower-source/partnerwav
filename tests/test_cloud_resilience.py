from harness import *
import os, sys, json, psycopg2
if not os.path.exists("/usr/lib/postgresql/16/bin/initdb"):
    print("SKIP: PostgreSQL 16 not installed"); srv.shutdown(); sys.exit(0)
from pgmock import start_pg, stop_pg, PgSupabase
USERS = {"cto@cloudwavconsulting.com": {"password": "op-pass-123", "id": "11111111-0000-0000-0000-000000000001"}}
PORTAL = {USERS["cto@cloudwavconsulting.com"]["id"]: {"role": "operator", "entity_id": None, "display_name": "Peter Phelan"}}
mock = PgSupabase(USERS, PORTAL, start_pg())
def admin(q, args=()):
    con = psycopg2.connect(mock.dsn); con.autocommit = True; cur = con.cursor(); cur.execute("set session_replication_role = replica"); cur.execute(q, args); con.close()
def settle(pg):
    for _ in range(40):
        if not pg.evaluate("CLOUD_PENDING()"): return True
        pg.wait_for_timeout(150)
def login(p):
    b, ctx, pg = open_page_supabase(p, mock)
    pg.fill("#loginEmail", "cto@cloudwavconsulting.com"); pg.fill("#loginPassword", "op-pass-123"); pg.click("#loginSubmit"); pg.wait_for_timeout(2500)
    return b, pg
def add_product(title):
    admin("insert into portal_records(collection,id,data,readers,writers) values ('shopProducts',%s,%s,'{*}','{}')",
          ("shop-x-" + title.lower().replace(" ", "-"), json.dumps({"id": "shop-x-" + title.lower().replace(" ", "-"), "title": title, "status": "published", "price": 0, "category": "Sales", "type": "Course", "audience": "all", "summary": "x"})))

with sync_playwright() as p:
    b, pg = login(p); settle(pg)
    # ----- a background refresh doesn't undo an unsaved dropdown choice
    nav(pg, "operator-partners"); pg.click('[data-en-view="en-siam-intelsense"]') if pg.locator('[data-en-view="en-siam-intelsense"]').count() else None
    nav(pg, "operator-programs"); pg.click('[data-configure="intelsense"]'); pg.wait_for_timeout(300)
    pg.select_option("#cfgPayoutSchedule", index=1); chosen = pg.input_value("#cfgPayoutSchedule")
    pg.select_option("#cfgFeeBasis", "contract")
    pg.fill("#cfgFeeBase", "2.5")    # focus stays in this field
    add_product("Refresh Test One")
    pg.evaluate("window.dispatchEvent(new Event('focus'))"); pg.wait_for_timeout(1500)
    ok(pg.input_value("#cfgFeeBase") == "2.5" and pg.input_value("#cfgFeeBasis") == "contract" and pg.input_value("#cfgPayoutSchedule") == chosen, "While you're editing, a background refresh waits")
    pg.locator("#programConfigContent h3").first.click(); pg.wait_for_timeout(2500)   # leave the field; the waiting refresh runs now
    ok(pg.evaluate("document.activeElement.tagName") != "INPUT", "Field no longer focused")
    ok(pg.input_value("#cfgFeeBase") == "2.5" and pg.input_value("#cfgFeeBasis") == "contract" and pg.input_value("#cfgPayoutSchedule") == chosen, "After the refresh, unsaved dropdown choices and typing are still there")
    nav(pg, "operator-shop")
    ok("Refresh Test One" in pg.inner_text("#operatorShopContent"), "...and the refresh did bring in the new data")
    # ----- Cloud Data: setup check
    nav(pg, "operator-data"); pg.click("[data-cloud-check]"); pg.wait_for_timeout(1500)
    res = pg.inner_text("#cloudCheckResult")
    ok(res.count("✓") == 3 and "✗" not in res, "Check setup: table, operator login and database rules all OK -- " + res.replace("\n", " | "))
    b.close()

    # ----- setup out of date is detected
    admin("create or replace function public.portal_operator_only(c text) returns boolean language sql immutable as $$ select c = any (array['affiliatePrograms','shopProducts']) $$;")
    b, pg = login(p); nav(pg, "operator-data"); pg.click("[data-cloud-check]"); pg.wait_for_timeout(1500)
    ok("✗ Database rules are up to date" in pg.inner_text("#cloudCheckResult") and "Re-run supabase/portal_records.sql" in pg.inner_text("#cloudCheckResult"), "An out-of-date database setup is detected, with the fix")
    b.close()

    # ----- data table missing: clear status, no screen redraw loop, retry recovers
    admin("alter table public.portal_records rename to portal_records_off")
    b, pg = login(p)
    ok("CAN'T LOAD DATA" in pg.inner_text("#cloudStatus").upper(), "Load failure says so in the status: " + pg.inner_text("#cloudStatus"))
    nav(pg, "operator-programs"); pg.click('[data-configure="intelsense"]'); pg.wait_for_timeout(300)
    pg.select_option("#cfgFeeBasis", "contract"); pg.locator("#programConfigContent h3").first.click()
    pg.wait_for_timeout(9500)   # at least one retry happens in this time
    ok(pg.input_value("#cfgFeeBasis") == "contract" and pg.locator("#cfgFeeSection").count() == 1, "Retries don't redraw the screen (your dropdown choice stays)")
    pg.click("#cloudStatus"); pg.wait_for_timeout(1800)
    m = pg.inner_text(".modal")
    ok("run supabase/portal_records.sql" in m.lower() and "✗ Data table portal_records" in m, "Clicking the status explains it and shows the setup check")
    admin("alter table public.portal_records_off rename to portal_records")
    pg.click("#cloudRetryBtn"); pg.wait_for_timeout(2500)
    ok("SAVED" in pg.inner_text("#cloudStatus").upper(), "Retry loads the data once the table is back")
    b.close()
stop_pg()
report()
