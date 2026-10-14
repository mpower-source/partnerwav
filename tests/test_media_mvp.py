from harness import *
import json

# Promoters (PR agencies, media, creators, event organizers, venues; listed under Media & Events) and CloudWAV's MVP Builder.
def store(pg):
    return json.loads(pg.evaluate("localStorage.getItem('partnerWAV_mediaMvp')") or "{}")

with sync_playwright() as p:
    b, pg = open_page(p)
    # ----- a vendor finds a Media & Events partner and asks, with the event code from the event
    role(pg, "vendor"); nav(pg, "media-directory"); pg.wait_for_timeout(300)
    card = pg.locator('#mediaDirectoryContent [data-med-card="zipevent"]')
    ok(card.count() == 1 and "Event organizer" in card.inner_text() and "Ask for a quote" in card.inner_text(), "ZipEvent is listed as an event organizer, with its services")
    ok("Event exclusive" in card.inner_text() and "FOUNDER15" not in pg.content().split("<script")[0], "Its event-exclusive offer shows, without the code")
    pg.click('#mediaDirectoryContent [data-med-kind="pr"]'); pg.wait_for_timeout(200)
    ok(pg.locator('#mediaDirectoryContent [data-med-card]').count() == 0, "Filter by kind")
    pg.click('#mediaDirectoryContent [data-med-kind=""]'); pg.wait_for_timeout(200)
    pg.click('#mediaDirectoryContent [data-med-request="zipevent"]'); pg.wait_for_timeout(300)
    pg.fill("#medReqDetails", "Ticketing for our launch event in Bangkok"); pg.fill("#medReqCode", "WRONG1"); pg.click("#medReqSend"); pg.wait_for_timeout(300)
    ok("doesn't match" in pg.inner_text("#medReqErr"), "A wrong event code is caught")
    pg.fill("#medReqCode", "founder15"); pg.click("#medReqSend"); pg.wait_for_timeout(400)
    r = [x for x in store(pg).get("requests", []) if x["kind"] == "media"]
    ok(r and r[0]["mediaId"] == "zipevent" and r[0]["codeOk"] and r[0]["offerId"] == "mo-demo" and r[0]["requesterKey"].startswith("vendor:") and r[0]["status"] == "new", "The request is sent with the event discount")
    ok("event code accepted" in pg.inner_text("#mediaDirectoryContent").lower(), "The vendor sees its request")

    # ----- MVP Builder
    nav(pg, "mvp-builder"); pg.wait_for_timeout(300)
    t = pg.inner_text("#mvpBuilderContent")
    ok(all(x in t for x in ["Quick MVP", "Secure code review", "Extra developers", "Investor-ready features", "Full MVP"]) and "Ask for a quote" in t, "MVP Builder packages, from a quick MVP to a full app")
    ok("sports coaching apps" in t.lower() and "loyalty programs" in t.lower() and "software houses" in t, "Shows what's being built, and that bigger builds go to software houses")
    pg.click('#mvpBuilderContent [data-mvp-request="pkg-security"]'); pg.wait_for_timeout(300)
    pg.click("#mvpReqSend"); pg.wait_for_timeout(150)
    ok(not pg.locator("#mvpReqErr").is_hidden(), "It needs a description")
    pg.fill("#mvpReqDetails", "Our Lovable app needs a security check before investor due diligence"); pg.fill("#mvpReqLink", "app.example.com"); pg.select_option("#mvpReqBudget", "USD 2,000 - 5,000")
    pg.click("#mvpReqSend"); pg.wait_for_timeout(300)
    m = [x for x in store(pg)["requests"] if x["kind"] == "mvp"]
    ok(m and m[0]["packageId"] == "pkg-security" and "Link: https://app.example.com" in m[0]["details"] and m[0]["budget"] == "USD 2,000 - 5,000", "The MVP request is saved")

    # ----- software houses don't get the MVP Builder; other vendors and partners do
    ok(pg.locator('#navVendor .navlink[data-screen="mvp-builder"]').get_attribute("hidden") is None, "A software vendor (Intelsense) sees the MVP Builder")
    role(pg, "operator"); nav(pg, "referrals"); pg.wait_for_timeout(300)
    pg.click('[data-ref-tab="houses"]'); pg.wait_for_timeout(200)
    pg.click('[data-house-edit="sh-demo"]'); pg.wait_for_timeout(300)
    pg.select_option("#hf_partnerId", "siam-digital"); pg.click("#hfSave"); pg.wait_for_timeout(300)
    role(pg, "partner"); pg.wait_for_timeout(300)
    ok(pg.locator('#navPartner .navlink[data-screen="mvp-builder"]').get_attribute("hidden") is not None, "A partner that is a software house doesn't see the MVP Builder")
    ok(pg.locator('#navPartner .navlink[data-screen="media-directory"]').get_attribute("hidden") is None, "...but still sees Media & Events")
    role(pg, "operator"); nav(pg, "referrals"); pg.wait_for_timeout(300); pg.click('[data-ref-tab="houses"]'); pg.wait_for_timeout(200)
    pg.click('[data-house-edit="sh-demo"]'); pg.wait_for_timeout(300); pg.select_option("#hf_partnerId", ""); pg.click("#hfSave"); pg.wait_for_timeout(300)
    role(pg, "partner"); pg.wait_for_timeout(300)
    ok(pg.locator('#navPartner .navlink[data-screen="mvp-builder"]').get_attribute("hidden") is None, "Other partners see the MVP Builder")

    # ----- the vendor wizard offers both as add-ons
    role(pg, "operator"); pg.goto(URL + "?demo=1&assess=1"); pg.wait_for_timeout(600)
    pg.fill("#va_company", "Acme"); pg.fill("#va_contactName", "Ann Lee"); pg.fill("#va_email", "ann@acme.example"); pg.check('[data-va-k="companyStage"][value="Established"]'); pg.click("[data-va-next]"); pg.wait_for_timeout(150)
    pg.fill("#va_productSummary", "Sensors"); pg.click("[data-va-next]"); pg.wait_for_timeout(150)
    pg.check('[data-va-k="programStage"][value="No partner program yet"]'); pg.check('[data-va-k="partners"][value="0"]'); pg.click("[data-va-next]"); pg.wait_for_timeout(150)
    pg.check('[data-va-k="support"][value="self"]'); pg.click("[data-va-next]"); pg.wait_for_timeout(150)
    wiz = pg.inner_text("#publicAssessContent")
    ok("MVP Builder" in wiz and "Media & Events promoters" in wiz, "The vendor wizard offers the MVP Builder and Media & Events as add-ons")
    pg.check('[data-va-k="addons"][value="mvp"]'); pg.wait_for_timeout(250)
    ok("What would help most from the MVP Builder?" in pg.inner_text("#publicAssessContent"), "Choosing the MVP Builder asks what would help most")

    # ----- CloudWAV: requests, partners, sponsorships
    pg.goto(URL + "?demo=1"); pg.wait_for_timeout(600)
    role(pg, "operator"); nav(pg, "operator-services"); pg.wait_for_timeout(300)
    ok(pg.locator("#opServicesContent [data-svc-row]").count() == 1, "CloudWAV sees the MVP request")
    rid = m[0]["id"]
    pg.select_option(f'[data-svc-house="{rid}"]', "sh-demo"); pg.fill(f'[data-svc-value="{rid}"]', "3500"); pg.click(f'[data-svc-save="{rid}"]'); pg.wait_for_timeout(300)
    m2 = [x for x in store(pg)["requests"] if x["id"] == rid][0]
    ok(m2["houseId"] == "sh-demo" and m2["status"] == "referred" and m2["value"] == 3500, "A bigger build can be sent to a software house")
    pg.click('[data-svc-tab="media"]'); pg.wait_for_timeout(200)
    rq = r[0]["id"]
    pg.select_option(f'[data-svc-status="{rq}"]', "won"); pg.fill(f'[data-svc-fee="{rq}"]', "4500"); pg.click(f'[data-svc-save="{rq}"]'); pg.wait_for_timeout(300)
    ok([x for x in store(pg)["requests"] if x["id"] == rq][0]["fee"] == 4500, "CloudWAV records the fee earned on a Media & Events request")
    pg.click('[data-svc-tab="packages"]'); pg.wait_for_timeout(200)
    pg.locator('[data-svc-pkg="pkg-quick-mvp"] [data-pk="price"]').fill("From USD 1,500"); pg.click('[data-svc-pk-save="pkg-quick-mvp"]'); pg.wait_for_timeout(250)
    ok([x for x in store(pg)["packages"] if x["id"] == "pkg-quick-mvp"][0]["price"] == "From USD 1,500", "CloudWAV sets package prices")

    # ----- a Media & Events partner: profile, sponsoring, offers, requests
    role(pg, "media"); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-media-overview"] and "ZipEvent" in pg.inner_text("#mediaOverviewContent"), "A Media & Events partner starts on its overview")
    nav(pg, "media-requests"); pg.wait_for_timeout(300)
    ok("Ticketing for our launch event" in pg.inner_text("#mediaRequestsContent") and "event code accepted" in pg.inner_text("#mediaRequestsContent").lower(), "It sees the requests for its services")
    nav(pg, "calendar"); pg.wait_for_timeout(400)
    cal = pg.inner_text("#calendarContent")
    ok(visible_screen(pg) == ["scr-calendar"] and ("Founder Night" in cal or "Claude Builders" in cal or "training" in cal.lower()), "Promoters have the Events & Calendar view the vendors, partners and affiliates use")
    nav(pg, "media-events"); pg.wait_for_timeout(300)
    evid = pg.get_attribute("#mediaEventsContent [data-med-ev]", "data-med-ev")
    pg.select_option(f'[data-med-pkg="{evid}"]', "booth"); pg.fill(f'[data-med-note="{evid}"]', "Ticketing demo table"); pg.click(f'[data-med-sponsor="{evid}"]'); pg.wait_for_timeout(300)
    sp = store(pg)["sponsorships"]
    ok(sp and sp[0]["eventId"] == evid and sp[0]["pkg"] == "booth" and sp[0]["status"] == "applied", "It applies to sponsor an event")
    nav(pg, "media-offers"); pg.wait_for_timeout(300)
    pg.fill("#medOfTitle", "Free event page setup"); pg.fill("#medOfCode", "bad code"); pg.click("[data-med-offer-save]"); pg.wait_for_timeout(200)
    ok(not pg.locator("#medOfErr").is_hidden(), "A code needs letters or numbers, no spaces")
    pg.fill("#medOfCode", "SPONSOR26"); pg.select_option("#medOfEvent", evid); pg.click("[data-med-offer-save]"); pg.wait_for_timeout(400)
    of = [o for o in store(pg)["offers"] if o["title"] == "Free event page setup"]
    ok(of and of[0]["eventId"] == evid and len(of[0]["codeHash"]) == 64 and "code" not in of[0], "The offer keeps only a fingerprint of the code")
    ok("Code: SPONSOR26" in pg.inner_text("#mediaOffersContent"), "...and the partner still sees its own code")
    nav(pg, "media-profile"); pg.wait_for_timeout(300)
    pg.fill("#medTagline", "Event platform, ticketing and promotion in Thailand")
    pg.locator("[data-med-svrow]").last.locator("input").first.fill("Sponsored event listing"); pg.click("[data-med-save]"); pg.wait_for_timeout(300)
    zp = [x for x in store(pg)["profiles"] if x["id"] == "zipevent"][0]
    ok(zp["tagline"].startswith("Event platform, ticketing") and any(s["name"] == "Sponsored event listing" for s in zp["services"]) and zp["status"] == "approved", "It edits its profile and services")

    # ----- CloudWAV confirms the sponsor; the event shows it
    role(pg, "operator"); nav(pg, "operator-services"); pg.wait_for_timeout(300)
    pg.click('[data-svc-tab="sponsors"]'); pg.wait_for_timeout(200)
    pg.click(f'[data-svc-sp-confirm="{sp[0]["id"]}"]'); pg.wait_for_timeout(300)
    ev = [e for e in json.loads(pg.evaluate("localStorage.getItem('partnerWAV_community')"))["events"] if e["id"] == evid][0]
    ok(ev.get("sponsors") and ev["sponsors"][0]["name"] == "ZipEvent", "Confirming adds the sponsor to the event")
    role(pg, "member"); nav(pg, "member-events"); pg.wait_for_timeout(300)
    ok("Sponsored by ZipEvent" in pg.inner_text(f'#memberEventsContent [data-tec-event="{evid}"]'), "Members see who sponsors the event")

    # ----- a new partner is checked before it is listed
    role(pg, "operator"); nav(pg, "operator-accounts"); pg.wait_for_timeout(300)
    pg.click("[data-acct-any]"); pg.wait_for_timeout(200)
    ok("Promoter" in pg.inner_text("#acctRole"), "Accounts & Logins can set up a Promoter")
    pg.keyboard.press("Escape")
    pg.set_viewport_size({"width": 390, "height": 844}); role(pg, "vendor"); nav(pg, "media-directory"); pg.wait_for_timeout(300)
    ok(pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0, "Media & Events fits a phone")
    b.close()
report()
