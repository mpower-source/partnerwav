from harness import *

with sync_playwright() as p:
    b, pg = open_page(p)
    # partner: Botnoi's View details lists Reseller, then Channel Manager, then Joint Venture
    nav(pg, "partner-directory")
    pg.locator('#directoryGrid [data-detail="botnoi"]').click(); pg.wait_for_timeout(300)
    lines = [l.inner_text().split("·")[0].strip() for l in pg.locator(".modal .tier-line").all()][:3]
    ok(lines == ["Reseller", "Channel Manager", "Joint Venture"], "View details order: " + ", ".join(lines))
    ok("Enroll as Reseller" in pg.inner_text(".modal"), "Partners enroll as Reseller first")
    pg.click(".modal .modal-close"); pg.wait_for_timeout(150)

    # partners can't edit tiers on the profile
    nav(pg, "vendor-network") if pg.locator('[data-screen="vendor-network"]:visible').count() else None
    role(pg, "vendor"); nav(pg, "vendor-network"); pg.locator('[data-view-vendor="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    sec = pg.locator("#vendorTiersSection")
    ok(sec.locator("[data-tier-edit-open]").count() == 0 and "message PartnerWAV" in sec.inner_text(), "Vendor sees its tiers (read-only, change through CloudWAV)")
    ok("Reseller" in sec.inner_text() and "Channel Manager" in sec.inner_text(), "Intelsense tiers listed on its profile")

    # CloudWAV edits Botnoi's offerings from the profile
    role(pg, "operator"); nav(pg, "vendor-network"); pg.locator('[data-view-vendor="botnoi"]:visible').first.click(); pg.wait_for_timeout(300)
    sec = pg.locator("#vendorTiersSection")
    ok([r.inner_text().split("·")[0].strip() for r in sec.locator("[data-tier-row]").all()] == ["Reseller", "Channel Manager", "Joint Venture"], "Botnoi profile lists Reseller, Channel Manager, Joint Venture")
    sec.locator("[data-tier-edit-open]").click(); pg.wait_for_timeout(250)
    ok(pg.locator("[data-tier-edit]").count() == 3 and pg.is_checked('[data-tier-rel="Joint Venture"]'), "Editor opens with the three offerings and relationship types")
    pg.fill('[data-tier-rate="0"]', "20% + 5%")
    pg.click('[data-tier-add]'); pg.wait_for_timeout(200)
    ok(pg.input_value('[data-tier-rate="0"]') == "20% + 5%" and pg.locator("[data-tier-edit]").count() == 4, "Typed values survive adding a row")
    pg.fill('[data-tier-name="3"]', "Referral"); pg.click('[data-tier-save="botnoi"]'); pg.wait_for_timeout(200)
    ok("needs its commission" in pg.inner_text("#tierEditError"), "Each offering needs its terms")
    pg.fill('[data-tier-rate="3"]', "10% one-time"); pg.fill('[data-tier-base="3"]', "First-year net revenue")
    pg.click('[data-tier-move="3"][data-dir="-1"]'); pg.wait_for_timeout(200)
    pg.check('[data-tier-rel="SaaS Resale"]')
    pg.click('[data-tier-save="botnoi"]'); pg.wait_for_timeout(300)
    names = [r.inner_text().split("·")[0].strip() for r in pg.locator("#vendorTiersSection [data-tier-row]").all()]
    ok(names == ["Reseller", "Channel Manager", "Referral", "Joint Venture"], "Saved in the new order: " + ", ".join(names))
    ok("20% + 5%" in pg.inner_text("#vendorTiersSection") and "SAAS RESALE" in pg.inner_text("#vendorTiersSection").upper(), "New rate and relationship type saved")
    # Configure program sees the same tiers
    nav(pg, "operator-programs"); pg.click('[data-configure="botnoi"]'); pg.wait_for_timeout(300)
    ok(pg.locator("#scr-operator-program-config").inner_text().count("Referral") >= 1, "Configure program uses the edited tiers")
    pg.click("[data-config-cancel]"); pg.wait_for_timeout(150)
    pg.reload(); pg.wait_for_timeout(700)
    role(pg, "partner"); nav(pg, "partner-directory"); pg.locator('#directoryGrid [data-detail="botnoi"]').click(); pg.wait_for_timeout(300)
    lines = [l.inner_text().split("·")[0].strip() for l in pg.locator(".modal .tier-line").all()][:4]
    ok(lines == ["Reseller", "Channel Manager", "Referral", "Joint Venture"] and "20% + 5%" in pg.inner_text(".modal"), "Kept after reload, and partners see it")
    pg.click(".modal .modal-close")

    # an older saved copy (only the JV tier) is re-ordered once
    pg.evaluate("""localStorage.setItem('partnerWAV_programTerms', JSON.stringify({ botnoi: { terms: null, tiers:[{tier:'Channel Manager', rate:'Per JV profit-allocation schedule', base:'Per Joint Venture Agreement, Schedule C'}], agreement:{type:'Joint Venture Agreement', status:'pending'}, status:'onboarding' } }))""")
    pg.reload(); pg.wait_for_timeout(700)
    nav(pg, "partner-directory"); pg.locator('#directoryGrid [data-detail="botnoi"]').click(); pg.wait_for_timeout(300)
    lines = [l.inner_text().split("·")[0].strip() for l in pg.locator(".modal .tier-line").all()][:3]
    ok(lines == ["Reseller", "Channel Manager", "Joint Venture"] and "Per JV profit-allocation" in pg.inner_text(".modal"), "Older saved Botnoi program is updated to the new order")
    b.close()
report()
