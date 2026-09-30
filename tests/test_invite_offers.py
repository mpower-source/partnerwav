from harness import *
import os
HERE = os.path.dirname(os.path.abspath(__file__))
QRJS = qrcode_js()
OFFER = "botnoi-sme-ai-invite"

with sync_playwright() as p:
    b, pg = open_page(p)
    pg.context.route("**/cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=QRJS, headers={"access-control-allow-origin": "*"}))

    # ----- not listed for partners or other vendors
    nav(pg, "affiliate-marketplace")
    ok(pg.locator(f'#affiliateMarketplaceGrid [data-offer="{OFFER}"]').count() == 0, "Partners don't see Botnoi's invite-only offer in the marketplace")
    role(pg, "vendor"); nav(pg, "affiliate-marketplace")
    ok(pg.locator(f'#affiliateMarketplaceGrid [data-offer="{OFFER}"]').count() == 0, "Other vendors (Intelsense) don't see it either")
    ok(pg.locator("#ourAffiliateBtn").is_visible() and pg.inner_text("#ourAffiliateBtn") == "Our affiliate program", "Vendors get an 'Our affiliate program' button")
    pg.click("#ourAffiliateBtn"); pg.wait_for_timeout(200)
    ok(pg.locator("#affiliateMarketplaceGrid .program-card").count() == 0 and "haven't added an affiliate program" in pg.inner_text("#affiliateMarketplaceGrid"), "Intelsense has none yet -- says how to add one")
    pg.click("#ourAffiliateBtn"); pg.wait_for_timeout(200)
    role(pg, "partner"); nav(pg, "affiliate-marketplace")
    ok(not pg.locator("#ourAffiliateBtn").is_visible(), "Partners don't get the button")

    # ----- CloudWAV sees it with the invite tools
    role(pg, "operator"); nav(pg, "affiliate-marketplace"); pg.wait_for_timeout(800)
    card = pg.locator(f'#affiliateMarketplaceGrid [data-offer="{OFFER}"]')
    ok(card.count() == 1 and card.locator("[data-invite-only]").count() == 1 and "Demo" in card.inner_text(), "Operator sees it, marked Invite only and Demo")
    ok("THB 300" not in card.inner_text() and card.locator("[data-aff-terms]").count() == 0, "Reward terms stay off the tile")
    ok(card.locator("img.entity-logo-img").count() == 1 and "svg" in card.locator("img.entity-logo-img").get_attribute("src"), "Botnoi robot logo on the offer")
    # "Vendor affiliate programs" filter for CloudWAV
    pg.click("#ourAffiliateBtn"); pg.wait_for_timeout(200)
    ids = [c.get_attribute("data-offer") for c in pg.locator("#affiliateMarketplaceGrid .program-card").all()]
    ok(OFFER in ids and "lovable" not in ids and "xero" not in ids, "Operator: 'Vendor affiliate programs' shows only vendors' offers")
    ok(pg.inner_text("#ourAffiliateBtn") == "Show all offers", "Button switches to 'Show all offers'")
    pg.click("#ourAffiliateBtn"); pg.wait_for_timeout(200)
    ok(pg.locator('#affiliateMarketplaceGrid [data-offer="lovable"]').count() == 1, "Back to all offers")
    card = pg.locator(f'#affiliateMarketplaceGrid [data-offer="{OFFER}"]')
    ok(card.locator("[data-invite-tools]").count() == 0 and card.locator("[data-edit-affiliate-offer]").count() == 1 and card.locator("[data-invite-open]").count() == 1, "Compact tile: Invite link & QR, Sign-ups and Edit offer buttons")
    box = pg.locator("#affiliateMarketplaceGrid").bounding_box(); cb = card.bounding_box()
    ok(cb["width"] < box["width"] / 2, "Shown as a normal-size tile")
    card.locator("[data-invite-open]").click(); pg.wait_for_timeout(700)
    tools = pg.locator(".modal [data-invite-tools]")
    link = tools.locator(".aff-link-input").input_value()
    ok(link.endswith("?invite=" + OFFER), "Invite link: " + link)
    ok(tools.locator("[data-qr-img]").count() == 1 and tools.locator("[data-qr-download]").get_attribute("download").endswith("-invite-qr.png"), "QR code is drawn in the portal, with a download")
    ok("wa.me/?text=" in tools.locator('[data-invite-share="whatsapp"]').get_attribute("href") and "line.me/R/share" in tools.locator('[data-invite-share="line"]').get_attribute("href"), "Share on WhatsApp and LINE")
    ok("Sign-ups (0)" in tools.inner_text(), "No sign-ups yet")
    pg.click(".modal [data-modal-ok]"); pg.wait_for_timeout(150)
    ok(card.locator("[data-enroll-affiliate]").count() == 0, "No Enroll button on an invite-only offer")
    # editor
    card.locator("[data-edit-affiliate-offer]").click(); pg.wait_for_timeout(300)
    ok(pg.input_value("#aoAudience") == "invite" and pg.locator("#aoInviteFields").is_visible() and "THB 5,000" in pg.input_value("#aoInvHeadline"), "Editor: audience 'Invite only' with the invite page fields")
    ok("THB 300" in pg.input_value("#aoTermAmount"), "Proposed reward is in the private terms")
    pg.select_option("#aoAudience", "marketplace"); pg.wait_for_timeout(100)
    ok(not pg.locator("#aoInviteFields").is_visible(), "Invite fields hide for a marketplace offer")
    pg.select_option("#aoAudience", "invite"); pg.fill("#aoInvValid", "2026-12-31")
    pg.click('#affiliateOfferForm button[type=submit]'); pg.wait_for_timeout(300)
    # CloudWAV-owned offers (no vendor) don't offer invite-only
    pg.locator('#affiliateMarketplaceGrid [data-direct-offer="hubspot"] [data-edit-affiliate-offer]').click(); pg.wait_for_timeout(300)
    ok(not pg.locator("#aoAudienceRow").is_visible(), "Invite-only is for vendor offers only (not CloudWAV's own)")
    pg.click('#scr-affiliate-offer-editor [data-back-screen="affiliate-marketplace"]'); pg.wait_for_timeout(200)

    # ----- the public invite page
    pg.goto(URL + "?invite=" + OFFER); pg.wait_for_timeout(800)
    ok(visible_screen(pg) == ["scr-public-invite"] and not pg.locator("#loginScreen").is_visible() and not pg.locator(".sidebar").is_visible(), "Public invite page: no sign-in, no portal menu")
    page = pg.inner_text("#publicInviteContent")
    ok("Help Thai businesses get THB 5,000 of free AI credits" in page and "600,000 BOTNOI Voice points" in page and "3M+ users" in page, "Shows Botnoi's offer")
    ok("Until 2026-12-31" in page, "End date set in the editor shows")
    ok("THB 300" not in page, "Private reward terms aren't on the public page")
    pg.click("#inviteSubmit"); pg.wait_for_timeout(200)
    err = pg.inner_text("#inviteError")
    ok("name" in err and "email" in err and "tick the box" in err, "Asks for name, email and consent")
    pg.fill("#invName", "Nok Sukjai"); pg.fill("#invEmail", "Nok@Example.co.th"); pg.fill("#invLine", "nok.ai")
    pg.select_option("#invRole", "Consultant / freelancer"); pg.check("#invConsent")
    pg.click("#inviteSubmit"); pg.wait_for_timeout(900)
    done = pg.locator('[data-invite-done="referrer"]')
    mine = pg.input_value("#inviteMyLink") if done.count() else ""
    ok(done.count() == 1 and "&ref=sg-" in mine, "Referrer gets a personal link: " + mine)
    ok(done.locator("[data-qr-img]").count() == 1, "...and their own QR code")

    # a business signs up through the referrer's link
    pg.goto(mine); pg.wait_for_timeout(800)
    ok("You were invited" in pg.inner_text("#publicInviteContent") and pg.is_checked('input[name="invKind"][value="business"]'), "Referral link: 'business' is pre-selected")
    pg.fill("#invName", "Somsri P."); pg.fill("#invEmail", "somsri@shop.co.th"); pg.check("#invConsent"); pg.click("#inviteSubmit"); pg.wait_for_timeout(200)
    ok("company name" in pg.inner_text("#inviteError"), "Businesses give their company name")
    pg.fill("#invCompany", "Somsri Thai Kitchen"); pg.fill("#invPhone", "081 234 5678"); pg.click("#inviteSubmit"); pg.wait_for_timeout(600)
    ok(pg.locator('[data-invite-done="business"]').count() == 1 and "will contact you" in pg.inner_text("#publicInviteContent"), "Business sees a thank-you")

    pg.set_viewport_size({"width": 390, "height": 844}); pg.goto(URL + "?invite=" + OFFER); pg.wait_for_timeout(700)
    ok(pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "Invite page fits a phone screen")
    pg.set_viewport_size({"width": 1280, "height": 900})
    pg.goto(URL + "?invite=does-not-exist"); pg.wait_for_timeout(600)
    ok("isn't available" in pg.inner_text("#publicInviteContent"), "Unknown invite handled")
    pg.goto(URL + "?invite=lovable"); pg.wait_for_timeout(600)
    ok("isn't available" in pg.inner_text("#publicInviteContent"), "Marketplace offers have no invite page")

    # ----- back in the portal: the sign-ups are leads
    pg.goto(URL + "?demo=1"); pg.wait_for_timeout(700)
    role(pg, "operator"); nav(pg, "affiliate-marketplace"); pg.wait_for_timeout(300)
    ok("2 sign-ups" in pg.inner_text(f'#affiliateMarketplaceGrid [data-offer="{OFFER}"]'), "Tile shows 2 sign-ups")
    pg.click(f'#affiliateMarketplaceGrid [data-offer="{OFFER}"] [data-invite-open]'); pg.wait_for_timeout(300)
    tools = pg.locator(".modal [data-invite-tools]")
    ok("Sign-ups (2)" in tools.inner_text() and "1 referrer · 1 business" in tools.inner_text(), "Invite panel counts 1 referrer and 1 business")
    tools.locator("[data-invite-signups]").click(); pg.wait_for_timeout(300)
    rows = pg.inner_text("#inviteSignupRows")
    ok("Somsri Thai Kitchen" in rows and "Nok Sukjai" in rows and "nok@example.co.th" in rows and "LINE: nok.ai" in rows, "Sign-up list with contact details")
    ok("1 referred" in rows and pg.locator("#inviteSignupRows tr").nth(0).inner_text().count("Nok Sukjai") == 1, "Business is credited to Nok; Nok brought in 1")
    with pg.expect_download() as dl:
        pg.click("#inviteSignupsCsv")
    csv = open(dl.value.path(), encoding="utf-8-sig").read()
    ok(csv.startswith("Name,Type,Company") and "Somsri P.,Business,Somsri Thai Kitchen" in csv and ",Nok Sukjai," in csv, "CSV export")
    b.close()

report()
