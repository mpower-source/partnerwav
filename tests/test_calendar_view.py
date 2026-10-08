from harness import *
import json, datetime

# Month calendar is the default view; clicking a day opens a pop-up with that day's events; List view is one click away.
now = datetime.datetime.now()
d1 = datetime.datetime(now.year, now.month, 14, 9, 0).astimezone(datetime.timezone.utc)
d2 = datetime.datetime(now.year, now.month, 14, 15, 0).astimezone(datetime.timezone.utc)
d3 = datetime.datetime(now.year, now.month, 20, 10, 0).astimezone(datetime.timezone.utc)
nm = (now.replace(day=1) + datetime.timedelta(days=40)).replace(day=5, hour=10)
d4 = nm.astimezone(datetime.timezone.utc)
iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%S.000Z")
key = lambda d: d.astimezone().strftime("%Y-%m-%d")
evs = [
    {"id": "e1", "ownerKey": "vendor:intelsense", "title": "Unisense AI partner training", "type": "Vendor training", "start": iso(d1), "durationMin": 60, "location": "", "link": "https://meet.example.com/u", "desc": "Hands-on training"},
    {"id": "e2", "ownerKey": "operator:", "title": "PartnerWAV onboarding", "type": "PartnerWAV training", "start": iso(d2), "durationMin": 60, "location": "", "link": "", "desc": ""},
    {"id": "e3", "ownerKey": "vendor:intelsense", "title": "Demo for Bangkok Bank", "type": "Demo", "visibility": "private", "start": iso(d3), "durationMin": 45, "location": "", "link": "", "desc": ""},
    {"id": "e4", "ownerKey": "operator:", "title": "Next month meetup", "type": "Meetup", "start": iso(d4), "durationMin": 60, "location": "Bangkok", "link": "", "desc": ""},
]

with sync_playwright() as p:
    b, pg = open_page(p)
    pg.evaluate("localStorage.setItem('partnerWAV_calendar', JSON.stringify({events:%s, bookings:[]}))" % json.dumps(evs))
    pg.reload(); pg.wait_for_timeout(700)

    role(pg, "operator"); nav(pg, "calendar")
    ok(pg.locator("#calMonth").count() == 1 and pg.locator("#calList").count() == 0, "Opens in calendar view by default")
    ok(now.strftime("%B") in pg.inner_text("[data-cal-month-label]"), "Shows the current month: " + pg.inner_text("[data-cal-month-label]"))
    day = pg.locator(f'[data-cal-day="{key(d1)}"]')
    ok(day.count() == 1 and day.locator("[data-cal-chip]").count() == 2, "A day with two events shows both")
    ok(pg.locator(f'[data-cal-day="{key(d3)}"] [data-cal-chip]').count() == 1, "CloudWAV sees the private demo on the grid")
    ok(pg.locator("[data-cal-day]").count() == 2, "Only days with events are clickable")

    # click the day (not a chip) -> pop-up with every event that day
    day.locator(".cal-num").click(); pg.wait_for_timeout(250)
    pop = pg.locator("#calPop")
    ok(pop.count() == 1 and pop.locator("[data-cal-pop-event]").count() == 2, "Clicking the day opens a pop-up with its events")
    t = pop.inner_text()
    ok("Unisense AI partner training" in t and "PartnerWAV onboarding" in t and "Hosted by" in t, "Pop-up shows the event details")
    ok(pop.locator('a[href*="calendar.google.com"]').count() == 2 and pop.locator("[data-cal-ics]").count() == 2, "Pop-up has the add-to-calendar buttons")
    ok(pop.locator('[data-cal-pop-event="e2"] [data-cal-edit]').count() == 1 and pop.locator('[data-cal-pop-event="e1"] [data-cal-edit]').count() == 0, "CloudWAV can edit only its own event from the pop-up")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    ok(pg.locator("#calPop").count() == 0, "Escape closes the pop-up")

    # clicking a chip puts that event first
    day.locator('[data-cal-chip="e2"]').click(); pg.wait_for_timeout(250)
    ok(pg.locator("#calPop [data-cal-pop-event]").first.get_attribute("data-cal-pop-event") == "e2", "Clicking an event puts it first in the pop-up")
    pg.locator("#calPop [data-cal-edit]").click(); pg.wait_for_timeout(250)
    ok(pg.locator("#calPop").count() == 0 and pg.input_value("#calTitle") == "PartnerWAV onboarding", "Edit from the pop-up opens the form")
    pg.locator("[data-cal-cancel]").first.click(); pg.wait_for_timeout(200)
    ok(pg.locator("#calMonth").count() == 1, "Cancel returns to the calendar")

    # month navigation
    pg.click('[data-cal-month="1"]'); pg.wait_for_timeout(200)
    ok(pg.locator(f'[data-cal-day="{key(d4)}"]').count() == 1, "Next month shows its events")
    pg.click('[data-cal-month="0"]'); pg.wait_for_timeout(200)
    ok(now.strftime("%B") in pg.inner_text("[data-cal-month-label]") and pg.locator(".cal-cell.today").count() == 1, "Today jumps back and marks today")

    # filters apply to the grid
    pg.select_option("#calTypeFilter", "Demo"); pg.wait_for_timeout(200)
    ok(pg.locator("[data-cal-day]").count() == 1, "Type filter applies to the calendar")
    pg.select_option("#calTypeFilter", ""); pg.wait_for_timeout(200)

    # list view and remembered choice
    pg.click('[data-cal-view="list"]'); pg.wait_for_timeout(200)
    ok(pg.locator("#calList").count() == 1 and pg.locator("#calMonth").count() == 0 and pg.locator("[data-cal-event]").count() >= 1, "List view shows the event cards")
    ok(pg.locator("[data-cal-event] .collab-ic svg").count() >= 1, "List cards use line icons")
    pg.reload(); pg.wait_for_timeout(700); role(pg, "operator"); nav(pg, "calendar")
    ok(pg.locator("#calList").count() == 1, "The chosen view is remembered")
    pg.click('[data-cal-view="calendar"]'); pg.wait_for_timeout(200)

    # partners don't see the private demo
    role(pg, "partner"); nav(pg, "calendar")
    ok(pg.locator(f'[data-cal-day="{key(d3)}"]').count() == 0, "Partners don't see the vendor's private demo")
    pg.locator(f'[data-cal-day="{key(d1)}"] .cal-num').click(); pg.wait_for_timeout(250)
    ok(pg.locator("#calPop [data-cal-edit]").count() == 0, "Partners get no Edit in the pop-up")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)

    # phone: dots instead of chips, still opens
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(250)
    ok(pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0, "No horizontal overflow at 390px")
    ok(pg.locator(f'[data-cal-day="{key(d1)}"] .cal-dots').is_visible(), "Phone shows dots on event days")
    pg.locator(f'[data-cal-day="{key(d1)}"]').click(); pg.wait_for_timeout(250)
    ok(pg.locator("#calPop [data-cal-pop-event]").count() == 2, "Tapping a day on a phone opens the pop-up")
    b.close()
report()
