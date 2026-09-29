from harness import *
from harness import _wire
import os, sys
if not os.path.exists("/usr/lib/postgresql/16/bin/initdb"):
    print("SKIP test_cloud: PostgreSQL 16 not installed"); srv.shutdown(); sys.exit(0)
from pgmock import start_pg, stop_pg, PgSupabase

USERS = {
    "ops@cloudwav.test":        {"password": "op-pass-123",   "id": "11111111-0000-0000-0000-000000000001"},
    "vendor@intelsense.test":   {"password": "vend-pass-123", "id": "11111111-0000-0000-0000-000000000002"},
    "partner@siamdigital.test": {"password": "part-pass-123", "id": "11111111-0000-0000-0000-000000000003"},
}
PORTAL = {
    USERS["ops@cloudwav.test"]["id"]:        {"role": "operator", "entity_id": None, "display_name": "Peter Phelan"},
    USERS["vendor@intelsense.test"]["id"]:   {"role": "vendor", "entity_id": "intelsense", "display_name": "Intelsense Admin"},
    USERS["partner@siamdigital.test"]["id"]: {"role": "partner", "entity_id": "siam-digital", "display_name": "Somchai K."},
}
PW = {e: u["password"] for e, u in USERS.items()}

dsn = start_pg()
mock = PgSupabase(USERS, PORTAL, dsn)
def db(collection=None):
    rows = mock.rows_as_operator()
    return [r for r in rows if collection is None or r["collection"] == collection]

def session(p, email, query=""):
    b, ctx, pg = open_page_supabase(p, mock, query)
    pg.fill("#loginEmail", email); pg.fill("#loginPassword", PW[email]); pg.click("#loginSubmit")
    pg.wait_for_timeout(1500)
    return b, ctx, pg

def wait_saved(pg, ms=6000):
    t = 0
    while t < ms:
        if (pg.inner_text("#cloudStatus") or "").strip() == "☁ Saved" and not pg.evaluate("CLOUD_PENDING()"): return True
        pg.wait_for_timeout(250); t += 250
    return False

with sync_playwright() as p:
    # ===== 0. Before CloudWAV has signed in once, a vendor's profile edit waits for setup
    b, ctx, pg = session(p, "vendor@intelsense.test")
    nav(pg, "vendor-network"); pg.locator('[data-view-vendor="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    pg.locator('[data-edit-vendor-profile="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    pg.fill("#vpOrigin", "Bangkok"); pg.locator('[data-vendor-edit-save="intelsense"]').first.click(); pg.wait_for_timeout(1200)
    ok("NOT SAVED" in pg.inner_text("#cloudStatus").upper() and "set up the shared portal data" in pg.get_attribute("#cloudStatus", "title"), "Vendor edit before setup: clear 'not saved yet' status")
    ok(len(db("programs")) == 0, "Nothing written before CloudWAV sets up the data")
    b.close()

    # ===== 1. Operator: first sign-in, empty database
    b, ctx, pg = session(p, "ops@cloudwav.test")
    ok("SAVED" in pg.inner_text("#cloudStatus").upper(), "Signed in: data loaded from Supabase (status chip)")
    nav(pg, "operator-approvals")
    ok("Bangkok Bank" not in pg.inner_text("#scr-operator-approvals"), "Demo deals are not shown in a signed-in session")
    nav(pg, "operator-shop")
    ok(pg.locator("[data-opshop-row]").count() == 9, "Real starter products available")
    ok(len(db("programs")) == 6 and len(db("shopProducts")) == 9, "Operator's first sign-in shares the starter records automatically")
    nav(pg, "operator-data")
    ok("portal_records" in pg.inner_text("#cloudDataContent"), "Cloud Data screen")
    pg.click("[data-cloud-seed]"); pg.wait_for_timeout(2500)
    cols = {r["collection"] for r in db()}
    ok({"programs", "shopProducts", "levelRules", "mspProspects", "affiliatePrograms", "landingPages"} <= cols, "Starter records saved to Supabase: " + ", ".join(sorted(cols)))
    ok(len(db("mspProspects")) == 61 and len(db("programs")) == 6, "All 61 prospects and 6 vendor programs stored")
    ok(all(r["is_public"] for r in db("programs")) and all(r["writers"] == ["vendor:" + r["id"]] for r in db("programs")), "Programs: public, each editable by its vendor")
    paid = [r for r in db("shopProducts") if r["data"].get("price")]
    ok(all(r["data"].get("accessLink", "") == "" for r in paid), "Paid products' access links are not stored on the public product")
    # operator edits a shop product with a payment + access link
    nav(pg, "operator-shop"); pg.click('[data-opshop-row="shop-sales-fundamentals"] [data-shop-edit]'); pg.wait_for_timeout(250)
    pg.fill("#shp_paymentLink", "https://buy.stripe.com/test_sales101"); pg.fill("#shp_accessLink", "https://learn.example/sales")
    pg.click('[data-shop-save="published"]'); pg.wait_for_timeout(300)
    ok(wait_saved(pg), "Operator edit saved")
    sp = [r for r in db("shopProducts") if r["id"] == "shop-sales-fundamentals"][0]
    acc = [r for r in db("shopAccess") if r["id"] == "shop-sales-fundamentals"]
    ok(sp["data"]["paymentLink"] == "https://buy.stripe.com/test_sales101" and sp["data"]["accessLink"] == "" and acc and acc[0]["data"]["link"] == "https://learn.example/sales" and acc[0]["readers"] == [], "Access link kept separately, readable by nobody until someone pays")
    # publish a landing page for the public route
    nav(pg, "operator-landing-pages"); pg.locator('[data-lp-edit="lp-intelsense-demo"]').click(); pg.wait_for_timeout(250)
    pg.click("[data-lp-draft]"); pg.check("#lpVendorApproved"); pg.click('[data-lp-save="publish"]'); pg.wait_for_timeout(300)
    ok(wait_saved(pg), "Landing page publish saved")
    lp = [r for r in db("landingPages") if r["id"] == "lp-intelsense-demo"][0]
    ok(lp["is_public"] and lp["data"]["status"] == "published", "Published landing page is public in Supabase")
    ok(not [k for k in pg.evaluate("Object.keys(localStorage)") if k.startswith("partnerWAV") or k == "partnerProjects"], "Nothing saved in the browser's local storage")
    b.close()

    # ===== 2. Vendor: edits own profile, submits an incentive
    b, ctx, pg = session(p, "vendor@intelsense.test")
    nav(pg, "vendor-network"); pg.locator('[data-view-vendor="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    pg.locator('[data-edit-vendor-profile="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    pg.fill("#vpVertical", "Enterprise AI (Thailand)"); pg.locator('[data-vendor-edit-save="intelsense"]').first.click(); pg.wait_for_timeout(300)
    ok(wait_saved(pg), "Vendor profile edit saved")
    ok([r for r in db("programs") if r["id"] == "intelsense"][0]["data"]["vertical"] == "Enterprise AI (Thailand)", "Vendor's own profile updated in Supabase")
    nav(pg, "vendor-incentives")
    vi = pg.inner_text("#vendorIncentivesContent")
    ok("Q4 Sales Acceleration SPIF" not in vi and "Unisense AI + AlterCrew Bundle SPIF" in vi, "Vendor sees no demo incentives -- only the Intelsense samples CloudWAV added on first sign-in")
    pg.locator('[data-goto-screen="vendor-incentive-editor"]:visible').first.click(); pg.wait_for_timeout(250)
    pg.select_option("#incType", "mdf"); pg.fill("#incTitle", "Q1 Co-marketing MDF"); pg.fill("#incDesc", "Co-funded events in Thailand")
    pg.fill("#mdfAmount", "3000"); pg.select_option("#mdfPeriod", "quarterly"); pg.fill("#incValidFrom", "2027-01-01"); pg.fill("#incValidUntil", "2027-03-31")
    pg.fill("#incClaimProcess", "Proposal first, claim with invoices."); pg.fill("#incMdfShare", "50"); pg.fill("#incMdfClaimDays", "45"); pg.fill("#incBudget", "30000")
    pg.click('#vendorIncentiveForm button[type=submit]'); pg.wait_for_timeout(300)
    ok(wait_saved(pg), "Incentive saved")
    inc = [r for r in db("incentives") if not r["data"].get("sample")]
    ok(len(inc) == 1 and inc[0]["data"]["status"] == "pending" and inc[0]["readers"] == ["vendor:intelsense"], "Incentive stored as pending, visible only to the vendor (and CloudWAV)")
    b.close()

    # ===== 3. Operator approves the incentive
    b, ctx, pg = session(p, "ops@cloudwav.test")
    nav(pg, "operator-marketing-approvals"); pg.click('[data-tab="incentives"]'); pg.wait_for_timeout(250)
    ok("Q1 Co-marketing MDF" in pg.inner_text("#incentiveApprovalsContent"), "Operator sees the vendor's incentive")
    pg.locator("#incentiveApprovalsContent [data-review-incentive]").first.click(); pg.wait_for_timeout(300)
    pg.click('[data-inc-action="approve"]'); pg.wait_for_timeout(300)
    ok(wait_saved(pg), "Approval saved")
    inc = db("incentives")[0]
    ok(inc["data"]["status"] == "approved" and inc["readers"] == ["*"], "Approved incentive now readable by everyone signed in")
    b.close()

    # ===== 4. Partner: profile, free course, sees the approved incentive
    b, ctx, pg = session(p, "partner@siamdigital.test")
    nav(pg, "partner-profile-editor"); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-partner-my-profile"], "Partner has no profile yet (demo profiles not shown)")
    pg.fill("#mpCompanyName", "Siam Digital MSP"); pg.fill("#mpCountry", "Thailand"); pg.fill("#mpTagline", "Managed IT for Thai SMBs")
    pg.click("#mpSaveBtn"); pg.wait_for_timeout(300)
    ok(wait_saved(pg), "Profile saved")
    pr = [r for r in db("partnerProfiles") if r["id"] != "cloudwav-consulting"]
    ok(len(pr) == 1 and pr[0]["id"] == "siam-digital" and pr[0]["writers"] == ["partner:siam-digital"], "Partner profile stored under their own id")
    nav(pg, "shop"); pg.click('[data-shop-card="shop-smm-101"] [data-shop-view]'); pg.wait_for_timeout(250)
    pg.click("[data-shop-buy]"); pg.wait_for_timeout(300)
    ok(wait_saved(pg), "Free order saved")
    o = db("shopOrders")
    ok(len(o) == 1 and o[0]["data"]["status"] == "paid" and o[0]["readers"] == ["partner:siam-digital"], "Free course order stored as paid (allowed by the server for free products)")
    pg.click('[data-screen-go="shop"]:visible'); pg.wait_for_timeout(200)
    pg.click('[data-shop-card="shop-sales-fundamentals"] [data-shop-view]'); pg.wait_for_timeout(250)
    pg.evaluate("() => { window.open = function(){ return null; }; }")
    pg.click("[data-shop-buy]"); pg.wait_for_timeout(300); ok(wait_saved(pg), "Paid order saved")
    o = [r for r in db("shopOrders") if r["data"]["productId"] == "shop-sales-fundamentals"]
    ok(o and o[0]["data"]["status"] == "awaiting", "Paid course order awaits payment")
    nav(pg, "vendor-network"); pg.locator('[data-view-vendor="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    vp = pg.inner_text("#vendorProfileContent")
    ok("Q1 Co-marketing MDF" in vp and "Enterprise AI (Thailand)" in vp, "Partner sees the vendor's edit and approved incentive")
    # try to mark own order paid from the browser: the client won't send it, and the server refuses it anyway
    try:
        mock.sql("update portal_records set data = jsonb_set(data,'{status}','\"paid\"') where collection='shopOrders' and data->>'productId'='shop-sales-fundamentals'", fetch=False, uid=USERS["partner@siamdigital.test"]["id"])
        ok(False, "Server refuses a partner marking their own order paid")
    except Exception as e:
        ok("Only CloudWAV" in str(e), "Server refuses a partner marking their own order paid")
    b.close()

    # ===== 5. Operator confirms payment; partner gets the access link after reload
    b, ctx, pg = session(p, "ops@cloudwav.test")
    nav(pg, "operator-shop"); pg.click('[data-opshop-tab="orders"]'); pg.wait_for_timeout(250)
    ok("Siam Digital MSP" in pg.inner_text("#operatorShopContent"), "Operator sees the partner's order")
    pg.click('[data-order-act="paid"]'); pg.wait_for_timeout(300); ok(wait_saved(pg), "Payment confirmation saved")
    acc = [r for r in db("shopAccess") if r["id"] == "shop-sales-fundamentals"][0]
    ok(acc["readers"] == ["partner:siam-digital"], "Buyer added to the access list")
    b.close()
    b, ctx, pg = session(p, "partner@siamdigital.test")
    nav(pg, "shop"); pg.click('[data-shop-tab="library"]'); pg.wait_for_timeout(300)
    card = pg.locator('[data-lib-card="shop-sales-fundamentals"]')
    ok(card.locator('a:has-text("Open course")').count() == 1 and card.locator('a:has-text("Open course")').get_attribute("href") == "https://learn.example/sales", "Partner gets the access link once paid")
    ok(pg.locator('[data-lib-card="shop-smm-101"]').count() == 1, "Library persisted in Supabase")
    b.close()

    # ===== 6. Public landing page from Supabase, no sign-in
    b = p.chromium.launch(); ctx = b.new_context()
    umd = supabase_umd()
    ctx.route("**/cdn.jsdelivr.net/npm/@supabase/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=umd))
    ctx.route(f"https://{SUPABASE_HOST}/**", mock.handle)
    pg = ctx.new_page(); _wire(pg); pg.goto(URL + "?lp=lp-intelsense-demo"); pg.wait_for_timeout(1500)
    ok("Intelsense AI" in pg.inner_text("#publicLandingContent") and "isn't available" not in pg.inner_text("#publicLandingContent"), "Public landing page loads from Supabase without signing in")
    pg.goto(URL + "?lp=lp-botnoi-enterprise"); pg.wait_for_timeout(1200)
    ok("isn't available" in pg.inner_text("#publicLandingContent"), "Unpublished page isn't readable publicly")
    b.close()

stop_pg()
ok(not mock.errors, "No writes refused by the server during normal use: " + "; ".join(mock.errors[:3]))
report()
