from harness import *

with sync_playwright() as p:
    b, pg = open_page(p)
    role(pg, "operator"); nav(pg, "operator-approvals")
    ok("Needs review (2)" in pg.inner_text("#dealTabs"), "Tabs show 2 deals needing review")
    rows = pg.locator("#approvalRows tr")
    ok(rows.count() == 2 and "Not checked" in rows.first.inner_text(), "Deals listed with pricing check column")

    # --- review screen
    pg.click('[data-review-deal="deal-bkk-bank"]'); pg.wait_for_timeout(250)
    ok(visible_screen(pg) == ["scr-operator-deal-review"], "Review opens the deal")
    box = pg.inner_text("#dealReviewContent")
    ok(all(x in box for x in ["Bangkok Bank branch rollout", "Siam Digital MSP", "Unisense AI", "$42,000", "12 months", "120 agent seats"]), "Shows partner's deal details and notes")
    ok("$6,300" in box and "15%" in box, "Estimates partner commission from program terms ($42,000 × 15%)")

    # pricing check
    pg.click('[data-pricing-check="high"]'); pg.wait_for_timeout(100)

    # validation: request changes needs a message
    pg.click('[data-deal-action="changes"]'); pg.wait_for_timeout(100)
    ok("Tell the partner what needs adjusting" in pg.inner_text("#dealError"), "Request changes requires a message")

    # template fills an editable message
    pg.click('[data-deal-template="high"]'); pg.wait_for_timeout(100)
    msg = pg.input_value("#dealMessage")
    ok("Hi Siam Digital MSP team" in msg and "Bangkok Bank branch rollout" in msg and "$42,000" in msg and "high side" in msg, "Template pre-fills a message")
    pg.fill("#dealMessage", msg + " Similar 6-branch rollouts closed around $36k.")
    pg.click('[data-deal-action="changes"]'); pg.wait_for_timeout(250)
    ok(visible_screen(pg) == ["scr-operator-approvals"] and "Changes requested (1)" in pg.inner_text("#dealTabs"), "Changes requested -> back on list, correct tab")
    pg.click('[data-deal-tab="changes"]'); pg.wait_for_timeout(100)
    ok("May be priced too high" in pg.inner_text("#approvalRows"), "Pricing check saved on the deal")

    # --- partner sees it
    role(pg, "partner"); nav(pg, "partner-commissions")
    mine = pg.locator("#myDealsList .deal-row")
    ok(mine.count() == 1 and "Bangkok Bank branch rollout" in mine.first.inner_text(), "Partner sees only their own deal (Siam Digital)")
    ok("NEW MESSAGE" in mine.first.inner_text().upper() and "CHANGES REQUESTED" in mine.first.inner_text().upper(), "Shows new message + changes requested")
    mine.first.locator("[data-view-deal]").click(); pg.wait_for_timeout(250)
    ok(visible_screen(pg) == ["scr-partner-deal-view"], "Partner opens the deal")
    view = pg.inner_text("#partnerDealContent")
    ok("closed around $36k" in view and "CloudWAV requested changes" in view, "Partner sees the operator's message")
    ok("May be priced too high" not in view, "Operator's private pricing check not shown to the partner")

    # partner replies, then updates + resubmits
    pg.fill("#partnerDealMessage", "Thanks -- we can drop to $37,500 if they sign for 24 months. Could you join the call Thursday?")
    pg.click("[data-partner-deal-send]"); pg.wait_for_timeout(150)
    ok("join the call Thursday" in pg.inner_text("#partnerDealThread"), "Partner reply appears in the thread")
    pg.fill("#pdValue", "$37,500"); pg.fill("#pdTerm", "24")
    pg.click("[data-resubmit-deal]"); pg.wait_for_timeout(200)
    view = pg.inner_text("#partnerDealContent")
    ok("NEEDS REVIEW" in view.upper() and "$42,000 → $37,500" in view and "12 → 24 months" in view, "Resubmitted with a change summary")
    ok(pg.locator("#pdValue").count() == 0, "Edit form hidden once resubmitted")

    # --- operator sees reply + resubmission
    role(pg, "operator"); nav(pg, "operator-approvals")
    row = pg.locator("#approvalRows tr").filter(has_text="Bangkok Bank")
    ok("NEW REPLY" in row.inner_text().upper() and "$37,500" in row.inner_text() and "1 new" in pg.inner_text("#dealTabs"), "Operator list flags the reply with the new value")
    row.locator("[data-review-deal]").click(); pg.wait_for_timeout(250)
    box = pg.inner_text("#dealReviewContent")
    ok("join the call Thursday" in box and "24 months" in box and "$5,625" in box, "Operator sees reply, new term, recalculated commission")
    pg.click('[data-deal-template="help"]'); pg.wait_for_timeout(50)
    pg.fill("#dealMessage", "Yes -- I'll join Thursday. Approving at $37,500.")
    pg.click('[data-deal-action="approve"]'); pg.wait_for_timeout(250)
    ok("Approved (1)" in pg.inner_text("#dealTabs") and "Needs review (1)" in pg.inner_text("#dealTabs"), "Approved; other deal still waiting")

    # decline needs a reason
    pg.click('[data-review-deal="deal-clinic-pilot"]'); pg.wait_for_timeout(200)
    pg.click('[data-deal-action="decline"]'); pg.wait_for_timeout(100)
    ok("reason for declining" in pg.inner_text("#dealError"), "Decline requires a reason")
    # send message only keeps status
    pg.fill("#dealMessage", "Can you confirm the clinics are fine with direct-to-patient shipping?")
    pg.click('[data-deal-action="message"]'); pg.wait_for_timeout(200)
    ok(visible_screen(pg) == ["scr-operator-deal-review"] and "direct-to-patient shipping" in pg.inner_text("#dealThread"), "Send message stays on the deal")
    ok("NEEDS REVIEW" in pg.inner_text("#dealReviewContent").upper(), "Status unchanged by a plain message")

    # partner submits a new deal -> lands in queue under their name
    role(pg, "partner"); nav(pg, "partner-commissions")
    pg.click("#submitDealBtn"); pg.wait_for_timeout(200)
    pg.fill("#dealName", "Siam Express contact-center pilot"); pg.fill("#dealCustomer", "Siam Express Logistics")
    pg.fill("#dealValue", "$18,000"); pg.fill("#dealNotes", "40 seats")
    pg.click("#modalSubmitDeal"); pg.wait_for_timeout(200)
    ok(pg.locator("#myDealsList .deal-row").count() == 2, "New deal shows in partner's list")
    role(pg, "operator"); nav(pg, "operator-approvals")
    row = pg.locator("#approvalRows tr").filter(has_text="Siam Express contact-center pilot")
    ok(row.count() == 1 and "Siam Digital MSP" in row.inner_text(), "Submitted deal attributed to the partner company (not a person)")

    # converted lead lands in the queue
    role(pg, "partner"); nav(pg, "partner-my-leads")
    conv = pg.locator("#leadsList [data-convert-lead]")
    if conv.count():
        conv.first.click(); pg.wait_for_timeout(250)
        role(pg, "operator"); nav(pg, "operator-approvals")
        ok("Needs review (3)" in pg.inner_text("#dealTabs"), "Converted lead is registered in Deal approvals")

    # persistence
    pg.reload(); pg.wait_for_timeout(700); role(pg, "operator"); nav(pg, "operator-approvals")
    ok("Approved (1)" in pg.inner_text("#dealTabs"), "Deals, statuses and threads persist after reload")

    pg.click('[data-deal-tab="approved"]'); pg.wait_for_timeout(100)
    pg.locator("[data-review-deal]").first.click(); pg.wait_for_timeout(200)
    ok(pg.locator('[data-deal-action="approve"]').count() == 0 and pg.locator('[data-deal-action="message"]').count() == 1, "Approved deal: can still message, no re-approve")

    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0, "No horizontal overflow at 390px")
    b.close()
report()
