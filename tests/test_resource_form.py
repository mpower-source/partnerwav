from harness import *
import json

# Submit Resource/Material: pick an existing partner program from a list; the vendor fills itself in.
# A selected box's highlight never runs into the label above it.
def open_editor(pg, who):
    role(pg, who); nav(pg, "resource-browse")
    pg.locator('[data-goto-screen="resources-editor"]:visible').first.click(); pg.wait_for_timeout(250)

with sync_playwright() as p:
    b, pg = open_page(p)
    # ----- a partner sees every vendor's program and products, grouped by vendor
    open_editor(pg, "partner")
    ok(pg.evaluate("document.getElementById('resourceProgram').tagName") == "SELECT", "Program is a dropdown")
    groups = pg.evaluate("[...document.querySelectorAll('#resourceProgram optgroup')].map(g => g.label)")
    ok("Intelsense AI" in groups and "Botnoi Voice" in groups and len(groups) >= 3, "Grouped by vendor: " + ", ".join(groups))
    opts = pg.evaluate("[...document.querySelectorAll('#resourceProgram optgroup[label=\"Intelsense AI\"] option')].map(o => o.textContent)")
    ok(opts[0] == "Intelsense AI (whole program)" and len(opts) > 1, "Each vendor offers its whole program and its products: " + ", ".join(opts))
    ok(pg.input_value("#resourceVendor") == "" and pg.get_attribute("#resourceVendor", "readonly") is not None, "Vendor starts empty and can't be typed into")
    prod = pg.evaluate("document.querySelectorAll('#resourceProgram optgroup[label=\"Intelsense AI\"] option')[1].value")
    pg.select_option("#resourceProgram", prod); pg.wait_for_timeout(100)
    ok(pg.input_value("#resourceVendor") == "Intelsense AI", "Picking a product fills in its vendor")
    pg.select_option("#resourceProgram", "botnoi::Botnoi Voice"); pg.wait_for_timeout(100)
    ok(pg.input_value("#resourceVendor") == "Botnoi Voice", "Picking another program updates the vendor")
    pg.fill("#resourceTitle", "Botnoi Battlecard"); pg.select_option("#resourceType", "pdf"); pg.fill("#resourceSummary", "Two pages")
    pg.fill("#resourceFileUrl", "https://example.com/battlecard.pdf"); pg.click("#resourceForm button[type=submit]"); pg.wait_for_timeout(300)
    rec = [r for r in json.loads(pg.evaluate("localStorage.getItem('partnerWAV_resourceData')"))["pending"] if r["title"] == "Botnoi Battlecard"]
    ok(rec and rec[0]["program"] == "Botnoi Voice" and rec[0]["vendor"] == "Botnoi Voice" and rec[0]["programId"] == "botnoi", "Saved with the program, its vendor and the program id")

    # ----- a vendor's own program is picked for them
    open_editor(pg, "vendor")
    groups = pg.evaluate("[...document.querySelectorAll('#resourceProgram optgroup')].map(g => g.label)")
    ok(len(groups) == 1, "A vendor sees only its own program: " + ", ".join(groups))
    ok(pg.input_value("#resourceProgram").endswith("::" + groups[0]) and pg.input_value("#resourceVendor") == groups[0], "...already selected, with the vendor filled in")

    # ----- the highlight around a selected box stays clear of its label
    for sel in ("#resourceTitle", "#resourceProgram", "#resourceSummary"):
        pg.focus(sel); pg.wait_for_timeout(100)
        gap = pg.evaluate("""s => { const el = document.querySelector(s), lab = el.parentElement.querySelector('label');
            const cs = getComputedStyle(el), ring = Math.max(0, parseFloat(cs.outlineWidth) + parseFloat(cs.outlineOffset));
            return el.getBoundingClientRect().top - ring - lab.getBoundingClientRect().bottom; }""", sel)
        ok(gap >= 2, sel + ": the highlight stays clear of the label (" + str(round(gap, 1)) + "px gap)")
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0, "Form fits a phone")
    b.close()
report()
