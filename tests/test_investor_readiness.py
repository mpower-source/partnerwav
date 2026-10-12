from harness import *
from ir_helpers import fill_readiness, pick, nxt
import json

# Investor readiness: vendors, partners and affiliates take a check (YC / Founder Institute / Thai investor criteria)
# before investors on PartnerWAV can see them. Must-haves gate it; CloudWAV reviews it.
def rd(pg): return json.loads(pg.evaluate("localStorage.getItem('partnerWAV_investorReadiness')") or "[]")

with sync_playwright() as p:
    b, pg = open_page(p)
    for who in ("vendor", "partner", "affiliate"):
        role(pg, who)
        ok(in_menu(pg, "investor-readiness"), who + ": Investor Readiness is in the menu")
    # ----- an affiliate that isn't ready yet
    role(pg, "affiliate"); nav(pg, "investor-readiness"); pg.wait_for_timeout(200)
    ok("pitch deck" in pg.inner_text("#investorReadinessContent").lower(), "The start screen lists what you'll need")
    pg.click("[data-ir-edit]"); pg.wait_for_timeout(150)
    nxt(pg)
    ok(not pg.locator("#irError").is_hidden(), "Required answers are checked on each step")
    pg.click("[data-ir-cancel]"); pg.wait_for_timeout(150)
    fill_readiness(pg, ready=False)
    res = pg.inner_text("#investorReadinessContent")
    ok(pg.locator('[data-ir-result="not"], [data-ir-result="almost"]').count() == 1 and pg.locator("[data-ir-submit]").count() == 0, "Not ready: no way to send it to investors")
    ok("A pitch deck that is ready" in res and "3-year financial model" in res, "The missing must-haves are listed")
    ok("Startup Grind Bangkok" in res and "Founder Institute Bangkok" in res and "TED Fund" in res, "...with places to get help, Startup Grind Bangkok first")
    ok("Seed round investors usually expect" in res, "Traction is compared with the benchmark for the round")

    # use of funds must add up to 100%
    pg.click("[data-ir-edit]"); pg.wait_for_timeout(150)
    for _ in range(4): nxt(pg)
    pg.fill('[data-ir-fund="product"]', "50"); pg.fill('[data-ir-fund="sales"]', "0"); pg.fill('[data-ir-fund="hiring"]', "0"); pg.fill('[data-ir-fund="expansion"]', "0")
    pg.locator('[data-ir-fund="product"]').dispatch_event("input")
    ok("50%" in pg.inner_text("[data-ir-fund-total]"), "The use-of-funds total updates as you type")
    pick(pg, "deck", "Ready"); pick(pg, "financialModel", "Ready"); nxt(pg)
    ok("add up to 100%" in pg.inner_text("#irError"), "Use of funds has to add up to 100%")
    while pg.locator("[data-ir-back]").count(): pg.click("[data-ir-back]"); pg.wait_for_timeout(100)
    pg.click("[data-ir-cancel]")

    # ----- a vendor that is ready: sends it, PartnerWAV approves, then it can show its round
    role(pg, "vendor"); nav(pg, "investor-readiness"); pg.wait_for_timeout(200)
    fill_readiness(pg, ready=True)
    sc = int(pg.inner_text(".ir-score b"))
    ok(pg.locator('[data-ir-result="ready"]').count() == 1 and sc >= 75, "Ready: score " + str(sc))
    ok(pg.locator("[data-ir-list]").count() == 0, "Investors can't see it before PartnerWAV reviews it")
    pg.click("[data-ir-submit]"); pg.wait_for_timeout(200)
    vk = rd(pg)[-1]["id"] if rd(pg)[-1]["id"].startswith("vendor:") else [r for r in rd(pg) if r["id"].startswith("vendor:")][0]["id"]
    ok([r for r in rd(pg) if r["id"] == vk][0]["status"] == "submitted", "Sent to PartnerWAV for review")
    pg.reload(); pg.wait_for_timeout(600); role(pg, "vendor"); nav(pg, "investor-readiness"); pg.wait_for_timeout(300)
    ok(pg.locator('[data-ir-result="ready"]').count() == 1 and pg.locator('[data-ir-status="submitted"]').count() == 1, "The check is still there after reloading the page")
    role(pg, "operator"); nav(pg, "operator-investors"); pg.click('[data-oi-tab="readiness"]'); pg.wait_for_timeout(200)
    card = pg.locator(f'[data-ir-review="{vk}"]')
    ok(card.count() == 1 and "Investor-ready" in card.text_content() and "deck.pdf" in card.inner_html(), "CloudWAV sees the answers, score and deck link")
    card.locator("[data-ir-approve]").click(); pg.wait_for_timeout(200)
    ok([r for r in rd(pg) if r["id"] == vk][0]["status"] == "approved", "CloudWAV approves it")
    role(pg, "vendor"); nav(pg, "investor-readiness"); pg.wait_for_timeout(200)
    pg.check("[data-ir-list]"); pg.wait_for_timeout(200)
    lst = json.loads(pg.evaluate("localStorage.getItem('partnerWAV_investors')"))["listings"]
    ok(any(l["id"] == vk for l in lst), "The approved vendor shows its round to investors")
    # changing answers takes it off until PartnerWAV reviews again
    fill_readiness(pg, ready=True, round_="Series A")
    rec = [r for r in rd(pg) if r["id"] == vk][0]
    lst = json.loads(pg.evaluate("localStorage.getItem('partnerWAV_investors')"))["listings"]
    ok(rec["status"] == "draft" and not any(l["id"] == vk for l in lst), "Changed answers need a fresh review; investors stop seeing it")
    ok("Series A round investors usually expect" in pg.inner_text("#investorReadinessContent"), "A bigger round is held to a higher benchmark")
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0, "The result fits a phone")
    pg.set_viewport_size({"width": 1280, "height": 900})

    # ----- Unisense sits under Intelsense
    role(pg, "partner"); nav(pg, "partner-directory"); pg.wait_for_timeout(300)
    ok(pg.locator('[data-program-subs="intelsense"] [data-program-sub="unisense"]').count() == 1, "Program Directory: Unisense is listed inside Intelsense AI")
    ok(pg.evaluate("[...document.querySelectorAll('#directoryGrid > .program-card .program-name')].map(e => e.textContent).indexOf('Unisense')") < 0, "...not as its own card")
    role(pg, "operator"); nav(pg, "operator-programs"); pg.wait_for_timeout(300)
    order = pg.evaluate("[...document.querySelectorAll('[data-op-prog]')].map(r => r.dataset.opProg)")
    ok(order.index("unisense") == order.index("intelsense") + 1 and "Product of Intelsense AI" in pg.inner_text('[data-op-prog="unisense"]'), "Manage Programs: Unisense right under Intelsense AI")
    nav(pg, "operator-overview"); pg.wait_for_timeout(300)
    rows = pg.evaluate("[...document.querySelectorAll('[data-roi-row]')].map(r => r.dataset.roiRow)")
    ok(rows.index("unisense") == rows.index("intelsense") + 1 and pg.locator('[data-roi-row="unisense"].op-sub').count() == 1, "Return by vendor: Unisense under Intelsense AI")
    b.close()
report()
