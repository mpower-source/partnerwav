from harness import *

with sync_playwright() as p:
    b, pg = open_page(p)
    for r, tops, secs in [("partner", 1, 5), ("vendor", 1, 4), ("affiliate", 2, 3), ("operator", 1, 6)]:
        role(pg, r)
        nid = "#nav" + r.title()
        ok(pg.locator(nid + " > .navlink:visible").count() == tops and pg.locator(nid + " .navsec-head:visible").count() == secs, f"{r.title()} menu: {tops} top link(s) and {secs} sections")
        ok(pg.locator(nid + " .navsec-items:visible").count() == 0, f"{r.title()} sections start collapsed on Overview")
    # operator: open a section, pick an item
    role(pg, "operator")
    ok(pg.locator('#navOperator [data-screen="operator-revenue"]').is_visible() is False, "Sub-items hidden until the section is opened")
    pg.click('#navOperator [data-sec="revenue"] .navsec-head'); pg.wait_for_timeout(100)
    ok(pg.locator('#navOperator [data-screen="operator-revenue"]').is_visible() and pg.get_attribute('#navOperator [data-sec="revenue"] .navsec-head', "aria-expanded") == "true", "Clicking a section opens it")
    pg.click('#navOperator [data-screen="operator-revenue"]'); pg.wait_for_timeout(200)
    ok(visible_screen(pg) == ["scr-operator-revenue"] and pg.get_attribute('#navOperator [data-screen="operator-revenue"]', "aria-current") == "true", "Sub-item opens its screen and is highlighted")
    pg.click('#navOperator [data-sec="approvals"] .navsec-head'); pg.wait_for_timeout(100)
    ok(pg.locator('#navOperator .navsec-items:visible').count() == 1 and pg.locator('#navOperator [data-screen="operator-approvals"]').is_visible(), "Opening another section closes the first")
    ok(pg.get_attribute('#navOperator [data-sec="revenue"] .navsec-head', "data-active") == "true", "Closed section holding the current screen stays marked")
    pg.click('#navOperator [data-sec="approvals"] .navsec-head'); pg.wait_for_timeout(100)
    ok(pg.locator('#navOperator .navsec-items:visible').count() == 0, "Clicking an open section closes it")
    # every screen reachable, each exactly once per role
    for r in ["partner", "vendor", "affiliate", "operator"]:
        role(pg, r)
        items = pg.evaluate("(id)=>[...document.querySelectorAll(id+' .navlink')].map(b=>b.getAttribute('data-screen')||'own')", "#nav" + r.title())
        ok(len(items) == len(set(items)) and len(items) == {"partner": 20, "vendor": 15, "affiliate": 11, "operator": 23}[r], f"{r.title()}: all {len(items)} menu items kept, none duplicated")
    # landing on a screen from elsewhere opens its section
    role(pg, "vendor"); nav(pg, "calendar")
    ok(pg.get_attribute('#navVendor [data-sec="connect"] .navsec-head', "aria-expanded") == "true" and visible_screen(pg) == ["scr-calendar"], "Vendor: Connect section open on Events & Calendar")
    # narrow screens
    pg.set_viewport_size({"width": 390, "height": 800}); pg.wait_for_timeout(150)
    ok(pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "No sideways scroll on a phone")
    report()
    b.close()
