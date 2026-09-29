from harness import *
import os, sys, json, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))

with sync_playwright() as p:
    b, pg = open_page(p)
    for r in ["partner", "vendor", "affiliate", "operator"]:
        role(pg, r)
        ok(pg.locator('[data-screen="channels"]:visible').count() == 1, f"'WhatsApp & LINE' in the {r} menu")
    # ----- partner: contact details
    role(pg, "partner"); nav(pg, "channels")
    pg.click('[data-ch-tab="contact"]'); pg.wait_for_timeout(150)
    ok(pg.input_value("#cWhatsApp") == "+66812345678" and pg.input_value("#cLine") == "siamdigital", "Loads my WhatsApp and LINE details")
    pg.fill("#cWhatsApp", "081 234 5678"); pg.click("[data-c-save]"); pg.wait_for_timeout(150)
    ok("country code" in pg.inner_text("#cError"), "Asks for the country code")
    pg.fill("#cWhatsApp", "+66 81 999 0000"); pg.fill("#cLine", "siam.digital"); pg.select_option("#cPreferred", "line"); pg.click("[data-c-save]"); pg.wait_for_timeout(200)
    ok(pg.locator('#chContactForm a[href="https://wa.me/66819990000"]').count() == 1 and pg.locator('#chContactForm a[href="https://line.me/R/ti/p/~siam.digital"]').count() == 1, "Saved: WhatsApp chat and LINE add-friend links")

    # ----- partner: add a Meetup WhatsApp group
    pg.click('[data-ch-tab="groups"]'); pg.wait_for_timeout(150)
    ok("Bangkok MSP Meetup (demo)" in pg.inner_text("#channelsContent"), "My groups lists my existing group")
    pg.click("[data-g-new]"); pg.wait_for_timeout(150)
    pg.fill("#gName", "Chiang Mai Tech Meetup"); pg.select_option("#gPlatform", "line-group")
    pg.fill("#gLink", "https://chat.whatsapp.com/ABC"); pg.click("[data-g-save]"); pg.wait_for_timeout(150)
    ok("doesn't look like a LINE group link" in pg.inner_text("#gError"), "Checks the link matches the platform")
    pg.select_option("#gPlatform", "whatsapp-group"); pg.fill("#gMembers", "~120"); pg.fill("#gCity", "Chiang Mai"); pg.fill("#gDesc", "Monthly tech meetup")
    pg.set_input_files("#gQrFile", os.path.join(HERE, "_qr_sample.png")); pg.wait_for_timeout(300)
    pg.click("[data-g-save]"); pg.wait_for_timeout(200)
    ok(pg.locator('[data-ch-group]').filter(has_text="Chiang Mai Tech Meetup").count() == 1, "Group added")
    ok(pg.locator('[data-ch-group]').filter(has_text="Chiang Mai Tech Meetup").locator(".aff-qr img").count() == 1, "With its QR code")

    # ----- share & broadcast
    pg.click('[data-ch-tab="share"]'); pg.wait_for_timeout(150)
    pg.select_option("#chTemplate", "event"); pg.wait_for_timeout(200)
    txt = pg.input_value("#chText")
    ok(txt.startswith("📅 Event update") and "Siam Digital MSP" in txt, "Event template fills the message")
    pg.fill("#chText", "📅 Meetup Thursday 7pm at True Digital Park -- RSVP: https://meetup.example/123")
    row = pg.locator('[data-ch-group-row]').filter(has_text="Chiang Mai Tech Meetup")
    href = row.locator('a[data-ch-app="whatsapp"]').get_attribute("href")
    ok(href.startswith("https://wa.me/?text=") and "True Digital Park" in urllib.parse.unquote(href), "WhatsApp share link carries the message")
    ok(urllib.parse.unquote(pg.get_attribute("#chLineAny", "href")).startswith("https://line.me/R/share?text=📅 Meetup"), "LINE share link carries the message")
    ctx = pg.context
    with ctx.expect_page() as newp:
        row.locator('a[data-ch-app="whatsapp"]').click()
    newp.value.close(); pg.wait_for_timeout(200)
    ok("Chiang Mai Tech Meetup" in pg.inner_text("#channelsContent") and "last shared" in row.inner_text(), "Sharing is logged per group")
    person = pg.locator('[data-ch-person="vendor:intelsense"]')
    ok(person.count() == 1 and urllib.parse.unquote(person.locator('a[data-ch-app="whatsapp"]').get_attribute("href")).startswith("https://wa.me/8801711000000?text=📅 Meetup"), "Send to a person: WhatsApp chat with the message")

    # ----- another role sees the group in the directory, and the contact buttons
    role(pg, "vendor"); nav(pg, "channels"); pg.click('[data-ch-tab="directory"]'); pg.wait_for_timeout(150)
    d = pg.inner_text("#chDirectoryGrid")
    ok("Chiang Mai Tech Meetup" in d and "Bangkok MSP Meetup" in d and "Intelsense Partners TH" not in d, "Directory shows other members' listed groups (not my own)")
    pg.click('[data-ch-dir-app="line"]'); pg.wait_for_timeout(150)
    ok("Chiang Mai Tech Meetup" not in pg.inner_text("#chDirectoryGrid"), "Filter by WhatsApp / LINE")
    pg.click('[data-ch-dir-app=""]'); pg.fill("#chDirSearch", "chiang"); pg.wait_for_timeout(200)
    ok(pg.locator("#chDirectoryGrid [data-ch-group]").count() == 1 and pg.locator("#chDirectoryGrid a:has-text('Join group')").get_attribute("href") == "https://chat.whatsapp.com/ABC", "Search + Join group link")
    nav(pg, "partner-messages"); pg.wait_for_timeout(200)
    pg.locator("#msgList [data-open-convo]").filter(has_text="Siam Digital").first.click(); pg.wait_for_timeout(200)
    ok(pg.locator('#msgThreadHeader [data-contact-wa="partner:siam-digital"]').count() == 1 and pg.locator('#msgThreadHeader [data-contact-line="partner:siam-digital"]').count() == 1, "Messages: WhatsApp / LINE buttons for the other person")
    # vendor profile shows the vendor's community group; partner profile shows contact buttons
    role(pg, "partner"); nav(pg, "vendor-network"); pg.locator('[data-view-vendor="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    ok(pg.locator('[data-vendor-groups="intelsense"] a').count() == 1 and pg.locator('[data-contact-buttons="vendor:intelsense"]').count() == 1, "Vendor profile: community group + WhatsApp/LINE buttons")
    # share from the Shop
    nav(pg, "shop"); pg.click('[data-shop-card="shop-smm-101"] [data-shop-view]'); pg.wait_for_timeout(250)
    pg.click("[data-share-channels]"); pg.wait_for_timeout(250)
    ok(visible_screen(pg) == ["scr-channels"] and "Social Media Marketing 101" in pg.input_value("#chText"), "Shop product: 'Share on WhatsApp / LINE' opens the composer prefilled")
    # hide contact
    nav(pg, "channels"); pg.click('[data-ch-tab="contact"]'); pg.uncheck("#cShow"); pg.click("[data-c-save]"); pg.wait_for_timeout(150)
    role(pg, "vendor"); nav(pg, "channels")
    ok(pg.locator('[data-ch-person="partner:siam-digital"]').count() == 0, "Hidden contact details aren't offered to others")
    # persists
    pg.reload(); pg.wait_for_timeout(700); role(pg, "partner"); nav(pg, "channels"); pg.click('[data-ch-tab="groups"]'); pg.wait_for_timeout(150)
    ok("Chiang Mai Tech Meetup" in pg.inner_text("#channelsContent"), "Groups persist")
    b.close()

# ----- signed in: stored in Supabase with the right access
if os.path.exists("/usr/lib/postgresql/16/bin/initdb"):
    from pgmock import start_pg, stop_pg, PgSupabase
    USERS = {"cto@cloudwavconsulting.com": {"password": "op-pass-123", "id": "11111111-0000-0000-0000-000000000001"},
             "partner@siamdigital.test": {"password": "part-pass-123", "id": "11111111-0000-0000-0000-000000000003"},
             "partner@gulfcoast.test": {"password": "gulf-pass-123", "id": "11111111-0000-0000-0000-000000000004"}}
    PORTAL = {USERS["cto@cloudwavconsulting.com"]["id"]: {"role": "operator", "entity_id": None, "display_name": "Peter Phelan"},
              USERS["partner@siamdigital.test"]["id"]: {"role": "partner", "entity_id": "siam-digital", "display_name": "Somchai"},
              USERS["partner@gulfcoast.test"]["id"]: {"role": "partner", "entity_id": "gulf-coast", "display_name": "Gulf"}}
    mock = PgSupabase(USERS, PORTAL, start_pg())
    def rows(c): return [r for r in mock.rows_as_operator() if r["collection"] == c]
    def settle(pg):
        for _ in range(40):
            if not pg.evaluate("CLOUD_PENDING()"): return True
            pg.wait_for_timeout(150)
    with sync_playwright() as p:
        b, ctx, pg = open_page_supabase(p, mock)
        pg.fill("#loginEmail", "cto@cloudwavconsulting.com"); pg.fill("#loginPassword", "op-pass-123"); pg.click("#loginSubmit"); pg.wait_for_timeout(2500); settle(pg); b.close()
        b, ctx, pg = open_page_supabase(p, mock)
        pg.fill("#loginEmail", "partner@siamdigital.test"); pg.fill("#loginPassword", "part-pass-123"); pg.click("#loginSubmit"); pg.wait_for_timeout(2500)
        nav(pg, "channels")
        ok("Bangkok MSP Meetup (demo)" not in pg.inner_text("#channelsContent"), "Signed in: no demo groups")
        pg.click('[data-ch-tab="contact"]'); pg.fill("#cWhatsApp", "+66 81 111 2222"); pg.fill("#cLine", "somchai"); pg.click("[data-c-save]"); pg.wait_for_timeout(200)
        pg.click('[data-ch-tab="groups"]'); pg.click("[data-g-new]"); pg.fill("#gName", "BKK MSP Meetup"); pg.fill("#gLink", "https://chat.whatsapp.com/XYZ"); pg.click("[data-g-save]"); pg.wait_for_timeout(200)
        pg.click("[data-g-new]"); pg.fill("#gName", "Private team group"); pg.fill("#gLink", "https://chat.whatsapp.com/PRIV"); pg.uncheck("#gListed"); pg.click("[data-g-save]"); pg.wait_for_timeout(800); settle(pg)
        c = rows("contactChannels"); g = {r["data"]["name"]: r for r in rows("socialGroups")}
        ok(len(c) == 1 and c[0]["id"] == "partner:siam-digital" and c[0]["readers"] == ["*"], "Contact details stored, visible to members")
        ok(g["BKK MSP Meetup"]["readers"] == ["*"] and g["Private team group"]["readers"] == ["partner:siam-digital"], "Listed group visible to members; unlisted one private")
        b.close()
        gid = USERS["partner@gulfcoast.test"]["id"]
        seen = [r["data"]["name"] for r in mock.sql("select data from portal_records where collection='socialGroups'", uid=gid)]
        ok("BKK MSP Meetup" in seen and "Private team group" not in seen, "Another partner sees only the listed group")
        try:
            mock.sql("insert into portal_records(collection,id,data,readers,writers) values ('contactChannels','partner:siam-digital',%s,'{*}','{partner:gulf-coast}') on conflict (collection,id) do update set data=excluded.data", (json.dumps({"id": "partner:siam-digital", "whatsapp": "+10000000000"}),), fetch=False, uid=gid); refused = False
        except Exception: refused = True
        ok(refused, "Nobody can change someone else's WhatsApp number")
        try:
            mock.sql("insert into portal_records(collection,id,data,readers,writers) values ('socialGroups','fake',%s,'{*}','{partner:gulf-coast}')", (json.dumps({"id": "fake", "ownerKey": "partner:siam-digital", "name": "Fake"}),), fetch=False, uid=gid); refused = False
        except Exception: refused = True
        ok(refused, "...or post a group in someone else's name")
    stop_pg()
    ok(not mock.errors, "No requests refused during normal use: " + "; ".join(mock.errors[:3]))
report()
