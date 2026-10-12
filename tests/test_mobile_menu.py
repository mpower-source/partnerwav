from harness import *

# Phones: the menu is a bar across the top with content underneath. It opens only when Menu is tapped,
# and choosing a screen closes it and shows that screen's content.
def bar(pg):
    return pg.evaluate("""() => { const s = document.querySelector('.sidebar').getBoundingClientRect();
        return { h: Math.round(s.height), w: Math.round(s.width), open: document.documentElement.classList.contains('mnav-open'),
                 links: [...document.querySelectorAll('.sidebar .navlink, .sidebar .navsec-head, .sidebar .role-btn')].filter(e => e.offsetParent).length,
                 overflow: document.documentElement.scrollWidth - innerWidth }; }""")

with sync_playwright() as p:
    b, pg = open_page(p)
    pg.set_viewport_size({"width": 390, "height": 844}); pg.reload(); pg.wait_for_timeout(700)
    d = bar(pg)
    ok(not d["open"] and d["h"] <= 72 and d["w"] == 390 and d["links"] == 0, "Phone: a slim bar across the top, menu closed: " + str(d))
    ok(pg.locator("#mnavToggle").is_visible() and pg.get_attribute("#mnavToggle", "aria-expanded") == "false", "A Menu button in the bar")
    top = pg.evaluate("document.querySelector('#scr-partner-overview').getBoundingClientRect().top")
    ok(top < 240, "The screen's content starts right under the bar (" + str(round(top)) + "px)")
    ok(d["overflow"] <= 0, "No sideways scrolling")

    pg.click("#mnavToggle"); pg.wait_for_timeout(250)
    d = bar(pg)
    ok(d["open"] and d["h"] >= 800 and d["links"] > 5 and pg.get_attribute("#mnavToggle", "aria-expanded") == "true", "Tapping Menu opens it over the page: " + str(d))
    ok(pg.inner_text("#mnavToggle").strip() == "Close", "...and the button now says Close")
    ok(pg.evaluate("getComputedStyle(document.body).overflow") == "hidden", "The page behind doesn't scroll while it's open")
    # sections still fold open inside the menu
    pg.locator('#navPartner .navsec:has([data-screen="calendar"]) .navsec-head').click(); pg.wait_for_timeout(150)
    ok(bar(pg)["open"] and pg.locator('#navPartner [data-screen="calendar"]').is_visible(), "Opening a section keeps the menu open")
    pg.locator('#navPartner [data-screen="calendar"]').click(); pg.wait_for_timeout(300)
    d = bar(pg)
    ok(not d["open"] and visible_screen(pg) == ["scr-calendar"], "Choosing a screen closes the menu and shows it")
    ok(pg.evaluate("scrollY") == 0, "...from the top")

    # Escape closes; a role switch (demo) keeps it open to pick a screen
    pg.click("#mnavToggle"); pg.wait_for_timeout(150); pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    ok(not bar(pg)["open"], "Escape closes the menu")
    pg.click("#mnavToggle"); pg.wait_for_timeout(150); pg.locator('[data-role="operator"]').click(); pg.wait_for_timeout(250)
    ok(bar(pg)["open"] and pg.locator('#navOperator').is_visible(), "Switching role keeps the menu open on that role's screens")
    pg.locator('#navOperator .navlink').first.click(); pg.wait_for_timeout(250)
    ok(not bar(pg)["open"], "...then picking a screen closes it")

    # the bar stays at the top while scrolling
    pg.evaluate("window.scrollTo(0, 1200)"); pg.wait_for_timeout(150)
    ok(abs(pg.evaluate("document.querySelector('.sidebar').getBoundingClientRect().top")) < 1, "The bar stays at the top while scrolling")

    # helpers used across the tests still work on a phone
    nav(pg, "operator-community"); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-operator-community"] and not bar(pg)["open"], "Going to a screen in a section works the same way")

    # desktop: unchanged sidebar, no Menu button; widening the window closes an open phone menu
    pg.click("#mnavToggle"); pg.wait_for_timeout(150)
    pg.set_viewport_size({"width": 1280, "height": 900}); pg.wait_for_timeout(250)
    d = bar(pg)
    ok(not d["open"] and d["w"] == 234 and not pg.locator("#mnavToggle").is_visible() and d["links"] > 5, "Desktop keeps the side menu: " + str(d))

    # public pages never show it
    pg.set_viewport_size({"width": 390, "height": 844}); pg.goto(URL + "?demo=1&events=thailand"); pg.wait_for_timeout(600)
    ok(not pg.locator("#mnavToggle").is_visible() and not pg.locator(".sidebar").is_visible(), "Public pages have no menu bar")
    b.close()
report()
