from harness import *

with sync_playwright() as p:
    b, pg = open_page(p)

    # ===== Operator: Shop Manager =====
    role(pg, "operator")
    ok(pg.locator('[data-screen="operator-shop"]:visible').count() == 1, "Shop Manager in the Operator menu")
    nav(pg, "operator-shop")
    rows = pg.locator("[data-opshop-row]")
    ok(rows.count() == 9, "9 starter products: " + str(rows.count()))
    txt = pg.inner_text("#operatorShopContent")
    ok(all(t in txt for t in ["Sales Fundamentals", "Finding & Closing Bigger Deals", "Build a Bigger Following", "Meetup Group", "Social Media Marketing 101"]), "Covers sales, bigger deals, social following, meetups, SMM 101")
    ok("waitlist mode" in txt, "Paid products without a payment link are flagged as waitlist mode")
    # add a payment link to Sales Fundamentals
    pg.click('[data-opshop-row="shop-sales-fundamentals"] [data-shop-edit]'); pg.wait_for_timeout(250)
    ok(visible_screen(pg) == ["scr-operator-shop-editor"] and pg.input_value("#shp_title") == "Sales Fundamentals for MSPs & VARs", "Editor loads the product")
    pg.fill("#shp_paymentLink", "not a link"); pg.click('[data-shop-save="published"]'); pg.wait_for_timeout(150)
    ok("full web address" in pg.inner_text("#shopEditError"), "Validates the payment link")
    pg.fill("#shp_paymentLink", "https://buy.stripe.com/test_sales101"); pg.fill("#shp_accessLink", "https://learn.cloudwav.example/sales-fundamentals")
    pg.click('[data-shop-save="published"]'); pg.wait_for_timeout(250)
    ok(visible_screen(pg) == ["scr-operator-shop"], "Saved")
    # new product
    pg.click('[data-shop-edit=""]'); pg.wait_for_timeout(250)
    pg.fill("#shp_title", "LinkedIn Profile Makeover Checklist"); pg.fill("#shp_summary", "Turn your LinkedIn profile into a lead magnet in an afternoon.")
    pg.select_option("#shp_type", "Template pack"); pg.select_option("#shp_category", "Social media"); pg.fill("#shp_price", "19")
    pg.wait_for_timeout(100)
    ok("LinkedIn Profile Makeover" in pg.inner_text("#shopEditPreview") and "$19" in pg.inner_text("#shopEditPreview"), "Live card preview")
    pg.click('[data-shop-save="draft"]'); pg.wait_for_timeout(250)
    ok(rows.count() == 10 and "DRAFT" in pg.locator("[data-opshop-row]").first.inner_text().upper(), "New product saved as a draft")

    # ===== Partner: browse + buy =====
    role(pg, "partner")
    ok(pg.locator('[data-screen="shop"]:visible').count() == 1, "Training & Shop in the Partner menu")
    nav(pg, "shop")
    cards = pg.locator("[data-shop-card]")
    n = cards.count()
    ok(n == 8 and pg.locator('[data-shop-card="shop-vendor-channel"]').count() == 0, "Partners see published partner/everyone products only (" + str(n) + ")")
    ok("LinkedIn Profile Makeover" not in pg.inner_text("#shopContent"), "Drafts hidden")
    pg.click('[data-shop-cat="Social media"]'); pg.wait_for_timeout(150)
    ok(cards.count() == 2, "Category filter")
    pg.click('[data-shop-cat=""]'); pg.wait_for_timeout(100)
    # free product
    pg.click('[data-shop-card="shop-smm-101"] [data-shop-view]'); pg.wait_for_timeout(250)
    ok(visible_screen(pg) == ["scr-shop-product"] and "WHAT'S INSIDE" in pg.inner_text("#shopProductContent").upper(), "Product page with outline")
    pg.click("[data-shop-buy]"); pg.wait_for_timeout(250)
    ok("Open in my library" in pg.inner_text("#shopProductContent"), "Free product goes straight to the library")
    # waitlist product
    pg.click('[data-screen-go="shop"]:visible'); pg.wait_for_timeout(200)
    pg.click('[data-shop-card="shop-bigger-deals"] [data-shop-view]'); pg.wait_for_timeout(250)
    pg.click("[data-shop-waitlist]"); pg.wait_for_timeout(200)
    ok("ON THE WAITLIST" in pg.inner_text("#shopProductContent").upper(), "Joined the waitlist")
    # paid product with link
    pg.click('[data-screen-go="shop"]:visible'); pg.wait_for_timeout(200)
    pg.click('[data-shop-card="shop-sales-fundamentals"] [data-shop-view]'); pg.wait_for_timeout(250)
    ok("Buy for $149" in pg.inner_text("#shopProductContent"), "Buy button with price")
    pg.evaluate("() => { window.__opened = []; window.open = function(u){ window.__opened.push(u); return null; }; }")
    pg.click("[data-shop-buy]"); pg.wait_for_timeout(400)
    ok(pg.evaluate("window.__opened") == ["https://buy.stripe.com/test_sales101"], "Opens the payment link in a new tab")
    ok("awaiting payment confirmation" in pg.inner_text("#shopProductContent"), "Order awaits confirmation")
    pg.click('[data-shop-tab-go]') if pg.locator('[data-shop-tab-go]').count() else None
    nav(pg, "shop"); pg.click('[data-shop-tab="library"]'); pg.wait_for_timeout(200)
    lib = pg.inner_text("#shopContent").upper()
    ok("MY LIBRARY (2)" in lib and "AWAITING PAYMENT" in lib, "Library shows both orders")

    # ===== Operator confirms payment =====
    role(pg, "operator"); nav(pg, "operator-shop"); pg.click('[data-opshop-tab="orders"]'); pg.wait_for_timeout(200)
    ot = pg.inner_text("#operatorShopContent").upper()
    ok("SIAM DIGITAL MSP" in ot and "AWAITING PAYMENT" in ot and "1 TO CONFIRM" in ot, "Operator sees the order and who bought it")
    pg.click('[data-order-act="paid"]'); pg.wait_for_timeout(200)
    ok(pg.locator('[data-order-act="paid"]').count() == 0, "Marked paid")
    pg.click('[data-opshop-tab="waitlist"]'); pg.wait_for_timeout(150)
    ok("FINDING & CLOSING BIGGER DEALS" in pg.inner_text("#operatorShopContent").upper() and "Siam Digital MSP" in pg.inner_text("#operatorShopContent"), "Waitlist shows demand")

    # ===== Partner completes the course -> counts toward level =====
    role(pg, "partner"); nav(pg, "shop"); pg.click('[data-shop-tab="library"]'); pg.wait_for_timeout(200)
    card = pg.locator('[data-lib-card="shop-sales-fundamentals"]')
    ok(card.locator('a:has-text("Open course")').get_attribute("href") == "https://learn.cloudwav.example/sales-fundamentals", "Paid: access link unlocked")
    card.locator("[data-shop-complete]").click(); pg.wait_for_timeout(200)
    ok("COMPLETED" in pg.locator('[data-lib-card="shop-sales-fundamentals"]').inner_text().upper(), "Marked complete")

    # ===== Operator: Partners & Tiers =====
    role(pg, "operator"); nav(pg, "operator-partners")
    ok(pg.locator("[data-en-row]").count() == 6, "6 enrollments listed")
    head = pg.inner_text("#operatorPartnersContent").upper()
    ok("COMMISSION TIER" in head and "LEVEL" in head and "PROGRESS" in head, "Table shows commission tier, level and progress")
    # filters
    pg.select_option("#opPartnerLevel", "Gold"); pg.wait_for_timeout(150)
    ok(pg.locator("[data-en-row]").count() == 1, "Level filter")
    pg.click("[data-oppart-reset]"); pg.wait_for_timeout(100)
    pg.click('[data-oppart-flag="pending-status"]'); pg.wait_for_timeout(150)
    ok(pg.locator("[data-en-row]").count() == 1 and "Gulf Coast" in pg.inner_text("#operatorPartnerRows"), "'To approve' shortcut")
    pg.click("[data-oppart-reset]"); pg.wait_for_timeout(100)
    pg.click('[data-oppart-flag="promote"]'); pg.wait_for_timeout(150)
    ok(pg.locator("[data-en-row]").count() >= 1 and "Portonics" in pg.inner_text("#operatorPartnerRows"), "'Ready to level up' finds Portonics (Unisense, meets Silver)")
    pg.click("[data-oppart-reset]"); pg.wait_for_timeout(100)
    pg.fill("#opPartnerQ", "portonics"); pg.wait_for_timeout(150)
    ok(pg.locator("[data-en-row]").count() == 2, "Search")
    pg.click("[data-oppart-reset]"); pg.wait_for_timeout(100)
    with pg.expect_download() as dl:
        pg.click("[data-oppart-export]")
    csv = open(dl.value.path()).read()
    ok(csv.startswith("Partner,Country,Program") and "Siam Digital MSP" in csv, "CSV export")

    # detail: Siam Digital / Intelsense -- course completed counts
    pg.click('[data-en-view="en-siam-intelsense"]'); pg.wait_for_timeout(250)
    d = pg.inner_text("#partnerDetailContent"); du = d.upper()
    ok(visible_screen(pg) == ["scr-operator-partner-detail"] and "Sales Fundamentals for MSPs & VARs" in d, "Detail shows completed training")
    ok("TO REACH PLATINUM" in du and "Courses completed: 4 of 4" in d, "Shows requirements for the next level")
    pg.select_option("#enLevel", "Silver"); pg.click("[data-en-level-save]"); pg.wait_for_timeout(150)
    ok("reason" in pg.inner_text("#enError"), "Moving down needs a reason")
    # promote Portonics Unisense
    nav(pg, "operator-partners"); pg.click('[data-en-view="en-portonics-unisense"]'); pg.wait_for_timeout(250)
    ok("Meets the requirements for Silver" in pg.inner_text("#partnerDetailContent"), "Suggests Silver")
    pg.click("[data-en-suggest]"); pg.fill("#enReason", "Passed $50k with 3 deals -- welcome to Silver!"); pg.click("[data-en-level-save]"); pg.wait_for_timeout(250)
    ok("Portonics" in pg.inner_text("#partnerDetailContent") and "Bronze → Silver" in pg.inner_text("#partnerDetailContent").replace("\n", " "), "Level changed with history")
    # approve pending enrollment
    nav(pg, "operator-partners"); pg.click('[data-en-view="en-gulf-cross"]'); pg.wait_for_timeout(250)
    pg.click('[data-en-status="active"]'); pg.wait_for_timeout(200)
    ok("Suspend" in pg.inner_text("#partnerDetailContent"), "Enrollment approved")
    # level requirements
    nav(pg, "operator-partners"); pg.click('[data-oppart-tab="levels"]'); pg.wait_for_timeout(200)
    ok(pg.locator("[data-lvl-key=minRevenue]").count() == 5, "Level requirements editor")
    pg.fill('[data-lvl="2"][data-lvl-key="minRevenue"]', "5000"); pg.click("[data-lvl-save]"); pg.wait_for_timeout(150)
    ok("can't need less" in pg.inner_text("#lvlError"), "Levels must go up in order")
    pg.fill('[data-lvl="2"][data-lvl-key="minRevenue"]', "60000"); pg.click("[data-lvl-save]"); pg.wait_for_timeout(200)
    ok(pg.locator("#lvlError").is_hidden(), "Saved requirements")

    # partner sees their level card
    role(pg, "partner"); pg.wait_for_timeout(300)
    lc = pg.inner_text("#partnerLevelCard")
    ok("Your partner level" in lc and "Intelsense AI" in lc and "Next: Platinum" in lc, "Partner overview shows level + what's next")

    # persistence
    pg.reload(); pg.wait_for_timeout(700); role(pg, "operator"); nav(pg, "operator-partners")
    ok("SILVER" in pg.locator('[data-en-row="en-portonics-unisense"]').inner_text().upper(), "Levels persist")
    nav(pg, "operator-shop")
    ok(pg.locator("[data-opshop-row]").count() == 10, "Products persist")

    # vendor sees vendor product
    role(pg, "vendor"); nav(pg, "shop"); pg.wait_for_timeout(200)
    ok(pg.locator('[data-shop-card="shop-sales-fundamentals"]').count() == 0 and pg.locator('[data-shop-card="shop-social-following"]').count() == 1, "Vendors see vendor/everyone products")
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0, "Shop fits at 390px")
    role(pg, "operator"); nav(pg, "operator-partners"); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0, "Partners & Tiers fits at 390px")
    b.close()
report()
