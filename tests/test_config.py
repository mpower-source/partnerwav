from harness import *

def open_config(pg, pid):
    pg.click(f'#operatorProgramRows [data-configure="{pid}"]'); pg.wait_for_timeout(250)

with sync_playwright() as p:
    b, pg = open_page(p)
    role(pg, "operator"); nav(pg, "operator-programs")
    rows = pg.locator("#operatorProgramRows tr")
    ok(rows.count() >= 6, "Manage programs lists every program")
    intel = rows.filter(has_text="Intelsense AI")
    ok("Reseller: 15% + 5%" in intel.inner_text(), "Commission column shows current rate")

    # --- opens a real screen pre-filled from the current listing
    open_config(pg, "intelsense")
    ok(visible_screen(pg) == ["scr-operator-program-config"], "Configure opens the configuration screen")
    t = pg.locator("[data-cfg-tier]")
    ok(t.count() == 2, "Both Intelsense tiers loaded")
    ok(t.nth(0).locator(".cfg-t-fy").input_value() == "15" and t.nth(0).locator(".cfg-t-ren").input_value() == "5", "Reseller parsed to 15 / 5")
    ok(t.nth(1).locator(".cfg-t-ovr").input_value() == "5", "Channel Manager override parsed to 5")
    ok(pg.input_value("#cfgAgreementType") == "Vendor Program Agreement" and pg.input_value("#cfgRevenueBase") == "net", "Agreement type + Net Revenue base loaded")
    ok(pg.locator("[data-cfg-remove-deduction]").count() == 3, "Default itemized deductions shown")
    ok(pg.locator("[data-cfg-product]").count() == 4, "Per-product rates for all 4 Intelsense products")

    # --- live preview
    t.nth(0).locator(".cfg-t-fy").fill("18"); pg.wait_for_timeout(100)
    ok("18% + 5%" in pg.inner_text("#cfgPreview"), "Preview updates live: " + pg.inner_text("#cfgPreview").split("\n")[0])

    # --- validation
    t.nth(0).locator(".cfg-t-fy").fill("150")
    pg.locator("[data-config-save]").first.click(); pg.wait_for_timeout(150)
    ok("between 0 and 100" in pg.inner_text("#cfgError"), "Rejects % over 100")
    ok(visible_screen(pg) == ["scr-operator-program-config"], "Stays on screen when invalid")
    t.nth(0).locator(".cfg-t-fy").fill("18")
    for _ in range(3): pg.locator("[data-cfg-remove-deduction]").first.click(); pg.wait_for_timeout(80)
    pg.locator("[data-config-save]").first.click(); pg.wait_for_timeout(150)
    ok("itemized" in pg.inner_text("#cfgError"), "Net Revenue requires itemized deductions (§5.4)")
    pg.fill("#cfgNewDeduction", "Refunds and chargebacks"); pg.press("#cfgNewDeduction", "Enter"); pg.wait_for_timeout(100)
    pg.fill("#cfgNewDeduction", "Payment processing fees"); pg.click("[data-cfg-add-deduction]"); pg.wait_for_timeout(100)
    pg.fill("#cfgNewDeduction", "payment PROCESSING fees"); pg.click("[data-cfg-add-deduction]"); pg.wait_for_timeout(100)
    ok(pg.locator("[data-cfg-remove-deduction]").count() == 2, "Deductions added (button + Enter), duplicate rejected")
    ok(pg.locator("[data-cfg-tier]").nth(0).locator(".cfg-t-fy").input_value() == "18", "Typed values survive re-render")

    # --- add a tier, set agreement parameters, per-product rate
    pg.click("[data-cfg-add-tier]"); pg.wait_for_timeout(100)
    new = pg.locator("[data-cfg-tier]").nth(2)
    new.locator(".cfg-t-name").fill("Affiliate"); new.locator(".cfg-t-fy").fill("10"); new.locator(".cfg-t-base").fill("Gross revenue")
    pg.select_option("#cfgAgreementStatus", "sent"); pg.fill("#cfgEffectiveDate", "2026-10-01")
    pg.select_option("#cfgCurrency", "THB"); pg.wait_for_timeout(100)
    ok("(THB)" in pg.inner_text("#scr-operator-program-config"), "Currency change updates minimum payout label")
    pg.select_option("#cfgPayoutSchedule", "Every 45 days")
    pg.fill("#cfgInstallerMargin", "8"); pg.fill("#cfgProtectionDays", "120"); pg.fill("#cfgNoticeDays", "45")
    pg.uncheck("#cfgProServices")
    pg.locator('[data-cfg-product="finsense-ai"] .cfg-p-fy').fill("20")
    prev = pg.inner_text("#cfgPreview")
    ok("Affiliate" in prev and "10%" in prev and "Finsense AI" in prev and "20% + 18%" not in prev, "Preview shows new tier and product rate")

    pg.locator("[data-config-save]").last.click(); pg.wait_for_timeout(250)
    ok(visible_screen(pg) == ["scr-operator-programs"], "Save returns to Manage programs")
    intel = pg.locator("#operatorProgramRows tr").filter(has_text="Intelsense AI")
    ok("Reseller: 18% + 5%" in intel.inner_text() and "Configured" in intel.inner_text(), "Table shows new rate + configured stamp")

    # --- flows through to what partners see
    nav(pg, "vendor-network"); pg.locator('[data-view-vendor="intelsense"]:visible').first.click(); pg.wait_for_timeout(200)
    vp = pg.inner_text("#vendorProfileContent")
    ok("18% + 5%" in vp and "15% + 5% + 5% override" in vp and "Affiliate" in vp and "10%" in vp, "Vendor profile shows the configured tiers")

    # --- reopen: values kept
    nav(pg, "operator-programs"); open_config(pg, "intelsense")
    ok(pg.input_value("#cfgAgreementStatus") == "sent" and pg.input_value("#cfgEffectiveDate") == "2026-10-01"
       and pg.input_value("#cfgCurrency") == "THB" and pg.input_value("#cfgInstallerMargin") == "8"
       and pg.input_value("#cfgProtectionDays") == "120" and pg.input_value("#cfgNoticeDays") == "45"
       and not pg.is_checked("#cfgProServices"), "Reopening shows saved agreement parameters")
    ok(pg.locator('[data-cfg-product="finsense-ai"] .cfg-p-fy').input_value() == "20", "Per-product rate saved")
    ok("Last saved" in pg.inner_text("#scr-operator-program-config"), "Shows last-saved stamp")

    # --- cancel discards
    pg.locator("[data-cfg-tier]").nth(0).locator(".cfg-t-fy").fill("30")
    pg.locator("[data-config-cancel]").first.click(); pg.wait_for_timeout(200)
    ok("Reseller: 18% + 5%" in pg.locator("#operatorProgramRows tr").filter(has_text="Intelsense AI").inner_text(), "Cancel discards unsaved changes")

    # --- non-standard rates survive the round trip
    open_config(pg, "crossconnect")
    ct = pg.locator("[data-cfg-tier]").nth(0)
    ok(ct.locator(".cfg-t-fy").input_value() == "12" and "hardware sale" in ct.locator(".cfg-t-note").input_value(), "Cross Connect '12% on hardware sale...' parsed to 12 + note")
    ok(pg.input_value("#cfgRevenueBase") == "gross", "Gross base detected from 'Gross sale price'")
    pg.locator("[data-config-save]").first.click(); pg.wait_for_timeout(200)
    ok("Affiliate: 12% on hardware sale + attach bonus" in pg.locator("#operatorProgramRows tr").filter(has_text="Cross Connect").inner_text(), "Unchanged rate text preserved on save")

    # --- persistence
    pg.reload(); pg.wait_for_timeout(700)
    role(pg, "operator"); nav(pg, "operator-programs")
    ok("Reseller: 18% + 5%" in pg.locator("#operatorProgramRows tr").filter(has_text="Intelsense AI").inner_text(), "Configuration persists after reload")

    # --- only operators
    role(pg, "vendor"); nav(pg, "vendor-network")
    ok(pg.locator("[data-configure]:visible").count() == 0, "No Configure outside the operator workspace")

    # --- mobile
    role(pg, "operator"); nav(pg, "operator-programs"); open_config(pg, "intelsense")
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0, "No horizontal overflow at 390px")
    b.close()
report()
