from harness import *
import os, sys, psycopg2
if not os.path.exists("/usr/lib/postgresql/16/bin/initdb"):
    print("SKIP: PostgreSQL 16 not installed"); srv.shutdown(); sys.exit(0)
from pgmock import start_pg, stop_pg, PgSupabase
USERS = {"cto@cloudwavconsulting.com": {"password": "op-pass-123", "id": "11111111-0000-0000-0000-000000000001"}}
PORTAL = {USERS["cto@cloudwavconsulting.com"]["id"]: {"role": "operator", "entity_id": None, "display_name": "Peter Phelan"}}
mock = PgSupabase(USERS, PORTAL, start_pg())
def db(c): return [r for r in mock.rows_as_operator() if r["collection"] == c]
def admin(q):
    con = psycopg2.connect(mock.dsn); con.autocommit = True; con.cursor().execute(q); con.close()
def settle(pg, n=60):
    for _ in range(n):
        if not pg.evaluate("CLOUD_PENDING()"): return True
        pg.wait_for_timeout(150)
    return False
def new_product(pg, title):
    nav(pg, "operator-shop"); pg.click('[data-shop-edit=""]'); pg.wait_for_timeout(250)
    pg.fill("#shp_title", title); pg.fill("#shp_summary", "Test product"); pg.fill("#shp_price", "0")
    pg.click('[data-shop-save="draft"]'); pg.wait_for_timeout(300)

with sync_playwright() as p:
    b, ctx, pg = open_page_supabase(p, mock)
    pg.fill("#loginEmail", "cto@cloudwavconsulting.com"); pg.fill("#loginPassword", "op-pass-123"); pg.click("#loginSubmit"); pg.wait_for_timeout(2500); settle(pg)
    # the database refuses one specific record (stands in for any server-side rule)
    admin("""create or replace function public.test_refuse() returns trigger language plpgsql as $$
             begin if new.data->>'title' = 'Refused Product' then raise exception 'Test rule: this product is not allowed'; end if; return new; end $$;
             create trigger test_refuse before insert or update on public.portal_records for each row execute function public.test_refuse();""")
    new_product(pg, "Refused Product")
    new_product(pg, "Good Product")
    pg.wait_for_timeout(2500)
    titles = [r["data"].get("title") for r in db("shopProducts")]
    ok("Good Product" in titles and "Refused Product" not in titles, "One refused record doesn't block the others (Good Product saved)")
    chip = pg.inner_text("#cloudStatus")
    ok("1 change not saved" in chip, "Status says exactly what's unsaved: " + chip)
    ok(not pg.evaluate("CLOUD_PENDING()"), "No endless retry loop on the refused record")
    pg.click("#cloudStatus"); pg.wait_for_timeout(250)
    m = pg.inner_text(".modal")
    ok("Refused Product" in m and "Test rule: this product is not allowed" in m and "rest of your changes are saved" in m, "Clicking the status explains what failed and why")
    ok("cto@cloudwavconsulting.com" in pg.input_value("#cloudErrDetails"), "Copyable details include the login")
    # fix the cause, retry
    admin("drop trigger test_refuse on public.portal_records;")
    pg.click("#cloudRetryBtn"); pg.wait_for_timeout(1500); settle(pg)
    titles = [r["data"].get("title") for r in db("shopProducts")]
    ok("Refused Product" in titles and "Saved" in pg.inner_text("#cloudStatus"), "Retry saves it once the cause is fixed")
    # editing a held record retries it automatically
    admin("""create trigger test_refuse before insert or update on public.portal_records for each row execute function public.test_refuse();""")
    new_product(pg, "Refused Product")
    pg.wait_for_timeout(2500)
    ok("not saved" in pg.inner_text("#cloudStatus"), "Refused again while the rule is on")
    admin("drop trigger test_refuse on public.portal_records;")
    nav(pg, "operator-shop"); rows = pg.locator("[data-opshop-row]")
    for i in range(pg.locator("[data-opshop-row]").filter(has_text="Refused Product").count()):
        nav(pg, "operator-shop"); pg.locator("[data-opshop-row]").filter(has_text="Refused Product").nth(i).locator("[data-shop-edit]").click(); pg.wait_for_timeout(250)
        pg.fill("#shp_summary", "Edited"); pg.click('[data-shop-save="draft"]'); pg.wait_for_timeout(1500)
    settle(pg)
    ok("Saved" in pg.inner_text("#cloudStatus"), "Editing the record again saves it")
    # Cloud Data screen explains too
    b.close()
stop_pg()
report()
