from harness import *
import os, sys, json, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))

with sync_playwright() as p:
    b, pg = open_page(p)
    nav(pg, "affiliate-marketplace")
    g = pg.locator("#affiliateMarketplaceGrid")
    txt = g.inner_text()
    ok(all(n in txt for n in ["Xero", "Zoho", "HubSpot", "FreshBooks", "Lovable"]), "Xero, Zoho, HubSpot, FreshBooks and Lovable tiles")
    ok("Northstar" not in txt and "MSP Learning Hub" not in txt, "Northstar PSA and MSP Learning Hub removed")
    ok(g.locator(".program-card").first.get_attribute("data-offer") == "lovable", "Lovable (link + QR ready) is first")
    ok(g.locator("[data-aff-terms]").count() == 0 and "180 days" not in txt and "Impact" not in txt and "15% - 20%" not in txt, "Commission terms are NOT shown on the tiles")
    ok(g.locator("[data-edit-affiliate-offer]").count() == 0, "Partners can't edit offers")
    ok(all(g.locator(f'[data-direct-offer="{i}"] img.entity-logo-img').count() == 1 for i in ["xero", "zoho", "hubspot", "freshbooks"]), "All four have logos")
    ok(g.locator("[data-link-pending]").count() == 4 and g.locator('[data-link-pending="lovable"]').count() == 0, "Link & QR 'coming soon' on the four new tiles, not on Lovable")
    ok(g.locator('[data-manage-affiliate="xero"]').count() == 1, "Xero enrollment still works")

    # operator: edit straight from the tile, before anyone enrolls
    role(pg, "operator"); nav(pg, "affiliate-marketplace")
    hs = pg.locator('#affiliateMarketplaceGrid [data-direct-offer="hubspot"]')
    ok(hs.locator("[data-aff-terms]").count() == 0 and hs.locator("[data-edit-affiliate-offer]").count() == 1, "Operator tile has 'Edit offer' (terms stay off the tile)")
    hs.locator("[data-edit-affiliate-offer]").click(); pg.wait_for_timeout(300)
    ok(pg.input_value("#aoTermCookie") == "180 days" and pg.input_value("#aoTermNetwork") == "Impact" and pg.locator("#aoLogoPreview img").count() == 1, "Editor shows the commission terms and logo for setup")
    pg.fill("#aoDirectLink", "https://hubspot.sjv.io/example-cloudwav")
    pg.set_input_files("#aoQrFile", os.path.join(HERE, "_qr_sample.png")); pg.wait_for_timeout(300)
    ok(pg.locator("#aoQrPreview img").count() == 1, "QR uploads and previews")
    pg.fill("#aoTermAmount", "30% flat"); pg.click('#affiliateOfferForm button[type=submit]'); pg.wait_for_timeout(300)
    # + Create Offer opens a blank form (not the last edited offer)
    pg.click("#createAffiliateOfferBtn"); pg.wait_for_timeout(300)
    ok(pg.input_value("#aoName") == "" and pg.input_value("#aoTermCookie") == "", "'+ Create Offer' opens a blank form")
    pg.click('#scr-affiliate-offer-editor [data-back-screen="affiliate-marketplace"]'); pg.wait_for_timeout(200)
    role(pg, "partner"); nav(pg, "affiliate-marketplace")
    hs = pg.locator('#affiliateMarketplaceGrid [data-direct-offer="hubspot"]')
    ok(hs.locator(".aff-link-input").input_value() == "https://hubspot.sjv.io/example-cloudwav" and hs.locator("[data-aff-qr] img").count() == 1, "HubSpot tile now shows the link and QR code")
    ok(hs.locator("[data-link-pending]").count() == 0, "'Coming soon' badge gone")
    order = [c.get_attribute("data-offer") for c in pg.locator("#affiliateMarketplaceGrid .program-card").all()]
    ok(order[:2] == ["lovable", "hubspot"], "Offers with a ready link move to the front: " + ",".join(order))

    # ----- vendor adds their own affiliate program
    role(pg, "vendor"); nav(pg, "affiliate-marketplace")
    ok(pg.locator("#createAffiliateOfferBtn").is_visible() and "affiliate program" in pg.inner_text("#createAffiliateOfferBtn"), "Vendors can add their affiliate program")
    ok(pg.locator("[data-edit-affiliate-offer]").count() == 0, "...but can't edit CloudWAV's offers")
    pg.click("#createAffiliateOfferBtn"); pg.wait_for_timeout(300)
    ok(pg.input_value("#aoName") == "Intelsense AI" and pg.locator("#aoVendorNote").is_visible(), "Form starts from the vendor's name and explains the review")
    pg.fill("#aoName", "Intelsense AI Affiliate Program"); pg.fill("#aoDesc", "Refer contact centers to Intelsense and earn on every paid seat -- we handle the demo, sale and onboarding.")
    pg.fill("#aoDirectLink", "https://intelsense.example/affiliates/join")
    pg.fill("#aoTermType", "Recurring (12 months)"); pg.fill("#aoTermAmount", "10%"); pg.fill("#aoTermCookie", "60 days"); pg.fill("#aoTermNetwork", "Direct")
    pg.click('#affiliateOfferForm button[type=submit]'); pg.wait_for_timeout(300)
    card = pg.locator('#affiliateMarketplaceGrid [data-vendor-offer="intelsense"]')
    ok(card.count() == 1, "Vendor sees their new offer")
    mine = pg.locator('#affiliateMarketplaceGrid .program-card').filter(has_text="Intelsense AI Affiliate Program")
    ok("WAITING FOR CLOUDWAV REVIEW" in mine.inner_text().upper() and "10%" not in mine.inner_text(), "Marked as waiting for review; terms not on the tile")
    role(pg, "partner"); nav(pg, "affiliate-marketplace")
    ok("Intelsense AI Affiliate Program" not in pg.inner_text("#affiliateMarketplaceGrid"), "Partners don't see it before review")
    role(pg, "operator"); nav(pg, "affiliate-marketplace")
    first = pg.locator("#affiliateMarketplaceGrid .program-card").first
    ok("Intelsense AI Affiliate Program" in first.inner_text() and first.locator('[data-offer-review="approve"]').count() == 1, "Operator sees it first, with Approve / Request changes")
    first.locator('[data-offer-review="approve"]').click(); pg.wait_for_timeout(300)
    role(pg, "partner"); nav(pg, "affiliate-marketplace")
    vcard = pg.locator('#affiliateMarketplaceGrid .program-card').filter(has_text="Intelsense AI Affiliate Program")
    ok(vcard.count() == 1 and "AFFILIATE PROGRAM · INTELSENSE AI" in vcard.inner_text().upper() and "10%" not in vcard.inner_text(), "Approved: partners see it, labelled with the vendor (no terms)")
    ok(vcard.locator('a:has-text("Join program")').get_attribute("href") == "https://intelsense.example/affiliates/join", "Join program opens the vendor's sign-up link")
    nav(pg, "vendor-network"); pg.locator('[data-view-vendor="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    ok("Affiliate program" in pg.inner_text("#vendorProfileContent") and pg.locator("#vendorAffiliateOffers .program-card").count() == 1, "Vendor profile shows the affiliate program next to the reseller program")
    pg.locator("#vendorAffiliateOffers [data-enroll-affiliate]").click(); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-affiliate-manage"] and "10%" not in pg.inner_text("#affiliateManageContent"), "Partner can enroll; manage screen shows no commission terms")
    # vendor edits -> back to review
    role(pg, "vendor"); nav(pg, "affiliate-marketplace")
    pg.locator('#affiliateMarketplaceGrid .program-card').filter(has_text="Intelsense AI Affiliate Program").locator("[data-edit-affiliate-offer]").click(); pg.wait_for_timeout(300)
    ok(pg.input_value("#aoTermAmount") == "10%", "Vendor sees their own terms in the editor")
    pg.fill("#aoTermAmount", "12%"); pg.click('#affiliateOfferForm button[type=submit]'); pg.wait_for_timeout(300)
    ok("WAITING FOR CLOUDWAV REVIEW" in pg.locator('#affiliateMarketplaceGrid .program-card').filter(has_text="Intelsense AI Affiliate Program").inner_text().upper(), "Edits go back to CloudWAV for review")
    # persists in demo
    pg.reload(); pg.wait_for_timeout(700); role(pg, "vendor"); nav(pg, "affiliate-marketplace")
    ok("Intelsense AI Affiliate Program" in pg.inner_text("#affiliateMarketplaceGrid"), "Vendor offer persists after reload")
    b.close()

# ----- cloud: an existing Northstar row in Supabase is hidden and marked deleted by the operator
if os.path.exists("/usr/lib/postgresql/16/bin/initdb"):
    from pgmock import start_pg, stop_pg, PgSupabase
    USERS = {"cto@cloudwavconsulting.com": {"password": "op-pass-123", "id": "11111111-0000-0000-0000-000000000001"},
             "vendor@intelsense.test": {"password": "vend-pass-123", "id": "11111111-0000-0000-0000-000000000002"},
             "partner@siamdigital.test": {"password": "part-pass-123", "id": "11111111-0000-0000-0000-000000000003"}}
    PORTAL = {USERS["cto@cloudwavconsulting.com"]["id"]: {"role": "operator", "entity_id": None, "display_name": "Peter Phelan"},
              USERS["vendor@intelsense.test"]["id"]: {"role": "vendor", "entity_id": "intelsense", "display_name": "Intelsense Admin"},
              USERS["partner@siamdigital.test"]["id"]: {"role": "partner", "entity_id": "siam-digital", "display_name": "Somchai"}}
    mock = PgSupabase(USERS, PORTAL, start_pg())
    import psycopg2
    con = psycopg2.connect(mock.dsn); con.autocommit = True; cur = con.cursor(); cur.execute("set session_replication_role = replica")
    for rid, name in [("northstar-psa", "Northstar PSA"), ("msp-learning-hub", "MSP Learning Hub"), ("xero", "Xero")]:
        cur.execute("insert into portal_records(collection,id,data,readers,writers) values ('affiliatePrograms',%s,%s,'{*}','{}')", (rid, json.dumps({"id": rid, "name": name, "category": "x", "desc": "x", "note": ""})))
    con.close()
    with sync_playwright() as p:
        b, ctx, pg = open_page_supabase(p, mock)
        pg.fill("#loginEmail", "cto@cloudwavconsulting.com"); pg.fill("#loginPassword", "op-pass-123"); pg.click("#loginSubmit"); pg.wait_for_timeout(3000)
        for _ in range(40):
            if not pg.evaluate("CLOUD_PENDING()"): break
            pg.wait_for_timeout(150)
        nav(pg, "affiliate-marketplace")
        ok("Northstar" not in pg.inner_text("#affiliateMarketplaceGrid"), "Signed in: old Northstar record in Supabase is hidden")
        rows = {r["id"]: r["data"] for r in mock.rows_as_operator() if r["collection"] == "affiliatePrograms"}
        ok(rows.get("northstar-psa", {}).get("_deleted") and rows.get("msp-learning-hub", {}).get("_deleted"), "...and marked deleted in Supabase")
        ok("hubspot" in rows and "freshbooks" in rows, "New tiles saved to Supabase")
        ok(rows["xero"].get("_rev") == 2 and "terms" not in rows["xero"], "An older Xero record in Supabase is updated -- without the commission terms in the shared record")
        terms = {r["id"]: r for r in mock.rows_as_operator() if r["collection"] == "affiliateTerms"}
        ok(terms.get("xero", {}).get("data", {}).get("terms", {}).get("network") == "PartnerStack" and terms["xero"]["readers"] == [], "Terms stored privately (CloudWAV only)")
        b.close()
        def login(email, pw):
            b, ctx, pg = open_page_supabase(p, mock)
            pg.fill("#loginEmail", email); pg.fill("#loginPassword", pw); pg.click("#loginSubmit"); pg.wait_for_timeout(2500)
            return b, pg
        def settle(pg):
            for _ in range(40):
                if not pg.evaluate("CLOUD_PENDING()"): return True
                pg.wait_for_timeout(150)
        # vendor adds an affiliate program
        b, pg = login("vendor@intelsense.test", "vend-pass-123")
        nav(pg, "affiliate-marketplace")
        ok("180 days" not in pg.inner_text("#affiliateMarketplaceGrid"), "Signed-in vendor: no CloudWAV terms anywhere on the page")
        pg.click("#createAffiliateOfferBtn"); pg.wait_for_timeout(300)
        pg.fill("#aoDesc", "Refer and earn"); pg.fill("#aoTermAmount", "10%"); pg.fill("#aoDirectLink", "https://intelsense.example/join")
        pg.click('#affiliateOfferForm button[type=submit]'); pg.wait_for_timeout(800); settle(pg)
        vo = [r for r in mock.rows_as_operator() if r["collection"] == "affiliatePrograms" and r["data"].get("vendorId") == "intelsense"]
        ok(len(vo) == 1 and vo[0]["data"]["status"] == "pending" and vo[0]["readers"] == ["vendor:intelsense"] and "terms" not in vo[0]["data"], "Vendor offer saved as pending, visible only to the vendor (and CloudWAV)")
        vt = [r for r in mock.rows_as_operator() if r["collection"] == "affiliateTerms" and r["id"] == vo[0]["id"]]
        ok(len(vt) == 1 and vt[0]["readers"] == ["vendor:intelsense"], "Its terms are private to the vendor and CloudWAV")
        oid = vo[0]["id"]
        b.close()
        pid = USERS["partner@siamdigital.test"]["id"]
        ok(mock.sql("select id from portal_records where collection in ('affiliateTerms') ", uid=pid) == [], "Partners can't read any commission terms")
        try:
            mock.sql("insert into portal_records(collection,id,data,readers,writers) values ('affiliatePrograms','p-offer',%s,'{*}','{partner:siam-digital}')", (json.dumps({"id": "p-offer", "name": "x"}),), fetch=False, uid=pid); refused = False
        except Exception: refused = True
        ok(refused, "Partners can't create affiliate offers")
        try:
            mock.sql("update portal_records set data = jsonb_set(data,'{status}','\"approved\"') where collection='affiliatePrograms' and id=%s", (oid,), fetch=False, uid=USERS["vendor@intelsense.test"]["id"]); refused = False
        except Exception: refused = True
        ok(refused, "Vendors can't approve their own offer")
        # operator approves; partner sees it
        b, pg = login("cto@cloudwavconsulting.com", "op-pass-123")
        nav(pg, "affiliate-marketplace")
        pg.locator(f'#affiliateMarketplaceGrid [data-offer-id="{oid}"][data-offer-review="approve"]').click(); pg.wait_for_timeout(800); settle(pg)
        b.close()
        b, pg = login("partner@siamdigital.test", "part-pass-123")
        nav(pg, "affiliate-marketplace")
        ok(pg.locator(f'#affiliateMarketplaceGrid [data-offer="{oid}"]').count() == 1, "After approval the partner sees the vendor's affiliate program")
        b.close()
    stop_pg()
report()
