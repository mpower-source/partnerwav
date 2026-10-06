from harness import *
import os, tempfile

with sync_playwright() as p:
    b, pg = open_page(p)
    # ----- Vendor Network filters
    role(pg, "partner"); nav(pg, "vendor-network")
    def names(): return [x.strip() for x in pg.locator("#vendorNetworkGrid .program-name").all_inner_texts()]
    def flt(v): pg.click(f'#vendorNetworkFilterRow [data-rel-filter="{v}"]'); pg.wait_for_timeout(200); return names()
    allv = flt("all")
    ok(len(allv) == len(set(allv)) and "CloudWAV Consulting" in allv, "All: every vendor and product once, including CloudWAV Consulting")
    saas = flt("SaaS Resale")
    ok(set(saas) == {"Unisense", "Finsense AI", "AI Hubspot", "AlterCrew"}, "SaaS Resale shows all four SaaS products: " + ", ".join(saas))
    ok(set(flt("Vendor Program")) == {"Intelsense AI", "Cross Connect", "Botnoi Voice", "CloudWAV Consulting"}, "Vendor Program shows the vendor programs only")
    ok(set(flt("Joint Venture")) == {"Botnoi Voice", "Portonics Ltd."}, "Joint Venture shows Botnoi and Portonics")
    ok(flt("Custom Marketing") == ["ZipEvent"], "Custom Marketing shows ZipEvent")
    for f in ["Vendor Program", "Joint Venture", "Custom Marketing", "SaaS Resale"]:
        got = flt(f)
        bad = pg.evaluate("""(f)=>[...document.querySelectorAll('#vendorNetworkGrid .program-card')].filter(c=>!c.querySelector('.program-top').innerText.toLowerCase().includes(f.toLowerCase()) && !c.querySelector('.badge.accent2')).length""", f)
        ok(bad == 0 and len(got) > 0, f"{f}: every tile shown carries that relationship badge")
    flt("all")
    card = pg.locator("#vendorNetworkGrid .program-card", has_text="CloudWAV Consulting").first
    ok("fractional CIO, CTO, CISO and CAIO" in card.inner_text() and len(card.locator(".program-desc").inner_text()) < 260, "CloudWAV Consulting tile has the short summary")
    nav(pg, "partner-directory"); pg.click('#directoryFilterRow [data-rel-filter="all"]')
    ok("CloudWAV Consulting" in pg.inner_text("#directoryGrid"), "CloudWAV Consulting is in the Program Directory too")

    # ----- menu order
    order = pg.evaluate("[...document.querySelectorAll('#navPartner [data-sec=\"business\"] .navlink')].map(b=>b.getAttribute('data-screen'))")
    ok(order.index("partner-my-leads") < order.index("partner-commissions"), "Partner > My Business: My Leads is above Commissions")
    role(pg, "operator")
    order = pg.evaluate("[...document.querySelectorAll('#navOperator [data-sec=\"vendors\"] .navlink')].map(b=>b.getAttribute('data-screen'))")
    ok(order[0] == "operator-assessments" and order[-1] == "vendor-network" and len(order) == 5, "Operator > Vendors & Programs: Assessments first, Vendor Network last")

    # ----- agreements: CloudWAV Consulting as a party
    nav(pg, "operator-agreements")
    opts = pg.locator("#agrNewParty option").all_inner_texts()
    ok(any(o.startswith("CloudWAV Consulting") and "Partner" in o for o in opts) and sum(o.startswith("CloudWAV Consulting") and "Partner" in o for o in opts) == 1, "CloudWAV Consulting is listed once as a partner to make agreements with")
    ok(not any(o == "CloudWAV Consulting · Vendor" for o in opts), "No vendor agreement between CloudWAV and itself")
    pg.select_option("#agrNewParty", "partner|partner:cloudwav-consulting"); pg.select_option("#agrNewProgram", "botnoi"); pg.click("[data-agr-create]"); pg.wait_for_timeout(300)
    row = pg.locator("#operatorAgreementsContent tr[data-agr-row]", has_text="CloudWAV Consulting").filter(has_text="Partner Reseller Agreement")
    ok(row.count() == 1 and "Botnoi Voice" in row.inner_text() and "Partner Reseller Agreement" in row.inner_text(), "Partner agreement between CloudWAV Consulting and Botnoi created")
    ok(row.locator("[data-agr-paper]").count() == 0 and row.locator('[data-agr-act="sent"]').count() == 1, "Our own paper can go straight out for signature")

    # ----- their own agreement: upload, review, then send
    d = tempfile.mkdtemp(); f = os.path.join(d, "Portonics MSA.pdf"); open(f, "wb").write(b"%PDF-1.4\n% test\n")
    bad = os.path.join(d, "notes.txt"); open(bad, "w").write("x")
    n0 = pg.locator("#operatorAgreementsContent tr[data-agr-row]").count()
    pg.select_option("#agrNewParty", "vendor|vendor:portonics-dev"); pg.select_option("#agrNewPaper", "outside"); pg.wait_for_timeout(100)
    ok(pg.locator("#agrNewFile").is_visible(), "Choosing 'Their own agreement' shows the file upload")
    pg.set_input_files("#agrNewFile", bad); pg.click("[data-agr-create]"); pg.wait_for_timeout(300)
    ok(pg.locator("#operatorAgreementsContent tr[data-agr-row]").count() == n0, "Only PDF or Word files are accepted")
    pg.select_option("#agrNewParty", "vendor|vendor:portonics-dev"); pg.select_option("#agrNewPaper", "outside"); pg.set_input_files("#agrNewFile", f); pg.click("[data-agr-create]"); pg.wait_for_timeout(500)
    row = pg.locator("#operatorAgreementsContent tr[data-agr-row]", has_text="Portonics Ltd.").filter(has_text="Their own agreement")
    t = row.inner_text()
    ok("Their own agreement" in t and "Portonics MSA.pdf" in t and "Needs review" in t, "Outside agreement is listed with its file and 'Needs review'")
    row.locator('[data-agr-act="sent"]').click(); pg.wait_for_timeout(300)
    ok(row.locator('[data-agr-act="signed"]').count() == 0 and row.locator('[data-agr-act="sent"]').count() == 1 and "Needs review" in row.inner_text(), "It cannot be sent for signature before it is reviewed")
    row.locator("[data-agr-review]").click(); pg.wait_for_timeout(200)
    ok(pg.locator("[data-agr-file]").count() == 1 and pg.locator("#agrReviewNote").is_visible(), "Review dialog: open the file, write notes")
    pg.fill("#agrReviewNote", "Their liability cap is lower; commission clause matches ours."); pg.click('[data-agr-review-save="reviewed"]'); pg.wait_for_timeout(300)
    ok("Reviewed" in row.inner_text() and row.locator("[data-agr-review]").count() == 0, "Marked reviewed")
    row.locator('[data-agr-act="sent"]').click(); pg.wait_for_timeout(300)
    ok("signature" in row.inner_text().lower() and row.locator('[data-agr-act="signed"]').count() == 1, "After review it goes out for signature")
    # switch one of ours to their paper
    row2 = pg.locator("#operatorAgreementsContent tr[data-agr-row]", has_text="CloudWAV Consulting").filter(has_text="Partner Reseller Agreement")
    row2.locator("[data-agr-outside]").click(); pg.wait_for_timeout(200)
    ok(pg.locator("[data-agr-outside-modal]").count() == 1 and "No file yet" in pg.inner_text(".modal"), "'Use their agreement' switches a draft to their paper")
    pg.click('[data-agr-review-save="reviewed"]'); pg.wait_for_timeout(200)
    ok(pg.locator("[data-agr-outside-modal]").count() == 1, "Cannot be marked reviewed without a file")
    pg.set_input_files("#agrFileReplace", f); pg.click('[data-agr-review-save="needed"]'); pg.wait_for_timeout(500)
    ok("Portonics MSA.pdf" in row2.inner_text() and "Needs review" in row2.inner_text(), "File uploaded later from the dialog")
    pg.reload(); pg.wait_for_timeout(900)
    role(pg, "operator"); nav(pg, "operator-agreements")
    ok("Portonics MSA.pdf" in pg.inner_text("#operatorAgreementsContent"), "Agreements and files are still there after a reload")
    pg.locator("#operatorAgreementsContent tr[data-agr-row]", has_text="Portonics Ltd.").filter(has_text="Their own agreement").locator("[data-agr-view]").click(); pg.wait_for_timeout(200)
    ok("liability cap" in pg.input_value("#agrReviewNote") if pg.locator("#agrReviewNote").count() else "liability cap" in pg.inner_text(".modal"), "CloudWAV's review notes are kept")
    report()
    b.close()
