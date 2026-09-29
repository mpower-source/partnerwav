from harness import *
with sync_playwright() as p:
    b, pg = open_page(p)
    # Intelsense samples: incentives + Yealink hardware
    role(pg, "vendor"); nav(pg, "vendor-incentives"); pg.wait_for_timeout(300)
    t = pg.inner_text("#scr-vendor-incentives")
    ok(all(x in t for x in ["Unisense AI + AlterCrew Bundle SPIF", "Finsense AI Banking Pilot Credits", "AI Hubspot Launch Co-Marketing Fund"]), "Intelsense sample incentives listed for the vendor")
    nav(pg, "vendor-hardware-offerings"); pg.wait_for_timeout(300)
    hw = pg.inner_text("#hardwareOfferingsContent")
    ok("Yealink IP Phone T54W" in hw and "Yealink Video Phone SIP-T58A" in hw and "SAMPLE · COMING SOON" in hw.upper(), "Yealink phones back under Intelsense, marked 'Sample · coming soon'")
    role(pg, "partner"); nav(pg, "vendor-network"); pg.locator('[data-view-vendor="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    v = pg.inner_text("#vendorProfileContent")
    ok("Unisense AI + AlterCrew Bundle SPIF" in v and "AI Hubspot Launch Co-Marketing Fund" not in v, "Partners see approved samples (marked Sample); the pending one waits for review")
    # Botnoi sample: free AI credits for Thai SMEs, waiting for review, in baht
    role(pg, "operator"); nav(pg, "operator-marketing-approvals"); pg.click('[data-tab="incentives"]'); pg.wait_for_timeout(300)
    row = pg.locator("#incentiveApprovalsContent .deal-row").filter(has_text="Free BOTNOI AI Credits for Thai SMEs")
    ok(row.count() == 1, "Botnoi's SME AI-credits incentive waits in Marketing Approvals")
    row.locator("[data-review-incentive]").click(); pg.wait_for_timeout(300)
    rv = pg.inner_text("#scr-operator-incentive-review")
    ok("฿5,000" in rv and "600,000 points for BOTNOI Voice" in rv and "2026-09-15" in rv, "Review shows ฿5,000 credits, the two point options and the Sept 15 end date")
    # vendor overview: edit the full profile in place, tile stays
    role(pg, "vendor"); nav(pg, "vendor-overview")
    ok(pg.locator("#vendorOwnProgramGrid .program-card").count() == 5 and pg.locator("#vendorOverviewEditBtn").is_visible(), "Overview shows the Intelsense tile plus its 4 product tiles, with 'Edit full profile'")
    order = [c.get_attribute("data-product-card") for c in pg.locator("#vendorOwnProgramGrid [data-product-card]").all()]
    ok(order == ["finsense-ai", "ai-hubspot", "altercrew"] and "Unisense" in pg.locator("#vendorOwnProgramGrid .program-card").nth(1).inner_text(), "Intelsense, then Unisense (its SaaS Resale program), then Finsense AI, AI Hubspot, AlterCrew")
    # Vendor Network: product tiles right after the Intelsense tile
    nav(pg, "vendor-network"); pg.wait_for_timeout(200)
    cards = pg.locator("#vendorNetworkGrid .program-card")
    names = [c.inner_text().split("\n")[0] for c in cards.all()]
    i = [k for k, n in enumerate(names) if n.startswith("I") and "Intelsense AI" in n][0] if any("Intelsense AI" in n for n in names) else -1
    seq = [cards.nth(k).get_attribute("data-product-card") for k in range(i + 2, i + 5)]
    ok(i >= 0 and cards.nth(i + 1).inner_text().split("\n")[0].startswith("U") and "SAAS RESALE" in cards.nth(i + 1).inner_text().upper() and seq == ["finsense-ai", "ai-hubspot", "altercrew"], "Vendor Network: Intelsense, Unisense, Finsense AI, AI Hubspot, AlterCrew in order")
    pnames = pg.locator("#vendorNetworkGrid .program-name").all_inner_texts()
    ok(sum(1 for n in pnames if "Unisense" in n) == 1, "Unisense listed once: " + str([n for n in pnames if "Unisense" in n]))
    ok(all("SAAS RESALE" in pg.locator(f'#vendorNetworkGrid [data-product-card="{k}"]').inner_text().upper() for k in ["finsense-ai", "ai-hubspot", "altercrew"]), "Product tiles look like the Unisense tile (SaaS Resale badge)")
    role(pg, "partner"); nav(pg, "vendor-network")
    fin = pg.locator('#vendorNetworkGrid [data-product-card="finsense-ai"]')
    ok(fin.locator("[data-apply-reseller]").count() == 1 and "(via Intelsense AI)" in fin.inner_text(), "Partners get 'Apply as Reseller' per product")
    fin.locator("[data-view-product]").click(); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-vendor-profile"] and pg.locator('[data-product-tile="finsense-ai"]').count() == 1, "'View details' opens the Intelsense profile at that product")
    role(pg, "vendor"); nav(pg, "vendor-overview")
    pg.click("#vendorOverviewEditBtn"); pg.wait_for_timeout(300)
    ok(pg.locator("#vendorOverviewEditForm").count() == 1 and pg.locator("#vendorOwnProgramGrid .program-card").first.is_visible(), "Full profile editor opens under the tile (tile still shown)")
    ok(pg.input_value("#vpName") == "Intelsense AI" and pg.locator('[data-vp-prod-name="0"]').count() == 1 and pg.locator("#vpLogoPreview").count() == 1, "Editor has company details, logo and products")
    pg.fill("#vpDesc", "Conversational AI for support, sales, finance and workforce teams."); pg.fill("#vpWebsite", "https://intelsense.ai")
    pg.locator('#vendorOverviewEditForm [data-vendor-edit-save="intelsense"]').first.click(); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-vendor-overview"] and pg.locator("#vendorOverviewEditForm").count() == 0, "Saved: stays on the overview, editor closes")
    ok("Conversational AI for support, sales, finance and workforce teams." in pg.inner_text("#vendorOwnProgramGrid"), "The tile shows the new description")
    pg.click("#vendorOverviewEditBtn"); pg.wait_for_timeout(200); pg.fill("#vpDesc", "throwaway"); pg.click("[data-vendor-overview-cancel]"); pg.wait_for_timeout(200)
    ok(pg.locator("#vendorOverviewEditForm").count() == 0 and "throwaway" not in pg.inner_text("#vendorOwnProgramGrid"), "Cancel closes without saving")
    pg.click("#vendorOverviewViewBtn"); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-vendor-profile"] and "https://intelsense.ai" in pg.inner_html("#vendorProfileContent"), "'View full profile' opens the profile with the saved changes")
    b.close()
report()
