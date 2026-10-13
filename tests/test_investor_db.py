from harness import *
import json

# CloudWAV's investor & incubator database: operator-only, segmented like the research (investment firms;
# accelerators, incubators & government; angels & individuals), searchable, with contact checks and CSV import.
def db(pg): return json.loads(pg.evaluate("localStorage.getItem('partnerWAV_investorDb')") or "[]")
CSV = '''Company Name,Website,City,Investment Focus,Company Type,Ticket Size (USD),Stage Focus,Contact 1 Name,Contact 1 Designation,Contact 1 Email,Contact 1 LinkedIn,Notes & Strategy
Example Seed Fund,examplefund.vc,Bangkok,"AI, SaaS",VC,$250K-$1M,Pre-seed - Seed,Ann Example,Partner,ann@examplefund.vc,linkedin.com/in/annexample,Met at Techsauce
Example Hackathon Hub,examplehub.co,Chiang Mai,"AI, Climate",Accelerator,$20K-$50K,Pre-seed,,,,,Runs a pitch night monthly
Jane Angel,,Bangkok,"Fintech, AI",Angel Investor,$50K-$200K,Seed,Jane Angel,Angel,jane@example.com,linkedin.com/in/janeangelexample,
SCB 10X (SCBX),scb10x.com,Bangkok,AI,Corporate VC,$1M-$20M,Seed-Growth,,,,,
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
    r = pg.evaluate("[...document.querySelectorAll('#navOperator .ic')].map(e => [e.closest('button').innerText.trim(), (e.querySelector('svg') || {}).nodeName || ''])")
    ok(all(x[1] for x in r) and pg.get_attribute('#navOperator [data-screen="operator-investor-db"] .ic', "data-pw-icon") == "database", "Menu: line icons only, including Investor Database and Event Connect: " + str([x[0] for x in r if not x[1]]))
    counts = pg.evaluate("Object.fromEntries([...document.querySelectorAll('[data-idb-count]')].map(e => [e.dataset.idbCount, +e.textContent]))")
    ok(counts == {"firms": 3, "programs": 4, "individuals": 1}, "Segmented like the research: " + str(counts))
    tabs = pg.evaluate("[...document.querySelectorAll('[data-idb-seg]')].map(b => b.textContent)")
    ok(tabs[1].startswith("Investment firms") and tabs[2].startswith("Accelerators, incubators") and tabs[3].startswith("Angels & individuals"), "Segment tabs: " + " | ".join(tabs))
    pg.click('[data-idb-seg="programs"]'); pg.wait_for_timeout(200)
    names = pg.evaluate("[...document.querySelectorAll('.idb-name')].map(e => e.textContent)")
    ok(len(names) == 4 and any("depa" in n for n in names) and not any("Beacon" in n for n in names), "Accelerators & government tab: " + ", ".join(names))
    pg.click('[data-idb-seg=""]'); pg.wait_for_timeout(150)
    pg.fill("#idbQ", "fintech"); pg.wait_for_timeout(400)
    found = pg.evaluate("[...document.querySelectorAll('.idb-name')].map(e => e.textContent)")
    ok("SCB 10X (SCBX)" in found and "depa (Digital Economy Promotion Agency)" not in found and "Example Angel (example)" not in found, "Search by focus: " + ", ".join(found))
    pg.fill("#idbQ", ""); pg.wait_for_timeout(400)
    pg.fill("#idbAmount", "15M"); pg.wait_for_timeout(400)
    fit = pg.evaluate("[...document.querySelectorAll('.idb-name')].map(e => e.textContent)")
    ok("Openspace Ventures" in fit and not any(n.startswith(("SCB 10X", "Beacon", "Example Angel", "depa")) for n in fit), "A USD 15M raise leaves out investors whose cheques are too small: " + str(fit))
    pg.fill("#idbAmount", ""); pg.wait_for_timeout(400)
    pg.select_option("#idbStage", "Pre-seed"); pg.wait_for_timeout(200)
    ok("Example Angel (example)" in pg.inner_text(".idb-cols") and "SCB 10X" not in pg.inner_text(".idb-cols"), "Filter by stage")
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
    # where they are based, a foreign parent, and the pilot-first route
    pg.set_viewport_size({"width": 1280, "height": 900}); pg.reload(); pg.wait_for_timeout(600); role(pg, "operator"); nav(pg, "operator-investor-db"); pg.wait_for_timeout(300)
    ok(pg.locator('[data-idb-row="idb-openspace-ventures"] [data-idb-abroad]').text_content() == "Based in Singapore", "An investor based outside Thailand is marked")
    ok(pg.locator('[data-idb-row="idb-plug-and-play-thailand"] [data-idb-parent]').count() == 1 and pg.locator('[data-idb-row="idb-plug-and-play-thailand"] [data-idb-abroad]').count() == 0, "A Thai office with a foreign parent shows the parent, not 'based abroad'")
    pg.select_option("#idbLoc", "abroad"); pg.wait_for_timeout(200)
    ok(pg.evaluate("[...document.querySelectorAll('[data-idb-row]')].map(e => e.dataset.idbRow)") == ["idb-openspace-ventures"], "Filter: based outside Thailand")
    pg.select_option("#idbLoc", "thailand"); pg.wait_for_timeout(200)
    ok(pg.locator('[data-idb-row="idb-openspace-ventures"]').count() == 0, "Filter: based in Thailand")
    pg.select_option("#idbLoc", ""); pg.select_option("#idbRoute", "pilot"); pg.wait_for_timeout(200)
    rows = pg.evaluate("[...document.querySelectorAll('[data-idb-row]')].map(e => e.dataset.idbRow)")
    ok(sorted(rows) == ["idb-beacon-venture-capital", "idb-scb-10x", "idb-true-incube"], "Filter: pilot first: " + str(rows))
    pg.click('[data-idb-row="idb-scb-10x"]'); pg.wait_for_timeout(200)
    row = pg.locator('[data-idb-detail="idb-scb-10x"]')
    ok("One FYI Center" in row.inner_text() and row.locator('[data-idb-sources] a').count() == 2 and row.locator('[data-idb-sources] a').first.get_attribute("href").startswith("https://"), "Details show a contact's note and the sources the record was checked against")
    ok("Pilot first: offer SCB / SCBX a paid pilot" in pg.inner_text('[data-idb-detail="idb-scb-10x"]') and "Based in: Thailand" in pg.inner_text('[data-idb-detail="idb-scb-10x"]'), "Details show the route in and where they are based")
    # ----- investor program: a company's own notes (Intelsense is the sample) show only in that company's view
    txt = lambda: pg.inner_text("#investorDbContent")
    opts = pg.evaluate("[...document.querySelectorAll('#idbRoute option')].map(o => o.textContent)")
    ok("Series A pipeline" not in opts and "Timing:" not in txt() and pg.locator("[data-idb-co-notes], [data-idb-groups]").count() == 0, "General view: no company's notes or sprint groups")
    ok(pg.evaluate("[...document.querySelectorAll('#idbCo option')].map(o => o.value)") == ["", "intelsense"], "Notes for: Intelsense AI is in the program and switched on")
    pg.select_option("#idbCo", "intelsense"); pg.wait_for_timeout(200)
    opts = pg.evaluate("[...document.querySelectorAll('#idbRoute option')].map(o => o.textContent)")
    ok("Sprint A: contact now" in opts and "Series A pipeline" in opts and "Not for this round" in opts, "Intelsense's view: its sprint groups appear as filters: " + str(opts))
    pg.select_option("#idbRoute", "seriesA"); pg.wait_for_timeout(200)
    rows = pg.evaluate("[...document.querySelectorAll('[data-idb-row]')].map(e => e.dataset.idbRow)")
    ok(sorted(rows) == ["idb-beacon-venture-capital", "idb-openspace-ventures"], "Filter: Series A pipeline: " + str(rows))
    pg.click('[data-idb-row="idb-openspace-ventures"]'); pg.wait_for_timeout(200)
    r = pg.inner_text('[data-idb-detail="idb-openspace-ventures"]')
    ok("notes for intelsense ai" in r.lower() and "Timing: Series A pipeline" in r, "Details show Intelsense's notes, labelled as Intelsense's")
    pg.select_option("#idbRoute", "notseed"); pg.wait_for_timeout(200)
    ok(pg.evaluate("[...document.querySelectorAll('[data-idb-row]')].map(e => e.dataset.idbRow)") == ["idb-depa"], "Filter: not for this round")
    pg.select_option("#idbRoute", ""); pg.wait_for_timeout(200)
    # editing in Intelsense's view writes to Intelsense's notes only
    pg.click('[data-idb-row="idb-scb-10x"]'); pg.wait_for_timeout(200)
    pg.locator('[data-idb-detail="idb-scb-10x"] [data-idb-edit]').click(); pg.wait_for_timeout(200)
    pg.fill("#idbBasedIn", "Singapore"); pg.fill("#idbCoTiming", "Come back after the pilot"); pg.click('#idbForm [data-idb-cogroup="sprintA"]'); pg.click("[data-idb-save]"); pg.wait_for_timeout(200)
    scb = [x for x in db(pg) if x["id"] == "idb-scb-10x"][0]
    ok(scb["basedIn"] == "Singapore" and scb["forCompany"]["intelsense"] == {"timing": "Come back after the pilot", "groups": ["sprintA"]} and "timing" not in scb, "Edits in Intelsense's view are saved as Intelsense's notes")
    # a second company joins; switching Intelsense off hides its notes everywhere, without deleting them
    pg.click("[data-idb-prog]"); pg.wait_for_timeout(200)
    pg.fill("#idbProgName", "Acme Robotics"); pg.click("[data-idb-prog-add]"); pg.wait_for_timeout(200)
    ok(pg.evaluate("[...document.querySelectorAll('#idbCo option')].map(o => o.value)") == ["", "intelsense", "acme-robotics"], "A company added to the program can be chosen")
    pg.select_option("#idbCo", "acme-robotics"); pg.wait_for_timeout(200)
    ok("notes for intelsense ai" not in txt().lower() and pg.locator("[data-idb-groups]").count() == 0, "Another company's view never shows Intelsense's notes")
    pg.select_option("#idbCo", "intelsense"); pg.wait_for_timeout(200)
    pg.click('[data-idb-prog-toggle="intelsense"]'); pg.wait_for_timeout(200)
    ok(pg.get_attribute('[data-idb-prog-toggle="intelsense"]', "aria-checked") == "false" and pg.evaluate("[...document.querySelectorAll('#idbCo option')].map(o => o.value)") == ["", "acme-robotics"] and pg.input_value("#idbCo") == "", "Switched off: Intelsense leaves Notes for, and the view goes back to general")
    ok("notes for intelsense ai" not in txt().lower() and [x for x in db(pg) if x["id"] == "idb-scb-10x"][0]["forCompany"]["intelsense"]["timing"] == "Come back after the pilot", "...its notes are hidden but kept")
    prog = [s for s in json.loads(pg.evaluate("localStorage.getItem('partnerWAV_softwareReferrals')"))["operatorSettings"] if s["id"] == "investorProgram"][0]
    ok([(c["id"], c["active"]) for c in prog["companies"]] == [("intelsense", False), ("acme-robotics", True)], "The program is saved with CloudWAV's settings: " + str(prog["companies"]))
    pg.click('[data-idb-prog-toggle="intelsense"]'); pg.wait_for_timeout(200)
    pg.select_option("#idbCo", "intelsense"); pg.wait_for_timeout(200)
    ok(pg.locator("[data-idb-groups]").count() > 0, "Switched back on: Intelsense's notes return")
    pg.click("[data-idb-prog-close]"); pg.select_option("#idbCo", ""); pg.wait_for_timeout(200)
    # records saved before the program existed move their Intelsense notes under Intelsense
    pg.evaluate("""() => { const d = JSON.parse(localStorage.getItem('partnerWAV_investorDb')); d.push({id:'idb-old', name:'Old Record', type:'VC fund', segment:'firms', tags:['Intelsense sprint B (pitch weeks 2-4)', 'Techsauce 2026'],
        talkingPoints:{intelsense:'Old angle'}, fit:{intelsense:'High'}, approach:'LinkedIn', timing:'Later', contacts:[]}); localStorage.setItem('partnerWAV_investorDb', JSON.stringify(d)); }""")
    pg.reload(); pg.wait_for_timeout(600); role(pg, "operator"); nav(pg, "operator-investor-db"); pg.wait_for_timeout(300)
    old = [x for x in db(pg) if x["id"] == "idb-old"][0]
    ok(old["tags"] == ["Techsauce 2026"] and old["forCompany"]["intelsense"] == {"talkingPoint": "Old angle", "fit": "High", "approach": "LinkedIn", "timing": "Later", "groups": ["sprintB"]} and not any(k in old for k in ("talkingPoints", "fit", "approach", "timing")), "Older records: Intelsense's notes move under Intelsense")
    # ----- layout: three columns (firms / programs / angels), same-size tiles; details open under the chosen tile, one at a time
    hs = lambda: sorted(set(pg.evaluate("[...document.querySelectorAll('.idb-row')].map(e => Math.round(e.getBoundingClientRect().height))")))
    cols = pg.evaluate("[...document.querySelectorAll('[data-idb-col]')].map(c => c.dataset.idbCol)")
    ok(cols == ["firms", "programs", "individuals"] and len(hs()) == 1, "Three columns, every tile the same height: " + str(cols) + " " + str(hs()))
    ok(pg.locator('[data-idb-col="programs"] [data-idb-row="idb-depa"]').count() == 1 and pg.locator('[data-idb-col="individuals"] [data-idb-row="idb-example-angel"]').count() == 1, "Each investor sits in its own segment's column")
    pg.click('[data-idb-row="idb-beacon-venture-capital"]'); pg.wait_for_timeout(200)
    ok(pg.evaluate("(() => { const r = document.querySelector('[data-idb-row=\"idb-beacon-venture-capital\"]'); return r.nextElementSibling && r.nextElementSibling.querySelector('[data-idb-detail=\"idb-beacon-venture-capital\"]') ? 1 : 0; })()") == 1, "Details open right under the tile")
    pg.click('[data-idb-row="idb-depa"]'); pg.wait_for_timeout(200)
    ok(pg.locator("[data-idb-detail]").count() == 1 and pg.locator('[data-idb-detail="idb-depa"]').count() == 1, "Opening one in another column closes the first")
    pg.click('[data-idb-row="idb-depa"]'); pg.wait_for_timeout(200)
    ok(pg.locator("[data-idb-detail]").count() == 0, "Clicking the open tile again closes it")
    pg.click('[data-idb-seg="programs"]'); pg.wait_for_timeout(200)
    ok(pg.evaluate("[...document.querySelectorAll('[data-idb-col]')].map(c => c.dataset.idbCol)") == ["programs"], "A segment tab shows just that column")
    ok(pg.locator("[data-idb-side] .idb-side-empty").count() == 1, "...with a details area beside it")
    rows = pg.evaluate("[...document.querySelectorAll('.idb-cols.side .idb-row')].map(r => r.dataset.idbRow)")
    pick = rows[-1]
    pg.click(f'[data-idb-row="{pick}"]'); pg.wait_for_timeout(250)
    geo = pg.evaluate(f"""(() => {{ const r = document.querySelector('[data-idb-row="{pick}"]').getBoundingClientRect(), p = document.querySelector('[data-idb-side] [data-idb-detail="{pick}"]');
      if (!p) return null; const q = p.closest('.idb-sidepanel').getBoundingClientRect(); return [Math.round(q.left - r.right), Math.round(q.top - r.top)]; }})()""")
    ok(geo is not None and 0 <= geo[0] <= 40 and abs(geo[1]) <= 2, "In one segment, the details open to the right of the clicked tile, level with it: " + str(geo))
    ok(pg.locator(".idb-inline").count() == 0, "...not under it")
    ok(pg.evaluate("[...document.querySelectorAll('.idb-cols.side .idb-row')].map(r => r.dataset.idbRow)")[0] == pick, "The chosen investor moves to the top of the list")
    ok(pg.evaluate("document.querySelector('.idb-cols.side').getBoundingClientRect().top") >= 0 and pg.evaluate("document.querySelector('.idb-sidepanel').getBoundingClientRect().top") < pg.evaluate("innerHeight"), "...and its details are on screen without scrolling")
    pg.click(f'[data-idb-row="{rows[0]}"]'); pg.wait_for_timeout(250)
    ok(pg.locator("[data-idb-detail]").count() == 1 and pg.locator(f'[data-idb-side] [data-idb-detail="{rows[0]}"]').count() == 1, "Choosing another tile moves the details next to it")
    ok(pg.evaluate("[...document.querySelectorAll('.idb-cols.side .idb-row')].map(r => r.dataset.idbRow)")[:1] == [rows[0]], "...and that tile goes to the top")
    pg.click(f'[data-idb-row="{rows[0]}"]'); pg.wait_for_timeout(200)
    ok(pg.locator("[data-idb-detail]").count() == 0, "...and clicking it again closes them")
    pg.click('[data-idb-seg=""]'); pg.wait_for_timeout(200)
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    pg.click('[data-idb-row="idb-depa"]'); pg.wait_for_timeout(200)
    ok(pg.locator('[data-idb-detail="idb-depa"]').is_visible() and len(hs()) == 1, "Phone: columns stack, details open under the tile: " + str(hs()))
    pg.click("[data-idb-close]"); pg.wait_for_timeout(200)
    ok(pg.locator("[data-idb-detail]").count() == 0, "Close shuts the details")
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0, "Fits a phone")
    b.close()
report()
