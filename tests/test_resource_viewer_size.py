from harness import *
import json

# Resource Library viewer: about twice the size on desktop, the usual size on phones.
RES = {"resources": [{"id": "res-big", "title": "Partner Deck", "type": "pdf", "uploadedBy": "Intelsense", "program": "Unisense",
                      "vendor": "Intelsense AI", "status": "published", "summary": "Deck", "fileSize": "1MB", "uploadedDate": "today",
                      "fileUrl": "https://www.youtube.com/watch?v=abcdefgh123"}], "pending": []}

def open_viewer(pg):
    role(pg, "partner"); nav(pg, "resource-browse"); pg.wait_for_timeout(200)
    pg.locator('[data-open-resource="res-big"]').first.click(); pg.wait_for_timeout(400)
    return pg.evaluate("""() => { const m = document.querySelector('.modal'), f = m && m.querySelector('#resPreviewSlot iframe');
        return { w: m ? Math.round(m.getBoundingClientRect().width) : 0, h: f ? Math.round(f.getBoundingClientRect().height) : 0,
                 overflow: document.documentElement.scrollWidth - innerWidth }; }""")

with sync_playwright() as p:
    b, pg = open_page(p)   # 1280 x 900
    pg.evaluate("v => localStorage.setItem('partnerWAV_resourceData', v)", json.dumps(RES))
    pg.set_viewport_size({"width": 1920, "height": 1200}); pg.reload(); pg.wait_for_timeout(600)
    d = open_viewer(pg)
    ok(d["w"] == 1120 and d["h"] >= 900, "Large desktop: the viewer is 1120px wide (was 560) with a tall preview: " + str(d))
    pg.evaluate("closeModal()")
    pg.set_viewport_size({"width": 1280, "height": 800}); pg.wait_for_timeout(200)
    d = open_viewer(pg)
    ok(d["w"] == 1120 and 600 <= d["h"] <= 800 * 0.78 + 1 and d["overflow"] <= 0, "Laptop: wide viewer, preview fits the screen height: " + str(d))
    pg.evaluate("closeModal()")
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    d = open_viewer(pg)
    ok(d["w"] <= 390 - 32 + 1 and d["h"] == 380 and d["overflow"] <= 0, "Phone: same size as before (380px preview), no sideways scrolling: " + str(d))
    b.close()
report()
