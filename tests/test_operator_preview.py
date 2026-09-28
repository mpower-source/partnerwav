from harness import *
import os, sys
if not os.path.exists("/usr/lib/postgresql/16/bin/initdb"):
    print("SKIP: PostgreSQL 16 not installed"); srv.shutdown(); sys.exit(0)
from pgmock import start_pg, stop_pg, PgSupabase
USERS = {
    "cto@cloudwavconsulting.com": {"password": "op-pass-123",   "id": "11111111-0000-0000-0000-000000000001"},
    "vendor@intelsense.test":     {"password": "vend-pass-123", "id": "11111111-0000-0000-0000-000000000002"},
}
PORTAL = {
    USERS["cto@cloudwavconsulting.com"]["id"]: {"role": "operator", "entity_id": None, "display_name": "Peter Phelan"},
    USERS["vendor@intelsense.test"]["id"]:     {"role": "vendor", "entity_id": "intelsense", "display_name": "Intelsense Admin"},
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
def switch(pg, role, company=None, other=None):
    pg.click(f'.role-btn[data-role="{role}"]'); pg.wait_for_timeout(250)
    if role == "operator": return
    if other: pg.fill("#previewOther", other)
    elif company: pg.select_option("#previewEntity", company)
    pg.click("#previewGo"); pg.wait_for_timeout(300)

with sync_playwright() as p:
    b, ctx, pg = session(p, "cto@cloudwavconsulting.com"); pg.wait_for_timeout(1000); settle(pg)
    ok(pg.locator(".role-switch").is_visible(), "Operator login shows the Partner / Vendor / Affiliate / Operator switcher")
    ok(visible_screen(pg) == ["scr-operator-overview"] and not pg.locator("#previewBanner").is_visible(), "Starts in the Operator workspace, no preview banner")

    # ----- Vendor
    pg.click('.role-btn[data-role="vendor"]'); pg.wait_for_timeout(250)
    opts = pg.locator("#previewEntity option").all_inner_texts()
    ok(any("Intelsense" in o for o in opts) and any("Botnoi" in o for o in opts), "Picker lists the vendors")
    pg.select_option("#previewEntity", "intelsense"); pg.click("#previewGo"); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-vendor-overview"] and pg.locator("#navVendor").is_visible() and not pg.locator("#navOperator").is_visible(), "Opens the Vendor workspace with the Vendor menu")
    ban = pg.inner_text("#previewBanner")
    ok("Vendor" in ban and "Intelsense" in ban and "signed in as CloudWAV" in ban, "Banner says who you're previewing as")
    ok("Intelsense" in pg.inner_text("#vendorOwnProgramGrid"), "Vendor overview shows Intelsense's program")
    nav(pg, "vendor-network")
    pg.locator('[data-view-vendor="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    ok(pg.locator('[data-edit-vendor-profile="intelsense"]:visible').count() >= 1, "Can edit Intelsense's profile as the vendor would")
    pg.locator('[data-edit-vendor-profile="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    pg.fill("#vpDesc", "Thai-first AI contact center (preview edit)")
    pg.locator('[data-vendor-edit-save="intelsense"]').first.click(); pg.wait_for_timeout(400); ok(settle(pg), "Saved")
    prog = [r for r in db("programs") if r["id"] == "intelsense"][0]
    ok(prog["data"]["desc"] == "Thai-first AI contact center (preview edit)" and prog["writers"] == ["vendor:intelsense"], "Vendor edits save to Supabase under the vendor's record")

    # ----- Partner
    switch(pg, "partner", company="siam-digital")
    ok(visible_screen(pg) == ["scr-partner-overview"] and pg.locator("#navPartner").is_visible(), "Opens the Partner workspace")
    ok("siam-digital" in pg.inner_text("#previewBanner") or "Siam Digital" in pg.inner_text("#previewBanner"), "Previewing Siam Digital")
    nav(pg, "partner-profile-editor"); pg.wait_for_timeout(300)
    pg.fill("#mpCompanyName", "Siam Digital MSP"); pg.fill("#mpCountry", "Thailand"); pg.fill("#mpTagline", "Managed IT for Thai SMEs")
    pg.click("#mpSaveBtn"); pg.wait_for_timeout(400); settle(pg)
    pp = db("partnerProfiles")
    ok(len(pp) == 1 and pp[0]["id"] == "siam-digital" and pp[0]["writers"] == ["partner:siam-digital"], "Partner profile created for siam-digital (the real partner can edit it later)")
    # messages can't be sent as the partner
    nav(pg, "partner-messages"); pg.select_option("#msgNewTo", "operator:"); pg.wait_for_timeout(250)
    pg.fill("#msgCompose", "hello"); pg.click("#msgSendBtn"); pg.wait_for_timeout(300); settle(pg)
    ok(db("messages") == [], "Messages can't be sent while previewing")

    # ----- Affiliate, with a typed id
    switch(pg, "affiliate", other="New Affiliate Co")
    ok(visible_screen(pg) == ["scr-affiliate-overview"] and "new-affiliate-co" in pg.inner_text("#previewBanner"), "Affiliate workspace, with a typed company id")

    # ----- back to operator
    pg.click("[data-preview-exit]"); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-operator-overview"] and pg.locator("#navOperator").is_visible() and not pg.locator("#previewBanner").is_visible(), "Back to Operator")
    nav(pg, "operator-revenue")
    ok(visible_screen(pg) == ["scr-operator-revenue"], "Operator screens work again")
    b.close()

    # a vendor login can't switch
    b, ctx, pg = session(p, "vendor@intelsense.test")
    ok(not pg.locator(".role-switch").is_visible(), "Other logins don't get the switcher")
    ok(visible_screen(pg) == ["scr-vendor-overview"], "Vendor login opens their own workspace")
    b.close()

stop_pg()
ok(not mock.errors, "No requests refused: " + "; ".join(mock.errors[:3]))
report()
