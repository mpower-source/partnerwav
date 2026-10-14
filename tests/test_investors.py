from harness import *
from ir_helpers import fill_readiness
import os, json

# Investors: a fifth login type with its own workspace. Companies choose to show their round to investors;
# investors ask PartnerWAV for introductions; CloudWAV makes them. Role buttons: Partner, Vendor, Affiliate,
# Investor, with Operator as its own row for CloudWAV.
def inv(pg): return json.loads(pg.evaluate("localStorage.getItem('partnerWAV_investors')") or "{}")

with sync_playwright() as p:
    b, pg = open_page(p)
    labels = pg.evaluate("[...document.querySelectorAll('.role-btn')].map(b => b.textContent.trim())")
    ok(labels == ["Partner", "Vendor", "Affiliate", "Investor", "Member", "Promoter", "Operator (CloudWAV)"], "Role buttons: " + ", ".join(labels))
    role(pg, "investor"); pg.wait_for_timeout(200)
    ok(visible_screen(pg) == ["scr-investor-overview"] and pg.get_attribute('[data-role="investor"]', "aria-pressed") == "true", "Investor opens the investor workspace, its button highlighted")
    ov = pg.inner_text("#investorOverviewContent")
    ok("Companies raising now" in ov and "Example SaaS Co" in ov, "The overview shows companies raising")
    # a company passes the readiness check, PartnerWAV approves it, then it shows its round
    role(pg, "vendor"); nav(pg, "vendor-overview"); pg.click("[data-funding-edit]"); pg.wait_for_timeout(150)
    ok(pg.locator("[data-funding-readiness]").count() == 1 and pg.locator("#fundShowInvestors").count() == 0, "The investment round points to the readiness check instead of a tick box")
    pg.click("[data-funding-cancel]")
    nav(pg, "investor-readiness"); pg.wait_for_timeout(200)
    fill_readiness(pg, ready=True)
    ok(pg.locator('[data-ir-result="ready"]').count() == 1, "The vendor is investor-ready")
    pg.click("[data-ir-submit]"); pg.wait_for_timeout(200)
    me = json.loads(pg.evaluate("localStorage.getItem('partnerWAV_investorReadiness')"))[0]["id"]
    role(pg, "operator"); nav(pg, "operator-investors"); pg.click('[data-oi-tab="readiness"]'); pg.wait_for_timeout(200)
    pg.locator(f'[data-ir-approve="{me}"]').click(); pg.wait_for_timeout(200)
    role(pg, "vendor"); nav(pg, "investor-readiness"); pg.wait_for_timeout(200)
    pg.check("[data-ir-list]"); pg.wait_for_timeout(300)
    lst = [l for l in inv(pg).get("listings", []) if l["id"] == me]
    ok(lst and lst[0]["round"] == "Seed" and lst[0]["target"] == "USD 1.5M" and lst[0]["reviewed"] and "deckUrl" not in json.dumps(lst[0]), "Showing the round creates a reviewed investor card, without the deck link")

    # the investor sees it and asks for an introduction
    role(pg, "investor"); nav(pg, "investor-deals"); pg.wait_for_timeout(300)
    card = pg.locator(f'#investorDealsContent [data-inv-listing="{me}"]')
    ok(card.count() == 1 and "USD 1.5M" in card.inner_text() and "Reviewed by PartnerWAV" in card.text_content(), "The investor sees the company's reviewed round")
    card.locator("[data-ir-ask]").click(); pg.wait_for_timeout(200)
    pg.fill("#irNote", "Interested in AI for SMEs"); pg.click("[data-ir-send]"); pg.wait_for_timeout(300)
    irs = inv(pg)["intros"]
    ok(len(irs) == 1 and irs[0]["listingId"] == me and irs[0]["status"] == "requested" and irs[0]["investorId"] == "beacon-vc", "The introduction request goes to PartnerWAV")
    ok("Waiting for PartnerWAV" in card.inner_text(), "The card shows it's waiting")
    nav(pg, "investor-intros"); pg.wait_for_timeout(200)
    ok("Interested in AI for SMEs" in pg.inner_text("#investorIntrosContent"), "My Introductions lists it")
    # profile
    nav(pg, "investor-profile"); pg.wait_for_timeout(200)
    pg.fill("#invTicket", "USD 250K - 2M"); pg.click('[data-inv-stage="Grants"]'); pg.click("[data-inv-save]"); pg.wait_for_timeout(200)
    prof = [x for x in inv(pg)["profiles"] if x["id"] == "beacon-vc"][0]
    ok(prof["ticket"] == "USD 250K - 2M" and "Grants" in prof["stages"], "The investor edits its profile")
    # investors only message PartnerWAV
    nav(pg, "partner-messages"); pg.wait_for_timeout(200)
    to = pg.evaluate("[...document.querySelectorAll('#msgNewTo option')].map(o => o.value).filter(Boolean)")
    ok(to == ["operator:"], "Investors message PartnerWAV only: " + str(to))
    nav(pg, "calendar"); pg.wait_for_timeout(200)
    ok(visible_screen(pg) == ["scr-calendar"], "Investors have Events & Calendar")

    # CloudWAV: Investors screen
    role(pg, "operator"); nav(pg, "operator-investors"); pg.click('[data-oi-tab="intros"]'); pg.wait_for_timeout(300)
    row = pg.locator(f'[data-oi-ir="{irs[0]["id"]}"]')
    ok(row.count() == 1 and "Beacon VC" in row.inner_text(), "CloudWAV sees the request")
    pg.fill(f'#oiReply-{irs[0]["id"]}', "Intro email sent to the founders"); row.locator("[data-oi-introduced]").click(); pg.wait_for_timeout(200)
    ok(inv(pg)["intros"][0]["status"] == "introduced", "CloudWAV marks it introduced")
    pg.click('[data-oi-tab="investors"]'); pg.click("[data-oi-new]"); pg.fill("#oiName", "Bangkok Angels"); pg.click("[data-oi-create]"); pg.wait_for_timeout(200)
    new = [x for x in inv(pg)["profiles"] if x["name"] == "Bangkok Angels"]
    ok(new and new[0].get("needsProfile"), "CloudWAV adds an investor")
    pg.locator(f'[data-oi-inv="{new[0]["id"]}"] [data-acct-setup="investor"]').click(); pg.wait_for_timeout(200)
    ok(pg.locator("#acctEmail").is_visible(), "...and sets up their login from there")
    pg.click("[data-acct-close]"); pg.wait_for_timeout(100)
    nav(pg, "operator-accounts"); pg.wait_for_timeout(300)
    pg.locator("[data-acct-any]").first.click(); pg.wait_for_timeout(200)
    opts = pg.evaluate("[...document.querySelectorAll('#acctRole option')].map(o => o.textContent)")
    ok(opts == ["Partner", "Vendor", "Affiliate", "Investor", "Member", "Promoter"], "New logins: " + ", ".join(opts))
    pg.click("[data-acct-close]")
    # phone
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    role(pg, "investor"); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0, "The investor workspace fits a phone")
    b.close()

    # ----- signed in: your own account type is highlighted, the others greyed out
    UID = "11111111-0000-0000-0000-000000000009"
    mock = MockSupabase({"vc@fund.test": {"password": "inv-pass-123", "id": UID}}, {UID: {"role": "investor", "entity_id": "seed-fund", "display_name": "Seed Fund"}})
    b, ctx, pg = open_page_supabase(p, mock)
    pg.fill("#loginEmail", "vc@fund.test"); pg.fill("#loginPassword", "inv-pass-123"); pg.click("#loginSubmit"); pg.wait_for_timeout(1500)
    ok(visible_screen(pg) == ["scr-investor-overview"], "An investor login opens the investor workspace")
    st = pg.evaluate("[...document.querySelectorAll('.role-btn')].map(b => [b.dataset.role, b.getAttribute('aria-pressed'), b.disabled, !!b.offsetParent])")
    ok(pg.locator(".role-switch").is_visible(), "Signed-in members see the role buttons")
    ok([x for x in st if x[1] == "true"] == [["investor", "true", False, True]], "...their own type highlighted: " + str(st))
    ok(all(x[2] for x in st if x[0] in ("partner", "vendor", "affiliate")) and not [x for x in st if x[0] == "operator" and x[3]], "...the others greyed out, and no Operator button")
    pg.locator('[data-role="partner"]').click(force=True); pg.wait_for_timeout(200)
    ok(visible_screen(pg) == ["scr-investor-overview"], "A greyed-out type can't be opened")
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    pg.click("#mnavToggle"); pg.wait_for_timeout(200)
    ok(pg.locator('[data-role="investor"]').is_visible() and pg.get_attribute('[data-role="investor"]', "aria-pressed") == "true", "On a phone the menu shows the same buttons, Investor highlighted")
    b.close()
report()
