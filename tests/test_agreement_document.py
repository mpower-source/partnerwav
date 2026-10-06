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

    # the one agreement type with no text yet says so
    pg.locator('#operatorAgreementsContent tr[data-agr-row="agr-vendor-unisense"] [data-agr-view]').click(); pg.wait_for_timeout(300)
    ok(pg.locator("[data-agr-no-text]").count() == 1 and "SaaS Reseller Agreement" in pg.inner_text("[data-agr-no-text]"), "SaaS Reseller Agreement (no text written yet) says so plainly")
    pg.click("#modalClose2"); pg.wait_for_timeout(150)

    # ----- Vendor Program Agreement: full text, filled from the program's configuration
    pg.locator('#operatorAgreementsContent tr[data-agr-row="agr-vendor-crossconnect"] [data-agr-edit]').click(); pg.wait_for_timeout(200)
    pg.select_option("#agrEditStatus", "draft"); pg.click("[data-agr-edit-save]"); pg.wait_for_timeout(300)
    pg.locator('#operatorAgreementsContent tr[data-agr-row="agr-vendor-crossconnect"] [data-agr-view]').click(); pg.wait_for_timeout(400)
    d = pg.locator(".agr-doc"); t = d.inner_text()
    ok("PartnerWAV Vendor Program Agreement" in t and d.locator("h2").count() >= 20 and all(x in t for x in ["The tier ladder", "Deal registration and conflict rules", "Certified Installer Network", "Professional services", "Schedule B", "Schedule F", "Signatures"]), "Vendor Program Agreement shows in full: 15 sections and Schedules A-F")
    flat = " ".join(t.split())
    ok('5.4 "Net Revenue" means' in flat and "5.2 The Override is additive" in flat and "6.3 The Vendor will not deal directly" in flat and "13.2 Either party may terminate for convenience" in flat and "13.5 Any post-termination restriction" in flat, "Clause numbers match the agreement outline (5.2, 5.4, 6.3, 13.2, 13.5)")
    ok(d.locator(".agr-table .agr-table td", has_text="Affiliate").count() >= 1 and "12% on hardware sale" in t and "Cross Connect" in t, "Schedule B carries the program's own tiers and rates")
    ok("90 days" in t and "Net Revenue" not in d.locator("p", has_text="Commission is calculated on").first.inner_text() and "Gross Revenue" in t, "Protection window and revenue base come from the program's configuration (Cross Connect pays on gross)")
    ok("platform fee of 3%" in t and "6%" in t, "The platform fee clause reflects the fee set in the portal")
    ok(pg.input_value('input[data-agr-field="cloudwavEntity"] >> nth=0') == "CloudWAV Real LLC, a Wyoming limited liability company" and pg.input_value('input[data-agr-field="cureDays"]') == "30", "CloudWAV details and standard values are pre-filled, and stay editable")
    miss = pg.inner_text("#agrDocStatus")
    ok("still to fill in" in miss and "Territory" in miss and "Their legal entity" in miss, "It lists what only you can supply (their legal entity, territory, governing law...)")
    for k, val in [("effectiveDate", "2026-11-01"), ("partyEntity", "Cross Connect Inc., a Delaware corporation"), ("territory", "United States and Thailand"), ("governingLaw", "the laws of the State of Wyoming, USA"), ("arbitrationSeat", "seated in Cheyenne, Wyoming under the AAA Commercial Rules"), ("partyContact", "Dana, dana@crossconnect.example")]:
        f = pg.locator(f'input[data-agr-field="{k}"]').first; f.fill(val); f.dispatch_event("change")
    pg.wait_for_timeout(200)
    ok("All fields are filled in" in pg.inner_text("#agrDocStatus"), "Filling them clears the list")
    ok(pg.locator('input[data-agr-field="effectiveDate"]').count() >= 2 and all(v == "2026-11-01" for v in pg.locator('input[data-agr-field="effectiveDate"]').evaluate_all("els => els.map(e => e.value)")), "A field that appears twice (opening line and schedule) stays in step")
    pg.click("[data-agr-doc-send]"); pg.wait_for_timeout(400)
    pg.locator('#operatorAgreementsContent tr[data-agr-row="agr-vendor-crossconnect"] [data-agr-view]').click(); pg.wait_for_timeout(300)
    t = pg.inner_text(".agr-doc")
    ok(pg.locator(".agr-doc input").count() == 0 and "Cross Connect Inc., a Delaware corporation" in t and "United States and Thailand" in t and "{{" not in t and "undefined" not in t, "Sent: fixed text, nothing left unfilled, no stray placeholders")
    pg.click(".modal-close"); pg.wait_for_timeout(200)

    # ----- the other three open in full too, with no stray placeholders
    for rowid, title, must in [("agr-vendor-botnoi", "PartnerWAV Joint Venture Agreement", ["Governance and Reserved Matters", "Exit, buy-sell and valuation", "Schedule F"]),
                               ("agr-vendor-zipevent", "PartnerWAV Custom Marketing Agreement", ["Marketing development fund", "Brand use and co-branding", "Schedule B -- MDF expense categories"]),
                               ("agr-partner-siam-digital-botnoi", "PartnerWAV Reseller Agreement", ["One account, many programs", "Deal registration and non-circumvention", "Schedule A -- Programs enrolled"])]:
        pg.locator(f'#operatorAgreementsContent tr[data-agr-row="{rowid}"] [data-agr-view]').click(); pg.wait_for_timeout(300)
        t = pg.inner_text(".agr-doc")
        ok(title in t and all(m in t for m in must) and "{{" not in t and "undefined" not in t and "Signatures" in t, title + " opens in full")
        pg.click(".modal-close"); pg.wait_for_timeout(150)
    pg.locator('#operatorAgreementsContent tr[data-agr-row="agr-partner-siam-digital-botnoi"] [data-agr-view]').click(); pg.wait_for_timeout(300)
    t = pg.inner_text(".agr-doc")
    ok("Intelsense AI" in t and "Botnoi Voice" in t and "Thailand" in t, "Reseller Agreement lists the partner's enrolled programs and country")
    pg.click(".modal-close"); pg.wait_for_timeout(150)
    # the partner reads the same document, read-only
    role(pg, "partner"); nav(pg, "partner-agreements")
    pg.locator('#agreementsContent tr[data-agr-row="agr-partner-siam-digital-botnoi"] [data-agr-view]').click(); pg.wait_for_timeout(300)
    ok("PartnerWAV Reseller Agreement" in pg.inner_text(".agr-doc") and pg.locator(".agr-doc input").count() == 0 and pg.locator("[data-agr-doc-send]").count() == 0, "The partner sees the full agreement, read-only")
    pg.click(".modal-close"); pg.wait_for_timeout(150)
    pg.reload(); pg.wait_for_timeout(900); role(pg, "operator"); nav(pg, "operator-agreements")
    pg.locator(f'#operatorAgreementsContent tr[data-agr-row="{aid}"] [data-agr-view]').click(); pg.wait_for_timeout(300)
    ok("CloudWAV Test LLC" in pg.inner_text(".agr-doc"), "Everything is still there after a reload")
    report()
    b.close()
