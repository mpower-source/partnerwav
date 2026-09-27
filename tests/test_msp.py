from harness import *

with sync_playwright() as p:
    b, pg = open_page(p)
    role(pg, "operator")
    ok(pg.locator('[data-screen="operator-msp-prospects"]:visible').count() == 1, "MSP Prospecting is back in the Operator menu")
    nav(pg, "operator-msp-prospects")
    ok(visible_screen(pg) == ["scr-operator-msp-prospects"], "MSP Prospecting screen opens")
    cards = pg.locator("#mspProspectsList .msp-card")
    ok(cards.count() == 5, "The 5 original Thailand MSP records are restored")
    ok(pg.locator("#mspProspectsList .badge.warn").count() == 5, "Placeholder records are labelled Sample data")

    # filters
    pg.fill("#mspSearchInput", "hospitality"); pg.wait_for_timeout(150)
    ok(cards.count() == 1 and "Phuket Tech Partners" in cards.first.inner_text(), "Search by specialty")
    pg.fill("#mspSearchInput", ""); pg.wait_for_timeout(100)
    pg.select_option("#mspCountryFilter", "Chiang Mai"); pg.wait_for_timeout(150)
    ok(cards.count() == 1 and "Chiang Mai Digital Solutions" in cards.first.inner_text(), "Location filter")
    pg.click("#mspResetFilter"); pg.wait_for_timeout(150)
    ok(cards.count() == 5, "Reset filters")

    # add a real VAR
    pg.click("[data-msp-add]"); pg.wait_for_timeout(200)
    pg.click("#mspFSave"); pg.wait_for_timeout(100)
    ok("Company name is required" in pg.inner_text("#mspFError"), "Add prospect validates required fields")
    pg.fill("#mspF_name", "Krungthep Systems Integration"); pg.select_option("#mspF_type", "VAR")
    pg.fill("#mspF_city", "Bangkok"); pg.fill("#mspF_email", "not-an-email"); pg.click("#mspFSave"); pg.wait_for_timeout(100)
    ok("valid email" in pg.inner_text("#mspFError"), "Email validated")
    pg.fill("#mspF_email", "partners@krungthep-si.example"); pg.fill("#mspF_specialties", "Network Engineering, Cybersecurity")
    pg.click("#mspFSave"); pg.wait_for_timeout(200)
    ok(cards.count() == 6 and "Krungthep Systems Integration" in cards.first.inner_text() and "VAR" in cards.first.inner_text(), "New VAR added at the top")
    pg.select_option("#mspTypeFilter", "VAR"); pg.wait_for_timeout(150)
    ok(cards.count() == 1, "Type filter: VARs only")
    pg.select_option("#mspTypeFilter", ""); pg.wait_for_timeout(100)

    # stage + notes
    pg.select_option("#mspStage-msp-th-2", "contacted"); pg.wait_for_timeout(150)
    pg.fill("#mspNotes-msp-th-2", "Spoke to Khun Nok, wants a Unisense demo"); pg.locator("#mspNotes-msp-th-2").blur(); pg.wait_for_timeout(150)
    ok("1" in pg.locator("#mspStats .map-stat").nth(1).inner_text(), "Stage change counted in stats")
    pg.select_option("#mspStageFilter", "contacted"); pg.wait_for_timeout(150)
    ok(cards.count() == 1 and "Chiang Mai" in cards.first.inner_text(), "Stage filter")
    pg.select_option("#mspStageFilter", ""); pg.wait_for_timeout(100)

    # invite a sample record: can't send without a real email; copy works
    pg.click('[data-msp-invite="msp-th-1"]'); pg.wait_for_timeout(200)
    ok("sample" in pg.inner_text(".modal").lower() and pg.input_value("#mspInvEmail") == "", "Sample record: warns and leaves recipient empty")
    pg.select_option("#mspInvProgram", "intelsense"); pg.wait_for_timeout(100)
    body = pg.input_value("#mspInvBody")
    ok("Intelsense AI" in body and "?apply=vendor&vendorId=intelsense" in body and "Bangkok IT Services Co." in body, "Invitation includes the vendor's partner-application link")
    pg.click("#mspInvSend"); pg.wait_for_timeout(100)
    ok("valid email" in pg.inner_text("#mspInvError"), "Won't send to an empty/sample address")
    pg.click("#mspInvCopy"); pg.wait_for_timeout(200)
    pg.click(".modal-close"); pg.wait_for_timeout(150)
    card1 = pg.locator('[data-msp-card="msp-th-1"]')
    ok("Invited to Intelsense AI" in card1.inner_text() and pg.input_value("#mspStage-msp-th-1") == "invited", "Copying the invite marks the prospect Invited")

    # invite the real VAR via email app
    first_id = pg.locator("#mspProspectsList .msp-card").first.get_attribute("data-msp-card")
    pg.click(f'[data-msp-invite="{first_id}"]'); pg.wait_for_timeout(200)
    ok(pg.input_value("#mspInvEmail") == "partners@krungthep-si.example", "Real prospect: recipient pre-filled")
    pg.select_option("#mspInvProgram", "botnoi"); pg.wait_for_timeout(100)
    ok("vendorId=botnoi" in pg.input_value("#mspInvBody"), "Changing program updates the link")
    pg.click("#mspInvSend"); pg.wait_for_timeout(400)
    ok("Invited to Botnoi Voice" in pg.locator(f'[data-msp-card="{first_id}"]').inner_text(), "Sending marks it Invited to Botnoi Voice")

    # persistence
    pg.reload(); pg.wait_for_timeout(700); role(pg, "operator"); nav(pg, "operator-msp-prospects")
    ok(pg.locator("#mspProspectsList .msp-card").count() == 6 and pg.input_value("#mspNotes-msp-th-2") == "Spoke to Khun Nok, wants a Unisense demo", "Prospects, stages and notes persist")

    # partner collaborations
    role(pg, "partner")
    ok(pg.locator('[data-screen="partner-collaboration-finder"]:visible').count() == 1, "Partner Collaborations back in the Partner menu")
    nav(pg, "partner-collaboration-finder")
    cc = pg.locator("#partnerCollaborationList .msp-card")
    ok(cc.count() == 5, "5 collaboration posts restored")
    ok("Posted by Gulf Coast VAR" in pg.inner_text("#partnerCollaborationList"), "Shows partner names, not ids")
    pg.select_option("#collabRegionFilter", "europe"); pg.wait_for_timeout(150)
    ok(cc.count() == 2, "Region filter works (Europe: 2)")
    pg.select_option("#collabRegionFilter", "apac"); pg.wait_for_timeout(150)
    ok(cc.count() == 2, "Region filter works (Asia Pacific: 2)")
    pg.click("#collabResetFilter"); pg.wait_for_timeout(100)
    pg.select_option("#collabTypeFilter", "joint-marketing"); pg.wait_for_timeout(150)
    ok(cc.count() == 1, "Type filter: Joint marketing")
    pg.click("#collabResetFilter"); pg.wait_for_timeout(100)
    ok("Your post" in cc.filter(has_text="Healthcare Digitization").inner_text().title() or "YOUR POST" in cc.filter(has_text="Healthcare Digitization").inner_text().upper(), "Own post can't be 'interested' in")
    cc.filter(has_text="Tampa Bay").locator("[data-express-interest]").click(); pg.wait_for_timeout(150)
    ok("Interest sent" in cc.filter(has_text="Tampa Bay").inner_text(), "Express interest works")
    pg.reload(); pg.wait_for_timeout(600); nav(pg, "partner-collaboration-finder")
    ok("Interest sent" in pg.locator("#partnerCollaborationList .msp-card").filter(has_text="Tampa Bay").inner_text(), "Interest persists after reload")

    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0, "No horizontal overflow at 390px")
    b.close()
report()
