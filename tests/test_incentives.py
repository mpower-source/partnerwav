from harness import *

with sync_playwright() as p:
    b, pg = open_page(p)

    # --- resource submission: vendors + partners only
    for r, expect in (("operator", False), ("affiliate", False), ("vendor", True), ("partner", True)):
        role(pg, r)
        if pg.locator('[data-screen="resource-browse"]:visible').count() == 0:
            ok(True, f"{r} has no Resource Library link (can't submit)"); continue
        nav(pg, "resource-browse")
        ok(pg.locator("#submitResourceBtn").is_visible() == expect, f"Submit Resource {'shown' if expect else 'hidden'} for {r}")

    # --- vendor creates an MDF incentive (type fields now appear)
    role(pg, "vendor"); nav(pg, "vendor-incentives")
    pg.locator('[data-goto-screen="vendor-incentive-editor"]:visible').first.click(); pg.wait_for_timeout(250)
    pg.select_option("#incType", "mdf"); pg.wait_for_timeout(100)
    ok(pg.locator("#mdfFields").is_visible() and pg.locator("#incMdfTerms").is_visible(), "Choosing MDF shows its fields (inline handler bug fixed)")
    pg.select_option("#incType", "spif"); pg.wait_for_timeout(100)
    pg.click("[data-inc-add-tier]"); pg.wait_for_timeout(100)
    ok(pg.locator("#spifTiersContainer .spifThreshold").count() == 2, "+ Add Tier works")
    pg.select_option("#incType", "mdf"); pg.wait_for_timeout(100)
    pg.fill("#incTitle", "Q1 Co-marketing MDF"); pg.fill("#incDesc", "Co-funded events and campaigns for Intelsense AI in Thailand")
    pg.fill("#mdfAmount", "3000"); pg.select_option("#mdfPeriod", "quarterly")
    pg.fill("#incValidFrom", "2027-01-01"); pg.fill("#incValidUntil", "2027-03-31")
    pg.click('#vendorIncentiveForm button[type=submit]'); pg.wait_for_timeout(200)
    ok(visible_screen(pg) == ["scr-vendor-incentive-editor"], "Blocked without claim process")
    pg.fill("#incClaimProcess", "Submit a proposal before the event; claim with invoices within the window.")
    pg.fill("#incMdfShare", "50"); pg.fill("#incMdfClaimDays", "45"); pg.fill("#incBudget", "30000")
    pg.select_option("#incPayoutTiming", "Within 30 days of claim approval")
    pg.click('#vendorIncentiveForm button[type=submit]'); pg.wait_for_timeout(250)
    ok(visible_screen(pg) == ["scr-vendor-incentives"] and "Q1 Co-marketing MDF" in pg.inner_text("#vendorIncentivesContent"), "Incentive submitted")
    ok("NEEDS REVIEW" in pg.inner_text("#vendorIncentivesContent").upper(), "Shows Needs review")

    # --- operator reviews
    role(pg, "operator"); nav(pg, "operator-marketing-approvals")
    pg.click('[data-tab="incentives"]'); pg.wait_for_timeout(200)
    content = pg.inner_text("#incentiveApprovalsContent")
    ok("Needs review (3)" in content, "Incentives tab loads (no crash) with 3 needing review (incl. the AI Hubspot sample): " + content.split("\n")[0])
    pg.click('#incentiveApprovalsContent [data-review-incentive]:right-of(:text("Q1 Co-marketing MDF"))') if False else pg.locator("#incentiveApprovalsContent .deal-row").filter(has_text="Q1 Co-marketing MDF").locator("[data-review-incentive]").click()
    pg.wait_for_timeout(250)
    ok(visible_screen(pg) == ["scr-operator-incentive-review"], "Review screen opens")
    box = pg.inner_text("#incentiveReviewContent")
    ok(all(x in box for x in ["$3,000", "50% of approved spend", "45 days", "$30,000", "Within 30 days of claim approval", "proposal before the event"]), "Shows the full terms")
    n_checks = pg.locator("[data-inc-check]").count()
    ok(n_checks == 10, "MDF checklist: 6 common + 4 MDF items (" + str(n_checks) + ")")
    for key in ("eligibility", "dates", "budget", "payout", "proposal", "window"):
        pg.check(f'[data-inc-check="{key}"]')
    pg.wait_for_timeout(100)
    ok("(6/10)" in pg.inner_text("#incCheckCount"), "Checklist progress updates")
    pg.click('[data-inc-template="gaps"]'); pg.wait_for_timeout(100)
    msg = pg.input_value("#incMessage")
    ok("Proof of performance" in msg and "anti-bribery" in msg and "Start and end dates" not in msg, "Template lists only the unticked items")
    pg.click('[data-inc-action="changes"]'); pg.wait_for_timeout(250)
    ok(visible_screen(pg) == ["scr-operator-marketing-approvals"] and "Changes requested (1)" in pg.inner_text("#incentiveApprovalsContent"), "Changes requested")

    # --- vendor sees feedback, edits + resubmits
    role(pg, "vendor"); nav(pg, "vendor-incentives")
    vc = pg.inner_text("#vendorIncentivesContent")
    ok("CloudWAV:" in vc and "Proof of performance" in vc and "CHANGES REQUESTED" in vc.upper(), "Vendor sees CloudWAV's feedback")
    pg.locator("#vendorIncentivesContent div").filter(has_text="Q1 Co-marketing MDF").locator("[data-edit-vendor-incentive]").last.click(); pg.wait_for_timeout(250)
    ok(pg.input_value("#incMdfShare") == "50" and pg.input_value("#incClaimProcess").startswith("Submit a proposal"), "Edit reloads saved terms")
    pg.fill("#incClaimProcess", "Proposal pre-approval required. Claim within 45 days with invoices and proof of performance (photos, attendee lists).")
    pg.click('#vendorIncentiveForm button[type=submit]'); pg.wait_for_timeout(250)
    ok("NEEDS REVIEW" in pg.inner_text("#vendorIncentivesContent").upper(), "Resubmitted -> back to Needs review")

    # --- operator approves; partners see it on the vendor profile
    role(pg, "operator"); nav(pg, "operator-marketing-approvals"); pg.click('[data-tab="incentives"]'); pg.wait_for_timeout(200)
    row = pg.locator("#incentiveApprovalsContent .deal-row").filter(has_text="Q1 Co-marketing MDF")
    ok("UPDATED" in row.inner_text().upper(), "Operator sees it was updated")
    row.locator("[data-review-incentive]").click(); pg.wait_for_timeout(250)
    ok("resubmitted" in pg.inner_text("#incThread") and "(6/10)" in pg.inner_text("#incCheckCount"), "Thread shows resubmission; checklist kept")
    pg.click('[data-inc-action="reject"]'); pg.wait_for_timeout(100)
    ok("reason for rejecting" in pg.inner_text("#incError"), "Reject needs a reason")
    pg.click('[data-inc-action="approve"]'); pg.wait_for_timeout(250)
    ok("Approved (6)" in pg.inner_text("#incentiveApprovalsContent"), "Approved (4 + the 2 approved Intelsense samples)")
    role(pg, "partner"); nav(pg, "vendor-network")
    pg.locator('[data-view-vendor="intelsense"]:visible').first.click(); pg.wait_for_timeout(250)
    ok("Current partner incentives" in pg.inner_text("#vendorProfileContent") and "Q1 Co-marketing MDF" in pg.inner_text("#vendorProfileContent"), "Partners see approved incentives on the vendor profile")
    ok("New Year Giveaway" not in pg.inner_text("#vendorProfileContent"), "Unapproved incentives hidden from partners")

    # persistence
    pg.reload(); pg.wait_for_timeout(700); role(pg, "vendor"); nav(pg, "vendor-incentives")
    ok("APPROVED" in pg.locator("#vendorIncentivesContent").inner_text().upper() and "Q1 Co-marketing MDF" in pg.inner_text("#vendorIncentivesContent"), "Incentives persist after reload")

    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0, "No horizontal overflow at 390px")
    b.close()
report()
