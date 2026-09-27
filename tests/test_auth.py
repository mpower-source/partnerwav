from harness import *

USERS = {
    "ops@cloudwav.test":        {"password": "op-pass-123",  "id": "11111111-0000-0000-0000-000000000001"},
    "vendor@intelsense.test":   {"password": "vend-pass-123", "id": "11111111-0000-0000-0000-000000000002"},
    "partner@siamdigital.test": {"password": "part-pass-123", "id": "11111111-0000-0000-0000-000000000003"},
    "aff@techbridge.test":      {"password": "aff-pass-123", "id": "11111111-0000-0000-0000-000000000004"},
    "norole@example.test":      {"password": "none-pass-123", "id": "11111111-0000-0000-0000-000000000005"},
}
PORTAL = {
    USERS["ops@cloudwav.test"]["id"]:        {"role": "operator", "entity_id": None, "display_name": "Peter Phelan"},
    USERS["vendor@intelsense.test"]["id"]:   {"role": "vendor", "entity_id": "intelsense", "display_name": "Intelsense Admin"},
    USERS["partner@siamdigital.test"]["id"]: {"role": "partner", "entity_id": "siam-digital", "display_name": "Somchai K."},
    USERS["aff@techbridge.test"]["id"]:      {"role": "affiliate", "entity_id": "techbridge-aff", "display_name": "TechBridge Affiliates"},
}

def login(pg, email, pw):
    pg.fill("#loginEmail", email); pg.fill("#loginPassword", pw)
    pg.click("#loginSubmit"); pg.wait_for_timeout(700)

with sync_playwright() as p:
    mock = MockSupabase(USERS, PORTAL)
    b, ctx, pg = open_page_supabase(p, mock)

    # --- locked until signed in
    ok(pg.locator("#loginScreen").is_visible(), "Sign-in screen shown without demo mode")
    ok(not pg.locator(".shell").is_visible(), "Portal hidden until signed in")
    ok(pg.evaluate("typeof window.supabase.createClient") == "function", "Real supabase-js v2 loaded")

    # --- errors
    pg.click("#loginSubmit"); pg.wait_for_timeout(150)
    ok("Enter your email and password" in pg.inner_text("#loginError"), "Empty form -> message")
    login(pg, "vendor@intelsense.test", "wrong")
    ok("don't match an account" in pg.inner_text("#loginError"), "Wrong password -> friendly error")
    ok(pg.locator("#loginScreen").is_visible(), "Still locked after failed sign-in")

    # --- vendor sign-in
    login(pg, "vendor@intelsense.test", "vend-pass-123")
    ok(not pg.locator("#loginScreen").is_visible() and pg.locator(".shell").is_visible(), "Vendor signs in")
    ok(visible_screen(pg) == ["scr-vendor-overview"], "Lands on vendor overview")
    ok(not pg.locator(".role-switch").is_visible(), "Role switcher hidden when signed in")
    ok(pg.inner_text("#accountBtn") == "IA", "Avatar shows account initials: " + pg.inner_text("#accountBtn"))
    rest_calls = [c for c in mock.calls if c[1] == "/rest/v1/portal_users"]
    ok(rest_calls and mock.uid_from_auth(rest_calls[-1][2]) == USERS["vendor@intelsense.test"]["id"], "Role looked up with the user's own session token")
    pg.click("#accountBtn"); pg.wait_for_timeout(100)
    meta = pg.inner_text("#accountMeta")
    ok("Vendor" in meta and "Intelsense AI" in meta and "vendor@intelsense.test" in meta, "Account menu: " + meta)
    pg.click("#accountBtn"); pg.wait_for_timeout(100)

    # --- vendor profile edit / save
    nav(pg, "vendor-network")
    pg.locator('[data-view-vendor="botnoi"]:visible').first.click(); pg.wait_for_timeout(200)
    vp = pg.locator("#vendorProfileContent")
    ok(vp.locator("[data-edit-vendor-profile]").count() == 0, "No Edit on another vendor's profile")
    pg.click("[data-back-vendor-network]"); pg.wait_for_timeout(150)
    pg.locator('[data-view-vendor="intelsense"]:visible').first.click(); pg.wait_for_timeout(200)
    ok(vp.locator('[data-edit-vendor-profile="intelsense"]').count() == 1, "Own profile shows Edit profile")
    vp.locator("[data-edit-vendor-profile]").click(); pg.wait_for_timeout(200)
    ok(pg.locator("#vpName").input_value() == "Intelsense AI" and pg.locator("[data-vendor-edit-save]").count() == 2, "Edit mode: form pre-filled, Save shown")
    pg.fill("#vpName", ""); pg.locator("[data-vendor-edit-save]").first.click(); pg.wait_for_timeout(150)
    ok("Company name is required" in pg.inner_text("#vpError"), "Blank name blocked")
    pg.fill("#vpName", "Intelsense AI"); pg.fill("#vpWebsite", "intelsense.ai"); pg.locator("[data-vendor-edit-save]").first.click(); pg.wait_for_timeout(150)
    ok("full web address for Website" in pg.inner_text("#vpError"), "Bad URL blocked")
    pg.fill("#vpWebsite", "https://intelsense.ai")
    pg.fill("#vpDesc", "Conversational-AI platform for enterprise support automation across South and Southeast Asia.")
    pg.fill('[data-vp-prod-name="1"]', "Finsense AI Pro")
    pg.locator("[data-vendor-edit-save]").last.click(); pg.wait_for_timeout(250)
    txt = vp.inner_text()
    ok("South and Southeast Asia" in txt and "Finsense AI Pro" in txt and vp.locator("#vpName").count() == 0, "Save exits edit mode and shows changes")
    # cancel discards
    vp.locator("[data-edit-vendor-profile]").click(); pg.wait_for_timeout(150)
    pg.fill("#vpDesc", "SHOULD NOT SAVE"); pg.click("[data-vendor-edit-cancel]"); pg.wait_for_timeout(150)
    ok("SHOULD NOT SAVE" not in vp.inner_text() and "South and Southeast Asia" in vp.inner_text(), "Cancel discards changes")

    # --- session persists on reload; edits persist
    pg.reload(); pg.wait_for_timeout(1000)
    ok(pg.locator(".shell").is_visible() and visible_screen(pg) == ["scr-vendor-overview"], "Still signed in after reload")
    nav(pg, "vendor-network"); pg.locator('[data-view-vendor="intelsense"]:visible').first.click(); pg.wait_for_timeout(200)
    ok("South and Southeast Asia" in pg.inner_text("#vendorProfileContent"), "Profile edits persist after reload")

    # --- sign out
    pg.click("#accountBtn"); pg.click("#signOutBtn"); pg.wait_for_timeout(1000)
    ok(pg.locator("#loginScreen").is_visible() and not pg.locator(".shell").is_visible(), "Sign out returns to sign-in")
    pg.reload(); pg.wait_for_timeout(900)
    ok(pg.locator("#loginScreen").is_visible(), "Stays signed out after reload")

    # --- partner / operator / affiliate
    login(pg, "partner@siamdigital.test", "part-pass-123")
    ok(visible_screen(pg) == ["scr-partner-overview"], "Partner lands on partner overview")
    nav(pg, "partner-network")
    mine = pg.locator("#networkGrid .program-card").filter(has_text="You")
    ok(mine.count() == 1 and "Siam Digital MSP" in mine.inner_text(), "Partner account linked to Siam Digital profile")
    pg.click("#accountBtn"); pg.click("#signOutBtn"); pg.wait_for_timeout(1000)
    login(pg, "ops@cloudwav.test", "op-pass-123")
    ok(visible_screen(pg) == ["scr-operator-overview"], "Operator lands on operator overview")
    pg.click("#accountBtn"); pg.wait_for_timeout(100)
    ok("Program Operator" in pg.inner_text("#accountMeta"), "Operator account menu")
    pg.click("#signOutBtn"); pg.wait_for_timeout(1000)
    login(pg, "aff@techbridge.test", "aff-pass-123")
    ok(visible_screen(pg) == ["scr-affiliate-overview"], "Affiliate lands on affiliate overview")
    pg.click("#accountBtn"); pg.wait_for_timeout(100)
    ok("TechBridge Solutions" in pg.inner_text("#accountMeta"), "Affiliate linked to TechBridge")
    pg.click("#signOutBtn"); pg.wait_for_timeout(1000)

    # --- vendor can't edit someone else's profile even as operator
    # --- account without a role
    login(pg, "norole@example.test", "none-pass-123")
    ok(pg.locator("#loginPanelNoAccount").is_visible() and "norole@example.test" in pg.inner_text("#noAccountText"), "Account without a role -> 'not set up yet'")
    ok(not pg.locator(".shell").is_visible(), "No-role account can't see the portal")
    pg.click("#noAccountSignOut"); pg.wait_for_timeout(1000)
    ok(pg.locator("#loginPanelSignIn").is_visible(), "Sign out from no-account screen")

    # --- forgot password
    pg.click("#forgotPasswordBtn"); pg.wait_for_timeout(150)
    ok("Enter your email above" in pg.inner_text("#loginError"), "Forgot password asks for email first")
    pg.fill("#loginEmail", "partner@siamdigital.test"); pg.click("#forgotPasswordBtn"); pg.wait_for_timeout(500)
    ok("reset link is on its way" in pg.inner_text("#loginInfo") and any(c[1] == "/auth/v1/recover" for c in mock.calls), "Reset email requested")

    # --- mobile
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0, "Sign-in fits at 390px")
    ctx.close(); b.close()

    # --- sign-in service unreachable (CDN blocked, no demo)
    b = p.chromium.launch(); pg = b.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(800)
    ok(pg.locator("#loginScreen").is_visible() and "Can't reach the sign-in service" in pg.inner_text("#loginError"), "Clear message when sign-in service is unreachable")
    b.close()
report()
