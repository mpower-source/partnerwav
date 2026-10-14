from harness import *

# Members, promoters and investors see the community calendar only: community events, pitch events and
# hackathons. The trainings, webinars and demos that vendors, partners and affiliates run stay inside the program.
with sync_playwright() as p:
    b, pg = open_page(p)
    role(pg, "vendor"); nav(pg, "calendar")
    pg.click("[data-cal-new]"); pg.wait_for_timeout(200)
    pg.fill("#calTitle", "Internal vendor training XYZ"); pg.fill("#calStart", "2030-03-15T14:00")
    pg.click("[data-cal-save]"); pg.wait_for_timeout(300)
    pg.click('[data-cal-view="list"]'); pg.wait_for_timeout(150)
    ok("Internal vendor training XYZ" in pg.inner_text("#calendarContent"), "A vendor's shared training is on the vendor calendar")
    pg.select_option("#calSetFilter", "training"); pg.wait_for_timeout(200)

    for r in ["member", "media", "investor"]:
        role(pg, r); nav(pg, "calendar"); pg.wait_for_timeout(300)
        ok(visible_screen(pg) == ["scr-calendar"], f"{r}: Events & Calendar is in the menu")
        sets = pg.evaluate("[...document.querySelectorAll('#calSetFilter option')].map(o => o.value)")
        ok(sets == ["", "community", "pitch"], f"{r}: only All, Community events and Pitch events & hackathons " + str(sets))
        if pg.locator('[data-cal-view="list"]').get_attribute("aria-pressed") != "true":
            pg.click('[data-cal-view="list"]'); pg.wait_for_timeout(200)
        txt = pg.inner_text("#calendarContent")
        types = pg.evaluate("[...document.querySelectorAll('#calendarContent [data-cal-event]')].map(e => e.innerText.toLowerCase())")
        ok("Internal vendor training XYZ" not in txt and len(types) > 0 and all(("community event" in t or "pitch event" in t or "hackathon" in t or "open call" in t) for t in types),
           f"{r}: sees community, pitch and hackathon events but not the vendor's training ({len(types)} events)")
        ok(pg.locator("#calendarContent [data-cal-new]").count() == 0, f"{r}: can't add events to the program calendar")
        types_opt = pg.evaluate("[...document.querySelectorAll('#calTypeFilter option')].map(o => o.textContent)")
        ok(not any(t in types_opt for t in ["Vendor training", "Webinar", "Demo"]), f"{r}: type filter has only community kinds")
        pg.click('[data-cal-view="calendar"]'); pg.wait_for_timeout(200)
        ok("Internal vendor training XYZ" not in pg.inner_text("#calendarContent"), f"{r}: ...in the month view too")

    role(pg, "vendor"); nav(pg, "calendar"); pg.wait_for_timeout(200)
    ok(pg.evaluate("[...document.querySelectorAll('#calSetFilter option')].length") == 5, "Vendors still have every calendar")
    b.close()
report()
