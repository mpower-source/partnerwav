from harness import *
from harness import _wire
import base64

LF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "leaflet")
BLANK_PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

def leaflet_files():
    """Leaflet 1.9.4 dist files: tests/vendor/leaflet/ if present, else fetched once via npm pack."""
    if not os.path.exists(os.path.join(LF, "leaflet.js")):
        import subprocess, tempfile, tarfile, glob
        d = tempfile.mkdtemp()
        subprocess.run(["npm", "pack", "leaflet@1.9.4", "--silent"], cwd=d, check=True, capture_output=True)
        os.makedirs(LF, exist_ok=True)
        with tarfile.open(glob.glob(os.path.join(d, "*.tgz"))[0]) as t:
            for n in ("leaflet.js", "leaflet.css"):
                open(os.path.join(LF, n), "wb").write(t.extractfile("package/dist/" + n).read())
    return {n: open(os.path.join(LF, n), "rb").read() for n in ("leaflet.js", "leaflet.css")}

tiles = []
def open_map_page(p, block_leaflet=False):
    files = leaflet_files()
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 1280, "height": 900})
    if not block_leaflet:
        ctx.route("**/cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js", lambda r: r.fulfill(status=200, content_type="application/javascript", body=files["leaflet.js"], headers={"access-control-allow-origin": "*"}))
        ctx.route("**/cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css", lambda r: r.fulfill(status=200, content_type="text/css", body=files["leaflet.css"], headers={"access-control-allow-origin": "*"}))
    def tile(r):
        tiles.append(r.request.url); r.fulfill(status=200, content_type="image/png", body=BLANK_PNG)
    ctx.route("**/tile.openstreetmap.org/**", tile)
    pg = ctx.new_page(); _wire(pg)
    pg.goto(URL + "?demo=1"); pg.wait_for_timeout(600)
    return b, pg

with sync_playwright() as p:
    b, pg = open_map_page(p)
    role(pg, "operator"); nav(pg, "operator-partner-map"); pg.wait_for_timeout(1200)
    ok(pg.evaluate("!!(window.L && window.L.map)"), "Leaflet loaded (with SRI integrity check)")
    ok(pg.locator("#partnerMapContainer.leaflet-container").count() == 1, "Interactive world map rendered")
    ok(pg.locator("#partnerMapContainer path.leaflet-interactive").count() == 9, "All 9 partners plotted: " + str(pg.locator("#partnerMapContainer path.leaflet-interactive").count()))
    ok(any("tile.openstreetmap.org" in t for t in tiles), "OpenStreetMap tiles requested (no API key)")
    stats = pg.inner_text("#mapStats")
    ok("9" in stats and "active" in stats and "countries" in stats, "Stats row: " + stats.replace("\n", " "))
    ok(pg.locator("[data-map-focus]").count() == 9, "Partner list shows all 9")
    ok(pg.locator(".leaflet-control-attribution").count() == 1 and "OpenStreetMap" in pg.inner_text(".leaflet-control-attribution"), "Map attribution shown")

    # filters drive both map and list
    pg.select_option("#mapStatusFilter", "active"); pg.wait_for_timeout(400)
    n_active = pg.locator("#partnerMapContainer path.leaflet-interactive").count()
    ok(n_active == 6 and pg.locator("[data-map-focus]").count() == 6, "Status filter: 6 active on map + list")
    pg.select_option("#mapRegionFilter", "apac"); pg.wait_for_timeout(400)
    names = pg.locator("[data-map-focus] .map-item-name").all_inner_texts()
    ok(sorted(names) == ["Aussie Partners Group", "Portonics Ltd.", "Siam Digital MSP"], "Region filter (APAC, active): " + str(names))
    ok(pg.locator("#partnerMapContainer path.leaflet-interactive").count() == 3, "Map shows the same 3")
    ok("3 OF 9" in pg.inner_text("#mapListTitle").upper(), "List title shows filtered count")
    pg.select_option("#mapStatusFilter", ""); pg.select_option("#mapRegionFilter", ""); pg.wait_for_timeout(300)
    pg.select_option("#mapProgramFilter", "Intelsense AI"); pg.wait_for_timeout(400)
    ok(pg.locator("[data-map-focus]").count() == 4, "Program filter: 4 Intelsense AI partners")
    pg.select_option("#mapProgramFilter", ""); pg.wait_for_timeout(300)

    # list click -> fly + popup
    pg.click('[data-map-focus="siam-digital"]'); pg.wait_for_timeout(1200)
    pop = pg.locator(".leaflet-popup-content")
    ok(pop.count() == 1 and "Siam Digital MSP" in pop.inner_text() and "Bangkok, Thailand" in pop.inner_text() and "Gold" in pop.inner_text(), "List click opens partner popup")
    ok(pg.evaluate("document.querySelector('#partnerMapContainer').querySelector('.leaflet-popup') !== null"), "Popup on the map")
    pg.click('.leaflet-popup-content [data-view-profile="siam-digital"]'); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-partner-profile"], "View profile from the map opens the partner profile")

    # back to map works (map re-used)
    nav(pg, "operator-partner-map"); pg.wait_for_timeout(700)
    ok(pg.locator("#partnerMapContainer path.leaflet-interactive").count() == 9, "Map redraws on return")
    # marker click
    pg.locator("#partnerMapContainer path.leaflet-interactive").first.click(force=True); pg.wait_for_timeout(400)
    ok(pg.locator(".leaflet-popup-content").count() == 1, "Clicking a marker opens its popup")

    # dark theme swaps basemap
    pg.click("#themeToggle"); pg.wait_for_timeout(800)
    dark = pg.evaluate("document.documentElement.getAttribute('data-theme')") == "dark"
    ok(pg.locator("#partnerMapContainer .map-tiles-dark").count() == (1 if dark else 0), "Dark theme darkens the map tiles")

    # mobile
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(400)
    ok(pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0, "No horizontal overflow at 390px")
    ok(pg.locator("#partnerMapContainer").bounding_box()["height"] >= 300, "Map keeps usable height on mobile")
    b.close()

    # offline: map service unreachable -> clear message, list still works
    b, pg = open_map_page(p, block_leaflet=True)
    role(pg, "operator"); nav(pg, "operator-partner-map"); pg.wait_for_timeout(1500)
    ok("couldn't load" in pg.inner_text("#partnerMapContainer") and pg.locator("[data-map-focus]").count() == 9, "Offline: message shown, list still works")
    b.close()
# errors expected from the blocked-CDN case are console 'Failed to load resource' (ignored)
report()
