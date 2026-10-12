from harness import *
import os, sys, json

# Event Connect: CloudWAV makes a page for an event, shows its QR code, and people it meets leave
# their name, company and WhatsApp number or LINE ID. Only CloudWAV sees who connected.
def ev_data(pg, key):
    return json.loads(pg.evaluate("localStorage.getItem('partnerWAV_eventConnect')") or "{}").get(key, [])

QRJS = qrcode_js()
with sync_playwright() as p:
    # ----- demo: CloudWAV creates an event page
    b, pg = open_page(p)
    pg.context.route("**/cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=QRJS, headers={"access-control-allow-origin": "*"}))
    pg.reload(); pg.wait_for_timeout(600)
    role(pg, "operator")
    ok(in_menu(pg, "operator-events"), "Event Connect is in CloudWAV's menu")
    nav(pg, "operator-events"); pg.wait_for_timeout(200)
    pg.click("[data-ev-new]"); pg.fill("#evName", "Bangkok Tech Meetup, 14 Nov"); pg.click("[data-ev-create]"); pg.wait_for_timeout(500)
    pages = ev_data(pg, "pages")
    ev = [e for e in pages if e["name"] == "Bangkok Tech Meetup, 14 Nov"]
    ok(ev and ev[0]["status"] == "published" and ev[0]["intro"], "The page is created, live, with the short overview filled in")
    eid = ev[0]["id"]
    card = pg.locator(f'[data-ev-row="{eid}"]')
    ok("?meet=" + eid in card.locator("input").input_value(), "Its link is shown")
    ok(card.locator(".ev-qr canvas, .ev-qr img").count() >= 1, "...with a QR code to print or show")

    # ----- a visitor scans the QR code (phone size)
    vis = pg.context.new_page(); vis.set_viewport_size({"width": 390, "height": 844})
    vis.goto(URL + "?demo=1&meet=" + eid); vis.wait_for_timeout(700)
    ok(vis.locator("#meetForm").count() == 1 and "Bangkok Tech Meetup" in vis.text_content("#meetForm"), "The visitor sees the event's connect page")
    ok(not vis.locator(".sidebar:visible, nav.navgroup:visible, .role-btn:visible").count(), "No portal menu or role switcher")
    fields = vis.evaluate("[...document.querySelectorAll('#meetForm input:not([type=hidden])')].filter(i => i.offsetParent && i.getBoundingClientRect().width > 2 && !/^hp_/.test(i.id)).map(i => i.id)")
    ok(fields == ["meetName", "meetCompany", "meetContact"], "Only three boxes to fill in: " + str(fields))
    ok(vis.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0, "Fits a phone with no sideways scrolling")
    ok(vis.evaluate("document.querySelector('#meetSubmit').getBoundingClientRect().bottom") < 844 * 1.2, "The Connect button is close to the first screen")
    vis.click("#meetSubmit"); vis.wait_for_timeout(200)
    ok(not vis.locator("#meetError").is_hidden() and "name" in vis.inner_text("#meetError").lower(), "An empty form asks for the name and number")
    vis.click('[data-meet-interest="partner"]'); vis.click('[data-meet-interest="investor"]')
    vis.fill("#meetName", "=HYPERLINK(\"http://x.test\")"); vis.fill("#meetCompany", "Riverside Hotel"); vis.fill("#meetContact", "+66 81 234 5678")
    vis.wait_for_timeout(1600); vis.click("#meetSubmit"); vis.wait_for_timeout(500)
    ok(vis.locator("[data-meet-done]").count() == 1, "A thank-you shows after tapping Connect")
    con = ev_data(vis, "connections")
    ok(len(con) == 1 and con[0]["channel"] == "whatsapp" and con[0]["contact"] == "+66 81 234 5678" and sorted(con[0]["interest"]) == ["investor", "partner"]
       and con[0]["eventId"] == eid and con[0]["status"] == "new", "The connection is saved with the channel, number and interests")

    # second visitor uses LINE, no company
    vis.goto(URL + "?demo=1&meet=" + eid); vis.wait_for_timeout(700)
    vis.click('[data-meet-channel="line"]')
    ok(vis.get_attribute("#meetContact", "placeholder") == "Your LINE ID", "Switching to LINE asks for a LINE ID")
    vis.fill("#meetName", "Ken Tanaka"); vis.fill("#meetContact", "not a valid id!"); vis.wait_for_timeout(1600); vis.click("#meetSubmit"); vis.wait_for_timeout(200)
    ok("LINE ID" in vis.inner_text("#meetError"), "A bad LINE ID is caught")
    vis.fill("#meetContact", "@kentanaka"); vis.click("#meetSubmit"); vis.wait_for_timeout(500)
    ok(vis.locator("[data-meet-done]").count() == 1 and len(ev_data(vis, "connections")) == 2, "LINE connections go through too")
    vis.close()

    # ----- CloudWAV sees both, with a button to message each one
    pg.reload(); pg.wait_for_timeout(600); role(pg, "operator"); nav(pg, "operator-events"); pg.wait_for_timeout(300)
    rows = pg.locator("#evPeople tbody tr")
    ok(rows.count() == 2, "Both people are listed")
    wa = pg.locator("#evPeople a.meet-wa").first.get_attribute("href")
    ln = pg.locator("#evPeople a.meet-line").first.get_attribute("href")
    ok(wa.startswith("https://wa.me/66812345678"), "WhatsApp button opens a chat with them: " + wa[:40])
    ok("line.me" in ln and "kentanaka" in ln, "LINE button opens their LINE: " + ln)
    ok("Partner, Investor" in rows.filter(has_text="Riverside").inner_text() or "Investor, Partner" in rows.filter(has_text="Riverside").inner_text(), "Their interests are shown")
    pg.locator('[data-ev-person] [data-ev-status]').first.click(); pg.wait_for_timeout(200)
    ok(any(c["status"] == "contacted" for c in ev_data(pg, "connections")), "A person can be marked contacted")
    with pg.expect_download() as dl:
        pg.click("[data-ev-csv]")
    csv = open(dl.value.path(), encoding="utf-8-sig").read()
    ok("'=HYPERLINK" in csv and "Riverside Hotel" in csv and "@kentanaka" in csv, "The CSV has everyone, and a formula-like name stays text")

    # ----- pausing the page stops new connections
    pg.click(f'[data-ev-toggle="{eid}"]'); pg.wait_for_timeout(300)
    v2 = pg.context.new_page(); v2.goto(URL + "?demo=1&meet=" + eid); v2.wait_for_timeout(600)
    ok(v2.locator("#meetForm").count() == 0 and "isn't taking connections" in v2.inner_text("#publicMeetContent"), "A paused page takes no connections")
    v2.close(); b.close()

    # ----- live Supabase: an anonymous visitor connects, only CloudWAV can read it
    if os.path.exists("/usr/lib/postgresql/16/bin/initdb"):
        import psycopg2
        from pgmock import start_pg, PgSupabase
        OP = {"email": "ops@cloudwav.test", "password": "op-pass-123", "id": "11111111-0000-0000-0000-000000000001"}
        mock = PgSupabase({OP["email"]: {"password": OP["password"], "id": OP["id"]}}, {OP["id"]: {"role": "operator", "entity_id": None, "display_name": "Peter"}}, start_pg())
        con = psycopg2.connect(mock.dsn); con.autocommit = True; cur = con.cursor()
        cur.execute("alter table public.portal_records disable trigger portal_records_guard")
        cur.execute("insert into public.portal_records (collection, id, data, readers, writers, is_public) values ('eventPages', 'ev-cloud', %s::jsonb, '{EVERYONE}', '{}', true)",
                    (json.dumps({"id": "ev-cloud", "name": "Cloud Expo", "intro": "Short overview", "status": "published"}),))
        cur.execute("alter table public.portal_records enable trigger portal_records_guard"); con.close()
        b, ctx, v = open_page_supabase(p, mock, "?meet=ev-cloud", viewport={"width": 390, "height": 844}); v.wait_for_timeout(800)
        ok(v.locator("#meetForm").count() == 1 and "Cloud Expo" in v.text_content("#meetForm"), "Cloud: the visitor sees the page without signing in")
        v.fill("#meetName", "Ploy S."); v.fill("#meetCompany", "Siam Hotels"); v.fill("#meetContact", "+66 89 000 1111")
        v.wait_for_timeout(1600); v.click("#meetSubmit"); v.wait_for_timeout(900)
        rows = [r for r in mock.rows_as_operator() if r["collection"] == "eventConnections"]
        ok(v.locator("[data-meet-done]").count() == 1 and len(rows) == 1 and rows[0]["data"]["name"] == "Ploy S." and rows[0]["readers"] == [],
           "Cloud: the connection is saved where only CloudWAV can read it")
        ok(rows and rows[0]["id"].startswith("evc-") and len(rows[0]["id"]) > 30, "...through the public submit function")
        b.close()
        b, ctx, op = open_page_supabase(p, mock)
        op.fill("#loginEmail", OP["email"]); op.fill("#loginPassword", OP["password"]); op.click("#loginSubmit"); op.wait_for_timeout(1800)
        nav(op, "operator-events"); op.wait_for_timeout(500)
        ok("Ploy S." in op.inner_text("#operatorEventsContent") and "Cloud Expo" in op.inner_text("#operatorEventsContent"), "Cloud: CloudWAV sees the new connection")
        b.close()
    else:
        print("SKIP cloud part: PostgreSQL 16 not installed")
report()
