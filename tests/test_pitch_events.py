from harness import *
import json

# A calendar of its own for pitch nights, demo days, accelerator open calls and hackathons -- in members' Events &
# Calendar, on the public Thailand calendar (?events=thailand&kind=pitch), and when CloudWAV or an organizer adds one.
def comm(pg): return json.loads(pg.evaluate("localStorage.getItem('partnerWAV_community')") or "{}")
def titles(pg): return pg.evaluate("[...document.querySelectorAll('#calList [data-cal-event] .msp-name')].map(e => e.firstChild.textContent.trim())")

with sync_playwright() as p:
    b, pg = open_page(p)
    # ----- members: a separate calendar for pitch events and hackathons
    for who in ("partner", "vendor", "affiliate", "investor"):
        role(pg, who); nav(pg, "calendar"); pg.wait_for_timeout(150)
        ok("Pitch events & hackathons" in pg.evaluate("[...document.querySelectorAll('#calSetFilter option')].map(o => o.textContent)"), who + ": the Pitch events & hackathons calendar is there")
    role(pg, "partner"); nav(pg, "calendar"); pg.wait_for_timeout(150)
    if pg.locator('[data-cal-view="list"]').count(): pg.click('[data-cal-view="list"]')
    pg.select_option("#calSetFilter", "pitch"); pg.wait_for_timeout(200)
    t = titles(pg)
    ok("Investor Pitch Night (example)" in t and "Seed Accelerator: applications open (example)" in t and not any("Builders Meetup" in x for x in t), "Pitch calendar: pitch nights and open calls, not ordinary meetups: " + str(t))
    types = pg.evaluate("[...document.querySelectorAll('#calTypeFilter option')].map(o => o.textContent)")
    ok(types == ["All types", "Pitch event", "Hackathon", "Open call"], "...with its own types: " + str(types))
    pg.select_option("#calTypeFilter", "Open call"); pg.wait_for_timeout(150)
    ok(titles(pg) == ["Seed Accelerator: applications open (example)"], "Filter to open calls")
    pg.select_option("#calSetFilter", "community"); pg.wait_for_timeout(150)
    ok(not any("Pitch Night" in x for x in titles(pg)), "Community events no longer include pitch events")

    # ----- CloudWAV adds a hackathon from Community Partners
    role(pg, "operator"); nav(pg, "operator-community"); pg.wait_for_timeout(200)
    pg.click('[data-co-tab="events"]'); pg.click("[data-ce-new]"); pg.wait_for_timeout(150)
    pg.click('#ceForm [data-ce-kind="hackathon"]')
    pg.select_option("#ceOrg", "org-startup-grind-bkk"); pg.fill("#ceTitle", "AI Agents Hack Day"); pg.fill("#ceStart", "2027-01-23T09:00"); pg.fill("#ceDuration", "480")
    pg.fill("#ceLink", "https://www.startupgrind.com/bangkok/"); pg.click("[data-ce-save]"); pg.wait_for_timeout(200)
    ev = [e for e in comm(pg)["events"] if e["title"] == "AI Agents Hack Day"]
    ok(ev and ev[0]["category"] == "hackathon", "CloudWAV lists a hackathon")
    ok("Hackathon" in pg.text_content(f'[data-ce-row="{ev[0]["id"]}"]'), "...marked as a hackathon")

    # ----- the public Thailand calendar
    vis = pg.context.new_page(); vis.set_viewport_size({"width": 390, "height": 844})
    vis.goto(URL + "?demo=1&events=thailand"); vis.wait_for_timeout(600)
    chips = vis.evaluate("[...document.querySelectorAll('[data-tec-kind]')].map(b => b.textContent)")
    ok("Pitch events & hackathons" in chips and "Hackathons" in chips, "Public calendar: filter by kind of event: " + str(chips))
    vis.click('[data-tec-kind="pitch"]'); vis.wait_for_timeout(200)
    txt = vis.inner_text("#publicEventsContent")
    ok("AI Agents Hack Day" in txt and "Investor Pitch Night" in txt and "Claude Builders Meetup" not in txt, "Pitch events & hackathons on their own")
    ok(vis.locator(f'[data-tec-event="{ev[0]["id"]}"] .tec-kind').count() == 1, "Each one carries its kind")
    vis.goto(URL + "?demo=1&events=thailand&kind=pitch"); vis.wait_for_timeout(600)
    ok("Claude Builders Meetup" not in vis.inner_text("#publicEventsContent") and vis.get_attribute('[data-tec-kind="pitch"]', "aria-pressed") == "true", "A shareable link opens straight on pitch events (&kind=pitch)")
    ok(vis.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0, "Fits a phone")
    # an organizer sends in a demo day
    vis.click("[data-tec-show]"); vis.wait_for_timeout(150)
    vis.select_option("#tecKindSel", "pitch"); vis.fill("#tecOrg", "Bangkok Angels"); vis.fill("#tecTitle", "Q1 Demo Day"); vis.fill("#tecStart", "2027-02-10T18:00")
    vis.fill("#tecLink", "https://example.com/demo-day"); vis.fill("#tecName", "Mai"); vis.fill("#tecContact", "@mai")
    vis.wait_for_timeout(1600); vis.click("#tecSubmit"); vis.wait_for_timeout(300)
    sub = [e for e in comm(vis)["events"] if e["title"] == "Q1 Demo Day"]
    ok(sub and sub[0]["category"] == "pitch" and sub[0]["status"] == "pending", "An organizer's demo day arrives as a pitch event, waiting for review")
    vis.close(); b.close()
report()
