from harness import *
import os, sys, json
if not os.path.exists("/usr/lib/postgresql/16/bin/initdb"):
    print("SKIP: PostgreSQL 16 not installed"); srv.shutdown(); sys.exit(0)
from pgmock import start_pg, stop_pg, PgSupabase
USERS = {
    "ops@cloudwav.test":      {"password": "op-pass-123",   "id": "11111111-0000-0000-0000-000000000001"},
    "vendor@intelsense.test": {"password": "vend-pass-123", "id": "11111111-0000-0000-0000-000000000002"},
}
PORTAL = {
    USERS["ops@cloudwav.test"]["id"]:      {"role": "operator", "entity_id": None, "display_name": "Peter Phelan"},
    USERS["vendor@intelsense.test"]["id"]: {"role": "vendor", "entity_id": "intelsense", "display_name": "Intelsense Admin"},
}
PW = {e: u["password"] for e, u in USERS.items()}
mock = PgSupabase(USERS, PORTAL, start_pg())
def db(c): return [r for r in mock.rows_as_operator() if r["collection"] == c]
def session(p, email):
    b, ctx, pg = open_page_supabase(p, mock)
    pg.fill("#loginEmail", email); pg.fill("#loginPassword", PW[email]); pg.click("#loginSubmit"); pg.wait_for_timeout(1500)
    return b, ctx, pg
def settle(pg):
    for _ in range(60):
        if not pg.evaluate("CLOUD_PENDING()"): return True
        pg.wait_for_timeout(150)
    return False

with sync_playwright() as p:
    # a prospective vendor, not signed in, sends the form
    b, ctx, pg = open_page_supabase(p, mock, "?assess=1"); pg.wait_for_timeout(500)
    pg.fill("#va_company", "Bright Hardware"); pg.fill("#va_contactName", "Ann Lee"); pg.fill("#va_email", "ann@bright.example"); pg.click("[data-va-next]"); pg.wait_for_timeout(200)
    pg.fill("#va_productSummary", "Smart sensors"); pg.click("[data-va-next]"); pg.wait_for_timeout(200)
    pg.check('[data-va-k="programStage"][value="No partner program yet"]'); pg.check('[data-va-k="partners"][value="1-10"]'); pg.click("[data-va-next]"); pg.wait_for_timeout(200)
    pg.check('[data-va-k="needs"][value="deals"]'); pg.check('[data-va-k="support"][value="self"]'); pg.click("[data-va-next]"); pg.wait_for_timeout(200)
    pg.check('[data-va-k="addons"][value="marketing"]'); pg.click("[data-va-next]"); pg.wait_for_timeout(200)
    pg.check('[data-va-k="consent"]'); pg.click("[data-va-next]"); pg.wait_for_timeout(1200)
    rows = db("vendorAssessments")
    ok("Thank you, Ann" in pg.inner_text("#publicAssessContent") and len(rows) == 1 and rows[0]["readers"] == [] and rows[0]["writers"] == [] and not rows[0]["is_public"], "Public form saves to Supabase, readable by CloudWAV only")
    ok(rows and rows[0]["data"]["status"] == "new" and rows[0]["data"]["addons"] == ["marketing"], "Answers stored, status New")
    b.close()

    b, ctx, pg = session(p, "ops@cloudwav.test"); pg.wait_for_timeout(1200); settle(pg)
    nav(pg, "operator-assessments"); pg.wait_for_timeout(300)
    row = pg.locator("[data-va-row]").filter(has_text="Bright Hardware")
    ok(row.count() == 1 and "NEW" in row.inner_text().upper(), "CloudWAV sees it as New")
    row.locator("[data-va-open]").click(); pg.wait_for_timeout(300)
    ok(pg.inner_text("#vaMonthly") == "$1,500", "Quote: Launch 500 + Marketing services 1,000")
    pg.select_option("#vaStatus", "quoted"); pg.click("[data-va-save]"); pg.wait_for_timeout(400); ok(settle(pg), "Saved")
    d = db("vendorAssessments")[0]["data"]
    ok(d["status"] == "quoted" and d["quote"]["planId"] == "launch", "Quote and status saved to Supabase")
    pg.click("[data-va-list]"); pg.click("[data-va-pricing]"); pg.wait_for_timeout(200); pg.fill('[data-pm="addons:marketing"]', "1200"); pg.click("#pmSave"); pg.wait_for_timeout(400); settle(pg)
    pm = db("pricingModel")
    ok(len(pm) == 1 and pm[0]["readers"] == [] and not pm[0]["is_public"] and [a for a in pm[0]["data"]["addons"] if a["id"] == "marketing"][0]["price"] == 1200, "Pricing model saved privately")
    b.close()

    b, ctx, pg = session(p, "vendor@intelsense.test"); pg.wait_for_timeout(800)
    n = mock.sql("select count(*) as n from portal_records where collection in ('vendorAssessments','pricingModel')", uid=USERS["vendor@intelsense.test"]["id"])[0]["n"]
    ok(n == 0 and pg.locator('[data-screen="operator-assessments"]:visible').count() == 0, "Vendors can't see assessments, quotes or the pricing model")
    b.close()

    b, ctx, pg = session(p, "ops@cloudwav.test"); pg.wait_for_timeout(1200); nav(pg, "operator-assessments"); pg.locator("[data-va-open]").first.click(); pg.wait_for_timeout(300)
    ok(pg.inner_text("#vaMonthly") == "$1,700", "Pricing model reloads from Supabase (Marketing services now 1,200)")
    b.close()
stop_pg()
report()
