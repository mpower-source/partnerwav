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
    hs = g.locator('[data-direct-offer="hubspot"]')
    t = hs.locator("[data-aff-terms]").inner_text()
    ok("Recurring (12 months)" in t and "30% flat" in t and "180 days" in t and "Impact" in t, "HubSpot terms on the tile")
    ok("15% - 20%" in g.locator('[data-direct-offer="zoho"]').inner_text() and "90 days" in g.locator('[data-direct-offer="zoho"]').inner_text(), "Zoho terms")
    fb = g.locator('[data-direct-offer="freshbooks"]').inner_text()
    ok("$5-$10 per free trial" in fb and "120 days" in fb and "PartnerStack / ShareASale" in fb, "FreshBooks terms")
    ok("PartnerStack" in g.locator('[data-direct-offer="xero"]').inner_text(), "Xero terms (PartnerStack)")
    ok(all(g.locator(f'[data-direct-offer="{i}"] img.entity-logo-img').count() == 1 for i in ["xero", "zoho", "hubspot", "freshbooks"]), "All four have logos")
    ok(g.locator("[data-link-pending]").count() == 4 and g.locator('[data-link-pending="lovable"]').count() == 0, "Link & QR 'coming soon' on the four new tiles, not on Lovable")
    ok(g.locator('[data-manage-affiliate="xero"]').count() == 1, "Xero enrollment still works")

    # operator adds HubSpot's link + QR later
    role(pg, "operator"); nav(pg, "affiliate-marketplace")
    pg.click('[data-edit-affiliate-offer="hubspot"]'); pg.wait_for_timeout(300)
    ok(pg.input_value("#aoTermCookie") == "180 days" and pg.locator("#aoLogoPreview img").count() == 1, "Editor loads terms and logo")
    pg.fill("#aoDirectLink", "https://hubspot.sjv.io/example-cloudwav")
    pg.set_input_files("#aoQrFile", os.path.join(HERE, "_qr_sample.png")); pg.wait_for_timeout(300)
    ok(pg.locator("#aoQrPreview img").count() == 1, "QR uploads and previews")
    pg.fill("#aoTermAmount", "30% flat"); pg.click('#affiliateOfferForm button[type=submit]'); pg.wait_for_timeout(300)
    role(pg, "partner"); nav(pg, "affiliate-marketplace")
    hs = pg.locator('#affiliateMarketplaceGrid [data-direct-offer="hubspot"]')
    ok(hs.locator(".aff-link-input").input_value() == "https://hubspot.sjv.io/example-cloudwav" and hs.locator("[data-aff-qr] img").count() == 1, "HubSpot tile now shows the link and QR code")
    ok(hs.locator("[data-link-pending]").count() == 0, "'Coming soon' badge gone")
    b.close()

# ----- cloud: an existing Northstar row in Supabase is hidden and marked deleted by the operator
if os.path.exists("/usr/lib/postgresql/16/bin/initdb"):
    from pgmock import start_pg, stop_pg, PgSupabase
    USERS = {"cto@cloudwavconsulting.com": {"password": "op-pass-123", "id": "11111111-0000-0000-0000-000000000001"}}
    PORTAL = {USERS["cto@cloudwavconsulting.com"]["id"]: {"role": "operator", "entity_id": None, "display_name": "Peter Phelan"}}
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
        ok(rows["xero"].get("terms", {}).get("network") == "PartnerStack" and "PartnerStack" in pg.inner_text('#affiliateMarketplaceGrid [data-direct-offer="xero"]'), "An older Xero record in Supabase is updated to the new version")
        b.close()
    stop_pg()
report()
