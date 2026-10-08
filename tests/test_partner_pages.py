from harness import *
import json

def pages(pg):
    return json.loads(pg.evaluate("localStorage.getItem('partnerWAV_partnerPages')") or "[]")

with sync_playwright() as p:
    b, pg = open_page(p)
    role(pg, "partner"); open_menu(pg, "partner-pages")
    ok(pg.locator('[data-screen="partner-pages"]:visible').count() == 1, "Partner menu has Landing Pages")
    role(pg, "vendor"); open_menu(pg, "vendor-overview")
    ok(pg.locator('#navVendor [data-screen="partner-pages"]').count() == 0, "Vendors don't get landing pages")
    nav(pg, "branding"); pg.wait_for_timeout(200)
    prev = pg.inner_text("#brandPreview").upper()
    ok("INVITE PAGE" in prev and "LANDING PAGE" not in prev and "INCENTIVE FLYER" in prev, "Vendor Branding previews the invite page and flyer, not a landing page")

    # ----- a partner makes a product page with a demo request
    role(pg, "partner"); nav(pg, "partner-pages"); pg.wait_for_timeout(200)
    ok("No landing pages yet" in pg.inner_text("#partnerPagesContent"), "Starts empty")
    pg.click("[data-pp-new]"); pg.wait_for_timeout(200)
    vend = pg.evaluate("[...document.querySelectorAll('#ppVendorPick option')].map(o=>o.value)")
    ok(len(vend) >= 1 and "intelsense" in vend, "Vendor list is the vendors this partner sells: " + ", ".join(vend))
    pg.select_option("#ppVendorPick", "intelsense"); pg.click('[data-pp-template="demo"]'); pg.wait_for_timeout(300)
    ok(pg.locator("#ppEditForm").count() == 1 and "Intelsense" in pg.input_value("#ppHeadline"), "Template opens the editor with copy drafted from the vendor")
    pv = pg.inner_text("#ppPreview")
    ok("REQUEST A DEMO" in pv.upper() and "About Intelsense AI" in pv and "Unisense AI" in pv, "Preview shows the product overview and the demo form")
    pg.fill("#ppHeadline", "Unisense AI for Bangkok hotels"); pg.wait_for_timeout(150)
    ok("Unisense AI for Bangkok hotels" in pg.inner_text("#ppPreview"), "Preview updates as you type")
    pg.click('[data-pp-save="publish"]'); pg.wait_for_timeout(300)
    row = pg.locator("[data-pp-row]").first
    ok(row.count() == 1 and "PUBLISHED" in row.inner_text().upper() and "?pp=" in row.inner_text(), "Published page is listed with its link")
    pid = pages(pg)[0]["id"]
    rec = pages(pg)[0]
    ok(rec["vendor"]["name"] == "Intelsense AI" and rec["partnerName"] and rec["status"] == "published", "Saved with the vendor details and partner name it shows")

    # ----- a visitor asks for a demo
    pg.goto(URL + "?demo=1&pp=" + pid); pg.wait_for_timeout(700)
    ok(pg.locator("[data-pp-page] h1").inner_text() == "Unisense AI for Bangkok hotels", "Public page opens without signing in")
    pg.click("[data-pp-submit]"); pg.wait_for_timeout(200)
    ok("name" in pg.inner_text("#ppError") and "email" in pg.inner_text("#ppError"), "Asks for the missing details")
    pg.fill("#ppName", "Ploy Srisuk"); pg.fill("#ppEmail", "ploy@riverside.co.th"); pg.fill("#ppCompany", "Riverside Hotel"); pg.fill("#ppPhone", "+66 81 234 5678")
    pg.fill("#ppNote", "A front-desk voice bot"); pg.check("#ppConsent"); pg.click("[data-pp-submit]"); pg.wait_for_timeout(400)
    ok(pg.locator("[data-pp-done]").count() == 1 and "Thanks, Ploy" in pg.inner_text("[data-pp-done]"), "Visitor sees a thank-you")

    # ----- it lands in My Leads
    pg.goto(URL + "?demo=1"); pg.wait_for_timeout(700); role(pg, "partner"); nav(pg, "partner-my-leads")
    card = pg.locator("#leadsList .card").filter(has_text="Riverside Hotel")
    ok(card.count() == 1 and "FROM YOUR LANDING PAGE" in card.inner_text().upper() and "ploy@riverside.co.th" in card.inner_text(), "The request is a lead in My Leads, with the contact details")
    nav(pg, "partner-pages"); pg.wait_for_timeout(200)
    ok("1 sign-up" in pg.inner_text("[data-pp-row]"), "Landing Pages shows the sign-up count")

    # ----- a webinar invite, in the partner's brand
    nav(pg, "branding"); pg.wait_for_timeout(200); pg.click('[data-brand-preset="1"]'); pg.click("[data-brand-save]"); pg.wait_for_timeout(300)
    ok("LANDING PAGE" in pg.inner_text("#brandPreview").upper() and "INCENTIVE FLYER" not in pg.inner_text("#brandPreview").upper(), "Partner Branding previews a landing page")
    nav(pg, "partner-pages"); pg.click("[data-pp-new]"); pg.wait_for_timeout(200)
    pg.select_option("#ppVendorPick", "intelsense"); pg.click('[data-pp-template="webinar"]'); pg.wait_for_timeout(300)
    ok(pg.locator("#ppStart").count() == 1 and pg.locator("#ppAgenda").count() == 1, "Webinar template has date, agenda and speakers")
    ok(pg.locator("#ppPreview .lp-page.branded").count() == 1, "Preview uses the partner's brand")
    pg.click('[data-pp-save="publish"]'); pg.wait_for_timeout(250)
    ok("date and time" in pg.inner_text("#ppEditError"), "Can't publish a webinar without a date")
    pg.fill("#ppStart", "2030-03-12T15:00"); pg.fill("#ppHeadline", "Live: AI front desks for hotels"); pg.click('[data-pp-save="publish"]'); pg.wait_for_timeout(300)
    web = [x for x in pages(pg) if x["template"] == "webinar"][0]
    ok(web["status"] == "published" and web["brand"]["primary"] == "#15803d", "Webinar page published with the partner's brand")
    cal = json.loads(pg.evaluate("localStorage.getItem('partnerWAV_calendar')") or "{}").get("events", [])
    ok(any(e["id"] == "ev-pp-" + web["id"] and e["type"] == "Webinar" for e in cal), "Publishing puts the webinar on Events & Calendar")
    pg.goto(URL + "?demo=1&pp=" + web["id"]); pg.wait_for_timeout(700)
    ok("2030" in pg.inner_text(".pp-when") and pg.locator("[data-pp-page].branded").count() == 1, "Public webinar page shows the date in the partner's brand")
    pg.fill("#ppName", "Ann Lee"); pg.fill("#ppEmail", "ann@example.com"); pg.check("#ppConsent"); pg.click("[data-pp-submit]"); pg.wait_for_timeout(400)
    ok("REGISTERED" in pg.inner_text("[data-pp-done]").upper() and pg.locator("[data-pp-google]").count() == 1, "Registered visitors can add it to their calendar")

    # ----- unpublish and delete
    pg.goto(URL + "?demo=1"); pg.wait_for_timeout(700); role(pg, "partner"); nav(pg, "partner-pages"); pg.wait_for_timeout(200)
    pg.locator("[data-pp-row]").filter(has_text="webinar").locator("[data-pp-edit]").click(); pg.wait_for_timeout(250)
    pg.click("[data-pp-unpublish]"); pg.wait_for_timeout(300)
    cal = json.loads(pg.evaluate("localStorage.getItem('partnerWAV_calendar')") or "{}").get("events", [])
    ok(not any(e["id"] == "ev-pp-" + web["id"] for e in cal), "Unpublishing takes the webinar off the calendar")
    pg.goto(URL + "?demo=1&pp=" + web["id"]); pg.wait_for_timeout(600)
    ok("isn't available" in pg.inner_text("#publicPartnerPageContent"), "An unpublished page's link stops working")
    pg.goto(URL + "?demo=1"); pg.wait_for_timeout(700); role(pg, "partner"); nav(pg, "partner-pages"); pg.wait_for_timeout(200)
    pg.locator("[data-pp-row]").filter(has_text="webinar").locator("[data-pp-edit]").click(); pg.wait_for_timeout(250)
    pg.click("[data-pp-delete]"); pg.wait_for_timeout(300)
    ok(pg.locator("[data-pp-row]").filter(has_text="webinar").count() == 0, "Deleted page leaves the list")

    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0, "No horizontal overflow at 390px")
    pg.goto(URL + "?demo=1&pp=" + pid); pg.wait_for_timeout(600)
    ok(pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0, "Public page fits a phone")
    pg2 = pg.context.new_page(); pg2.goto(URL + "?pp=" + pid); pg2.wait_for_timeout(700)
    ok(pg2.locator(".sidebar").is_hidden() and pg2.locator("#scr-public-partner-page").is_visible(), "Public link opens without the portal menu or a sign-in")
    b.close()
report()
