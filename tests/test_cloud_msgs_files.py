from harness import *
import os, sys, tempfile
if not os.path.exists("/usr/lib/postgresql/16/bin/initdb"):
    print("SKIP: PostgreSQL 16 not installed"); srv.shutdown(); sys.exit(0)
from pgmock import start_pg, stop_pg, PgSupabase

USERS = {
    "ops@cloudwav.test":        {"password": "op-pass-123",   "id": "11111111-0000-0000-0000-000000000001"},
    "vendor@intelsense.test":   {"password": "vend-pass-123", "id": "11111111-0000-0000-0000-000000000002"},
    "partner@siamdigital.test": {"password": "part-pass-123", "id": "11111111-0000-0000-0000-000000000003"},
    "partner@gulfcoast.test":   {"password": "gulf-pass-123", "id": "11111111-0000-0000-0000-000000000004"},
}
PORTAL = {
    USERS["ops@cloudwav.test"]["id"]:        {"role": "operator", "entity_id": None, "display_name": "Peter Phelan"},
    USERS["vendor@intelsense.test"]["id"]:   {"role": "vendor", "entity_id": "intelsense", "display_name": "Intelsense Admin"},
    USERS["partner@siamdigital.test"]["id"]: {"role": "partner", "entity_id": "siam-digital", "display_name": "Somchai K."},
    USERS["partner@gulfcoast.test"]["id"]:   {"role": "partner", "entity_id": "gulf-coast", "display_name": "Gulf Coast"},
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
def profile(pg, name):
    nav(pg, "partner-profile-editor"); pg.wait_for_timeout(300)
    pg.fill("#mpCompanyName", name); pg.fill("#mpCountry", "Thailand"); pg.fill("#mpTagline", "IT services")
    pg.click("#mpSaveBtn"); pg.wait_for_timeout(300); settle(pg)

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 100]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
pdf_path = os.path.join(tempfile.mkdtemp(), "intelsense-deck.pdf"); open(pdf_path, "wb").write(PDF)
big_path = os.path.join(tempfile.mkdtemp(), "big.pdf"); open(big_path, "wb").write(b"%PDF-1.4\n" + b"0" * (5 * 1024 * 1024))

with sync_playwright() as p:
    b, ctx, pg = session(p, "ops@cloudwav.test"); pg.wait_for_timeout(1500); settle(pg); b.close()   # shares starter records
    # partners create their profiles so they can be messaged
    b, ctx, pg = session(p, "partner@gulfcoast.test"); profile(pg, "Gulf Coast VAR"); b.close()
    b, ctx, pg = session(p, "partner@siamdigital.test"); profile(pg, "Siam Digital MSP")

    # ===== Messages: partner -> vendor
    nav(pg, "partner-messages")
    ok("No conversations yet" in pg.inner_text("#msgList"), "Signed in: no demo conversations")
    pg.select_option("#msgNewTo", "vendor:intelsense"); pg.wait_for_timeout(300)
    pg.fill("#msgCompose", "Hi Intelsense -- can we get a demo tenant for a Bangkok bank?"); pg.click("#msgSendBtn"); pg.wait_for_timeout(300)
    ok(settle(pg), "Message saved")
    m = db("messages")
    ok(len(m) == 1 and m[0]["data"]["from"] == "partner:siam-digital" and sorted(m[0]["readers"]) == ["partner:siam-digital", "vendor:intelsense"], "Message stored, readable only by the two people")
    # message Gulf Coast too (partner to partner)
    pg.select_option("#msgNewTo", "partner:gulf-coast"); pg.wait_for_timeout(300)
    pg.fill("#msgCompose", "Want to team up on the clinic project?"); pg.click("#msgSendBtn"); pg.wait_for_timeout(300); settle(pg)
    b.close()

    # ===== vendor sees it and replies
    b, ctx, pg = session(p, "vendor@intelsense.test")
    nav(pg, "partner-messages")
    lst = " | ".join(pg.locator("#msgList [data-open-convo]").all_inner_texts())
    ok("Siam Digital MSP" in lst and "demo tenant" in lst and "Gulf Coast" not in lst, "Vendor sees the partner's message (and not other people's)")
    ok(pg.locator("#msgList .unread-dot").count() == 1, "Shown as unread")
    pg.locator("#msgList [data-open-convo]").first.click(); pg.wait_for_timeout(200)
    ok("demo tenant" in pg.inner_text("#msgThreadBody"), "Opens the conversation")
    pg.fill("#msgCompose", "Yes -- I'll set one up today."); pg.click("#msgSendBtn"); pg.wait_for_timeout(300); settle(pg)
    b.close()

    # ===== Gulf Coast sees only their conversation; partner sees the vendor reply
    b, ctx, pg = session(p, "partner@gulfcoast.test"); nav(pg, "partner-messages")
    lst = " | ".join(pg.locator("#msgList [data-open-convo]").all_inner_texts())
    ok("Siam Digital MSP" in lst and "team up" in lst and "Intelsense" not in lst and "demo tenant" not in lst, "Other partner sees only their own conversation")
    b.close()
    b, ctx, pg = session(p, "partner@siamdigital.test"); nav(pg, "partner-messages")
    pg.locator("#msgList [data-open-convo]").filter(has_text="Intelsense").click(); pg.wait_for_timeout(200)
    ok("set one up today" in pg.inner_text("#msgThreadBody"), "Partner sees the vendor's reply")
    # message CloudWAV from the network "Message" button
    pg.select_option("#msgNewTo", "operator:"); pg.wait_for_timeout(300)
    pg.fill("#msgCompose", "Question about my Gold level"); pg.click("#msgSendBtn"); pg.wait_for_timeout(300); settle(pg)
    b.close()
    b, ctx, pg = session(p, "ops@cloudwav.test"); nav(pg, "partner-messages")
    lst = " | ".join(pg.locator("#msgList [data-open-convo]").all_inner_texts())
    ok("Gold level" in lst and "demo tenant" not in lst and "team up" not in lst, "CloudWAV inbox shows messages to CloudWAV, not partners' private chats")
    b.close()

    # ===== Files: vendor uploads a PDF to Supabase Storage
    b, ctx, pg = session(p, "vendor@intelsense.test")
    nav(pg, "resource-browse"); pg.locator('[data-goto-screen="resources-editor"]:visible').first.click(); pg.wait_for_timeout(250)
    pg.set_input_files("#resourceFileInput", big_path); pg.wait_for_timeout(300)
    ok("Attached: big.pdf" in pg.inner_text("#resourceFileStatus"), "Signed in: a 5 MB file is accepted (limit 50 MB, was 3 MB)")
    pg.set_input_files("#resourceFileInput", pdf_path); pg.wait_for_timeout(300)
    pg.fill("#resourceTitle", "Intelsense Partner Deck"); pg.select_option("#resourceType", "pdf")
    pg.fill("#resourceProgram", "Intelsense AI"); pg.fill("#resourceVendor", "Intelsense AI"); pg.fill("#resourceSummary", "Partner-facing overview")
    pg.click('#resourceForm button[type=submit]'); pg.wait_for_timeout(2500); settle(pg)
    pr = db("pendingResources")
    ok(len(pr) == 1 and pr[0]["data"].get("filePath", "").startswith("resources/") and not pr[0]["data"].get("fileData"), "Resource record points at the stored file (no file data in the database row)")
    key = "portal-files/" + pr[0]["data"]["filePath"]
    ok(key in mock.files and mock.files[key][0].startswith(b"%PDF-1.4"), "The PDF itself is in Supabase Storage")
    b.close()

    # ===== partner can't see the pending file; operator reviews it
    rows = mock.sql("select name from storage.objects", uid=USERS["partner@siamdigital.test"]["id"])
    ok(rows == [], "Other users can't see a pending file")
    b, ctx, pg = session(p, "ops@cloudwav.test")
    nav(pg, "resource-approvals")
    card = pg.locator("#approvalQueueGrid .card").filter(has_text="Intelsense Partner Deck")
    ok("File attached: intelsense-deck.pdf" in card.inner_text(), "Queue shows the stored file")
    card.locator('[data-review-decision=""]').click(); pg.wait_for_timeout(1200)
    fr = pg.locator("#approvalReviewContent .res-preview iframe")
    ok(fr.count() == 1 and "/storage/v1/object/sign/portal-files/resources/" in fr.get_attribute("src"), "Preview uses a short-lived signed link")
    head = pg.evaluate("async () => { const r = await fetch(document.querySelector('#approvalReviewContent .res-preview iframe').src); return (await r.text()).slice(0, 8); }")
    ok(head == "%PDF-1.4", "Operator opens the actual uploaded PDF")
    pg.select_option("#approvalDecision", "approve"); pg.click('#approvalForm button[type=submit]'); pg.wait_for_timeout(500); settle(pg)
    b.close()

    # ===== partner opens the published file
    b, ctx, pg = session(p, "partner@siamdigital.test")
    nav(pg, "resource-browse"); pg.wait_for_timeout(300)
    pg.locator('[data-open-resource]').first.click(); pg.wait_for_timeout(1200)
    ok(pg.locator(".modal .res-preview iframe").count() == 1, "Partner opens the published file from the Resource Library")
    b.close()

stop_pg()
ok(not mock.errors, "No requests refused during normal use: " + "; ".join(mock.errors[:3]))
report()
