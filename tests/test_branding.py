from harness import *
import json

def hexv(pg, key):
    return pg.input_value(f"#brandH_{key}").lower()

with sync_playwright() as p:
    b, pg = open_page(p)
    for r in ["vendor", "partner", "operator"]:
        role(pg, r); open_menu(pg, "branding")
        ok(pg.locator('[data-screen="branding"]:visible').count() == 1, f"{r.title()} menu has Branding")

    # ----- CloudWAV: Botnoi's colours, matched from botnoigroup.com, are set up
    role(pg, "operator"); nav(pg, "branding"); pg.wait_for_timeout(300)
    ok(pg.input_value("#brandTarget") == "vendor:botnoi", "CloudWAV opens on a company (Botnoi)")
    ok(hexv(pg, "primary") == "#61a6fa" and hexv(pg, "dark") == "#1d1f25" and pg.input_value("#brandFont") == "IBM Plex Sans Thai", "Botnoi's sky blue, charcoal and IBM Plex Sans Thai are filled in")
    ok("botnoigroup.com" in pg.inner_text("[data-brand-status]"), "Says where the colours came from")
    ok(pg.get_attribute('[data-brand-style="dark"]', "aria-pressed") == "true", "Botnoi uses the dark header style")
    hero = pg.locator("#brandPreview .lp-page.branded .lp-hero")
    ok(hero.count() == 1 and pg.evaluate("getComputedStyle(document.querySelector('#brandPreview .lp-hero')).backgroundColor") == "rgb(29, 31, 37)", "Preview landing page uses the charcoal header")
    ok(pg.locator("#brandPreview .flyer.branded").count() == 1, "Preview flyer uses the brand")

    # ----- Botnoi's public invite page picks up the colours
    pg.goto(URL + "?invite=botnoi-sme-ai-invite"); pg.wait_for_timeout(600)
    ok(pg.locator("[data-invite-page].branded.hs-dark").count() == 1, "Botnoi's invite page uses Botnoi's brand")
    ok(pg.evaluate("getComputedStyle(document.querySelector('[data-invite-page] .lp-hero')).backgroundColor") == "rgb(29, 31, 37)", "Invite page header is Botnoi's charcoal")
    pg.goto(URL + "?demo=1"); pg.wait_for_timeout(600)

    # ----- a vendor without a brand sets one up
    role(pg, "vendor"); nav(pg, "branding"); pg.wait_for_timeout(300)
    ok("Not set yet" in pg.inner_text("[data-brand-status]"), "Intelsense starts on PartnerWAV colours")
    pg.click('[data-brand-preset="0"]'); pg.wait_for_timeout(150)
    ok(hexv(pg, "primary") == "#2563eb" and hexv(pg, "dark") == "#0f172a", "A starter palette fills the colours")
    pg.fill("#brandH_primary", "zz12"); pg.wait_for_timeout(100)
    ok(pg.input_value("#brandC_primary") == "#2563eb", "An unfinished colour code is ignored")
    pg.fill("#brandH_primary", "#1E40AF"); pg.wait_for_timeout(150)
    ok(pg.input_value("#brandC_primary") == "#1e40af", "Typing a colour code updates the colour")
    pg.fill("#brandH_light", "#ffff00"); pg.wait_for_timeout(100)
    pg.fill("#brandH_primary", "#ffee00"); pg.wait_for_timeout(150)
    pg.fill("#brandH_dark", "#f8f8f8"); pg.click('[data-brand-style="dark"]'); pg.wait_for_timeout(150)
    ok("hard to read" in pg.inner_text("#brandChecks") or "close to the dark colour" in pg.inner_text("#brandChecks"), "Warns when header text or buttons would be hard to read")
    pg.click('[data-brand-preset="0"]'); pg.fill("#brandH_primary", "#1e40af"); pg.select_option("#brandFont", "Kanit"); pg.wait_for_timeout(150)
    ok("Kanit" in pg.evaluate("getComputedStyle(document.querySelector('#brandPreview .lp-page')).fontFamily"), "Font shows in the preview")
    pg.click("[data-brand-logo]"); pg.wait_for_timeout(800)
    ok("logo" in pg.inner_text("#brandLogoNote").lower(), "Match my logo reads colours from the logo: " + pg.inner_text("#brandLogoNote"))
    pg.click('[data-brand-preset="0"]'); pg.fill("#brandH_primary", "#1e40af"); pg.select_option("#brandFont", "Kanit"); pg.wait_for_timeout(100)
    pg.fill("#brandWebsite", "intelsense.ai"); pg.click("[data-brand-save]"); pg.wait_for_timeout(300)
    kits = json.loads(pg.evaluate("localStorage.getItem('partnerWAV_brandKits')"))
    mine = [k for k in kits if k["id"] == "vendor:intelsense"]
    ok(mine and mine[0]["primary"] == "#1e40af" and mine[0]["font"] == "Kanit" and mine[0]["heroStyle"] == "dark" and mine[0]["website"] == "https://intelsense.ai", "Brand saved with colours, font, style and website")
    ok(any(k["id"] == "vendor:botnoi" for k in kits), "Botnoi's brand is kept")

    # ----- flyers use the brand, and keep the colours they were saved with
    nav(pg, "vendor-incentives"); pg.click('[data-flyer-new="inc-2"]'); pg.wait_for_timeout(300)
    ok(pg.get_attribute('[data-fly-theme="brand"]', "aria-pressed") == "true", "A new flyer starts in the brand colours")
    ok(pg.evaluate("getComputedStyle(document.querySelector('#flyPreview .flyer-band')).backgroundColor") == "rgb(15, 23, 42)", "Flyer header uses the brand's dark colour")
    ok(pg.evaluate("getComputedStyle(document.querySelector('#flyPreview .flyer-cta') || document.querySelector('#flyPreview .flyer')).fontFamily").startswith('Kanit') or "Kanit" in pg.evaluate("getComputedStyle(document.querySelector('#flyPreview .flyer')).fontFamily"), "Flyer uses the brand font")
    pg.click("[data-fly-ai]"); pg.wait_for_timeout(400); pg.click('[data-fly-save="draft"]'); pg.wait_for_timeout(300)
    fl = [f for f in json.loads(pg.evaluate("localStorage.getItem('partnerWAV_incentiveFlyers')")) if f["incentiveId"] == "inc-2"][0]
    ok(fl["theme"] == "brand" and fl["brand"]["primary"] == "#1e40af", "The saved flyer keeps a copy of the brand colours")
    nav(pg, "branding"); pg.wait_for_timeout(200); pg.fill("#brandH_primary", "#be123c"); pg.wait_for_timeout(100); pg.click("[data-brand-save]"); pg.wait_for_timeout(300)
    fl = [f for f in json.loads(pg.evaluate("localStorage.getItem('partnerWAV_incentiveFlyers')")) if f["incentiveId"] == "inc-2"][0]
    ok(fl["brand"]["primary"] == "#1e40af", "Changing the brand doesn't change a saved flyer")
    nav(pg, "vendor-incentives"); pg.click('[data-flyer-new="inc-2"]'); pg.wait_for_timeout(300)
    ok(pg.evaluate("getComputedStyle(document.querySelector('#flyPreview .flyer-cta')).backgroundColor") == "rgb(190, 18, 60)", "Opening it again to edit shows the current brand")
    pg.click('[data-fly-theme="teal"]'); pg.wait_for_timeout(150)
    ok(pg.locator("#flyPreview .flyer.branded").count() == 0, "A PartnerWAV colour can still be picked instead")

    # ----- landing pages (built by CloudWAV) use the vendor's brand
    role(pg, "operator"); nav(pg, "operator-landing-pages"); pg.locator('[data-lp-edit="lp-intelsense-demo"]').click(); pg.wait_for_timeout(300)
    ok(pg.is_checked("#lpUseBrand") and pg.locator("#lpPreview .lp-page.branded").count() == 1, "Landing page preview uses the vendor's brand")
    ok(pg.evaluate("getComputedStyle(document.querySelector('#lpPreview .lp-cta')).backgroundColor") == "rgb(190, 18, 60)", "Button in the brand's main colour")
    pg.uncheck("#lpUseBrand"); pg.wait_for_timeout(200)
    ok(pg.locator("#lpPreview .lp-page.branded").count() == 0, "Unticking goes back to PartnerWAV colours")
    pg.check("#lpUseBrand"); pg.wait_for_timeout(150)
    pg.click("[data-lp-draft]"); pg.check("#lpVendorApproved"); pg.click('[data-lp-save="publish"]'); pg.wait_for_timeout(300)
    lps = json.loads(pg.evaluate("localStorage.getItem('partnerWAV_landingPages')") or "[]")
    lp = [l for l in lps if l["id"] == "lp-intelsense-demo"]
    ok(lp and lp[0]["brand"]["primary"] == "#be123c", "Published page keeps the brand colours it was published with")
    pg.goto(URL + "?lp=lp-intelsense-demo"); pg.wait_for_timeout(600)
    ok(pg.locator(".lp-public-wrap .lp-page.branded").count() == 1, "Public landing page shows the brand")
    pg.goto(URL + "?demo=1"); pg.wait_for_timeout(600)

    # ----- reset, persistence, other companies
    role(pg, "vendor"); nav(pg, "branding"); pg.wait_for_timeout(200)
    pg.click("[data-brand-reset]"); pg.wait_for_timeout(300)
    ok("Not set yet" in pg.inner_text("[data-brand-status]"), "Can go back to PartnerWAV colours")
    pg.reload(); pg.wait_for_timeout(700); role(pg, "operator"); nav(pg, "branding"); pg.wait_for_timeout(200)
    ok(hexv(pg, "primary") == "#61a6fa", "Botnoi's brand is still there after reload")
    pg.select_option("#brandTarget", "vendor:intelsense"); pg.wait_for_timeout(200)
    ok("Not set yet" in pg.inner_text("[data-brand-status]"), "Removed brand stays removed after reload")
    pg.click('[data-brand-preset="1"]'); pg.click("[data-brand-save]"); pg.wait_for_timeout(300)
    ok("Set up by PartnerWAV" in pg.inner_text("[data-brand-status]"), "CloudWAV can set up a company's brand for them")

    # ----- partner and phone
    role(pg, "partner"); nav(pg, "branding"); pg.wait_for_timeout(200)
    ok(pg.locator("#brandForm").count() == 1 or "Complete your company profile" in pg.inner_text("#brandingContent"), "Partners get Branding for their own company")
    role(pg, "vendor"); nav(pg, "branding")
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(250)
    ok(pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0, "No horizontal overflow at 390px")
    b.close()
report()
