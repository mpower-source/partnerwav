from harness import *
import json

# Startup Perks: free credits and discounts from software companies (Claude, Notion, AWS...). Members see the visible ones;
# only CloudWAV adds, edits or hides them. Every card is the same size; the full terms open in a details window.
def perks(pg): return json.loads(pg.evaluate("localStorage.getItem('partnerWAV_startupPerks')") or "[]")
def cards(pg): return pg.evaluate("[...document.querySelectorAll('[data-perk]')].map(e => e.dataset.perk)")

with sync_playwright() as p:
    b, pg = open_page(p)
    for who in ("partner", "vendor", "affiliate"):
        role(pg, who)
        ok(in_menu(pg, "startup-perks"), who + ": Startup Perks is in the menu")
    role(pg, "vendor"); nav(pg, "startup-perks"); pg.wait_for_timeout(300)
    c = cards(pg)
    ok("perk-claude" in c and "perk-notion" in c and "perk-aws" in c and len(c) >= 8, "Starter perks: " + ", ".join(c))
    claude = pg.inner_text('[data-perk="perk-claude"]')
    ok("Claude Team" in claude and "1,000" in claude and pg.get_attribute('[data-perk="perk-claude"] [data-perk-apply]', "href") == "https://claude.com/programs/startups", "Claude Startups: free year of Team + API credits, with a link to the offer")
    hs = pg.evaluate("[...document.querySelectorAll('.perk-card')].map(e => Math.round(e.getBoundingClientRect().height))")
    ok(len(set(hs)) == 1, "Every card is the same size: " + str(sorted(set(hs))))
    ok(pg.locator("[data-perk-edit], [data-perk-new], [data-perk-hide]").count() == 0, "Members can't edit")
    # details window
    pg.click('[data-perk-open="perk-notion"]'); pg.wait_for_timeout(200)
    d = pg.inner_text('[data-perk-detail="perk-notion"]')
    ok("6 months" in d and "partner" in d.lower() and "Notion.com" in d, "Details show who qualifies, the partner route and the source")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    ok(pg.locator("[data-perk-detail]").count() == 0, "Escape closes the details")
    # filter and search
    pg.click('[data-perk-cat="cloud"]'); pg.wait_for_timeout(200)
    ok("perk-aws" in cards(pg) and "perk-claude" not in cards(pg), "Filter by category")
    pg.click('[data-perk-cat=""]'); pg.fill("#perkQ", "notion"); pg.wait_for_timeout(400)
    ok(cards(pg)[0] == "perk-notion", "Search")
    pg.fill("#perkQ", ""); pg.wait_for_timeout(400)

    # ----- CloudWAV adds, edits and hides perks
    role(pg, "operator"); nav(pg, "startup-perks"); pg.wait_for_timeout(300)
    ok(pg.locator("[data-perk-partner-note]").count() == 1, "CloudWAV sees which offers grow through a partner")
    pg.click("[data-perk-new]"); pg.wait_for_timeout(150)
    pg.click("[data-perk-save]"); pg.wait_for_timeout(150)
    ok(not pg.locator("#perkErr").is_hidden(), "Company and offer are required")
    pg.fill("#perkProvider", "Linear"); pg.fill("#perkProgram", "Linear for Startups"); pg.select_option("#perkCat", "productivity")
    pg.fill("#perkValue", "6 months free on the Business plan"); pg.fill("#perkWho", "Early-stage startups"); pg.fill("#perkUrl", "linear.app/startups")
    pg.fill("#perkSources", "https://linear.app/startups"); pg.click("[data-perk-save]"); pg.wait_for_timeout(200)
    x = [p2 for p2 in perks(pg) if p2["provider"] == "Linear"]
    ok(x and x[0]["url"] == "https://linear.app/startups" and x[0]["category"] == "productivity" and not x[0]["hidden"], "CloudWAV adds a perk")
    pg.click(f'[data-perk-open="{x[0]["id"]}"]'); pg.wait_for_timeout(200)
    pg.click(f'[data-perk-detail] [data-perk-hide="{x[0]["id"]}"]'); pg.wait_for_timeout(200)
    ok([p2 for p2 in perks(pg) if p2["id"] == x[0]["id"]][0]["hidden"], "...and can hide it")
    pg.click("[data-perk-close]"); pg.wait_for_timeout(150)
    role(pg, "partner"); nav(pg, "startup-perks"); pg.wait_for_timeout(300)
    ok(x[0]["id"] not in cards(pg), "Members don't see hidden perks")
    pg.reload(); pg.wait_for_timeout(600); role(pg, "operator"); nav(pg, "startup-perks"); pg.wait_for_timeout(300)
    ok(x[0]["id"] in cards(pg), "Perks are kept after reloading")
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0, "Fits a phone")
    b.close()
report()
