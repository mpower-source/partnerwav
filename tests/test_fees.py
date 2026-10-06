from harness import *

with sync_playwright() as p:
    b, pg = open_page(p)

    # ===== Configure program: CloudWAV platform fee section with recommended defaults
    role(pg, "operator"); nav(pg, "operator-programs")
    pg.click('[data-configure="intelsense"]'); pg.wait_for_timeout(250)
    sec = pg.locator("#cfgFeeSection")
    ok(sec.count() == 1 and "CLOUDWAV PLATFORM FEE" in sec.inner_text().upper(), "Configure program has a CloudWAV platform fee section")
    ok(pg.input_value("#cfgFeeBase") == "2" and pg.input_value("#cfgFeeSourced") == "5" and pg.input_value("#cfgFeeThreshold") == "1000000"
       and pg.input_value("#cfgFeeLargeBase") == "1" and pg.input_value("#cfgFeeLargeSourced") == "2.5", "Recommended defaults: 2% / 5%, 1% / 2.5% above 1,000,000")
    ok("on top of" in sec.inner_text() and "never deducted" in sec.inner_text(), "Explains the vendor pays it on top of partner commission")
    ok("recommended defaults" in sec.inner_text(), "Flags that defaults aren't confirmed yet")
    prev = pg.inner_text("#cfgFeePreview")
    ok("$50,000 deal" in prev and "$1,000" in prev and "$2,500" in prev, "Preview: $50,000 deal -> $1,000 base, $2,500 sourced")
    ok("$2,000,000 deal" in prev and "$30,000" in prev and "1.5% overall" in prev, "Large deals: only the part above the threshold gets the lower rate ($2M -> $30,000)")
    # validation
    pg.fill("#cfgFeeBase", "25"); pg.wait_for_timeout(100)
    pg.click("[data-config-save]"); pg.wait_for_timeout(200)
    ok("far outside the norm" in pg.inner_text("#cfgError"), "Blocks an out-of-norm fee")
    pg.fill("#cfgFeeBase", "120"); pg.click("[data-config-save]"); pg.wait_for_timeout(200)
    ok("between 0 and 100" in pg.inner_text("#cfgError"), "Percentages must be 0-100")
    # live preview follows the inputs
    pg.fill("#cfgFeeBase", "4"); pg.wait_for_timeout(150)
    ok("$2,000" in pg.inner_text("#cfgFeePreview"), "Preview updates live (4% of $50,000 = $2,000)")
    # other config edits keep the fee draft (re-render on add tier)
    pg.click("[data-cfg-add-tier]"); pg.wait_for_timeout(200)
    ok(pg.input_value("#cfgFeeBase") == "4", "Fee inputs survive a form re-render")
    pg.locator("[data-cfg-remove-tier]").last.click(); pg.wait_for_timeout(200)
    pg.fill("#cfgFeeBase", "2"); pg.click("[data-config-save]"); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-operator-programs"], "Saved")
    fees = pg.evaluate("JSON.parse(localStorage.getItem('partnerWAV_programFees'))")
    ok(len(fees) == 1 and fees[0]["id"] == "intelsense" and fees[0]["basePct"] == 2 and fees[0]["sourcedPct"] == 5, "Fee saved per program")
    prog = pg.evaluate("JSON.stringify(JSON.parse(localStorage.getItem('partnerWAV_programTerms') || '{}'))")
    ok("sourcedPct" not in prog and "basePct" not in prog, "Fee is NOT stored on the public program record")
    pg.click('[data-configure="intelsense"]'); pg.wait_for_timeout(250)
    ok("recommended defaults" not in pg.inner_text("#cfgFeeSection"), "Saved rates are shown as confirmed")
    pg.click("[data-config-cancel]"); pg.wait_for_timeout(150)

    # ===== Partners & Tiers: who sourced the partner
    nav(pg, "operator-partners"); pg.click('[data-en-view="en-siam-botnoi"]'); pg.wait_for_timeout(250)
    ok(pg.input_value("#enSource") == "vendor", "Partner detail shows how the partner joined (default: vendor's own)")
    pg.select_option("#enSource", "cloudwav"); pg.wait_for_timeout(150)
    en = pg.evaluate("JSON.parse(localStorage.getItem('partnerWAV_enrollments')).filter(e => e.id === 'en-siam-botnoi')[0].source")
    ok(en == "cloudwav", "Source saved on the enrollment")
    calc = pg.evaluate("PW_FEES.forDeal({ programId:'botnoi', partnerId:'siam-digital', value:'$10,000' })")
    ok(calc and round(calc["amount"]) == 500 and calc["sourced"], "Sourced partner -> 5% ($10,000 -> $500)")
    calc = pg.evaluate("PW_FEES.forDeal({ programId:'botnoi', partnerId:'portonics', value:'$10,000' })")
    ok(calc and round(calc["amount"]) == 200 and not calc["sourced"], "Vendor's own / no enrollment -> 2% ($200)")
    calc = pg.evaluate("PW_FEES.forDeal({ programId:'botnoi', partnerId:'portonics', value:'฿3,000,000' })")
    ok(calc and round(calc["amount"]) == 40000 and calc["text"] == "฿40,000", "Large THB deal: 2% of 1M + 1% of 2M = ฿40,000, in the deal's currency")

    # ===== Deal review: fee card, recorded on approval
    nav(pg, "operator-approvals"); pg.click('[data-review-deal="deal-bkk-bank"]'); pg.wait_for_timeout(250)
    card = pg.inner_text("#dealFeeCard")
    ok("$2,100" in card and "CloudWAV sourced this partner" in card, "Deal review shows the fee: Siam Digital was CloudWAV-sourced for Intelsense -> 5% of $42,000 = $2,100")
    ok("$6,300" in pg.inner_text("#dealReviewContent"), "Partner commission is unchanged ($6,300)")
    pg.click('[data-deal-action="approve"]'); pg.wait_for_timeout(300)
    pf = pg.evaluate("JSON.parse(localStorage.getItem('partnerWAV_platformFees'))")
    ok(len(pf) == 1 and pf[0]["id"] == "deal-bkk-bank" and pf[0]["amount"] == 2100 and pf[0]["status"] == "due" and pf[0]["rate"] == 5 and pf[0]["sourced"], "Approval records a $2,100 fee, due")
    # a later rate change doesn't rewrite the recorded fee
    nav(pg, "operator-programs"); pg.click('[data-configure="intelsense"]'); pg.wait_for_timeout(250)
    pg.fill("#cfgFeeSourced", "5"); pg.click("[data-config-save]"); pg.wait_for_timeout(300)
    nav(pg, "operator-approvals"); pg.click('[data-deal-tab="approved"]'); pg.wait_for_timeout(150)
    pg.click('[data-review-deal="deal-bkk-bank"]'); pg.wait_for_timeout(250)
    ok("$2,100" in pg.inner_text("#dealFeeCard") and "DUE" in pg.inner_text("#dealFeeCard").upper(), "Approved deal keeps the fee recorded at approval, with its status")

    # ===== CloudWAV Revenue
    ok(in_menu(pg, "operator-revenue"), "CloudWAV Revenue in the Operator menu")
    nav(pg, "operator-revenue")
    txt = pg.inner_text("#operatorRevenueContent")
    ok("$2,100" in txt and "Bangkok Bank branch rollout" in txt and "CloudWAV-sourced" in txt, "Revenue lists the platform fee")
    ok("฿24,000" in txt and "Riverside Boutique Hotels" in txt, "Software referral share: 30% of the ฿80,000 fee = ฿24,000")
    pg.click('[data-fee-status="invoiced"]'); pg.wait_for_timeout(200)
    ok(pg.locator("#revFeeRows [data-fee-row]").count() == 1 and "INVOICED" in pg.inner_text("#revFeeRows").upper(), "Mark invoiced")
    pg.click('[data-fee-status="paid"]'); pg.wait_for_timeout(200)
    ok(pg.locator("#revFeeRows [data-fee-row]").count() == 0, "Paid fee leaves the Open list")
    pg.click('[data-rev-filter="paid"]'); pg.wait_for_timeout(150)
    ok("$2,100" in pg.inner_text("#revFeeRows") and "PAID" in pg.inner_text("#revFeeRows").upper(), "Paid tab shows it")
    tiles = pg.inner_text("#operatorRevenueContent .stat-row")
    ok("PLATFORM FEES PAID\n$2,100" in tiles.upper() or ("$2,100" in tiles and "1 deal" in tiles), "Paid total tile")
    with pg.expect_download() as dl:
        pg.click("[data-rev-export]")
    csv = open(dl.value.path(), encoding="utf-8").read()
    ok("Platform fee,Bangkok Bank branch rollout" in csv and "Software referral,Riverside Boutique Hotels" in csv and ",2100,paid" in csv, "CSV export")

    # ===== Vendor sees what they owe; partner doesn't see the fee
    role(pg, "vendor"); nav(pg, "vendor-overview")
    ok("platform fee" not in pg.inner_text("#scr-vendor-overview").lower(), "Not on the vendor Overview any more")
    nav(pg, "partner-agreements"); pg.wait_for_timeout(200)
    vc = pg.inner_text("#vendorFeeCard")
    ok("CLOUDWAV PLATFORM FEE" in vc.upper() and "Vendor Program Agreement" in vc and "Bangkok Bank branch rollout" in vc and "$2,100" in vc and "never reduces" in vc, "Vendor sees the platform fee under Agreements, as part of the Vendor Program Agreement")
    pg.locator('[data-agr-row="agr-vendor-intelsense"] [data-agr-view]').click(); pg.wait_for_timeout(250)
    ok("platform operator fee of" in pg.inner_text(".modal .agr-doc") and "Partners CloudWAV brought to the Program" in pg.inner_text(".modal") and "never reduces what a Partner earns" in pg.inner_text(".modal"), "The fee is written into the vendor's full agreement")
    pg.click(".modal .modal-close"); pg.wait_for_timeout(150)
    pg.locator('[data-agr-row="agr-partner-siam-digital-intelsense"] [data-agr-view]').click(); pg.wait_for_timeout(250)
    ok(pg.locator(".modal [data-agr-fee-terms]").count() == 0, "...but not in a partner's agreement for the same program")
    pg.click(".modal .modal-close"); pg.wait_for_timeout(150)
    role(pg, "partner"); nav(pg, "partner-commissions")
    pg.locator("#myDealsList [data-view-deal]").first.click(); pg.wait_for_timeout(250)
    ok("platform fee" not in pg.inner_text("body").lower() and "2,100" not in pg.inner_text("body"), "Partners never see CloudWAV's fee")

    # ===== persists across reload
    pg.reload(); pg.wait_for_timeout(800)
    rec = pg.evaluate("PW_FEES.recorded()")
    ok(len(rec) == 1 and rec[0]["status"] == "paid" and pg.evaluate("PW_FEES.forProgram('intelsense').sourcedPct") == 5, "Fees persist")

    # ===== disabled fee
    role(pg, "operator"); nav(pg, "operator-programs"); pg.click('[data-configure="botnoi"]'); pg.wait_for_timeout(250)
    pg.uncheck("#cfgFeeEnabled"); pg.wait_for_timeout(100)
    ok("No platform fee" in pg.inner_text("#cfgFeePreview"), "Fee can be switched off per program")
    pg.click("[data-config-save]"); pg.wait_for_timeout(300)
    ok(pg.evaluate("PW_FEES.forDeal({ programId:'botnoi', partnerId:'siam-digital', value:'$10,000' }).off") is True, "Switched off -> no fee")
    b.close()

report()
