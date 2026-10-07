from harness import *

with sync_playwright() as p:
    b, pg = open_page(p)
    card = lambda k: " | ".join(pg.inner_text('[data-roi="%s"]' % k).split("\n"))
    smp = lambda k: pg.locator('[data-roi="%s"][data-roi-sample]' % k).count() == 1

    # ----- before a subscription is recorded: an example, marked as one
    role(pg, "vendor"); nav(pg, "vendor-overview")
    ok(pg.locator('#scr-vendor-overview [data-roi="vendor"]').count() == 1 and smp("vendor") and "SAMPLE" in card("vendor") and "$20.00" in card("vendor"), "Vendor overview leads with the return card; an example until there is a subscription: " + card("vendor")[:110])
    box = pg.locator("#vendorRoiCard").bounding_box(); tiles = pg.locator("#vendorStatRow").bounding_box()
    ok(box["y"] < tiles["y"], "The card sits above the tiles")
    role(pg, "partner"); nav(pg, "partner-overview")
    ok(smp("partner") and "at no cost to you" in card("partner"), "Partner overview has its own card, an example until a deal is approved")
    role(pg, "operator"); nav(pg, "operator-overview")
    ok(smp("operator") and "Subscription not entered" in pg.inner_text('[data-roi-row="intelsense"]'), "Operator: example overall, and each vendor row says what is missing")

    # ----- CloudWAV records the vendor's subscription
    nav(pg, "operator-programs"); pg.click('#operatorProgramRows [data-configure="intelsense"]'); pg.wait_for_timeout(250)
    pg.fill("#cfgFeeMonthly", "497"); pg.fill("#cfgFeeStart", "2025-01-01")
    pg.locator("[data-config-save]").first.click(); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-operator-programs"], "Subscription saved with the program's fee settings")
    nav(pg, "operator-overview")
    ok(not smp("operator") and "$40.74" in card("operator") and "$243,000" in card("operator") and "$5,964" in card("operator") and "1 of" in card("operator"), "Overall: $243,000 sold / (12 x $497) = $40.74 per $1: " + card("operator")[:140])
    row = pg.inner_text('[data-roi-row="intelsense"]')
    ok("$243,000" in row and "$5,964" in row and "$40.74" in row, "Intelsense row: " + " | ".join(row.split()))
    role(pg, "vendor"); nav(pg, "vendor-overview")
    ok(not smp("vendor") and "For every $1 you spend on PartnerWAV, your partners sell" in card("vendor") and "$40.74" in card("vendor") and "13" in card("vendor"), "Vendor sees its own figure: " + card("vendor")[:150])

    # ----- it moves with sales: a deal is approved (revenue up, operator fee added to the cost)
    role(pg, "operator"); nav(pg, "operator-approvals")
    pg.locator('[data-review-deal="deal-bkk-bank"]').first.click(); pg.wait_for_timeout(250)
    pg.locator('[data-deal-action="approve"]').first.click(); pg.wait_for_timeout(300)
    role(pg, "vendor"); nav(pg, "vendor-overview")
    ok("$35.34" in card("vendor") and "$285,000" in card("vendor") and "$8,064" in card("vendor") and "14" in card("vendor"), "After a $42,000 deal: $285,000 / ($5,964 + $2,100 operator fee) = $35.34: " + card("vendor")[:150])
    role(pg, "partner"); nav(pg, "partner-overview")
    ok(not smp("partner") and "You have earned" in card("partner") and "$6,300" in card("partner") and "1" in card("partner"), "Partner who closed it: 15% of $42,000 = $6,300 earned, nothing paid: " + card("partner")[:150])
    pg.reload(); pg.wait_for_timeout(700); role(pg, "vendor"); nav(pg, "vendor-overview")
    ok("$35.34" in card("vendor"), "Kept after a reload")
    role(pg, "partner"); nav(pg, "partner-overview")
    ok("subscription" not in card("partner").lower() and "$8,064" not in pg.inner_text("#scr-partner-overview"), "Partners do not see what a vendor pays CloudWAV")
    for r, scr in (("vendor", "vendor-overview"), ("partner", "partner-overview"), ("operator", "operator-overview")):
        role(pg, r); nav(pg, scr); pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
        ok(pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0, "No horizontal overflow at 390px: " + r)
        pg.set_viewport_size({"width": 1280, "height": 900})
    b.close()
report()
