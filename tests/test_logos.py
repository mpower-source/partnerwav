from harness import *
import tempfile, struct, zlib

def png(path, rgb):
    w = h = 64
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    return path
T = tempfile.mkdtemp()
RED, GREEN, BLUE, GOLD = png(T+"/red.png", (220,30,30)), png(T+"/green.png", (30,180,60)), png(T+"/blue.png", (30,60,220)), png(T+"/gold.png", (230,180,20))

def pick(pg, prefix, path):
    with pg.expect_file_chooser() as fc:
        pg.click(f'[data-browse-logo="{prefix}"]')
    fc.value.set_files(path); pg.wait_for_timeout(400)

with sync_playwright() as p:
    b, pg = open_page(p)

    # --- vendor: company logo + a product logo from the Vendor Network profile
    role(pg, "vendor"); nav(pg, "vendor-network")
    pg.locator('[data-view-vendor="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    pg.locator('[data-edit-vendor-profile="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    ok(pg.locator("#vpLogoPreview").count() == 1 and pg.locator("#vpProd0LogoPreview").count() == 1, "Vendor edit form has company + product logo pickers")
    pick(pg, "vp", RED)
    ok(pg.locator("#vpLogoPreview img").count() == 1 and pg.input_value("#vpLogo").startswith("data:image/"), "Company logo uploads + previews")
    pick(pg, "vpProd1", BLUE)
    ok(pg.locator("#vpProd1LogoPreview img").count() == 1, "Product logo uploads + previews")
    pg.locator('[data-vendor-edit-save="intelsense"]').first.click(); pg.wait_for_timeout(400)
    tile = pg.locator('[data-product-tile="finsense-ai"]')
    ok(tile.locator("img.entity-logo-img").count() == 1, "Product tile shows its logo")
    ok(pg.locator('[data-product-tile="unisense-ai"] img.entity-logo-img').count() == 0 and pg.locator('[data-product-tile="unisense-ai"] .entity-logo-fallback').count() == 1, "Products without a logo show initials")
    ok(pg.locator("#vendorProfileContent .profile-header img.entity-logo-img").count() >= 1, "Company logo on the profile")
    # remove product logo again works
    pg.locator('[data-edit-vendor-profile="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    ok(pg.locator("#vpProd1LogoPreview img").count() == 1, "Saved product logo loads back into the editor")

    # --- vendor: My Program Listing logo is now saved across reloads
    pg.locator('[data-vendor-edit-cancel]').first.click(); pg.wait_for_timeout(200)
    pg.reload(); pg.wait_for_timeout(700); role(pg, "vendor"); nav(pg, "vendor-network")
    pg.locator('[data-view-vendor="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    ok(pg.locator('[data-product-tile="finsense-ai"] img.entity-logo-img').count() == 1 and pg.locator("#vendorProfileContent .profile-header img.entity-logo-img").count() >= 1, "Vendor + product logos persist after reload")

    # --- partner: My Profile edits their own profile (demo partner = Siam Digital MSP), with a logo
    role(pg, "partner"); nav(pg, "partner-profile-editor"); pg.wait_for_timeout(300)
    ok(pg.input_value("#profileName") == "Siam Digital MSP" and "Edit" in pg.inner_text("#profileEditorTitle"), "Partner My Profile opens their own profile")
    pick(pg, "pe", GREEN)
    ok(pg.locator("#peLogoPreview img").count() == 1, "Partner logo uploads + previews")
    pg.click('#partnerProfileForm button[type=submit]'); pg.wait_for_timeout(400)
    nav(pg, "partner-network"); pg.wait_for_timeout(300)
    card = pg.locator(".program-card").filter(has_text="Siam Digital MSP").first
    ok(card.locator("img.entity-logo-img").count() == 1, "Partner logo shows in the Partner Network")
    nav(pg, "partner-profile-editor"); pg.wait_for_timeout(300)
    ok(pg.locator("#peLogoPreview img").count() == 1, "Saved logo loads back into the editor")

    # --- affiliate: My Profile with a logo, persisted
    role(pg, "affiliate"); nav(pg, "affiliate-profile-editor"); pg.wait_for_timeout(300)
    ok(pg.input_value("#affiliateName") == "TechBridge Solutions" and "Edit" in pg.inner_text("#affiliateEditorTitle"), "Affiliate My Profile opens their own profile")
    pick(pg, "af", GOLD)
    ok(pg.locator("#afLogoPreview img").count() == 1, "Affiliate logo uploads + previews")
    pg.click('#affiliateProfileForm button[type=submit]'); pg.wait_for_timeout(400)
    pg.reload(); pg.wait_for_timeout(700); role(pg, "affiliate"); nav(pg, "affiliate-profile-editor"); pg.wait_for_timeout(300)
    ok(pg.locator("#afLogoPreview img").count() == 1, "Affiliate logo persists after reload")
    pg.click('[data-remove-logo="af"]'); pg.wait_for_timeout(100)
    ok(pg.locator("#afLogoPreview img").count() == 0 and pg.input_value("#afLogo") == "", "Remove clears the logo")

    # wrong file type
    bad = T + "/notes.txt"; open(bad, "w").write("hi")
    with pg.expect_file_chooser() as fc: pg.click('[data-browse-logo="af"]')
    fc.value.set_files(bad); pg.wait_for_timeout(300)
    ok("PNG, JPG, WEBP, or SVG" in pg.inner_text("#toast"), "Non-image rejected with guidance")

    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0, "No horizontal overflow at 390px")
    b.close()
report()
