from harness import *
import os, json, re

# Community Partners: CloudWAV tracks the communities it works with, lists their events on a public
# Thailand calendar (?events=thailand), and organizers can send events in for review.
def comm(pg):
    return json.loads(pg.evaluate("localStorage.getItem('partnerWAV_community')") or "{}")

QRJS = qrcode_js()
with sync_playwright() as p:
    b, pg = open_page(p)
    pg.context.route("**/cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=QRJS, headers={"access-control-allow-origin": "*"}))
    pg.reload(); pg.wait_for_timeout(600)
    role(pg, "operator")
    ok(in_menu(pg, "operator-community"), "Community Partners is in CloudWAV's menu")
    nav(pg, "operator-community"); pg.wait_for_timeout(400)
    body = pg.inner_text("#operatorCommunityContent")
    ok("Bangkok Entrepreneurs" in body and "Bangkok Entrepreneurs (online community)" in body and "Claude Thailand Community" in body, "The three communities are there to start")
    ok(pg.locator('[data-co-row="org-claude-thailand"] a.cp-link').get_attribute("href") == "https://www.facebook.com/groups/1745892855948687", "The Claude Thailand Community links to its Facebook group")
    ok(pg.locator(".cp-share .ev-qr img, .cp-share .ev-qr canvas").count() >= 1, "The public calendar link has a QR code")

    # log a SaaS builder found in the Claude group
    row = pg.locator('[data-co-row="org-claude-thailand"]')
    row.locator("summary").click()
    pg.fill("#coOppCo-org-claude-thailand", "Example SaaS Co"); pg.select_option("#coOppType-org-claude-thailand", "vendor"); pg.fill("#coOppNote-org-claude-thailand", "Could list on PartnerWAV")
    pg.click('[data-co-opp-add="org-claude-thailand"]'); pg.wait_for_timeout(200)
    org = [o for o in comm(pg)["orgs"] if o["id"] == "org-claude-thailand"][0]
    ok(org["opps"] and org["opps"][0]["company"] == "Example SaaS Co" and org["opps"][0]["type"] == "vendor", "An opportunity found in the community is logged")

    # edit a community: mark it a partner with agreed perks
    pg.click('[data-co-edit="org-bkk-entrepreneurs"]'); pg.wait_for_timeout(200)
    pg.select_option("#coStatus", "partner"); pg.click('[data-co-perk="mention"]'); pg.click('[data-co-save="org-bkk-entrepreneurs"]'); pg.wait_for_timeout(200)
    org = [o for o in comm(pg)["orgs"] if o["id"] == "org-bkk-entrepreneurs"][0]
    ok(org["status"] == "partner" and org["perks"].get("mention"), "A community can be marked a partner with what's been agreed")

    # add a community's event, in Bangkok time
    pg.click('[data-ce-new="org-bkk-entrepreneurs"]'); pg.wait_for_timeout(200)
    ok(pg.input_value("#ceOrg") == "org-bkk-entrepreneurs", "Adding from a community picks it")
    pg.fill("#ceTitle", "Bangkok Entrepreneurs Mixer"); pg.fill("#ceStart", "2027-01-20T18:30"); pg.fill("#ceVenue", "Glowfish Sathorn"); pg.fill("#cePrice", "Free")
    pg.fill("#ceLink", "https://www.bangkokentrepreneurs.com/events"); pg.click("[data-ce-save]"); pg.wait_for_timeout(300)
    ev = [e for e in comm(pg)["events"] if e["title"] == "Bangkok Entrepreneurs Mixer"]
    ok(ev and ev[0]["start"] == "2027-01-20T11:30:00.000Z" and ev[0]["status"] == "published" and ev[0]["orgId"] == "org-bkk-entrepreneurs", "Saved as 18:30 Bangkok time (11:30 UTC), listed")
    ok("18:30" in pg.inner_text(f'[data-ce-row="{ev[0]["id"]}"]'), "Shown in Bangkok time")

    # an Event Connect page for that event
    pg.click(f'[data-ce-connect="{ev[0]["id"]}"]'); pg.wait_for_timeout(500)
    pages = json.loads(pg.evaluate("localStorage.getItem('partnerWAV_eventConnect')") or "{}").get("pages", [])
    ok(any(x.get("communityEventId") == ev[0]["id"] and x["name"] == "Bangkok Entrepreneurs Mixer" for x in pages) and visible_screen(pg) == ["scr-operator-events"], "One click makes an Event Connect page for it")

    # ----- the public calendar on a phone
    vis = pg.context.new_page(); vis.set_viewport_size({"width": 390, "height": 844})
    vis.goto(URL + "?demo=1&events=thailand"); vis.wait_for_timeout(700)
    txt = vis.inner_text("#publicEventsContent")
    ok("Thailand Tech & Startup Events" in txt and "Bangkok Entrepreneurs Mixer" in txt and "Claude Builders Meetup" in txt, "The public calendar lists the communities' events")
    ok("Startup Drinks by the Beach" not in txt, "An event waiting for review isn't listed")
    ok(not vis.locator(".sidebar:visible, .role-btn:visible").count(), "No portal menu")
    ok(vis.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0, "Fits a phone")
    card = vis.locator(f'[data-tec-event="{ev[0]["id"]}"]')
    ok("18:30" in card.inner_text() and "Glowfish Sathorn" in card.inner_text(), "Times are in Bangkok time with the venue")
    ok(card.locator("[data-tec-register]").get_attribute("href") == "https://www.bangkokentrepreneurs.com/events", "Register goes to the organizer's page")
    ok("calendar.google.com" in card.locator("[data-tec-google]").get_attribute("href"), "Add to Google Calendar is there")
    vis.click('[data-tec-city="Chiang Mai"]'); vis.wait_for_timeout(200)
    t2 = vis.inner_text("#publicEventsContent")
    ok("SaaS Growth Workshop" in t2 and "Bangkok Entrepreneurs Mixer" not in t2, "Filter by city")

    # one community's own calendar link
    vis.goto(URL + "?demo=1&events=thailand&org=org-bkk-entrepreneurs"); vis.wait_for_timeout(600)
    t3 = vis.inner_text("#publicEventsContent")
    ok("Bangkok Entrepreneurs events" in t3 and "Bangkok Entrepreneurs Mixer" in t3 and "Claude Builders Meetup" not in t3, "A community's own link shows only their events")

    # an organizer sends an event in
    vis.goto(URL + "?demo=1&events=thailand"); vis.wait_for_timeout(600)
    vis.click("[data-tec-show]"); vis.wait_for_timeout(200)
    vis.click("#tecSubmit"); vis.wait_for_timeout(200)
    ok(not vis.locator("#tecError").is_hidden(), "An empty form explains what's missing")
    vis.fill("#tecOrg", "Hua Hin Makers"); vis.fill("#tecTitle", "Makers Night"); vis.fill("#tecStart", "2027-02-02T19:00"); vis.select_option("#tecCity", "Hua Hin")
    vis.fill("#tecLink", "https://www.meetup.com/huahin-makers"); vis.fill("#tecName", "Dao"); vis.fill("#tecContact", "@daoline")
    vis.wait_for_timeout(1600); vis.click("#tecSubmit"); vis.wait_for_timeout(400)
    ok(vis.locator("[data-tec-done]").count() == 1, "The organizer gets a thank-you")
    sub = [e for e in comm(vis)["events"] if e["title"] == "Makers Night"]
    ok(sub and sub[0]["status"] == "pending" and sub[0]["submitter"]["contact"] == "@daoline", "It waits for review with their contact")
    vis.close()

    # CloudWAV approves: the organizer becomes a community, the contact stays private
    pg.reload(); pg.wait_for_timeout(600); role(pg, "operator"); nav(pg, "operator-community"); pg.wait_for_timeout(300)
    pg.click('[data-co-tab="review"]'); pg.wait_for_timeout(200)
    ok("Makers Night" in pg.inner_text("#operatorCommunityContent") and "@daoline" in pg.inner_text("#operatorCommunityContent"), "CloudWAV sees it waiting, with who sent it")
    pg.click(f'[data-ce-approve="{sub[0]["id"]}"]'); pg.wait_for_timeout(300)
    d = comm(pg); e2 = [e for e in d["events"] if e["id"] == sub[0]["id"]][0]
    o2 = [o for o in d["orgs"] if o["name"] == "Hua Hin Makers"]
    ok(e2["status"] == "published" and "submitter" not in e2 and o2 and e2["orgId"] == o2[0]["id"], "Approving lists it and adds the organizer to the communities")
    ok(o2 and "@daoline" in o2[0]["contact"] and o2[0]["status"] == "talking", "...with their contact kept in CloudWAV's private record")

    # members see the listed events in their own Events & Calendar
    role(pg, "partner"); nav(pg, "calendar"); pg.wait_for_timeout(300)
    if pg.locator('[data-cal-view="list"]').count(): pg.click('[data-cal-view="list"]'); pg.wait_for_timeout(300)
    lst = pg.inner_text("#calendarContent")
    ok("Bangkok Entrepreneurs Mixer" in lst and "Community event" in lst and "Hosted by Bangkok Entrepreneurs" in lst, "Partners see community events in Events & Calendar")
    ok(pg.locator(f'[data-cal-event="cal-{ev[0]["id"]}"] [data-cal-edit]').count() == 0, "...read-only")
    b.close()

    # ----- live Supabase: an organizer sends an event in, CloudWAV approves, the public sees it
    if os.path.exists("/usr/lib/postgresql/16/bin/initdb"):
        from pgmock import start_pg, PgSupabase
        OP = {"email": "ops@cloudwav.test", "password": "op-pass-123", "id": "11111111-0000-0000-0000-000000000001"}
        mock = PgSupabase({OP["email"]: {"password": OP["password"], "id": OP["id"]}}, {OP["id"]: {"role": "operator", "entity_id": None, "display_name": "Peter"}}, start_pg())
        b, ctx, v = open_page_supabase(p, mock, "?events=thailand", viewport={"width": 390, "height": 844}); v.wait_for_timeout(900)
        ok("(example)" not in v.inner_text("#publicEventsContent"), "Cloud: the public calendar shows no starter examples")
        v.click("[data-tec-show]"); v.wait_for_timeout(200)
        v.fill("#tecOrg", "Bangkok AI Builders"); v.fill("#tecTitle", "Agents Night"); v.fill("#tecStart", "2027-03-03T18:00")
        v.fill("#tecLink", "https://lu.ma/agents"); v.fill("#tecName", "Kai"); v.fill("#tecContact", "kai@example.com")
        v.wait_for_timeout(1600); v.click("#tecSubmit"); v.wait_for_timeout(900)
        rows = [r for r in mock.rows_as_operator() if r["collection"] == "communityEvents"]
        ok(v.locator("[data-tec-done]").count() == 1 and len(rows) == 1 and rows[0]["data"]["status"] == "pending" and not rows[0]["is_public"], "Cloud: the event arrives waiting for review")
        b.close()
        b, ctx, op = open_page_supabase(p, mock)
        op.fill("#loginEmail", OP["email"]); op.fill("#loginPassword", OP["password"]); op.click("#loginSubmit"); op.wait_for_timeout(1800)
        nav(op, "operator-community"); op.wait_for_timeout(400)
        ok("Claude Thailand Community" in op.inner_text("#operatorCommunityContent"), "Cloud: the three communities are saved for CloudWAV")
        op.click('[data-co-tab="review"]'); op.wait_for_timeout(200)
        op.click(f'[data-ce-approve="{rows[0]["id"]}"]')
        for _ in range(40):
            if not op.evaluate("CLOUD_PENDING()"): break
            op.wait_for_timeout(150)
        row = [r for r in mock.rows_as_operator() if r["collection"] == "communityEvents"][0]
        ok(row["is_public"] and row["data"]["status"] == "published" and "submitter" not in row["data"], "Cloud: approved and public, without the organizer's contact")
        orgs = [r for r in mock.rows_as_operator() if r["collection"] == "communityOrgs"]
        ok(any(r["data"].get("name") == "Bangkok AI Builders" and "kai@example.com" in r["data"].get("contact", "") and r["readers"] == [] for r in orgs), "Cloud: the organizer's contact is kept privately")
        b.close()
        b, ctx, v = open_page_supabase(p, mock, "?events=thailand"); v.wait_for_timeout(900)
        ok("Agents Night" in v.inner_text("#publicEventsContent") and "Bangkok AI Builders" in v.inner_text("#publicEventsContent"), "Cloud: the public sees the listed event")
        ok("kai@example.com" not in v.content(), "Cloud: ...and never the organizer's contact")
        b.close()
    else:
        print("SKIP cloud part: PostgreSQL 16 not installed")
report()
