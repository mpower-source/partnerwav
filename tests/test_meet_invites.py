from harness import *
import json, datetime

# Intro Meetings: CloudWAV invites a company to meet PartnerWAV. The email comes from partnerwav@gmail.com with a
# Google Meet link (made by the meet-invite server function); templates are editable and filled in per company.
def settings(pg):
    d = json.loads(pg.evaluate("localStorage.getItem('partnerWAV_softwareReferrals')") or "{}")
    return {r["id"]: r for r in d.get("operatorSettings", [])}
def sent(pg):
    return json.loads(pg.evaluate("localStorage.getItem('partnerWAV_meetInvites')") or "[]")

day = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
with sync_playwright() as p:
    b, pg = open_page(p)
    role(pg, "partner")
    ok(not in_menu(pg, "operator-meet-invites"), "Partners don't see Intro Meetings")
    role(pg, "operator")
    ok(in_menu(pg, "operator-meet-invites"), "CloudWAV has Intro Meetings")
    ok(pg.get_attribute('#navOperator [data-screen="operator-meet-invites"] .ic', "data-pw-icon") == "video", "Menu: line icon")
    nav(pg, "operator-meet-invites"); pg.wait_for_timeout(300)
    ok(pg.input_value("#meetSubject") == "Introducing PartnerWAV to {{company}}" and "{{meet_link}}" in pg.input_value("#meetBody"), "The intro template is ready to use")

    pg.fill("#meetCompany", "Acme Software"); pg.fill("#meetName", "Ann Lee"); pg.fill("#meetEmail", "ann@acme.example")
    pg.fill("#meetDate", day); pg.fill("#meetTime", "10:00"); pg.select_option("#meetTz", "America/New_York"); pg.select_option("#meetDur", "30")
    pg.wait_for_timeout(200)
    pv = pg.inner_text("[data-meet-preview]")
    ok("Introducing PartnerWAV to Acme Software" in pv and "Hi Ann," in pv and "10:00 AM" in pv and ("EDT" in pv or "EST" in pv) and "30 minutes" in pv, "The preview fills in the company, name, date and time")
    ok("google meet link" in pv.lower() and "{{" not in pv, "...and marks where the Meet link goes " + str([l for l in pv.splitlines() if "{{" in l]))

    # their logo: white artwork on a see-through background gets a dark chip so it doesn't vanish
    from PIL import Image, ImageDraw
    import tempfile, os
    im = Image.new("RGBA", (600, 200), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse((40, 60, 120, 140), fill=(110, 220, 200, 255)); d.rectangle((150, 70, 420, 130), fill=(245, 245, 245, 255)); d.rectangle((440, 70, 540, 130), fill=(110, 220, 200, 255))
    logo_path = os.path.join(tempfile.mkdtemp(), "client-logo.png"); im.save(logo_path)
    pg.set_input_files("#meetLogoFile", logo_path); pg.wait_for_timeout(600)
    ok(pg.locator("[data-meet-logo]").count() == 1 and pg.get_attribute('[data-meet-logo-bg="#231f3a"]', "aria-pressed") == "true", "A light logo on a clear background is put on a dark chip")
    size = pg.evaluate("(() => { const i = document.querySelector('[data-meet-logo] img'); return [i.naturalWidth, i.naturalHeight]; })()")
    ok(size[0] <= 400 and size[1] <= 80 and abs(size[0] / size[1] - 501 / 81) < 0.2, "The logo is trimmed to its artwork and made small for email: " + str(size))
    ok(pg.locator("[data-meet-preview-logo] img").count() == 1, "The preview shows it next to PartnerWAV")
    pg.click('[data-meet-logo-bg="#ffffff"]'); pg.wait_for_timeout(150)
    ok("255, 255, 255" in pg.evaluate("getComputedStyle(document.querySelector('[data-meet-preview-logo]')).backgroundColor"), "The logo background can be changed")
    pg.click('[data-meet-logo-bg="#231f3a"]'); pg.wait_for_timeout(150)

    # customise this one invite
    pg.fill("#meetBody", pg.input_value("#meetBody").replace("Best regards", "Looking forward to it")); pg.wait_for_timeout(150)
    ok("Looking forward to it" in pg.inner_text("[data-meet-preview]"), "The message can be changed for this company")

    # checks before sending
    pg.fill("#meetEmail", "not-an-email"); pg.click("[data-meet-send]"); pg.wait_for_timeout(150)
    ok(not pg.locator("#meetErr").is_hidden() and "email" in pg.inner_text("#meetErr"), "A bad email address is caught")
    pg.fill("#meetEmail", "ann@acme.example")
    body = pg.input_value("#meetBody"); pg.fill("#meetBody", body.replace("{{meet_link}}", "")); pg.click("[data-meet-send]"); pg.wait_for_timeout(150)
    ok("{{meet_link}}" in pg.inner_text("#meetErr"), "The Meet link field can't be dropped")
    pg.fill("#meetBody", body)

    # demo: nothing is really sent
    pg.click("[data-meet-test]"); pg.wait_for_timeout(250)
    ok("Demo: nothing was sent" in pg.inner_text("#meetMsg"), "Without Google connected, it says nothing was sent")
    s = sent(pg)
    ok(len(s) == 1 and s[0]["status"] == "demo" and s[0]["email"] == "partnerwav@gmail.com", "A test goes only to partnerwav@gmail.com")
    pg.click("[data-meet-send]"); pg.wait_for_timeout(250)
    s = sent(pg)
    ok(s[1].get("logo") and s[1]["logo"]["bg"] == "#231f3a" and s[1]["logo"]["dataUrl"].startswith("data:image/png;base64,"), "The logo is kept with the invite")
    ok(len(s) == 2 and s[1]["email"] == "ann@acme.example" and s[1]["company"] == "Acme Software" and s[1]["timeZone"] == "America/New_York" and s[1]["durationMin"] == 30, "The invite is logged")
    start = datetime.datetime.fromisoformat(s[1]["start"].replace("Z", "+00:00"))
    ok(start.hour in (14, 15) and start.minute == 0, "10:00 New York time is saved as the right moment (UTC " + s[1]["start"] + ")")

    pg.click('[data-meet-tab="sent"]'); pg.wait_for_timeout(200)
    ok(pg.locator("[data-meet-row]").count() == 2 and "Acme Software" in pg.inner_text("#meetContent"), "Sent tab lists the invites")
    pg.click(f'[data-meet-again="{s[1]["id"]}"]'); pg.wait_for_timeout(200)
    ok(pg.input_value("#meetCompany") == "Acme Software" and pg.input_value("#meetEmail") == "ann@acme.example", "Invite again fills the form")
    ok(pg.locator("[data-meet-preview-logo] img").count() == 1, "...including their logo")
    pg.click("[data-meet-logo-remove]"); pg.wait_for_timeout(150)
    ok(pg.locator("[data-meet-preview-logo]").count() == 0, "The logo can be removed")

    # the same message on WhatsApp and LINE
    pg.click('[data-meet-tab="new"]'); pg.wait_for_timeout(200)
    pg.fill("#meetCompany", "Siam Cloud"); pg.fill("#meetName", "Nok Chai"); pg.fill("#meetEmail", "nok@siamcloud.example")
    pg.fill("#meetDate", day); pg.fill("#meetTime", "14:00"); pg.select_option("#meetTz", "Asia/Bangkok")
    pg.check("#meetViaWa"); pg.check("#meetViaLine"); pg.click("[data-meet-send]"); pg.wait_for_timeout(200)
    ok("WhatsApp number" in pg.inner_text("#meetErr"), "WhatsApp needs their number")
    pg.fill("#meetWa", "+66 81 234 5678"); pg.fill("#meetLine", "nokchai"); pg.click("[data-meet-send]"); pg.wait_for_timeout(300)
    ok(pg.locator("[data-meet-just]").count() == 1, "After sending, it offers WhatsApp and LINE straight away")
    rec = [m for m in sent(pg) if m["company"] == "Siam Cloud"][0]
    wa = pg.locator(f'[data-meet-just] [data-meet-wa="{rec["id"]}"]').get_attribute("href")
    ln = pg.locator(f'[data-meet-just] [data-meet-line="{rec["id"]}"]').get_attribute("href")
    from urllib.parse import unquote
    ok(wa.startswith("https://wa.me/66812345678?text=") and "Hi Nok," in unquote(wa) and "Siam Cloud" in unquote(wa) and "2:00 PM" in unquote(wa), "WhatsApp opens their chat with the same message: " + unquote(wa)[:90])
    ok(ln.startswith("https://line.me/R/share?text=") and "Hi Nok," in unquote(ln) and "nokchai" in pg.inner_text("[data-meet-just]"), "LINE opens with the same message, to pick their chat")
    ok("Google Meet link" in unquote(wa), "In demo the Meet link spot is marked (the real link goes in once Google is connected)")
    pg.locator(f'[data-meet-just] [data-meet-wa="{rec["id"]}"]').evaluate("a => { a.removeAttribute('target'); a.addEventListener('click', e => e.preventDefault()); }")
    pg.click(f'[data-meet-just] [data-meet-wa="{rec["id"]}"]'); pg.wait_for_timeout(300)
    ok([m for m in sent(pg) if m["company"] == "Siam Cloud"][0].get("waAt"), "Opening WhatsApp is noted on the invite")

    # WhatsApp only: no Google needed, a pasted Meet link and a short message
    pg.click('[data-meet-tab="new"]'); pg.wait_for_timeout(200)
    pg.click('[data-meet-mode="whatsapp"]'); pg.wait_for_timeout(200)
    ok(pg.locator("#meetSubject").count() == 0 and pg.locator("#meetWaBody").count() == 1 and pg.locator("[data-meet-wa-note]").count() == 1, "WhatsApp only: a short message instead of the email")
    pg.fill("#meetCompany", "CoolOn"); pg.fill("#meetName", "Alex Tan"); pg.fill("#meetDate", day); pg.fill("#meetTime", "14:00"); pg.select_option("#meetTz", "America/New_York")
    pg.click("[data-meet-send]"); pg.wait_for_timeout(150)
    e = pg.inner_text("#meetErr")
    ok("WhatsApp number" in e and "Meet link" in e, "It needs their number and a Meet link")
    ok(pg.get_attribute("[data-meet-new-link]", "href") == "https://meet.google.com/new", "A button makes a new Meet link")
    pg.fill("#meetWa", "+1 (212) 555-0147"); pg.fill("#meetLink", "https://meet.google.com/xyz-abcd-efg"); pg.wait_for_timeout(150)
    pv = pg.inner_text("[data-meet-wa-preview]")
    ok("Hi Alex," in pv and "CoolOn" in pv and "2:00 PM" in pv and "https://meet.google.com/xyz-abcd-efg" in pv, "The WhatsApp preview fills in, with the pasted Meet link")
    ok(len(pv) < 450, "The WhatsApp message is short (" + str(len(pv)) + " characters)")
    pg.locator("[data-meet-gcal]").evaluate("a => a.addEventListener('click', e => e.preventDefault())")
    pg.click("[data-meet-gcal]"); pg.wait_for_timeout(100)
    gh = pg.get_attribute("[data-meet-gcal]", "href")
    ok(gh.startswith("https://calendar.google.com/calendar/r/eventedit?text=PartnerWAV%20intro%3A%20CoolOn&dates=") and ("T180000Z" in gh or "T190000Z" in gh), "Google Calendar opens a filled-in event to add a Meet link to")
    pg.evaluate("window.__opened = []; window.open = (u) => { window.__opened.push(u); return null; }")
    pg.click("[data-meet-send]"); pg.wait_for_timeout(300)
    opened = [u for u in pg.evaluate("window.__opened") if u]
    from urllib.parse import unquote as uq
    ok(len(opened) == 1 and opened[0].startswith("https://wa.me/12125550147?text=") and "https://meet.google.com/xyz-abcd-efg" in uq(opened[0]) and "Hi Alex," in uq(opened[0]), "WhatsApp opens their chat with the short message")
    w = [m for m in sent(pg) if m.get("channel") == "whatsapp"]
    ok(w and w[0]["status"] == "whatsapp" and w[0]["meetLink"] == "https://meet.google.com/xyz-abcd-efg" and w[0]["company"] == "CoolOn", "It's logged as a WhatsApp invite")
    row = pg.locator(f'[data-meet-row="{w[0]["id"]}"]')
    ok(row.count() == 1 and "whatsapp" in row.inner_text().lower() and uq(row.locator("[data-meet-wa]").get_attribute("href")).endswith("https://partnerwav.com"), "Sent tab: WhatsApp again uses the same short message")
    pg.click(f'[data-meet-again="{w[0]["id"]}"]'); pg.wait_for_timeout(200)
    ok(pg.get_attribute('[data-meet-mode="whatsapp"]', "aria-pressed") == "true" and pg.input_value("#meetWa") == "+1 (212) 555-0147", "Invite again stays on WhatsApp")
    pg.click('[data-meet-mode="email"]'); pg.wait_for_timeout(200)
    ok(pg.input_value("#meetCompany") == "CoolOn" and pg.locator("#meetSubject").count() == 1, "Switching back to email keeps what's typed")

    # templates
    pg.click('[data-meet-tab="templates"]'); pg.wait_for_timeout(200)
    pg.fill("#meetSender", "Peter at PartnerWAV"); pg.click("[data-meet-sender]"); pg.wait_for_timeout(200)
    ok(settings(pg)["meetTemplates"]["senderName"] == "Peter at PartnerWAV", "The sender name is saved")
    pg.fill("#meetWaTpl", "Hi {{first_name}}, quick intro to PartnerWAV. Meet: {{meet_link}}"); pg.click("[data-meet-wa-save]"); pg.wait_for_timeout(200)
    ok(settings(pg)["meetTemplates"]["waBody"] == "Hi {{first_name}}, quick intro to PartnerWAV. Meet: {{meet_link}}", "The short WhatsApp message can be edited")
    pg.click("[data-meet-tpl-new]"); pg.wait_for_timeout(200)
    pg.fill("#meetTplName", "Vendor intro"); pg.fill("#meetTplSubject", "{{company}} on PartnerWAV"); pg.fill("#meetTplBody", "Hi {{first_name}}, no link here")
    pg.click("[data-meet-tpl-save]"); pg.wait_for_timeout(150)
    ok("{{meet_link}}" in pg.inner_text("#meetTplErr"), "A template must keep the Meet link")
    pg.fill("#meetTplBody", "Hi {{first_name}},\n\nJoin us: {{meet_link}}\n\n{{sender_name}}"); pg.click("[data-meet-tpl-save]"); pg.wait_for_timeout(200)
    tpls = settings(pg)["meetTemplates"]["templates"]
    ok(len(tpls) == 2 and tpls[1]["name"] == "Vendor intro", "A second template is saved")
    pg.click('[data-meet-tab="new"]'); pg.wait_for_timeout(200)
    pg.select_option("#meetTplSel", tpls[1]["id"]); pg.wait_for_timeout(200)
    ok(pg.input_value("#meetSubject") == "{{company}} on PartnerWAV" and "Peter at PartnerWAV" in pg.inner_text("[data-meet-preview]"), "Choosing a template fills the email, signed with the sender name")

    # Google connection tab: setup steps, no keys in the page
    pg.click('[data-meet-tab="google"]'); pg.wait_for_timeout(200)
    g = pg.inner_text("#meetContent")
    ok("partnerwav@gmail.com" in g and "Gmail API" in g and "gmail.send" in g and "calendar.events" in g and "Publish app" in g, "Setup steps for the Google account are there")
    pg.click("[data-meet-check]"); pg.wait_for_timeout(150)
    ok("can't be checked" in pg.inner_text("#meetCheckMsg"), "Check the connection explains itself in demo")
    html = pg.content()
    ok("GOCSPX" not in html and "refresh_token" not in html, "No Google keys in the page")

    pg.set_viewport_size({"width": 390, "height": 844}); pg.click('[data-meet-tab="new"]'); pg.wait_for_timeout(300)
    ok(pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0, "Fits a phone")
    b.close()
# --- signed in as CloudWAV: the meet-invite server function sends it
class MeetMock(MockSupabase):
    def __init__(self, *a, fail=False):
        super().__init__(*a); self.fail = fail; self.meet_calls = []
    def handle(self, route):
        req = route.request
        if "/functions/v1/meet-invite" in req.url and req.method == "POST":
            body = json.loads(req.post_data or "{}"); self.meet_calls.append(body)
            h = {"access-control-allow-origin": "*"}
            if body.get("action") == "status":
                return route.fulfill(status=200, content_type="application/json", headers=h, body=json.dumps({"ok": True, "sender": "partnerwav@gmail.com", "missing": []}))
            if self.fail:
                return route.fulfill(status=502, content_type="application/json", headers=h, body=json.dumps({"error": "Google refused the saved sign-in (refresh token)."}))
            return route.fulfill(status=200, content_type="application/json", headers=h, body=json.dumps({"ok": True, "test": body.get("test"), "meetLink": "https://meet.google.com/abc-defg-hij",
                "eventId": "ev1", "eventLink": "https://www.google.com/calendar/event?eid=ev1", "messageId": "m1", "calendarInvite": body.get("addGuests")}))
        return super().handle(route)
OPID = "11111111-0000-0000-0000-000000000009"
for fail in (False, True):
    with sync_playwright() as p:
        mock = MeetMock({"ops@cloudwav.test": {"password": "ops-pass-123", "id": OPID}}, {OPID: {"role": "operator", "entity_id": None, "display_name": "Ops"}}, fail=fail)
        b, ctx, pg = open_page_supabase(p, mock)
        pg.fill("#loginEmail", "ops@cloudwav.test"); pg.fill("#loginPassword", "ops-pass-123"); pg.click("#loginSubmit"); pg.wait_for_timeout(1500)
        nav(pg, "operator-meet-invites"); pg.wait_for_timeout(300)
        pg.fill("#meetCompany", "Acme Software"); pg.fill("#meetName", "Ann Lee"); pg.fill("#meetEmail", "ann@acme.example"); pg.fill("#meetGuests", "cto@acme.example")
        pg.fill("#meetDate", day); pg.fill("#meetTime", "09:30"); pg.select_option("#meetTz", "Asia/Bangkok")
        if not fail:
            pg.click("[data-meet-test]"); pg.wait_for_timeout(800)
            t0 = mock.meet_calls[-1]
            ok(t0["test"] is True and "Test sent" in pg.inner_text("#meetMsg"), "Signed in: the test goes through the meet-invite function")
            pg.set_input_files("#meetLogoFile", logo_path); pg.wait_for_timeout(600)
            pg.fill("#meetWa", "+66812345678"); pg.check("#meetViaWa")
            pg.click("[data-meet-send]"); pg.wait_for_timeout(900)
            c = mock.meet_calls[-1]
            wa = pg.locator("[data-meet-just] [data-meet-wa]").get_attribute("href")
            from urllib.parse import unquote
            ok("https://meet.google.com/abc-defg-hij" in unquote(wa), "Signed in: the WhatsApp message carries the real Meet link")
            ok(c["test"] is False and c["to"] == [{"email": "ann@acme.example", "name": "Ann Lee"}] and c["guests"] == [{"email": "cto@acme.example"}] and c["timeZone"] == "Asia/Bangkok" and c["addGuests"] is True, "Signed in: the invite carries the people, time zone and calendar choice")
            ok("{{meet_link}}" in c["body"] and "Acme Software" in c["subject"] and "{{company}}" not in c["body"] and "9:30 AM" in c["body"], "...with everything filled in except the Meet link, which the server adds")
            ok(c["start"].startswith(day + "T02:30"), "9:30 Bangkok time is 02:30 UTC: " + c["start"])
            ok(c.get("logo") and c["logo"]["type"] == "image/png" and c["logo"]["bg"] == "#231f3a" and c["logo"]["company"] == "Acme Software" and len(c["logo"]["data"]) > 100 and not c["logo"]["data"].startswith("data:"), "Signed in: the logo goes to the server as a small PNG")
            ok("[Google Meet link]" not in pg.inner_text("#meetContent"), "Signed in, nothing is left as a placeholder")
            pg.wait_for_timeout(300)
            ok(pg.locator("[data-meet-row]").count() == 2 and "https://meet.google.com/abc-defg-hij" in pg.content(), "Sent tab shows it with the Meet link")
            pg.click('[data-meet-tab="new"]'); pg.wait_for_timeout(200)
            pg.fill("#meetCompany", "CoolOn"); pg.fill("#meetName", "Alex"); pg.fill("#meetEmail", "alex@coolon.example"); pg.fill("#meetDate", day); pg.fill("#meetTime", "11:00")
            pg.fill("#meetLink", "https://meet.google.com/own-link-abc"); pg.click("[data-meet-send]"); pg.wait_for_timeout(900)
            c2 = mock.meet_calls[-1]
            ok(c2["meetLink"] == "https://meet.google.com/own-link-abc" and "https://meet.google.com/own-link-abc" in c2["body"], "Signed in: a pasted Meet link is sent in the email instead of making one")
            pg.click('[data-meet-tab="google"]'); pg.wait_for_timeout(200); pg.click("[data-meet-check]"); pg.wait_for_timeout(600)
            ok("Connected: invites go out from partnerwav@gmail.com" in pg.inner_text("#meetCheckMsg"), "Check the connection reports the Gmail account")
        else:
            pg.click("[data-meet-send]"); pg.wait_for_timeout(900)
            ok("refresh token" in pg.inner_text("#meetMsg"), "A Google problem is shown in plain words")
        b.close()
report()
