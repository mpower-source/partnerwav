from harness import *
import os, sys, json
if not os.path.exists("/usr/lib/postgresql/16/bin/initdb"):
    print("SKIP: PostgreSQL 16 not installed"); srv.shutdown(); sys.exit(0)
from pgmock import start_pg, stop_pg, PgSupabase
USERS = {
    "ops@cloudwav.test":        {"password": "op-pass-123",   "id": "11111111-0000-0000-0000-000000000001"},
    "vendor@intelsense.test":   {"password": "vend-pass-123", "id": "11111111-0000-0000-0000-000000000002"},
    "partner@siamdigital.test": {"password": "part-pass-123", "id": "11111111-0000-0000-0000-000000000003"},
    "vendor@botnoi.test":       {"password": "bot-pass-123",  "id": "11111111-0000-0000-0000-000000000005"},
}
PORTAL = {
    USERS["ops@cloudwav.test"]["id"]:        {"role": "operator", "entity_id": None, "display_name": "Peter Phelan"},
    USERS["vendor@intelsense.test"]["id"]:   {"role": "vendor", "entity_id": "intelsense", "display_name": "Intelsense Admin"},
    USERS["partner@siamdigital.test"]["id"]: {"role": "partner", "entity_id": "siam-digital", "display_name": "Somchai K."},
    USERS["vendor@botnoi.test"]["id"]:       {"role": "vendor", "entity_id": "botnoi", "display_name": "Botnoi Admin"},
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
def refused(q, args, email):
    try: mock.sql(q, args, fetch=False, uid=USERS[email]["id"]); return False
    except Exception: return True

with sync_playwright() as p:
    b, ctx, pg = session(p, "ops@cloudwav.test"); pg.wait_for_timeout(1500); settle(pg)
    nav(pg, "operator-programs"); pg.click('[data-configure="intelsense"]'); pg.wait_for_timeout(250)
    pg.fill("#cfgFeeBase", "2.5"); pg.click("[data-config-save]"); pg.wait_for_timeout(400); settle(pg)
    pf = db("programFees")
    ok(len(pf) == 1 and pf[0]["id"] == "intelsense" and pf[0]["readers"] == ["vendor:intelsense"] and pf[0]["writers"] == [] and not pf[0]["is_public"], "Program fee stored privately: CloudWAV + that vendor only")
    prog = [r for r in db("programs") if r["id"] == "intelsense"][0]
    ok("basePct" not in json.dumps(prog["data"]), "Not on the public program record")
    b.close()

    # partner registers a deal (straight into the database, as the partner)
    deal = {"id": "deal-cloud-1", "partnerId": "siam-digital", "partner": "Siam Digital MSP", "programId": "intelsense", "program": "Intelsense AI", "productId": "", "product": "",
            "deal": "Chiang Mai hospital voice bot", "customer": "CM Hospital", "value": "$80,000", "termMonths": 12, "submitted": "today", "status": "pending", "pricingCheck": "",
            "notes": "", "thread": [], "unreadOperator": True, "unreadPartner": False}
    mock.sql("insert into portal_records(collection,id,data,readers,writers) values ('deals',%s,%s,%s,%s)",
             ("deal-cloud-1", json.dumps(deal), ["partner:siam-digital", "vendor:intelsense"], ["partner:siam-digital"]), fetch=False, uid=USERS["partner@siamdigital.test"]["id"])

    b, ctx, pg = session(p, "ops@cloudwav.test")
    nav(pg, "operator-approvals"); pg.click('[data-review-deal="deal-cloud-1"]'); pg.wait_for_timeout(300)
    ok("$2,000" in pg.inner_text("#dealFeeCard"), "Fee estimate uses the saved 2.5% ($80,000 -> $2,000)")
    pg.click('[data-deal-action="approve"]'); pg.wait_for_timeout(400); ok(settle(pg), "Saved")
    fr = db("platformFees")
    ok(len(fr) == 1 and fr[0]["data"]["amount"] == 2000 and fr[0]["data"]["status"] == "due" and fr[0]["readers"] == ["vendor:intelsense"], "Fee record stored, readable by the vendor only")
    nav(pg, "operator-revenue"); pg.click('[data-fee-status="invoiced"]'); pg.wait_for_timeout(300); settle(pg)
    ok(db("platformFees")[0]["data"]["status"] == "invoiced", "Status change saved")
    b.close()

    b, ctx, pg = session(p, "vendor@intelsense.test"); nav(pg, "partner-agreements"); pg.wait_for_timeout(300)
    ok(pg.locator("#vendorFeeCard").count() == 0 and "Chiang Mai hospital voice bot" not in pg.inner_text("#scr-partner-agreements"), "No platform fee summary on the vendor's Agreements page")
    b.close()

    sel = "select id from portal_records where collection in ('platformFees','programFees')"
    ok(mock.sql(sel, uid=USERS["partner@siamdigital.test"]["id"]) == [], "Partners can't read CloudWAV fees")
    ok(mock.sql(sel, uid=USERS["vendor@botnoi.test"]["id"]) == [], "Other vendors can't read them")
    ok(refused("update portal_records set data = jsonb_set(data,'{status}','\"paid\"') where collection='platformFees'", (), "vendor@intelsense.test")
       or db("platformFees")[0]["data"]["status"] == "invoiced", "Vendor can't mark their own fee paid")
    ok(refused("insert into portal_records(collection,id,data,readers,writers) values ('programFees','botnoi','{\"basePct\":0}',%s,%s)", (["vendor:botnoi"], ["vendor:botnoi"]), "vendor@botnoi.test"), "Vendor can't set their own fee")

stop_pg()
ok(not mock.errors, "No requests refused during normal use: " + "; ".join(mock.errors[:3]))
report()
