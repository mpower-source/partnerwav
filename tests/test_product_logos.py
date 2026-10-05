from harness import *

with sync_playwright() as p:
    b, pg = open_page(p)
    role(pg, "vendor"); nav(pg, "vendor-network"); pg.wait_for_timeout(300)
    srcs = pg.evaluate("[...document.querySelectorAll('#scr-vendor-network img.entity-logo-img')].map(i => i.getAttribute('src'))")
    svg = [s for s in srcs if s.startswith("data:image/svg+xml") and "fill%3D%22%23ffffff%22" in s]
    ok(len(svg) >= 4, "Vendor Network: the four Intelsense product tiles show their SVG symbols on white (%d found)" % len(svg))
    ok(pg.evaluate("[...document.querySelectorAll('#scr-vendor-network img.entity-logo-img')].every(i => i.complete && i.naturalWidth > 0)"), "All logos load")
    pg.locator('[data-view-vendor="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    ok(pg.locator("#vendorProfileContent [data-product-tile] img.entity-logo-img").count() == 4, "Intelsense profile: each of the 4 products has its icon")
    # a saved copy with the icons removed gets them back once; an uploaded logo is kept
    pg.evaluate("""localStorage.setItem('partnerWAV_vendorProfileEdits', JSON.stringify({ intelsense: { products: [
      { product_id:'unisense-ai', name:'Unisense AI', desc:'x', logo:'' }, { product_id:'finsense-ai', name:'Finsense AI', desc:'x', logo:'data:image/png;base64,iVBORw0KGgo=' },
      { product_id:'ai-hubspot', name:'AI Hubspot', desc:'x', logo:'' }, { product_id:'altercrew', name:'AlterCrew', desc:'x', logo:'' } ] } }))""")
    pg.reload(); pg.wait_for_timeout(600)
    role(pg, "vendor"); nav(pg, "vendor-network"); pg.locator('[data-view-vendor="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    got = pg.evaluate("[...document.querySelectorAll('#vendorProfileContent [data-product-tile]')].map(t => [t.getAttribute('data-product-tile'), (t.querySelector('img.entity-logo-img') || {src:''}).src.slice(0, 22)])")
    d = dict(got)
    ok(d.get("unisense-ai", "").startswith("data:image/svg") and d.get("altercrew", "").startswith("data:image/svg") and d.get("finsense-ai", "").startswith("data:image/png"), "Saved products without icons get them; an uploaded one is kept")
    b.close()
report()
