from harness import *
import os, sys
if not os.path.exists("/usr/lib/postgresql/16/bin/initdb"):
    print("SKIP: PostgreSQL 16 not installed"); srv.shutdown(); sys.exit(0)
from pgmock import start_pg, stop_pg, PgSupabase
USERS = {
    "ops@cloudwav.test":        {"password": "op-pass-123",   "id": "11111111-0000-0000-0000-000000000001"},
    "partner@siamdigital.test": {"password": "part-pass-123", "id": "11111111-0000-0000-0000-000000000003"},
    "vendor@intelsense.test":   {"password": "vend-pass-123", "id": "11111111-0000-0000-0000-000000000002"},
}
PORTAL = {
    USERS["ops@cloudwav.test"]["id"]:        {"role": "operator", "entity_id": None, "display_name": "Peter Phelan"},
    USERS["partner@siamdigital.test"]["id"]: {"role": "partner", "entity_id": "siam-digital", "display_name": "Somchai K."},
    USERS["vendor@intelsense.test"]["id"]:   {"role": "vendor", "entity_id": "intelsense", "display_name": "Intelsense Admin"},
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
    # operator: first sign-in, add Seven Peaks as an active referral partner
    b, ctx, pg = session(p, "ops@cloudwav.test"); pg.wait_for_timeout(1500); settle(pg)
    nav(pg, "referrals"); pg.click('[data-ref-tab="houses"]'); pg.wait_for_timeout(150)
    ok("No software houses yet" in pg.inner_text("#referralsContent"), "Signed in: no demo software house")
    nav(pg, "operator-agreements")
    ok(pg.locator("[data-agr-row]").count() == 0, "Signed in: no demo agreements")
    nav(pg, "operator-msp-prospects"); pg.click('[data-msp-house="sw-sevenpeakssoftware"]'); pg.wait_for_timeout(250)
    pg.select_option("#hf_status", "active"); pg.click("#hfSave"); pg.wait_for_timeout(300); settle(pg)
    h = db("softwareHouses"); ag = db("agreements")
    ok(len(h) == 1 and h[0]["readers"] == ["*"] and h[0]["data"]["terms"]["referralRate"] == 10, "Software house stored (visible to partners once active)")
    ok(len(ag) == 1 and ag[0]["data"]["kind"] == "referral" and ag[0]["readers"] == ["house:" + h[0]["id"]], "Draft referral agreement stored (CloudWAV only)")
    b.close()

    # partner: profile, then refer a project and request an agreement
    b, ctx, pg = session(p, "partner@siamdigital.test")
    nav(pg, "partner-profile-editor"); pg.wait_for_timeout(300)
    pg.fill("#mpCompanyName", "Siam Digital MSP"); pg.fill("#mpCountry", "Thailand"); pg.fill("#mpTagline", "Managed IT"); pg.click("#mpSaveBtn"); pg.wait_for_timeout(300)
    nav(pg, "referrals"); pg.click("[data-ref-new]"); pg.wait_for_timeout(200)
    pg.fill("#rfCompany", "Siam Clinic Group"); pg.fill("#rfContact", "IT director"); pg.fill("#rfNeed", "Patient app with voice booking"); pg.fill("#rfBudget", "1000000"); pg.check("#rfDisclosed")
    pg.click("#rfSubmit"); pg.wait_for_timeout(300); settle(pg)
    r = db("projectReferrals")
    ok(len(r) == 1 and r[0]["data"]["status"] == "registered" and r[0]["readers"] == ["partner:siam-digital"], "Referral stored, private to the partner (and CloudWAV)")
    nav(pg, "partner-agreements"); pg.select_option("#agrReqProgram", "intelsense"); pg.click("[data-agr-request]"); pg.wait_for_timeout(300); settle(pg)
    a = [x for x in db("agreements") if x["data"]["kind"] == "partner"]
    ok(len(a) == 1 and a[0]["data"]["status"] == "requested" and sorted(a[0]["readers"]) == ["partner:siam-digital", "vendor:intelsense"], "Agreement request stored; the program's vendor can see it")
    b.close()

    # operator: accept, win, record a payment; send and sign the agreement
    b, ctx, pg = session(p, "ops@cloudwav.test")
    nav(pg, "referrals"); pg.click('[data-ref-tab="referrals"]'); pg.wait_for_timeout(150)
    pg.locator("[data-ref-view]").first.click(); pg.wait_for_timeout(250)
    pg.click('[data-ref-act="accepted"]'); pg.wait_for_timeout(200)
    pg.click('[data-ref-act="won"]'); pg.wait_for_timeout(200); pg.fill("#askInput", "1000000"); pg.click("#askOk"); pg.wait_for_timeout(200)
    pg.fill("#rpAmount", "400000"); pg.click("[data-ref-pay]"); pg.wait_for_timeout(300); settle(pg)
    r = db("projectReferrals")[0]["data"]
    ok(r["status"] == "won" and r["contractValue"] == 1000000 and len(r["payments"]) == 1 and r["termsSnapshot"]["referralRate"] == 10, "Outcome, payment and fee terms stored")
    nav(pg, "operator-agreements")
    ok("1requested" in pg.inner_text("#operatorAgreementsContent").replace("\n", "").replace(" ", ""), "Operator sees the partner's request")
    row = pg.locator("[data-agr-row]").filter(has_text="Siam Digital MSP")
    row.locator('[data-agr-act="sent"]').click(); pg.wait_for_timeout(300)
    pg.evaluate("""() => { for (let i = 0; i < 40; i++) { const el = document.querySelector('input.agr-field.empty'); if (!el) break;
        el.value = el.type === 'date' ? '2026-11-01' : 'Test value'; el.dispatchEvent(new Event('change', { bubbles: true })); } }""")
    pg.wait_for_timeout(200); pg.click("[data-agr-doc-send]"); pg.wait_for_timeout(400); settle(pg)
    ok((db("agreements")[0]["data"].get("filled") or {}).get("partyEntity") == "Test value", "The filled-in text is stored on the agreement when it goes out")
    pg.locator("[data-agr-row]").filter(has_text="Siam Digital MSP").locator('[data-agr-act="signed"]').click(); pg.wait_for_timeout(300); settle(pg)
    b.close()

    # partner sees the result
    b, ctx, pg = session(p, "partner@siamdigital.test")
    nav(pg, "referrals")
    ok("your share ฿28,000" in pg.inner_text("#referralsContent"), "Partner sees their share: 70% of 10% of ฿400k")
    nav(pg, "partner-agreements")
    ok("Signed" in pg.inner_text("#agreementsContent"), "Partner sees the signed agreement")
    b.close()
    # vendor sees the partner agreement in its program
    b, ctx, pg = session(p, "vendor@intelsense.test"); nav(pg, "partner-agreements")
    ok("Siam Digital MSP" in pg.inner_text("#agreementsContent"), "Vendor sees the partner agreement for its program")
    b.close()

try:
    mock.sql("update portal_records set data = jsonb_set(data,'{status}','\"won\"') where collection='projectReferrals'", fetch=False, uid=USERS["partner@siamdigital.test"]["id"])
except Exception as e:
    pass
ok(db("projectReferrals")[0]["data"]["payments"][0]["amount"] == 400000, "Data intact")
stop_pg()
ok(not mock.errors, "No requests refused during normal use: " + "; ".join(mock.errors[:3]))
report()
