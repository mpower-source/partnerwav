from harness import *
import json, datetime

# Community Partners > Event sources: the feeds the events-sync function reads (Luma / Meetup iCal links,
# Eventbrite organizers), the sites checked by hand every Saturday (Meetup search, Eventbrite search,
# Zipevent), and the paste-in for that weekly list. Everything found waits for review.
def comm(pg):
    return json.loads(pg.evaluate("localStorage.getItem('partnerWAV_community')") or "{}")
def settings(pg):
    d = json.loads(pg.evaluate("localStorage.getItem('partnerWAV_softwareReferrals')") or "{}")
    return {r["id"]: r for r in d.get("operatorSettings", [])}

soon = (datetime.date.today() + datetime.timedelta(days=12)).isoformat()
later = (datetime.date.today() + datetime.timedelta(days=20)).isoformat()
CSV = ("title,date,time,city,venue,link,organizer,price,source\n"
       f"AI Agents Night,{soon},19:00,Bangkok,True Digital Park,https://www.meetup.com/ai-bkk/events/123,AI Bangkok,Free,meetup\n"
       f"\"Pitch Night, Season 2\",{later},18:30,Online,Zoom,https://www.zipeventapp.com/e/pitch-2,Startup TH,,zipevent\n"
       "Old Meetup,2020-01-01,19:00,Bangkok,,https://lu.ma/old,X,,luma\n"
       f"No Link,{soon},19:00,Bangkok,,,X,,luma\n")

with sync_playwright() as p:
    b, pg = open_page(p)
    role(pg, "operator")
    nav(pg, "operator-community"); pg.wait_for_timeout(400)
    pg.click('[data-co-tab="sources"]'); pg.wait_for_timeout(300)
    body = pg.inner_text("#operatorCommunityContent")
    ok("Where tech events come from" in body and "Checked by hand on Saturdays (4)" in body, "The Event sources tab lists the four sites checked by hand")
    ok(all(x in body for x in ["Luma: Bangkok", "Meetup: tech in Bangkok", "Eventbrite: science & tech in Bangkok", "Zipevent"]), "Luma, Meetup, Eventbrite and Zipevent are there to start")
    ok("Meetup Pro" in body and "closed its public event search" in body, "It says why Meetup and Eventbrite search are checked by hand")
    ok(pg.locator("[data-evs-run]").is_disabled(), "Check sources now waits until there is a feed to read")

    # add a Luma calendar's iCal link
    pg.select_option("#evsKind", "ical"); pg.fill("#evsLabel", "AI Bangkok (Luma)")
    pg.fill("#evsUrl", "webcal://api.lu.ma/ics/get?entity=calendar&id=cal-test"); pg.select_option("#evsCity", "Bangkok")
    pg.check("#evsAllTech"); pg.click("[data-evs-add]"); pg.wait_for_timeout(300)
    src = [s for s in settings(pg)["eventSources"]["sources"] if s["label"] == "AI Bangkok (Luma)"]
    ok(src and src[0]["kind"] == "ical" and src[0]["url"].startswith("https://api.lu.ma/ics/") and src[0]["allTech"] and src[0]["city"] == "Bangkok", "An iCal source is saved (webcal:// becomes https://)")
    ok("Read automatically (1)" in pg.inner_text("#operatorCommunityContent") and not pg.locator("[data-evs-run]").is_disabled(), "It shows under Read automatically and the check can run")

    # an Eventbrite organizer needs its numeric id
    pg.select_option("#evsKind", "eventbrite"); pg.fill("#evsUrl", "not-a-number"); pg.click("[data-evs-add]"); pg.wait_for_timeout(200)
    ok(not pg.locator("#evsErr").is_hidden() and "organizer" in pg.inner_text("#evsErr"), "An Eventbrite organizer without an id is explained")
    pg.fill("#evsUrl", "https://www.eventbrite.com/o/techsauce-17583938910"); pg.click("[data-evs-add]"); pg.wait_for_timeout(300)
    ok(any(s.get("orgId") == "17583938910" for s in settings(pg)["eventSources"]["sources"]), "...the id is taken from the organizer page address")

    # switch one off, change the keywords
    sid = src[0]["id"]
    pg.click(f'[data-evs-toggle="{sid}"]'); pg.wait_for_timeout(200)
    ok([s for s in settings(pg)["eventSources"]["sources"] if s["id"] == sid][0]["active"] is False and pg.get_attribute(f'[data-evs-toggle="{sid}"]', "aria-checked") == "false", "A source can be switched off")
    pg.fill("#evsKeywords", "AI, startup\nfintech"); pg.click("[data-evs-kw]"); pg.wait_for_timeout(200)
    ok(settings(pg)["eventSources"]["keywords"] == ["AI", "startup", "fintech"], "Keywords are saved")
    ok(not any(k in s for s in settings(pg)["eventSources"]["sources"] for k in ("token", "secret", "apiKey")), "No tokens are kept in the portal")

    # demo: Check sources now explains what it needs
    pg.click(f'[data-evs-toggle="{sid}"]'); pg.wait_for_timeout(200)
    pg.click("[data-evs-run]"); pg.wait_for_timeout(200)
    ok("events-sync" in pg.inner_text("#evsRunMsg"), "Without Supabase, the check says what it needs instead of failing")

    # paste the Saturday list
    pg.fill("#evsPaste", CSV); pg.click("[data-evs-import]"); pg.wait_for_timeout(300)
    msg = pg.inner_text("#evsPasteMsg")
    ok("2 added" in msg and "2 skipped" in msg, "The Saturday list adds the good rows and skips past or link-less ones")
    evs = [e for e in comm(pg)["events"] if e.get("source")]
    ai = [e for e in evs if e["title"] == "AI Agents Night"]
    pitch = [e for e in evs if e["title"] == "Pitch Night, Season 2"]
    ok(ai and ai[0]["status"] == "pending" and ai[0]["source"] == "meetup" and ai[0]["start"] == soon + "T12:00:00.000Z" and ai[0]["id"].startswith("ce-ext-"), "Rows wait for review, in Bangkok time, marked with where they came from")
    ok(pitch and pitch[0]["city"] == "Online" and pitch[0]["category"] == "pitch" and pitch[0]["source"] == "zipevent", "A pitch night online is recognised")
    pg.fill("#evsPaste", CSV); pg.click("[data-evs-import]"); pg.wait_for_timeout(300)
    ok("0 added" in pg.inner_text("#evsPasteMsg") and "2 already there" in pg.inner_text("#evsPasteMsg"), "Pasting the same list again adds nothing twice")

    pg.click('[data-co-tab="review"]'); pg.wait_for_timeout(300)
    card = pg.locator(f'[data-ce-row="{ai[0]["id"]}"]')
    ok(card.count() == 1 and "from meetup" in card.inner_text().lower(), "In review, the event shows where it came from")
    pg.click(f'[data-ce-approve="{ai[0]["id"]}"]'); pg.wait_for_timeout(300)
    ok([e for e in comm(pg)["events"] if e["id"] == ai[0]["id"]][0]["status"] == "published", "Approving lists it")

    # removing an imported event keeps a note, so the next check doesn't bring it back
    pg.click('[data-co-tab="events"]'); pg.wait_for_timeout(300)
    pg.click(f'[data-ce-delete="{ai[0]["id"]}"]'); pg.wait_for_timeout(300)
    gone = [e for e in comm(pg)["events"] if e["id"] == ai[0]["id"]]
    ok(gone and gone[0]["status"] == "declined" and gone[0].get("deletedAt") and not pg.locator(f'[data-ce-row="{ai[0]["id"]}"]').count(), "A removed imported event disappears but is remembered")
    pg.click('[data-co-tab="sources"]'); pg.wait_for_timeout(200)
    pg.fill("#evsPaste", CSV); pg.click("[data-evs-import]"); pg.wait_for_timeout(300)
    ok("1 already there" in pg.inner_text("#evsPasteMsg") or "2 already there" in pg.inner_text("#evsPasteMsg"), "...and is not added again")

    # phone
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(300)
    wide = pg.evaluate("""() => [...document.querySelectorAll('#operatorCommunityContent *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1).slice(0, 5).map(e => e.tagName + '.' + e.className + ' ' + Math.round(e.getBoundingClientRect().right))""")
    ok(pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0, "Event sources fits a phone " + str(wide))
    b.close()
report()
