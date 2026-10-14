from harness import *
import json

# MVP Builder wizard, Fractional leadership (once a product is live) and Dev Leads (a software house works a lead).
def store(pg):
    return json.loads(pg.evaluate("localStorage.getItem('partnerWAV_mediaMvp')") or "{}")
def refs(pg):
    return json.loads(pg.evaluate("localStorage.getItem('partnerWAV_softwareReferrals')") or "{}").get("referrals", [])
def txt(pg, sel):
    return pg.locator(sel).inner_text()

with sync_playwright() as p:
    b, pg = open_page(p)
    # ----- a vendor: Fractional and Dev Leads stay hidden until they apply
    role(pg, "vendor")
    ok(pg.locator('#navVendor .navlink[data-screen="fractional"]').get_attribute("hidden") is not None, "Fractional is hidden until the product is live")
    ok(pg.locator('#navVendor .navlink[data-screen="dev-leads"]').get_attribute("hidden") is not None, "Dev Leads is hidden for a company that isn't a software house")
    nav(pg, "mvp-builder"); pg.wait_for_timeout(300)
    ok("Where is your product today?" in txt(pg, "#mvpBuilderContent"), "MVP Builder asks where the product is today")

    # ----- the wizard decides: a bigger build with leadership goes to a software house and to Fractional
    pg.click("[data-mvp-wizard]"); pg.wait_for_timeout(250)
    pg.check('input[name="mw-stage"][value="building"]'); pg.click("#mvpWizNext"); pg.wait_for_timeout(120)
    pg.check('input[name="mw-team"][value="outsourced"]'); pg.click("#mvpWizNext"); pg.wait_for_timeout(120)
    pg.click("#mvpWizNext"); pg.wait_for_timeout(120)
    ok("Choose at least one" in txt(pg, "#mvpWizErr"), "The wizard needs at least one need")
    pg.check('input[name="mw-need"][value="full"]'); pg.check('input[name="mw-need"][value="leadership"]'); pg.wait_for_timeout(50)
    ok(pg.locator("#mwRoles").is_visible(), "Choosing leadership asks which fractional roles")
    pg.check('input[name="mw-role"][value="CTO"]'); pg.click("#mvpWizNext"); pg.wait_for_timeout(120)
    pg.select_option("#mwBudget", "USD 15,000 - 50,000"); pg.fill("#mwDetails", "A full LINE booking app for our clinic network")
    pg.click("#mvpWizNext"); pg.wait_for_timeout(150)
    sug = txt(pg, "#mvpWizBody")
    ok("A bigger build: a specialty software house" in sug and "Fractional leadership: Fractional CTO" in sug, "The suggestion sends a bigger build to a software house, and leadership to Fractional")
    pg.click("#mvpWizNext"); pg.wait_for_timeout(300)
    st = store(pg)
    dev = [r for r in st.get("requests", []) if r["kind"] == "mvp" and r.get("route") == "devlead"]
    fr = [r for r in st.get("requests", []) if r["kind"] == "fractional"]
    ok(len(dev) == 1 and dev[0]["packageId"] == "pkg-full" and dev[0]["budget"] == "USD 15,000 - 50,000", "The build is saved as a dev-lead request")
    ok(len(fr) == 1 and fr[0]["roles"] == ["CTO"] and fr[0]["stage"] == "building", "Leadership is saved as a Fractional request")
    ok(any(s["stage"] == "building" for s in st.get("stages", [])), "The product stage is remembered")

    # ----- a small first version stays with CloudWAV's MVP Builder, even with no dev team
    pg.click("[data-mvp-wizard]"); pg.wait_for_timeout(250)
    pg.check('input[name="mw-stage"][value="idea"]'); pg.click("#mvpWizNext"); pg.wait_for_timeout(100)
    pg.check('input[name="mw-team"][value="none"]'); pg.click("#mvpWizNext"); pg.wait_for_timeout(100)
    pg.check('input[name="mw-need"][value="first"]'); pg.click("#mvpWizNext"); pg.wait_for_timeout(100)
    pg.select_option("#mwBudget", "Under USD 2,000"); pg.fill("#mwDetails", "A prototype to test with users"); pg.click("#mvpWizNext"); pg.wait_for_timeout(100)
    small = txt(pg, "#mvpWizBody")
    ok("CloudWAV's MVP Builder: Quick MVP" in small and "software house" not in small, "A small first version goes to CloudWAV's Quick MVP, even with no dev team")
    pg.click("#mvpWizNext"); pg.wait_for_timeout(250)

    # ----- CloudWAV sends the bigger build to a software house: it becomes a dev lead with its deadlines
    role(pg, "operator"); nav(pg, "operator-services"); pg.wait_for_timeout(300)
    row = [r for r in store(pg)["requests"] if r["kind"] == "mvp" and r.get("route") == "devlead"][0]
    pg.click('[data-svc-tab="mvp"]'); pg.wait_for_timeout(150)
    pg.select_option(f'[data-svc-house="{row["id"]}"]', "sh-demo"); pg.fill(f'[data-svc-value="{row["id"]}"]', "9000")
    pg.click(f'[data-svc-save="{row["id"]}"]'); pg.wait_for_timeout(300)
    leads = [r for r in refs(pg) if r.get("source") == "mvp"]
    ok(len(leads) == 1 and leads[0]["houseId"] == "sh-demo" and leads[0]["status"] == "registered" and leads[0]["mvpRequestId"] == row["id"], "Sending it to a house creates a dev lead there")
    ok(leads[0]["respondBy"] and leads[0]["closeBy"], "The dev lead has a respond-by date and a 30-day close date")

    # ----- Lead partner: first look at dev leads, with a fee
    pg.click('[data-svc-tab="leadpartners"]'); pg.wait_for_timeout(200)
    pg.fill('[data-lead-specialty="sh-demo"]', "LINE and voice AI"); pg.fill('[data-lead-fee="sh-demo"]', "500")
    pg.click('[data-lead-save="sh-demo"]'); pg.wait_for_timeout(250)
    houses = json.loads(pg.evaluate("localStorage.getItem('partnerWAV_softwareReferrals')")).get("houses", [])
    ok(any(h["id"] == "sh-demo" and h.get("leadPartner", {}).get("fee") == 500 for h in houses), "A software house can be a Lead partner, with its monthly fee")

    # ----- the software house's own login works the lead
    nav(pg, "referrals"); pg.click('[data-ref-tab="houses"]'); pg.wait_for_timeout(200)
    pg.click('[data-house-edit="sh-demo"]'); pg.wait_for_timeout(250)
    pg.select_option("#hf_partnerId", "siam-digital"); pg.click("#hfSave"); pg.wait_for_timeout(300)
    role(pg, "partner"); pg.wait_for_timeout(300)
    ok(pg.locator('#navPartner .navlink[data-screen="dev-leads"]').get_attribute("hidden") is None, "A software house's own login sees Dev Leads")
    nav(pg, "dev-leads"); pg.wait_for_timeout(250)
    lid = leads[0]["id"]
    pg.click(f'[data-dl-act="accept"][data-dl-id="{lid}"]'); pg.wait_for_timeout(250)
    lead = [r for r in refs(pg) if r["id"] == lid][0]
    ok(lead["status"] == "accepted" and lead["quoteBy"] and any(x["stage"] == "Accepted" for x in lead["progress"]), "Accepting logs the step and sets the quote date")
    pg.fill(f'[data-dl-amount="{lid}"]', "9500"); pg.click(f'[data-dl-act="quote"][data-dl-id="{lid}"]'); pg.wait_for_timeout(250)
    pg.fill(f'[data-dl-amount="{lid}"]', "9000"); pg.click(f'[data-dl-act="won"][data-dl-id="{lid}"]'); pg.wait_for_timeout(250)
    pg.click(f'[data-dl-act="delivered"][data-dl-id="{lid}"]'); pg.wait_for_timeout(250)
    st = store(pg)
    ok((next(r for r in st["requests"] if r["id"] == row["id"]))["status"] == "delivered", "Delivered marks the MVP request as built and live")
    ok(any(s["stage"] == "live" for s in st.get("stages", [])), "...and the company's product is now live")

    # ----- the company's product is live: Fractional opens
    role(pg, "vendor"); pg.wait_for_timeout(300)
    ok(pg.locator('#navVendor .navlink[data-screen="fractional"]').get_attribute("hidden") is None, "Fractional opens once the MVP is built")
    nav(pg, "fractional"); pg.wait_for_timeout(250)
    ok("Fractional CAIO" in txt(pg, "#fractionalContent"), "The Fractional page lists the four roles")
    pg.check('[data-fr-role="CISO"]'); pg.fill("#frDetails", "Investors want a security review before the next round")
    pg.click("[data-fr-send]"); pg.wait_for_timeout(250)
    ok(any(r["kind"] == "fractional" and r["roles"] == ["CISO"] for r in store(pg)["requests"]), "A Fractional request is saved with its role")
    ok(pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0, "Fractional fits a phone")
    b.close()
report()
