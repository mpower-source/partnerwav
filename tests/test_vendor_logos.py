from harness import *
import base64, os, tempfile

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAEklEQVR4nGP4z8CAFWEXHbQSACj/P8Fu7N9hAAAAAElFTkSuQmCC")
with sync_playwright() as p:
    b, pg = open_page(p)
    role(pg, "operator"); nav(pg, "operator-programs")
    rows = pg.locator("#operatorProgramRows tr")
    def row(name): return pg.locator("#operatorProgramRows tr", has_text=name).first
    for name, kind in [("Intelsense AI", "image/svg"), ("Cross Connect", "image/svg"), ("Portonics Ltd.", "image/png"), ("ZipEvent", "image/png"), ("Botnoi Voice", "image/svg")]:
        src = row(name).locator("img.op-logo").get_attribute("src") or ""
        ok(src.startswith("data:" + kind) and "%3Ctext" not in src, f"{name}: its own symbol shows in Manage programs")
    ok("6CC5ED" in row("Intelsense AI").locator("img.op-logo").get_attribute("src") and "INTEL" not in row("Intelsense AI").locator("img.op-logo").get_attribute("src"), "Intelsense: just the light-blue AI piece")
    ok(pg.evaluate("[...document.querySelectorAll('#operatorProgramRows img.op-logo')].every(i=>i.complete && i.naturalWidth>0)"), "All logos load as images")

    # ----- operator changes a vendor's logo
    f = os.path.join(tempfile.mkdtemp(), "new.png"); open(f, "wb").write(PNG)
    row("Unisense").locator("[data-op-logo]").click(); pg.wait_for_timeout(150)
    ok("Logo for Unisense" in pg.inner_text(".modal"), "Logo button opens a logo dialog for that vendor")
    before = row("Unisense").locator("img.op-logo").get_attribute("src")
    pg.set_input_files("#oplLogoFile", f); pg.wait_for_timeout(500)
    pg.click("[data-op-logo-save]"); pg.wait_for_timeout(300)
    after = row("Unisense").locator("img.op-logo").get_attribute("src")
    ok(after != before and after.startswith("data:image/"), "Uploading and saving replaces the logo")
    row("Unisense").locator("[data-op-logo]").click(); pg.wait_for_timeout(150)
    pg.click('[data-remove-logo="opl"]'); pg.click("[data-op-logo-save]"); pg.wait_for_timeout(300)
    ok(row("Unisense").locator("img.op-logo").count() == 0 and "Add logo" in row("Unisense").inner_text(), "Removing leaves an 'Add logo' button")

    # ----- operator adds a new vendor with a logo
    pg.click('[data-goto-screen="operator-program-editor"]'); pg.wait_for_timeout(200)
    pg.fill("#opProgramName", "AgentID"); pg.fill("#opProgramVertical", "AI agents"); pg.fill("#opProgramOrigin", "Thailand"); pg.fill("#opProgramDesc", "Identity for AI agents.")
    pg.select_option("#opProgramRelationship", "Vendor Program"); pg.select_option("#opProgramStatus", "onboarding")
    pg.set_input_files("#oppLogoFile", f); pg.wait_for_timeout(500)
    ok(pg.locator("#oppLogoPreview img").count() == 1, "New-vendor form shows the chosen logo")
    pg.click('#operatorProgramForm button[type="submit"]'); pg.wait_for_timeout(400)
    ok(visible_screen(pg) == ["scr-operator-programs"] and row("AgentID").locator("img.op-logo").count() == 1, "New vendor is listed in Manage programs with its logo")
    nav(pg, "vendor-network")
    ok("AgentID" in pg.inner_text("#scr-vendor-network"), "New vendor appears in the Vendor Network")
    role(pg, "partner"); nav(pg, "partner-directory")
    ok("AgentID" in pg.inner_text("#scr-partner-directory"), "New vendor appears in the Program Directory")
    role(pg, "operator"); nav(pg, "operator-programs")
    row("AgentID").locator("[data-configure]").click(); pg.wait_for_timeout(300)
    ok(len(visible_screen(pg)) == 1, "Its Configure screen opens")
    pg.reload(); pg.wait_for_timeout(900)
    role(pg, "operator"); nav(pg, "operator-programs")
    ok(row("AgentID").locator("img.op-logo").count() == 1 and row("Unisense").locator("img.op-logo").count() == 0, "Added vendor and logo changes are still there after a reload")

    # ----- a saved copy with the old letter placeholder gets the new symbol; an uploaded logo is kept
    pg.evaluate("""()=>{ localStorage.setItem('partnerWAV_vendorProfileEdits', JSON.stringify({
        crossconnect:{ name:'Cross Connect', logo:'data:image/svg+xml;utf8,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" rx="14" fill="#7a9c00"/><text x="32" y="43" font-family="Arial, sans-serif" font-size="26" font-weight="700" fill="#fff" text-anchor="middle">C</text></svg>') },
        zipevent:{ name:'ZipEvent', logo:'data:image/png;base64,UPLOADED' } })); }""")
    pg.reload(); pg.wait_for_timeout(900)
    role(pg, "operator"); nav(pg, "operator-programs")
    ok("c7d6ce" in row("Cross Connect").locator("img.op-logo").get_attribute("src"), "Old letter placeholder is replaced by the symbol")
    ok(row("ZipEvent").locator("img.op-logo").get_attribute("src").endswith("UPLOADED"), "A logo someone uploaded is left alone")
    if os.environ.get("SHOT"): pg.screenshot(path=os.environ["SHOT"])
    report()
    b.close()
