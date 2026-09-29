from harness import *
with sync_playwright() as p:
    b,pg=open_page(p)
    nav(pg,"affiliate-marketplace")
    g=pg.locator("#affiliateMarketplaceGrid")
    ok(g.locator(".program-card").count()==5,"5 programs shown (Xero, Zoho, HubSpot, FreshBooks, Lovable)")
    ok(g.locator(".aff-panel").count()==0,"Tiles stay compact (no link/services panel on the tile)")
    ok(g.locator('[data-manage-affiliate="xero"]').count()==1,"Pre-enrolled Xero shows 'Enrolled ✓ · Manage →'")

    # Enroll takes you straight to the manage screen
    btn=g.locator('[data-enroll-affiliate]').first; aid=btn.get_attribute("data-enroll-affiliate")
    btn.click(); pg.wait_for_timeout(250)
    ok(visible_screen(pg)==["scr-affiliate-manage"],f"Enrolling {aid} opens the manage screen")
    m=pg.locator("#affiliateManageContent")
    ok(m.locator(".aff-panel").count()==1,"Manage screen shows link, services and activity")
    link=m.locator(".aff-link-input").input_value()
    ok(f"affiliateId={aid}" in link and "partnerId=siam-digital" in link and "apply=affiliate" in link and "partnerwav-v11-merged.html" in link, "Link format: "+link)
    ok("Enrolled " in m.inner_text() and "Commission:" in m.inner_text(),"Shows enrolled date and commission")

    # Services
    m.locator(".aff-service-input").fill("Xero Accounting Setup"); m.locator("[data-aff-add-service]").click(); pg.wait_for_timeout(150)
    m.locator(".aff-service-input").fill("Payroll migration"); m.locator(".aff-service-input").press("Enter"); pg.wait_for_timeout(150)
    chips=m.locator(".aff-service-chip").all_inner_texts()
    ok(len(chips)==2,"Two services added (button + Enter): "+str(chips))
    m.locator(".aff-service-input").fill("payroll MIGRATION"); m.locator("[data-aff-add-service]").click(); pg.wait_for_timeout(150)
    ok(m.locator(".aff-service-chip").count()==2,"Duplicate service rejected")
    m.locator("[data-aff-remove-service]").nth(1).click(); pg.wait_for_timeout(150)
    ok(m.locator(".aff-service-chip").count()==1,"Service removed")
    ok(visible_screen(pg)==["scr-affiliate-manage"],"Stays on manage screen while editing services")

    # Copy
    m.locator("[data-copy-affiliate-link]").click(); pg.wait_for_timeout(300)
    ok(pg.evaluate("navigator.clipboard.readText()")==link,"Copy puts the link on the clipboard")

    # Back returns to the marketplace, tile compact with Manage button
    pg.click("[data-affiliate-manage-back]"); pg.wait_for_timeout(200)
    ok(visible_screen(pg)==["scr-affiliate-marketplace"],"Back returns to the Affiliate Marketplace")
    ok(pg.locator(f'#affiliateMarketplaceGrid [data-manage-affiliate="{aid}"]').count()==1,"Newly enrolled tile now shows Manage")

    # Xero: Manage opens its screen with seeded link activity
    pg.click('#affiliateMarketplaceGrid [data-manage-affiliate="xero"]'); pg.wait_for_timeout(200)
    m=pg.locator("#affiliateManageContent")
    ok("Xero" in m.inner_text() and m.locator(".aff-activity li").count()==2,"Xero manage screen shows 2 link activity entries")
    ok("Bangkok Bookkeeping Co." in m.inner_text() and "Chiang Mai Dental Group" in m.inner_text(),"Activity lists Bangkok Bookkeeping and Chiang Mai Dental")

    # Back goes to wherever you came from (Affiliate role overview -> My affiliate tools)
    role(pg,"affiliate"); nav(pg,"affiliate-overview")
    mine=pg.locator('#myAffiliateGrid [data-manage-affiliate="xero"]')
    ok(mine.count()==1,"My affiliate tools tile has Manage")
    mine.first.click(); pg.wait_for_timeout(200)
    ok(visible_screen(pg)==["scr-affiliate-manage"],"Manage opens from My affiliate tools")
    pg.click("[data-affiliate-manage-back]"); pg.wait_for_timeout(200)
    ok(visible_screen(pg)==["scr-affiliate-overview"],"Back returns to the screen you came from")
    role(pg,"partner")

    # persistence
    pg.reload(); pg.wait_for_timeout(600)
    nav(pg,"affiliate-marketplace")
    pg.click(f'#affiliateMarketplaceGrid [data-manage-affiliate="{aid}"]'); pg.wait_for_timeout(200)
    m=pg.locator("#affiliateManageContent")
    ok(m.locator(".aff-service-chip").count()==1 and m.locator(".aff-service-chip").first.inner_text().startswith("Xero Accounting Setup"),"Enrollment + services persist after reload")

    # mobile + dark
    pg.set_viewport_size({"width":390,"height":844}); pg.wait_for_timeout(200)
    ow=pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    ok(ow<=0,f"No horizontal overflow at 390px (overflow={ow})")
    pg.evaluate("document.documentElement.setAttribute('data-theme','dark')")
    b.close()
report()
