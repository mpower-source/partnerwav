from harness import *
with sync_playwright() as p:
    b, pg = open_page(p)
    pg.context.grant_permissions(["clipboard-read", "clipboard-write"])
    for r in ("partner", "affiliate", "vendor"):
        role(pg, r)
        if pg.locator('[data-screen="affiliate-marketplace"]:visible').count() == 0: continue
        nav(pg, "affiliate-marketplace")
        tile = pg.locator('#affiliateMarketplaceGrid [data-direct-offer="lovable"]')
        ok(tile.count() == 1, r + ": Lovable tile in the Affiliate Marketplace")
        t = tile.inner_text()
        ok("Lovable" in t and "AI App Builder" in t.title() or "AI APP BUILDER" in t.upper(), r + ": name + category")
        ok("DIRECT OFFER FROM CLOUDWAV" in t.upper() and "extra 10 credits" in t, r + ": direct-offer badge + note")
        ok(tile.locator(".aff-link-input").input_value() == "https://lovable.dev/invite/DTIM5CC", r + ": invite link on the tile")
        ok(tile.locator('a:has-text("Open")').get_attribute("href") == "https://lovable.dev/invite/DTIM5CC", r + ": Open link")
    role(pg, "partner"); nav(pg, "affiliate-marketplace")
    tile = pg.locator('#affiliateMarketplaceGrid [data-direct-offer="lovable"]')
    lg = tile.locator("img.entity-logo-img")
    ok(lg.count() == 1 and lg.evaluate("i => i.naturalWidth") == 256, "Lovable logo on the tile")
    qr = tile.locator("[data-aff-qr] img")
    ok(qr.count() == 1 and qr.evaluate("i => i.naturalWidth") > 0, "QR code shown on the tile")
    with pg.expect_download() as dl:
        tile.locator('a:has-text("Download QR code")').click()
    import cv2
    path = dl.value.path(); img = cv2.imread(str(path))
    ok(dl.value.suggested_filename == "lovable-invite-qr.png" and cv2.QRCodeDetector().detectAndDecode(img)[0] == "https://lovable.dev/invite/DTIM5CC", "Downloaded QR scans to the invite link")
    tile.locator("[data-copy-direct]").click(); pg.wait_for_timeout(200)
    ok(pg.evaluate("navigator.clipboard.readText()") == "https://lovable.dev/invite/DTIM5CC", "Copy link copies the invite link")
    tile.locator("[data-enroll-affiliate]").click(); pg.wait_for_timeout(300)
    if visible_screen(pg) != ["scr-affiliate-manage"]:
        pg.locator('[data-manage-affiliate="lovable"]:visible').first.click(); pg.wait_for_timeout(300)
    ok(pg.locator("#affiliateManageContent [data-aff-qr] img").count() == 1, "QR code on the manage screen too")
    ok(pg.locator("#affiliateManageContent .aff-link-input").first.input_value() == "https://lovable.dev/invite/DTIM5CC", "Enrolled: 'Your affiliate link' is the Lovable invite link")
    role(pg, "operator"); nav(pg, "affiliate-marketplace") if pg.locator('[data-screen="affiliate-marketplace"]:visible').count() else None
    b.close()
report()
