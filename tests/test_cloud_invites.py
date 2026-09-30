from harness import *
import os, sys, json
if not os.path.exists("/usr/lib/postgresql/16/bin/initdb"):
    print("SKIP: PostgreSQL 16 not installed"); srv.shutdown(); sys.exit(0)
from pgmock import start_pg, stop_pg, PgSupabase
HERE = os.path.dirname(os.path.abspath(__file__))
QRJS = qrcode_js()
USERS = {
    "ops@cloudwav.test":      {"password": "op-pass-123",   "id": "11111111-0000-0000-0000-000000000001"},
    "vendor@intelsense.test": {"password": "vend-pass-123", "id": "11111111-0000-0000-0000-000000000002"},
    "vendor@botnoi.test":     {"password": "bot-pass-123",  "id": "11111111-0000-0000-0000-000000000005"},
}
PORTAL = {
    USERS["ops@cloudwav.test"]["id"]:      {"role": "operator", "entity_id": None, "display_name": "Peter Phelan"},
    USERS["vendor@intelsense.test"]["id"]: {"role": "vendor", "entity_id": "intelsense", "display_name": "Intelsense Admin"},
    USERS["vendor@botnoi.test"]["id"]:     {"role": "vendor", "entity_id": "botnoi", "display_name": "Botnoi Admin"},
}
PW = {e: u["password"] for e, u in USERS.items()}
OFFER = "botnoi-sme-ai-invite"
mock = PgSupabase(USERS, PORTAL, start_pg())
def db(c): return [r for r in mock.rows_as_operator() if r["collection"] == c]
def qr(ctx): ctx.route("**/cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=QRJS, headers={"access-control-allow-origin": "*"}))
def session(p, email):
    b, ctx, pg = open_page_supabase(p, mock); qr(ctx)
    pg.fill("#loginEmail", email); pg.fill("#loginPassword", PW[email]); pg.click("#loginSubmit"); pg.wait_for_timeout(1500)
    return b, ctx, pg
def settle(pg):
    for _ in range(60):
        if not pg.evaluate("CLOUD_PENDING()"): return True
        pg.wait_for_timeout(150)
    return False

with sync_playwright() as p:
    b, ctx, pg = session(p, "ops@cloudwav.test"); pg.wait_for_timeout(1500); settle(pg)
    row = [r for r in db("affiliatePrograms") if r["id"] == OFFER]
    ok(len(row) == 1 and row[0]["is_public"] and row[0]["writers"] == ["vendor:botnoi"], "Botnoi invite offer saved: public (for the invite page), editable by Botnoi")
    ok("terms" not in row[0]["data"] and [t for t in db("affiliateTerms") if t["id"] == OFFER][0]["readers"] == ["vendor:botnoi"], "Reward terms stored privately")
    b.close()

    # anonymous visitor: no account, page and sign-up go straight to Supabase
    b, ctx, pg = open_page_supabase(p, mock, "?invite=" + OFFER); qr(ctx); pg.wait_for_timeout(800)
    ok("THB 5,000" in pg.inner_text("#publicInviteContent"), "Invite page loads from Supabase without signing in")
    pg.fill("#invName", "Nok Sukjai"); pg.fill("#invEmail", "nok@example.co.th"); pg.check("#invConsent"); pg.click("#inviteSubmit"); pg.wait_for_timeout(1200)
    mine = pg.input_value("#inviteMyLink") if pg.locator("#inviteMyLink").count() else ""
    sg = db("affiliateSignups")
    ok(len(sg) == 1 and sg[0]["readers"] == ["vendor:botnoi"] and not sg[0]["is_public"] and sg[0]["data"]["kind"] == "referrer", "Sign-up saved through submit_affiliate_signup, readable by Botnoi only")
    ok(sg and mine.endswith("&ref=" + sg[0]["id"]), "Personal link uses the saved sign-up id")
    pg.goto(mine); pg.wait_for_timeout(1000)
    pg.fill("#invName", "Somsri P."); pg.fill("#invEmail", "somsri@shop.co.th"); pg.fill("#invCompany", "Somsri Thai Kitchen"); pg.check("#invConsent"); pg.click("#inviteSubmit"); pg.wait_for_timeout(1200)
    sg = db("affiliateSignups")
    ok(len(sg) == 2 and any(r["data"]["kind"] == "business" and r["data"]["referredBy"] == mine.split("ref=")[1] for r in sg), "Business sign-up credited to the referrer")
    b.close()

    # Botnoi sees its offer and the leads; Intelsense doesn't
    b, ctx, pg = session(p, "vendor@botnoi.test"); nav(pg, "affiliate-marketplace"); pg.wait_for_timeout(800)
    tools = pg.locator(f'#affiliateMarketplaceGrid [data-offer="{OFFER}"] [data-invite-tools]')
    ok(tools.count() == 1 and "Sign-ups (2)" in tools.inner_text(), "Botnoi sees its invite link and 2 sign-ups")
    tools.locator("[data-invite-signups]").click(); pg.wait_for_timeout(300)
    ok("Somsri Thai Kitchen" in pg.inner_text("#inviteSignupRows") and "Nok Sukjai" in pg.inner_text("#inviteSignupRows"), "Botnoi's sign-up list")
    b.close()
    b, ctx, pg = session(p, "vendor@intelsense.test"); nav(pg, "affiliate-marketplace"); pg.wait_for_timeout(500)
    ok(pg.locator(f'[data-offer="{OFFER}"]').count() == 0 and mock.sql("select count(*) as n from portal_records where collection='affiliateSignups'", uid=USERS["vendor@intelsense.test"]["id"])[0]["n"] == 0, "Intelsense sees neither the offer nor the sign-ups")
    b.close()

stop_pg()
report()
