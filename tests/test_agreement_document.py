from harness import *

with sync_playwright() as p:
    b, pg = open_page(p)
    role(pg, "operator"); nav(pg, "operator-agreements")
    ok("Not entered yet" in pg.inner_text("[data-agr-legal-state]"), "Agreements screen says CloudWAV's legal details are not entered yet")
    # a new Software Project Referral Agreement with the demo software house
    opts = pg.locator("#agrNewParty option").evaluate_all("els => els.map(e => [e.value, e.textContent])")
    house = [o for o in opts if o[0].startswith("referral|")][0]
    pg.select_option("#agrNewParty", house[0]); pg.wait_for_timeout(100)
    ok(pg.input_value("#agrNewType") == "Software Project Referral Agreement", "A software house pre-selects the referral agreement")
    pg.click("[data-agr-create]"); pg.wait_for_timeout(300)
    row = pg.locator("#operatorAgreementsContent tr[data-agr-row]", has_text="Software Project Referral Agreement").filter(has_text="Draft").first
    aid = row.get_attribute("data-agr-row")
    row.locator("[data-agr-view]").click(); pg.wait_for_timeout(300)
    doc = pg.locator(".agr-doc")
    txt = doc.inner_text()
    ok(doc.locator("h2").count() >= 12 and "Referral fee" in txt and "Schedule A" in txt and "Signatures" in txt, "View opens the whole agreement: every section, the schedule and the signature block")
    name = house[1].split(" · ")[0]
    ok(doc.locator(".agr-filled", has_text=name).count() >= 1 and doc.locator(".agr-filled").count() > 15, "What the portal knows is filled in and highlighted (company name, rates, periods)")
    ok(doc.locator("input.agr-field.empty").count() >= 3 and "still to fill in" in pg.inner_text("#agrDocStatus"), "What it cannot know is left as fill-in fields, with a count")
    pg.click("[data-agr-doc-send]"); pg.wait_for_timeout(300)
    ok(pg.locator("[data-agr-doc]").count() == 1 and "draft" in row.inner_text().lower(), "It cannot be sent while fields are empty")
    # fill in from the document itself
    pg.fill('input[data-agr-field="effectiveDate"]', "2026-10-15"); pg.locator('input[data-agr-field="effectiveDate"]').dispatch_event("change")
    for k, val in [("cloudwavEntity", "CloudWAV Test LLC, a Wyoming limited liability company, of 1 Main St"), ("houseContact", "Somchai, somchai@house.example"), ("cloudwavContact", "Peter, legal@cloudwav.example")]:
        f = pg.locator(f'input[data-agr-field="{k}"]').first; f.fill(val); f.dispatch_event("change")
    pg.wait_for_timeout(200)
    ok("All fields are filled in" in pg.inner_text("#agrDocStatus") and pg.locator("input.agr-field.empty").count() == 0, "Filling the fields clears the count")
    pg.click(".modal-close"); pg.wait_for_timeout(200)
    row = pg.locator(f'#operatorAgreementsContent tr[data-agr-row="{aid}"]')
    row.locator("[data-agr-view]").click(); pg.wait_for_timeout(300)
    ok(pg.input_value('input[data-agr-field="houseContact"]') == "Somchai, somchai@house.example", "Typed values are kept on the agreement")
    pg.click("[data-agr-doc-send]"); pg.wait_for_timeout(400)
    ok("signature" in row.inner_text().lower(), "With everything filled it goes out for signature")
    row.locator("[data-agr-view]").click(); pg.wait_for_timeout(300)
    ok(pg.locator(".agr-doc input").count() == 0 and "CloudWAV Test LLC" in pg.inner_text(".agr-doc") and "2026-10-15" in pg.inner_text(".agr-doc") and pg.locator("[data-agr-doc-send]").count() == 0, "Once sent, the text is fixed: read-only, no blanks")
    ok(pg.locator("[data-agr-doc-print]").count() == 1 and pg.locator("[data-agr-doc-word]").count() == 1, "It can be printed / saved as PDF or downloaded for Word")
    pg.click(".modal-close"); pg.wait_for_timeout(200)

    # legal details, entered once, fill the next agreement
    pg.click("[data-agr-legal-open]"); pg.wait_for_timeout(200)
    pg.fill("#legalEntity", "CloudWAV Real LLC, a Wyoming limited liability company"); pg.fill("#legalContact", "Legal Desk, legal@cloudwav.example"); pg.click("[data-agr-legal-save]"); pg.wait_for_timeout(300)
    ok("Filled into every agreement" in pg.inner_text("[data-agr-legal-state]"), "Legal details saved")
    pg.select_option("#agrNewParty", house[0]); pg.click("[data-agr-create]"); pg.wait_for_timeout(300)
    row2 = pg.locator("#operatorAgreementsContent tr[data-agr-row]", has_text="Software Project Referral Agreement").filter(has_text="Draft").first
    row2.locator("[data-agr-view]").click(); pg.wait_for_timeout(300)
    ok(pg.input_value('input[data-agr-field="cloudwavEntity"] >> nth=0') == "CloudWAV Real LLC, a Wyoming limited liability company" and pg.input_value('input[data-agr-field="cloudwavContact"]') == "Legal Desk, legal@cloudwav.example", "A new agreement starts with CloudWAV's details already filled in")
    pg.click(".modal-close"); pg.wait_for_timeout(200)
    row.locator("[data-agr-view]").click(); pg.wait_for_timeout(300)
    ok("CloudWAV Test LLC" in pg.inner_text(".agr-doc") and "CloudWAV Real LLC" not in pg.inner_text(".agr-doc"), "The agreement already sent keeps the text it went out with")
    pg.click(".modal-close"); pg.wait_for_timeout(200)

    # agreements whose text is not in the portal say so
    pg.locator('#operatorAgreementsContent tr[data-agr-row="agr-vendor-intelsense"] [data-agr-view]').click(); pg.wait_for_timeout(300)
    ok(pg.locator("[data-agr-no-text]").count() == 1 and "Vendor Program Agreement" in pg.inner_text("[data-agr-no-text]"), "An agreement without its text in the portal says so plainly")
    pg.click("#modalClose2"); pg.wait_for_timeout(150)
    pg.reload(); pg.wait_for_timeout(900); role(pg, "operator"); nav(pg, "operator-agreements")
    pg.locator(f'#operatorAgreementsContent tr[data-agr-row="{aid}"] [data-agr-view]').click(); pg.wait_for_timeout(300)
    ok("CloudWAV Test LLC" in pg.inner_text(".agr-doc"), "Everything is still there after a reload")
    report()
    b.close()
