from harness import *
import json, os, tempfile

# Members: people CloudWAV invites to PartnerWAV. One place for Thailand's tech, AI, startup, investor and business
# events, a profile with a picture, and connections with other members (in the app, WhatsApp, LINE and LinkedIn).
def mem(pg):
    return json.loads(pg.evaluate("localStorage.getItem('partnerWAV_members')") or "{}")

with sync_playwright() as p:
    b, pg = open_page(p)
    role(pg, "member"); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-member-overview"], "A member starts on their overview")
    menu = pg.evaluate("[...document.querySelectorAll('#navMember .navlink')].map(b => b.getAttribute('data-screen'))")
    ok(menu == ["member-overview", "member-events", "member-people", "partner-messages", "startup-perks", "member-profile"], "Member menu: Overview, Events, People, Messages, Startup Perks, My Profile")
    ok(pg.evaluate("[...document.querySelectorAll('#navMember .ic')].every(e => e.querySelector('svg'))"), "Member menu uses line icons")
    ov = pg.inner_text("#memberOverviewContent")
    ok("Welcome, Ploy" in ov and "Coming up" in ov and "1 connection request" in ov, "Overview: welcome, upcoming events and the waiting request")
    ok(pg.locator("[data-mem-goalcard='saas']").count() == 1 and pg.locator("[data-mem-goalcard='mvp']").count() == 1, "Overview: list a SaaS product, or build an MVP with PartnerWAV")
    pg.click('[data-mem-interest="saas"]'); pg.wait_for_timeout(200)
    ok("saas" in [m for m in mem(pg)["profiles"] if m["id"] == "mem-ploy"][0]["goals"], "'I'm interested' is saved on the profile")

    # events: the approved community calendar
    nav(pg, "member-events"); pg.wait_for_timeout(300)
    n_all = pg.locator("#memberEventsContent [data-tec-event]").count()
    ok(n_all >= 3 and pg.locator("#memberEventsContent [data-tec-register]").count() >= 1, "Events: the approved Thailand events, with Register")
    pg.click('#memberEventsContent [data-mem-kind="hackathon"]'); pg.wait_for_timeout(200)
    kinds = pg.evaluate("[...document.querySelectorAll('#memberEventsContent .tec-kind')].map(e => e.textContent.toLowerCase())")
    ok(kinds and all("hackathon" in k for k in kinds), "Filter by kind of event")
    pg.click('#memberEventsContent [data-mem-kind=""]'); pg.fill("#memEvQ", "pitch"); pg.wait_for_timeout(500)
    ok(0 < pg.locator("#memberEventsContent [data-tec-event]").count() < n_all, "Search events")
    pg.fill("#memEvQ", ""); pg.wait_for_timeout(400)

    # people: request waiting, accept it, then contact options appear
    nav(pg, "member-people"); pg.wait_for_timeout(300)
    ok("Requests (1)" in pg.inner_text("#memberPeopleContent") and "My connections (1)" in pg.inner_text("#memberPeopleContent"), "People: everyone, requests and connections")
    arun = pg.locator('#memberPeopleContent [data-mem-card="mem-arun"]')
    ok(arun.locator("text=WhatsApp").count() == 1 and arun.locator("[data-mem-msg]").count() == 1, "A connection shows Message and WhatsApp")
    david = pg.locator('#memberPeopleContent [data-mem-card="mem-david"]')
    ok(david.locator("[data-mem-connect]").count() == 1 and david.locator("text=WhatsApp").count() == 0 and david.locator("a:has-text('LinkedIn')").count() == 1, "Not connected: Connect and LinkedIn only, no WhatsApp")
    pg.click('#memberPeopleContent [data-mem-tab="requests"]'); pg.wait_for_timeout(200)
    pg.click('#memberPeopleContent [data-mem-accept="mem-nok"]'); pg.wait_for_timeout(300)
    c = [x for x in mem(pg)["connections"] if x["id"] == "mc-mem-nok--mem-ploy"][0]
    ok(c["status"] == "accepted", "Accepting a request connects you")
    mine = [x for x in mem(pg)["contacts"] if x["id"] == "mem-ploy"][0]
    ok(sorted(mine["sharedWith"]) == ["member:mem-arun", "member:mem-nok"], "Your WhatsApp and LINE are shared with your connections only")
    pg.click('#memberPeopleContent [data-mem-tab="all"]'); pg.wait_for_timeout(200)
    pg.click('#memberPeopleContent [data-mem-connect="mem-david"]'); pg.wait_for_timeout(300)
    d = [x for x in mem(pg)["connections"] if x["id"] == "mc-mem-david--mem-ploy"]
    ok(d and d[0]["status"] == "pending" and d[0]["from"] == "member:mem-ploy" and d[0]["to"] == "member:mem-david", "Connect sends a request")
    ok(pg.locator('#memberPeopleContent [data-mem-card="mem-david"] [data-mem-withdraw]').count() == 1, "...which can be withdrawn")
    pg.click('#memberPeopleContent [data-mem-topic="Investors & funding"]'); pg.wait_for_timeout(200)
    ok(pg.evaluate("[...document.querySelectorAll('#memberPeopleContent [data-mem-card]')].map(e => e.dataset.memCard)") == ["mem-david"], "Filter people by interest")

    # message a connection in the app
    pg.click('#memberPeopleContent [data-mem-topic=""]'); pg.wait_for_timeout(200)
    pg.click('#memberPeopleContent [data-mem-msg="mem-arun"]'); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-partner-messages"] and "Arun Mehta" in pg.inner_text("#scr-partner-messages"), "Message opens a conversation in the app")

    # profile with a picture
    nav(pg, "member-profile"); pg.wait_for_timeout(300)
    from PIL import Image
    pic = os.path.join(tempfile.mkdtemp(), "me.png"); Image.new("RGB", (800, 600), (200, 120, 90)).save(pic)
    pg.set_input_files("#memPhotoFile", pic); pg.wait_for_timeout(600)
    pg.fill("#memHeadline", "Founder of Spa Slot"); pg.fill("#memLinkedin", "linkedin.com/in/ploy-example"); pg.fill("#memLine", "ploy.spa")
    pg.click('[data-mem-ptopic="Marketing & growth"]'); pg.click("[data-mem-save]"); pg.wait_for_timeout(300)
    me = [m for m in mem(pg)["profiles"] if m["id"] == "mem-ploy"][0]
    ok(me["headline"] == "Founder of Spa Slot" and me["linkedin"] == "https://linkedin.com/in/ploy-example" and "Marketing & growth" in me["topics"], "Profile saved: headline, LinkedIn and interests")
    ok(me.get("photo", "").startswith("data:image/jpeg;base64,") and len(me["photo"]) < 60000, "Profile picture is saved, made small")
    ok([x for x in mem(pg)["contacts"] if x["id"] == "mem-ploy"][0]["line"] == "ploy.spa", "LINE is kept with the private contact details")
    pg.fill("#memLinkedin", "https://example.com/me"); pg.click("[data-mem-save]"); pg.wait_for_timeout(200)
    ok("LinkedIn" in pg.inner_text("#memErr"), "LinkedIn must be a linkedin.com address")

    # CloudWAV: sets members up like any other account, and can preview the member space
    role(pg, "operator"); nav(pg, "operator-accounts"); pg.wait_for_timeout(300)
    pg.click("[data-acct-any]"); pg.wait_for_timeout(200)
    ok("Member" in pg.inner_text("#acctRole"), "Accounts & Logins can set up a Member")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    pg.set_viewport_size({"width": 390, "height": 844}); role(pg, "member"); nav(pg, "member-people"); pg.wait_for_timeout(300)
    ok(pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0, "People fits a phone")
    b.close()
report()
