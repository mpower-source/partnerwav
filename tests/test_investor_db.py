from harness import *
import json

# CloudWAV's investor & incubator database: operator-only, segmented like the research (investment firms;
# accelerators, incubators & government; angels & individuals), searchable, with contact checks and CSV import.
def db(pg): return json.loads(pg.evaluate("localStorage.getItem('partnerWAV_investorDb')") or "[]")
CSV = '''Company Name,Website,City,Investment Focus,Company Type,Ticket Size (USD),Stage Focus,Contact 1 Name,Contact 1 Designation,Contact 1 Email,Contact 1 LinkedIn,Notes & Strategy
Example Seed Fund,examplefund.vc,Bangkok,"AI, SaaS",VC,$250K-$1M,Pre-seed - Seed,Ann Example,Partner,ann@examplefund.vc,linkedin.com/in/annexample,Met at Techsauce
Example Hackathon Hub,examplehub.co,Chiang Mai,"AI, Climate",Accelerator,$20K-$50K,Pre-seed,,,,,Runs a pitch night monthly
Jane Angel,,Bangkok,"Fintech, AI",Angel Investor,$50K-$200K,Seed,Jane Angel,Angel,jane@example.com,linkedin.com/in/janeangelexample,
SCB 10X (Siam Commercial Bank),scb10x.com,Bangkok,AI,Corporate VC,$1M-$20M,Seed-Growth,,,,,
=HYPERLINK("http://bad.test"),,,,VC,,,,,,,
'''

with sync_playwright() as p:
    b, pg = open_page(p)
    for who in ("partner", "vendor", "affiliate", "investor"):
        role(pg, who)
        ok(not in_menu(pg, "operator-investor-db"), who + " can't open the investor database")
    role(pg, "operator")
    ok(in_menu(pg, "operator-investor-db"), "CloudWAV has the Investor Database")
    nav(pg, "operator-investor-db"); pg.wait_for_timeout(300)
    counts = pg.evaluate("Object.fromEntries([...document.querySelectorAll('[data-idb-count]')].map(e => [e.dataset.idbCount, +e.textContent]))")
    ok(counts == {"firms": 2, "programs": 4, "individuals": 1}, "Segmented like the research: " + str(counts))
    tabs = pg.evaluate("[...document.querySelectorAll('[data-idb-seg]')].map(b => b.textContent)")
    ok(tabs[1].startswith("Investment firms") and tabs[2].startswith("Accelerators, incubators") and tabs[3].startswith("Angels & individuals"), "Segment tabs: " + " | ".join(tabs))
    pg.click('[data-idb-seg="programs"]'); pg.wait_for_timeout(200)
    names = pg.evaluate("[...document.querySelectorAll('.idb-name')].map(e => e.textContent)")
    ok(len(names) == 4 and any("depa" in n for n in names) and not any("Beacon" in n for n in names), "Accelerators & government tab: " + ", ".join(names))
    pg.click('[data-idb-seg=""]'); pg.wait_for_timeout(150)
    pg.fill("#idbQ", "fintech"); pg.wait_for_timeout(400)
    found = pg.evaluate("[...document.querySelectorAll('.idb-name')].map(e => e.textContent)")
    ok("SCB 10X (Siam Commercial Bank)" in found and "depa (Digital Economy Promotion Agency)" not in found and "Example Angel (example)" not in found, "Search by focus: " + ", ".join(found))
    pg.fill("#idbQ", ""); pg.wait_for_timeout(400)
    pg.fill("#idbAmount", "15M"); pg.wait_for_timeout(400)
    ok(pg.evaluate("[...document.querySelectorAll('.idb-name')].map(e => e.textContent)") == ["SCB 10X (Siam Commercial Bank)"] or "SCB 10X (Siam Commercial Bank)" in pg.inner_text("#investorDbContent") and "Example Angel" not in pg.inner_text(".idb-grid"), "A USD 15M raise shows only investors whose cheques fit")
    pg.fill("#idbAmount", ""); pg.wait_for_timeout(400)
    pg.select_option("#idbStage", "Pre-seed"); pg.wait_for_timeout(200)
    ok("Example Angel (example)" in pg.inner_text(".idb-grid") and "SCB 10X" not in pg.inner_text(".idb-grid"), "Filter by stage")
    pg.select_option("#idbStage", "")

    # contacts: LinkedIn and email buttons, and flags to check before reaching out
    pg.locator('[data-idb-open="idb-example-angel"]').first.click(); pg.wait_for_timeout(200)
    c = pg.locator('[data-idb-contact="idb-example-angel|0"]')
    ok(c.locator("a.idb-li").get_attribute("href") == "https://www.linkedin.com/in/example" and c.locator('a[href^="mailto:"]').count() == 1, "Each contact has LinkedIn and email buttons")
    ok("Email not confirmed" in c.text_content(), "Unconfirmed details are flagged")
    c.locator("[data-idb-check]").click(); pg.wait_for_timeout(200)
    ok([x for x in db(pg) if x["id"] == "idb-example-angel"][0]["contacts"][0]["checked"], "...and can be marked checked")

    # add a record by hand
    pg.click("[data-idb-new]"); pg.wait_for_timeout(150)
    pg.fill("#idbName", "Bangkok Angel Network"); pg.select_option("#idbType", "Individual investor"); pg.fill("#idbFormFocus", "AI, SaaS"); pg.fill("#idbTicketMin", "50K"); pg.fill("#idbTicketMax", "300K")
    pg.click('#idbForm [data-idb-stage="Seed"]'); pg.fill("#idbCName", "Somchai Example"); pg.fill("#idbCLinkedin", "linkedin.com/in/somchaiexample"); pg.click("[data-idb-save]"); pg.wait_for_timeout(200)
    x = [x for x in db(pg) if x["name"] == "Bangkok Angel Network"]
    ok(x and x[0]["segment"] == "individuals" and x[0]["ticketMin"] == 50000 and x[0]["ticketMax"] == 300000 and x[0]["stages"] == ["Seed"] and x[0]["contacts"][0]["linkedin"] == "https://linkedin.com/in/somchaiexample", "Add a record by hand")
    pg.reload(); pg.wait_for_timeout(600); role(pg, "operator"); nav(pg, "operator-investor-db"); pg.wait_for_timeout(300)
    ok("Bangkok Angel Network" in pg.inner_text("#investorDbContent"), "Records are still there after reloading the page")

    # CSV import from a sheet like the research files
    pg.click("[data-idb-import]"); pg.wait_for_timeout(150)
    pg.fill("#idbPaste", CSV); pg.fill("#idbTag", "Techsauce 2026"); pg.click("[data-idb-preview]"); pg.wait_for_timeout(200)
    out = pg.inner_text("#idbImportOut")
    ok("4 new records" in out and "1 already in the database" in out, "Import preview: new vs already there: " + out[:120])
    pg.click("[data-idb-commit]"); pg.wait_for_timeout(200)
    d = db(pg); f = [x for x in d if x["name"] == "Example Seed Fund"][0]; h = [x for x in d if x["name"] == "Example Hackathon Hub"][0]; j = [x for x in d if x["name"] == "Jane Angel"][0]
    ok(f["segment"] == "firms" and f["ticketMin"] == 250000 and f["ticketMax"] == 1000000 and f["stages"] == ["Pre-seed", "Seed"] and f["tags"] == ["Techsauce 2026"] and f["contacts"][0]["flags"], "Imported firm: ticket, stages, tag, contact to check")
    ok(h["segment"] == "programs" and j["segment"] == "individuals", "Imported records land in the right segments")
    with pg.expect_download() as dl:
        pg.click("[data-idb-export]")
    csv = open(dl.value.path(), encoding="utf-8-sig").read()
    ok("Example Seed Fund" in csv and "'=HYPERLINK" in csv and "Investment firms" in csv, "Download CSV, formula-safe")
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0, "Fits a phone")
    b.close()
report()
