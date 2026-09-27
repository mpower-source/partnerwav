from harness import *

with sync_playwright() as p:
    b, pg = open_page(p)
    role(pg, "operator")
    for scr in ("operator-msp-engagements", "operator-landing-pages"):
        ok(pg.locator(f'[data-screen="{scr}"]:visible').count() == 1, f"{scr} is in the Operator menu")

    # --- engagement tracker starts empty and explains how to fill it
    nav(pg, "operator-msp-engagements")
    ok("No outreach logged yet" in pg.inner_text("#engagementRows"), "Empty tracker explains where entries come from")

    # --- log activity from MSP Prospecting
    nav(pg, "operator-msp-prospects")
    pg.click('[data-msp-log="apl-gopomelo"]'); pg.wait_for_timeout(200)
    pg.select_option("#engMethod", "Botnoi voice call"); pg.select_option("#engVendor", "botnoi")
    pg.select_option("#engOutcome", "meeting"); pg.fill("#engNotes", "Owner keen on Thai voice AI for hotel front desks; demo on Friday")
    pg.click("#engSave"); pg.wait_for_timeout(200)
    ok(pg.input_value("#mspStage-apl-gopomelo") == "interested", "Meeting booked moves the prospect to Interested")

    # --- invite also logs an engagement
    pg.click('[data-msp-invite="apl-clarityit"]'); pg.wait_for_timeout(200)
    pg.select_option("#mspInvProgram", "intelsense"); pg.click("#mspInvCopy"); pg.wait_for_timeout(200)
    pg.click(".modal-close"); pg.wait_for_timeout(150)

    nav(pg, "operator-msp-engagements")
    rows = pg.locator("#engagementRows tr")
    ok(rows.count() == 2, "Tracker lists both touches: " + str(rows.count()))
    txt = pg.inner_text("#engagementRows")
    ok("Botnoi voice call" in txt and "GoPomelo" in txt and "hotel front desks" in txt, "Logged call shows method, MSP and notes")
    ok("Email invitation" in txt and "Clarity IT" in txt, "Invite was logged automatically")
    stats = pg.inner_text("#engStats")
    ok("2" in stats and "contacted" in stats and "meetings" in stats, "Funnel stats: " + stats.replace("\n", " "))
    # update outcome inline -> onboarded
    eid = pg.locator("#engagementRows [data-eng-outcome]").first.get_attribute("data-eng-outcome")
    row_msp = pg.locator("#engagementRows tr").first.inner_text()
    pg.select_option(f'[data-eng-outcome="{eid}"]', "onboarded"); pg.wait_for_timeout(200)
    ok("1onboarded" in pg.inner_text("#engStats").replace(" ", "").replace("\n", ""), "Outcome change updates funnel")
    pg.select_option("#engMethodFilter", "Botnoi voice call"); pg.wait_for_timeout(150)
    ok(pg.locator("#engagementRows tr").count() == 1, "Method filter")
    pg.select_option("#engMethodFilter", ""); pg.wait_for_timeout(100)

    # --- landing pages
    nav(pg, "operator-landing-pages")
    ok(pg.locator("#landingPagesList .msp-card").count() == 3, "3 restored landing pages (as drafts)")
    ok(pg.locator("#landingPagesList .badge.good").count() == 0, "None published until the vendor signs off")
    pg.locator('[data-lp-edit="lp-intelsense-demo"]').click(); pg.wait_for_timeout(250)
    ok(visible_screen(pg) == ["scr-landing-page-editor"] and pg.input_value("#lpTitle") == "Intelsense AI - Partner Program", "Editor loads the page")
    pg.click('[data-lp-save="publish"]'); pg.wait_for_timeout(150)
    err = pg.inner_text("#lpError")
    ok("headline" in err and "vendor has approved" in err, "Publishing requires copy + vendor approval")
    pg.click("[data-lp-draft]"); pg.wait_for_timeout(150)
    head = pg.input_value("#lpHeadline"); body = pg.input_value("#lpBody")
    ok(head == "Intelsense AI for MSPs and VARs in Thailand" and "Reseller partners earn 15% + 5%" in body, "Draft copy pulls vendor details + commission terms")
    pg.fill("#lpHeadline", "Sell Intelsense AI to your Thai customers")
    pg.wait_for_timeout(100)
    ok("Sell Intelsense AI to your Thai customers" in pg.inner_text("#lpPreview"), "Live preview")
    pg.check("#lpVendorApproved"); pg.click('[data-lp-save="publish"]'); pg.wait_for_timeout(250)
    card = pg.locator("#landingPagesList .msp-card").filter(has_text="Intelsense AI - Partner Program")
    ok("PUBLISHED" in card.inner_text().upper() and "?lp=lp-intelsense-demo" in card.inner_text(), "Published with a public link")

    # new page
    pg.click("[data-lp-new]"); pg.wait_for_timeout(200)
    pg.select_option("#lpVendor", "botnoi"); pg.fill("#lpTitle", "Botnoi Voice -- Chiang Mai MSPs")
    pg.fill("#lpCtaUrl", "not-a-url"); pg.click('[data-lp-save="draft"]'); pg.wait_for_timeout(150)
    ok("full web address" in pg.inner_text("#lpError"), "Validates button link")
    pg.fill("#lpCtaUrl", ""); pg.click('[data-lp-save="draft"]'); pg.wait_for_timeout(200)
    ok(pg.locator("#landingPagesList .msp-card").count() == 4, "New draft saved")

    # invite can use the landing page
    nav(pg, "operator-msp-prospects")
    pg.click('[data-msp-invite="apl-beryl8"]'); pg.wait_for_timeout(200)
    pg.select_option("#mspInvProgram", "intelsense"); pg.wait_for_timeout(100)
    opts = pg.locator("#mspInvLink option").all_inner_texts()
    ok(any("Landing page: Intelsense AI - Partner Program" in o for o in opts), "Invite offers the published landing page")
    pg.select_option("#mspInvLink", "lp-intelsense-demo"); pg.wait_for_timeout(100)
    ok("?lp=lp-intelsense-demo" in pg.input_value("#mspInvBody"), "Invitation links to the landing page")
    pg.click(".modal-close"); pg.wait_for_timeout(100)
    b.close()

    # --- public page (no sign-in, no portal chrome). Data lives in this browser until the Supabase move,
    # so reuse the same storage by opening a new page in a context that has it.
    b = p.chromium.launch(); ctx = b.new_context()
    pg = ctx.new_page(); pg.goto(URL + "?demo=1"); pg.wait_for_timeout(500)
    pg.evaluate("""() => { const pages = [{ id:"lp-test", vendorId:"intelsense", title:"Intelsense AI - Partner Program", targetAudience:"MSPs and VARs in Thailand",
      cta:"Apply to become a partner", ctaUrl:"", features:["Four products to resell"], headline:"Sell Intelsense AI to your Thai customers", body:"Body text", status:"published", vendorApproved:true }];
      localStorage.setItem("partnerWAV_landingPages", JSON.stringify(pages)); }""")
    pg.goto(URL + "?lp=lp-test"); pg.wait_for_timeout(700)
    ok(visible_screen(pg) == ["scr-public-landing"] and not pg.locator("#loginScreen").is_visible(), "Public landing page opens without sign-in")
    ok(not pg.locator(".sidebar").is_visible(), "No portal navigation on the public page")
    ok("Sell Intelsense AI to your Thai customers" in pg.inner_text("#publicLandingContent"), "Shows the published copy")
    href = pg.locator("#publicLandingContent .lp-cta").get_attribute("href")
    ok("?apply=vendor&vendorId=intelsense" in href, "Button goes to the vendor's partner application")
    pg.click("#publicLandingContent .lp-cta"); pg.wait_for_timeout(700)
    ok(visible_screen(pg) == ["scr-public-partner-apply"], "Clicking through opens the application form")
    pg.goto(URL + "?lp=does-not-exist"); pg.wait_for_timeout(600)
    ok("isn't available" in pg.inner_text("#publicLandingContent"), "Unknown/unpublished page handled")
    pg.set_viewport_size({"width": 390, "height": 844}); pg.goto(URL + "?lp=lp-test"); pg.wait_for_timeout(600)
    ok(pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0, "Public page fits at 390px")
    b.close()
report()
