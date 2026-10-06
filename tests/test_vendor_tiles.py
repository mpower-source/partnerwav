from harness import *

with sync_playwright() as p:
    b, pg = open_page(p)
    role(pg, "vendor"); nav(pg, "vendor-overview")
    t = lambda k: pg.inner_text('#vendorStatRow [data-vstat="%s"]' % k)
    ok(pg.locator("#vendorStatRow .stat-tile").count() == 4, "Vendor overview shows four tiles")
    ok("ACTIVE PARTNERS" in t("partners").upper() and "\n3\n" in t("partners") + "\n", "Active partners counted from enrollments: " + t("partners").replace("\n", " | "))
    ok("$243,000" in t("revenue") and "13 deals closed" in t("revenue"), "Partner-sold revenue and closed deals: " + t("revenue").replace("\n", " | "))
    ok("OPEN DEALS" in t("deals").upper() and "$42,000 in the pipeline" in t("deals"), "Open deals with pipeline value: " + t("deals").replace("\n", " | "))
    ok("Thailand" in t("countries") and "Bangladesh" in t("countries"), "Countries reached lists partner countries: " + t("countries").replace("\n", " | "))
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0, "No horizontal overflow at 390px")
    b.close()
report()
