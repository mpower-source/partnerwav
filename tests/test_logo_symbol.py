from harness import *
import os
F = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
def dims(pg, sel):
    return pg.evaluate("s => new Promise(r => { const i = new Image(); i.onload = () => r([i.naturalWidth, i.naturalHeight]); i.src = document.querySelector(s).value; })", sel)
def ink_share(pg, sel):
    # share of the square covered by non-white, non-transparent pixels
    return pg.evaluate("""s => new Promise(r => { const i = new Image(); i.onload = () => { const c = document.createElement('canvas'); c.width = i.naturalWidth; c.height = i.naturalHeight;
      const x = c.getContext('2d'); x.drawImage(i, 0, 0); const d = x.getImageData(0, 0, c.width, c.height).data; let n = 0;
      for (let k = 0; k < d.length; k += 4) if (d[k+3] > 40 && (d[k] < 200 || d[k+1] < 200 || d[k+2] < 200)) n++; r(n / (c.width * c.height)); }; i.src = document.querySelector(s).value; })""", sel)

with sync_playwright() as p:
    b, pg = open_page(p)
    role(pg, "vendor"); nav(pg, "vendor-overview"); pg.click("#vendorOverviewEditBtn"); pg.wait_for_timeout(300)
    ok(all(pg.locator(f"#vpProd{i}LogoPreview img").count() == 1 for i in range(4)), "Intelsense products start with their built-in symbols")
    # symbol + words PNG -> just the symbol
    pg.set_input_files("#vpLogoFile", os.path.join(F, "logo_symbol_words.png")); pg.wait_for_timeout(700)
    w, h = dims(pg, "#vpLogo")
    ok(w == h and w <= 256, f"Trimmed to a square symbol ({w}x{h})")
    ok(ink_share(pg, "#vpLogo") > 0.4, "The square is filled by the symbol, not tiny words")
    ok("Trimmed to the symbol" in pg.inner_text("#vpLogoNote"), "Says it kept just the symbol")
    icon = pg.input_value("#vpLogo")
    pg.click('#vpLogoNote [data-logo-use="full"]'); pg.wait_for_timeout(200)
    full = pg.input_value("#vpLogo")
    ok(full != icon and "Using the full logo" in pg.inner_text("#vpLogoNote"), "Can switch to the full logo")
    pg.click('#vpLogoNote [data-logo-use="icon"]'); pg.wait_for_timeout(200)
    ok(pg.input_value("#vpLogo") == icon, "...and back to the symbol")
    # SVG symbol + words -> symbol; full stays the original SVG
    pg.set_input_files("#vpProd1LogoFile", os.path.join(F, "logo_symbol_words.svg")); pg.wait_for_timeout(900)
    v = pg.input_value("#vpProd1Logo")
    ok(v.startswith("data:image/png") and "Trimmed to the symbol" in pg.inner_text("#vpProd1LogoNote"), "SVG with words: symbol kept as a sharp PNG")
    pg.click('#vpProd1LogoNote [data-logo-use="full"]'); pg.wait_for_timeout(200)
    ok(pg.input_value("#vpProd1Logo").startswith("data:image/svg+xml"), "Full logo keeps the original SVG")
    pg.click('#vpProd1LogoNote [data-logo-use="icon"]'); pg.wait_for_timeout(200)
    # plain square logo: unchanged behaviour, no note
    pg.set_input_files("#vpProd2LogoFile", os.path.join(F, "logo_square.png")); pg.wait_for_timeout(700)
    ok(pg.locator("#vpProd2LogoNote").count() == 0 and dims(pg, "#vpProd2Logo")[0] == 256, "A square logo is used as-is (no trimming)")
    # a symbol + name on a dark background (like Intelsense's product list)
    pg.set_input_files("#vpProd3LogoFile", os.path.join(F, "logo_dark_row.png")); pg.wait_for_timeout(700)
    ok("Trimmed to the symbol" in pg.inner_text("#vpProd3LogoNote"), "Works on a symbol + name on a dark background too")
    # remove clears the note
    pg.click('[data-remove-logo="vp"]'); pg.wait_for_timeout(150)
    ok(pg.locator("#vpLogoNote").count() == 0, "Remove clears it")
    pg.set_input_files("#vpLogoFile", os.path.join(F, "logo_symbol_words.png")); pg.wait_for_timeout(700)
    pg.locator('#vendorOverviewEditForm [data-vendor-edit-save="intelsense"]').first.click(); pg.wait_for_timeout(300)
    # product tiles on the profile show the symbols
    pg.click("#vendorOverviewViewBtn"); pg.wait_for_timeout(300)
    ok(pg.locator("[data-product-tile] img.entity-logo-img").count() == 4, "Every product tile shows a logo (uploaded or built-in)")
    b.close()
report()
