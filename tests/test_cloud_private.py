from harness import *
import os, sys, json
if not os.path.exists("/usr/lib/postgresql/16/bin/initdb"):
    print("SKIP: PostgreSQL 16 not installed"); srv.shutdown(); sys.exit(0)
import psycopg2
from pgmock import start_pg, PgSupabase

# Second security review, fix step 2: CloudWAV's private enrollment notes and members' HubSpot / Notion requests
# never go into a record other companies (or the public) can read.
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
def sql_as(email, q):
    return mock.sql(q, (), uid=USERS[email]["id"])
def session(p, email):
    b, ctx, pg = open_page_supabase(p, mock)
    pg.fill("#loginEmail", email); pg.fill("#loginPassword", PW[email]); pg.click("#loginSubmit"); pg.wait_for_timeout(1800)
    return b, ctx, pg
def settle(pg):
    for _ in range(60):
        if not pg.evaluate("CLOUD_PENDING()"): return True
        pg.wait_for_timeout(150)
    return False

# an enrollment saved before this fix, with CloudWAV's note still inside the shared record
con = psycopg2.connect(mock.dsn); con.autocommit = True; cur = con.cursor()
cur.execute("alter table public.portal_records disable trigger portal_records_guard")
cur.execute("insert into public.portal_records (collection, id, data, readers, writers, is_public) values ('enrollments', 'en-siam-intelsense', %s::jsonb, %s, '{}', false)",
            (json.dumps({"id": "en-siam-intelsense", "partnerId": "siam-digital", "partner": "Siam Digital MSP", "country": "Thailand", "programId": "intelsense",
                         "tier": "Reseller", "level": "Gold", "status": "active", "joined": "2025-11-04", "revenue12m": 182000, "dealsClosed": 9, "history": [],
                         "notes": "Old note: override 20%"}), ["partner:siam-digital", "vendor:intelsense"]))
cur.execute("alter table public.portal_records enable trigger portal_records_guard"); con.close()

with sync_playwright() as p:
    # ----- CloudWAV signs in: the old note moves to the private record by itself
    b, ctx, op = session(p, "ops@cloudwav.test"); settle(op)
    en = [r for r in db("enrollments") if r["id"] == "en-siam-intelsense"][0]
    notes = db("enrollmentNotes")
    ok("notes" not in en["data"], "The note is taken out of the shared enrollment record")
    ok(len(notes) == 1 and notes[0]["data"]["notes"] == "Old note: override 20%" and notes[0]["readers"] == [] and notes[0]["writers"] == [], "...and kept in a record only CloudWAV can read")
    # CloudWAV writes a new private note
    nav(op, "operator-partners"); op.wait_for_timeout(300)
    op.locator('[data-en-view="en-siam-intelsense"]').first.click(); op.wait_for_timeout(300)
    ok(op.input_value("#enNotes") == "Old note: override 20%", "CloudWAV still sees its note")
    op.fill("#enNotes", "Override 20% first year, agreed 1 Oct"); op.locator("#enNotes").dispatch_event("input"); op.locator("#enNotes").blur(); op.wait_for_timeout(300); settle(op)
    ok([r["data"]["notes"] for r in db("enrollmentNotes")] == ["Override 20% first year, agreed 1 Oct"] and "notes" not in [r for r in db("enrollments") if r["id"] == "en-siam-intelsense"][0]["data"],
       "A new note is saved privately, never into the shared record")
    b.close()

    # ----- the partner and the vendor on that enrollment can't read it
    for who in ("partner@siamdigital.test", "vendor@intelsense.test"):
        rows = sql_as(who, "select collection, data from public.portal_records where (collection = 'enrollments' and id = 'en-siam-intelsense') or collection = 'enrollmentNotes'")
        ok(len(rows) == 1 and rows[0]["collection"] == "enrollments" and "notes" not in rows[0]["data"], who.split("@")[0] + " sees the enrollment without CloudWAV's note")
    b, ctx, pt = session(p, "partner@siamdigital.test"); settle(pt)
    ok(pt.evaluate("JSON.stringify(document.body.innerText).indexOf('Override 20%') < 0"), "The partner's portal never shows the note")

    # ----- a partner asks for HubSpot: the request is private, and no contact card appears
    nav(pt, "integrations"); pt.wait_for_timeout(300)
    pt.locator("[data-int-hs]").first.check(); pt.click('[data-int-save="hubspot"]'); pt.wait_for_timeout(400); settle(pt)
    req = [r for r in db("integrationRequests") if r["id"] == "partner:siam-digital"]
    card = [r for r in db("contactChannels") if r["id"] == "partner:siam-digital"]
    ok(req and req[0]["data"]["integrations"]["hubspot"]["requested"] and req[0]["readers"] == ["partner:siam-digital"], "The HubSpot request is saved privately")
    ok(not card or ("integrations" not in card[0]["data"] and card[0]["readers"] == ["partner:siam-digital"]), "No contact card is shared because of it")
    b.close()
    rows = sql_as("vendor@intelsense.test", "select id from public.portal_records where collection = 'integrationRequests'")
    ok(rows == [], "Other companies can't see the request")

    # ----- CloudWAV still sees the request in Integrations
    b, ctx, op = session(p, "ops@cloudwav.test"); settle(op)
    nav(op, "integrations"); op.wait_for_timeout(400)
    ok("siam-digital" in op.inner_text("#intRequests").lower().replace(" ", "-"), "CloudWAV sees the partner's HubSpot request")
    b.close()
report()
