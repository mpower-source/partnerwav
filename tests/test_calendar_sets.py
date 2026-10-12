from harness import *
import json
from datetime import datetime, timedelta, timezone

# Events & Calendar: next to the type filter, pick which calendar to see -- trainings & events, demos,
# or community events (the Thailand calendar's listings) -- or all of them.
now = datetime.now(timezone.utc)
def iso(days, h=3): return (now + timedelta(days=days)).replace(hour=h, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S.000Z")
EVS = [
    {"id": "ev-train", "title": "Unisense partner training", "type": "Vendor training", "start": iso(2), "durationMin": 60, "ownerKey": "vendor:intelsense", "visibility": "shared"},
    {"id": "ev-web", "title": "Q4 pricing webinar", "type": "Webinar", "start": iso(3), "durationMin": 60, "ownerKey": "operator:", "visibility": "shared"},
    {"id": "ev-demo", "title": "Demo for Riverside Hotels", "type": "Demo", "start": iso(4), "durationMin": 45, "ownerKey": "partner:siam-digital", "visibility": "private"},
]
def titles(pg):
    return pg.evaluate("[...document.querySelectorAll('#calList [data-cal-event] .msp-name')].map(e => e.firstChild.textContent.trim())")

with sync_playwright() as p:
    b, pg = open_page(p)
    pg.evaluate("v => localStorage.setItem('partnerWAV_calendar', JSON.stringify({events: JSON.parse(v), bookings: []}))", json.dumps(EVS))
    pg.reload(); pg.wait_for_timeout(700)
    for who in ("partner", "vendor", "affiliate"):
        role(pg, who); nav(pg, "calendar"); pg.wait_for_timeout(200)
        ok(pg.locator("#calSetFilter").is_visible() and pg.locator("#calTypeFilter").is_visible(), who + ": a calendar picker sits next to the type filter")
    role(pg, "partner"); nav(pg, "calendar"); pg.wait_for_timeout(200)
    opts = pg.evaluate("[...document.querySelectorAll('#calSetFilter option')].map(o => o.textContent)")
    ok(opts == ["All calendars", "Trainings & events", "Demos", "Community events"], "Calendars: " + ", ".join(opts))
    pg.click('[data-cal-view="list"]'); pg.wait_for_timeout(200)
    t = titles(pg)
    ok("Unisense partner training" in t and "Demo for Riverside Hotels" in t and any("(example)" in x for x in t), "All calendars shows everything: " + str(len(t)))

    pg.select_option("#calSetFilter", "training"); pg.wait_for_timeout(200)
    t = titles(pg)
    ok(t == ["Unisense partner training", "Q4 pricing webinar"], "Trainings & events: just trainings and webinars: " + str(t))
    types = pg.evaluate("[...document.querySelectorAll('#calTypeFilter option')].map(o => o.textContent)")
    ok("Demo" not in types and "Community event" not in types and "Webinar" in types, "...and the type filter offers only those types")
    pg.select_option("#calTypeFilter", "Webinar"); pg.wait_for_timeout(200)
    ok(titles(pg) == ["Q4 pricing webinar"], "The two filters work together")

    pg.select_option("#calSetFilter", "demos"); pg.wait_for_timeout(200)
    ok(titles(pg) == ["Demo for Riverside Hotels"] and pg.locator("#calTypeFilter").count() == 0, "Demos: only demos")
    ok("private" in pg.inner_text("[data-cal-set-note]") and "Schedule a demo" in pg.inner_text("[data-cal-new]"), "...with a note that they're private, and Schedule a demo")
    pg.click("[data-cal-new]"); pg.wait_for_timeout(200)
    ok(pg.input_value("#calType") == "Demo", "A new event from the Demos calendar starts as a demo")
    pg.click("[data-cal-cancel] >> nth=0"); pg.wait_for_timeout(200)

    pg.select_option("#calSetFilter", "community"); pg.wait_for_timeout(200)
    t = titles(pg)
    ok(t and all("(example)" in x for x in t) and "Unisense partner training" not in t, "Community events: only the communities' events: " + str(t))
    ok(pg.locator("[data-cal-new]").count() == 0 and "?events=thailand" in pg.get_attribute("[data-cal-set-note] a", "href"), "...with a link to the public Thailand calendar, and no Add button for members")
    pg.click('[data-cal-view="calendar"]'); pg.wait_for_timeout(200)
    ok(pg.locator("#calSetFilter").input_value() == "community", "The month view keeps the chosen calendar")
    pg.reload(); pg.wait_for_timeout(600); role(pg, "partner"); nav(pg, "calendar"); pg.wait_for_timeout(200)
    ok(pg.locator("#calSetFilter").input_value() == "community", "The choice is remembered")

    role(pg, "operator"); nav(pg, "calendar"); pg.wait_for_timeout(200)
    ok(pg.locator('[data-goto-screen="operator-community"]').count() == 1, "CloudWAV gets a button to add community events from Community Partners")
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0, "Fits a phone")
    b.close()
report()
