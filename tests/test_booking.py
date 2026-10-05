from harness import *

with sync_playwright() as p:
    b, pg = open_page(p)
    # CloudWAV: no booking link yet -> hint on Vendor Assessments
    role(pg, "operator"); nav(pg, "operator-assessments")
    ok(pg.locator("[data-va-booking-hint]").count() == 1, "Hint to add a Calendly link while none is set")
    nav(pg, "channels"); pg.click('[data-ch-tab="contact"]'); pg.wait_for_timeout(200)
    ok(pg.locator("#cBooking").count() == 1 and pg.input_value("#cFollowUp") == "two business days", "Operator: booking link field and the reply promise (default two business days)")
    pg.fill("#cBooking", "ftp://nope"); pg.click("[data-c-save]"); pg.wait_for_timeout(150)
    ok("secure web address" in pg.inner_text("#cError"), "Booking link must be a web address")
    pg.fill("#cBooking", "calendly.com/cloudwav/intro"); pg.fill("#cFollowUp", "one business day"); pg.click("[data-c-save]"); pg.wait_for_timeout(300)
    ok(pg.input_value("#cBooking") == "https://calendly.com/cloudwav/intro", "Saved, tidied to https://")
    nav(pg, "operator-assessments")
    ok(pg.locator("[data-va-booking-hint]").count() == 0, "Hint goes away once a link is set")

    # vendor sends the assessment -> thank-you page has the promise and the booking button
    pg.goto(URL + "?assess=1"); pg.wait_for_timeout(600)
    pg.fill("#va_company", "Acme"); pg.fill("#va_contactName", "Ann Lee"); pg.fill("#va_email", "ann@acme.example"); pg.check('[data-va-k="companyStage"][value="Established"]'); pg.click("[data-va-next]"); pg.wait_for_timeout(150)
    pg.fill("#va_productSummary", "Sensors"); pg.click("[data-va-next]"); pg.wait_for_timeout(150)
    pg.check('[data-va-k="programStage"][value="No partner program yet"]'); pg.check('[data-va-k="partners"][value="0"]'); pg.click("[data-va-next]"); pg.wait_for_timeout(150)
    pg.check('[data-va-k="support"][value="self"]'); pg.click("[data-va-next]"); pg.wait_for_timeout(150)
    pg.click("[data-va-next]"); pg.wait_for_timeout(150); pg.check('[data-va-k="consent"]'); pg.click("[data-va-next]"); pg.wait_for_timeout(500)
    done = pg.inner_text("#publicAssessContent")
    ok("within one business day" in done, "Thank-you page uses CloudWAV's reply promise")
    ok(pg.locator("[data-va-book]").get_attribute("href") == "https://calendly.com/cloudwav/intro" and "Book a call now" in done, "Thank-you page has 'Book a call now' to the Calendly link")

    # partners (and vendors, affiliates) can add their own booking link
    pg.goto(URL + "?demo=1"); pg.wait_for_timeout(500)
    role(pg, "partner"); nav(pg, "channels"); pg.click('[data-ch-tab="contact"]'); pg.wait_for_timeout(200)
    ok(pg.locator("#cBooking").count() == 1 and pg.locator("#cFollowUp").count() == 0, "Partner: booking link field (no CloudWAV-only settings)")
    pg.fill("#cBooking", "https://calendly.com/siam-digital/30min"); pg.click("[data-c-save]"); pg.wait_for_timeout(300)
    ok(pg.locator('#chContactForm [data-contact-book]').count() == 1, "Preview shows a 'Book a call' button")
    role(pg, "vendor"); nav(pg, "channels"); pg.click('[data-ch-tab="contact"]'); pg.wait_for_timeout(200)
    ok(pg.locator("#cBooking").count() == 1, "Vendor: booking link field")
    role(pg, "affiliate"); nav(pg, "channels"); pg.click('[data-ch-tab="contact"]'); pg.wait_for_timeout(200)
    ok(pg.locator("#cBooking").count() == 1 or "Create your profile first" in pg.inner_text("#channelsContent"), "Affiliate: booking link field (once they have a profile)")
    # others see it on a profile: the vendor adds one, CloudWAV views the vendor's profile
    role(pg, "vendor"); nav(pg, "channels"); pg.click('[data-ch-tab="contact"]'); pg.wait_for_timeout(200)
    pg.fill("#cBooking", "https://calendly.com/intelsense/demo"); pg.click("[data-c-save]"); pg.wait_for_timeout(300)
    role(pg, "operator"); nav(pg, "vendor-network"); pg.locator('[data-view-vendor="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    link = pg.locator('#vendorProfileContent [data-contact-book="vendor:intelsense"]')
    ok(link.count() == 1 and link.get_attribute("href") == "https://calendly.com/intelsense/demo" and pg.locator('#vendorProfileContent [data-contact-wa]').count() == 1, "The vendor's profile shows 'Book a call' next to WhatsApp")
    b.close()
report()
