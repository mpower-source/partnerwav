from harness import *

with sync_playwright() as p:
    b, pg = open_page(p)
    role(pg, "vendor"); nav(pg, "vendor-overview")
    t = lambda k: pg.inner_text('#vendorStatRow [data-vstat="%s"]' % k).replace("\n", " | ")
    smp = lambda k: pg.locator('#vendorStatRow [data-vstat="%s"][data-sample]' % k).count() == 1
    ok(pg.locator("#vendorStatRow .stat-tile").count() == 6 and pg.locator('#vendorStatRow [data-vstat="countries"]').count() == 0, "Vendor overview shows six tiles, no Countries reached")
    ok("ACTIVE PARTNERS" in t("partners").upper() and "| 3 |" in t("partners") and not smp("partners"), "Active partners counted from enrollments: " + t("partners"))
    ok("$243,000" in t("revenue") and "13 deals closed" in t("revenue") and not smp("revenue"), "Partner-sold revenue and closed deals: " + t("revenue"))
    ok("$42,000 in the pipeline" in t("deals") and not smp("deals"), "Open deals with pipeline value: " + t("deals"))
    ok(smp("applications") and "TechBridge" not in t("applications"), "The two demo applications count as sample, not real: " + t("applications"))
    ok(smp("commission") and "SAMPLE" in t("commission").upper() and "$51,360" in t("commission"), "No approved deal yet: commission tile shows a marked sample: " + t("commission"))
    ok(smp("demos") and pg.locator("#vendorStatNote").is_visible(), "No demo this month: sample tile, and the note explains Sample")

    # real numbers replace the samples: approve the open deal, schedule a demo this month
    pg.evaluate("""(function(){ var d = new Date(); d.setDate(15); d.setHours(10,0,0,0);
      var c = JSON.parse(localStorage.getItem('partnerWAV_calendar') || '{"events":[],"bookings":[]}');
      c.events = (c.events || []).concat([{ id:'ev-demo-1', ownerKey:'vendor:intelsense', type:'Demo', title:'Unisense demo', start:d.toISOString(), durationMin:30 }]);
      localStorage.setItem('partnerWAV_calendar', JSON.stringify(c)); })()""")
    pg.reload(); pg.wait_for_timeout(700)
    role(pg, "operator"); nav(pg, "operator-approvals")
    pg.locator('[data-review-deal="deal-bkk-bank"]').first.click(); pg.wait_for_timeout(250)
    pg.locator('[data-deal-action="approve"]').first.click(); pg.wait_for_timeout(300)
    role(pg, "vendor"); nav(pg, "vendor-overview")
    ok(not smp("commission") and "$6,300" in t("commission") and "1 approved deal" in t("commission"), "Approved $42,000 deal at 15%: " + t("commission"))
    ok(not smp("demos") and "| 1 |" in t("demos"), "Demo scheduled this month is counted: " + t("demos"))
    ok(smp("deals"), "With no open deal left, that tile falls back to a marked sample")
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0, "No horizontal overflow at 390px")
    b.close()
report()
