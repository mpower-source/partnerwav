from harness import *

with sync_playwright() as p:
    b, pg = open_page(p)
    for r in ["partner", "vendor", "operator"]:
        role(pg, r)
        ok(pg.locator('[data-screen="integrations"]:visible').count() == 1, f"{r.title()} menu has Integrations")
    role(pg, "affiliate"); ok(pg.locator('#navAffiliate [data-screen="integrations"]').count() == 1, "Affiliate menu has Integrations")

    # ----- vendor: Calendly
    role(pg, "vendor"); nav(pg, "integrations")
    box = pg.locator("#integrationsContent")
    ok(all(x in box.inner_text() for x in ["Calendly", "HubSpot", "WhatsApp & LINE", "Planned"]), "Cards: Calendly, HubSpot, WhatsApp & LINE, Planned")
    ok("NOT SET UP" in pg.locator('[data-int="calendly"]').inner_text().upper(), "Calendly starts as not set up")
    pg.fill("#intBooking", "notalink"); pg.click('[data-int-save="calendly"]'); pg.wait_for_timeout(150)
    ok("secure web address" in pg.inner_text("#intCalError"), "Needs a real link")
    pg.fill("#intBooking", "calendly.com/intelsense/demo")
    pg.evaluate("document.querySelector('[data-screen=\"integrations\"]').click()"); pg.wait_for_timeout(150)
    ok(pg.input_value("#intBooking") == "calendly.com/intelsense/demo", "A background refresh doesn't wipe what's being typed")
    pg.click('[data-int-save="calendly"]'); pg.wait_for_timeout(300)
    cal = pg.locator('[data-int="calendly"]')
    ok("CONNECTED" in cal.inner_text().upper() and pg.input_value("#intBooking") == "https://calendly.com/intelsense/demo", "Saved and shown as connected")
    pg.click("[data-int-test]"); pg.wait_for_timeout(400)
    fr = pg.locator(".modal [data-book-frame]")
    ok(fr.count() == 1 and fr.get_attribute("src").startswith("https://calendly.com/intelsense/demo?embed_domain=") and "embed_type=Inline" in fr.get_attribute("src"), "'Try it' opens Calendly's scheduler inside PartnerWAV")
    pg.click(".modal [data-modal-ok]"); pg.wait_for_timeout(150)

    # others see "Book a call" on the vendor's profile; it opens in the portal
    role(pg, "operator"); nav(pg, "vendor-network"); pg.locator('[data-view-vendor="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    pg.click('#vendorProfileContent [data-contact-book="vendor:intelsense"]'); pg.wait_for_timeout(400)
    ok(pg.locator(".modal [data-book-frame]").count() == 1 and "Book a call with Intelsense" in pg.inner_text(".modal"), "Profile 'Book a call' opens the scheduler in the portal")
    pg.evaluate("window.dispatchEvent(new MessageEvent('message', { origin:'https://calendly.com', data:{ event:'calendly.event_scheduled' } }))"); pg.wait_for_timeout(200)
    ok("Call booked" in pg.inner_text("#toast"), "Confirms when Calendly reports the booking")
    pg.evaluate("window.dispatchEvent(new MessageEvent('message', { origin:'https://evil.example', data:{ event:'calendly.event_scheduled' } }))")
    pg.click(".modal [data-modal-ok]"); pg.wait_for_timeout(150)

    # embed switched off, or a non-Calendly link -> new tab as before
    role(pg, "vendor"); nav(pg, "integrations"); pg.uncheck("#intEmbed"); pg.click('[data-int-save="calendly"]'); pg.wait_for_timeout(300)
    role(pg, "operator"); nav(pg, "vendor-network"); pg.locator('[data-view-vendor="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    with pg.context.expect_page() as newp:
        pg.click('#vendorProfileContent [data-contact-book="vendor:intelsense"]')
    ok(pg.locator(".modal [data-book-frame]").count() == 0 and newp.value is not None, "With the embed off it opens in a new tab")
    newp.value.close()

    # ----- vendor: HubSpot request
    role(pg, "vendor"); nav(pg, "integrations")
    pg.click('[data-int-save="hubspot"]'); pg.wait_for_timeout(150)
    ok("at least one" in pg.inner_text("#intHsError"), "HubSpot: choose what to sync")
    pg.check('[data-int-hs="contacts"]'); pg.check('[data-int-hs="deals"]'); pg.select_option("#intHsDir", "both"); pg.click('[data-int-save="hubspot"]'); pg.wait_for_timeout(300)
    hs = pg.locator('[data-int="hubspot"]')
    ok("SETUP REQUESTED" in hs.inner_text().upper() and pg.is_checked('[data-int-hs="deals"]') and pg.input_value("#intHsDir") == "both", "HubSpot shows 'Setup requested' with the choices kept")
    ok("never in a web page" in hs.inner_text(), "Explains why it's a request (key stays on a server)")
    ok(pg.locator("#intRequests").count() == 0, "Vendors don't see other accounts' requests")
    role(pg, "operator"); nav(pg, "integrations")
    req = pg.locator('[data-int-req="vendor:intelsense"]')
    ok(req.count() == 1 and "Contacts and companies" in req.inner_text() and "Registered deals" in req.inner_text(), "CloudWAV sees the request and what to sync")
    pg.reload(); pg.wait_for_timeout(600); role(pg, "vendor"); nav(pg, "integrations")
    ok("SETUP REQUESTED" in pg.locator('[data-int="hubspot"]').inner_text().upper() and pg.input_value("#intBooking").endswith("/demo"), "Kept after reload")
    pg.click('[data-int-cancel="hubspot"]'); pg.wait_for_timeout(300)
    ok("NOT CONNECTED" in pg.locator('[data-int="hubspot"]').inner_text().upper(), "Request can be cancelled")
    b.close()
report()
