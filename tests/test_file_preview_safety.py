from harness import *
import json, base64

# Security review finding 4: a file declared as a PDF (or anything else) but holding a web page
# must never be shown as a page inside the portal.
HTML = b"<html><body><h1>Fake page</h1><script>try{parent.__xss=1}catch(e){} try{opener&&(opener.__xss=1)}catch(e){} window.__ran=1</script></body></html>"
DATA_HTML = "data:text/html;base64," + base64.b64encode(HTML).decode()

BASE = {"id": "pend-evil", "title": "Partner Deck", "type": "pdf", "uploadedBy": "Intelsense", "program": "Unisense", "vendor": "Intelsense AI",
        "status": "pending", "fileSize": "1KB", "submittedDate": "just now", "summary": "", "transcription": "", "previewText": "", "reason": "awaiting_review"}
def plant(pg, mime, data, name, url=""):
    r = dict(BASE, fileMime=mime, fileData=data, fileName=name, fileUrl=url)
    pg.evaluate("v => localStorage.setItem('partnerWAV_resourceData', v)", json.dumps({"resources": [], "pending": [r]}))
    return r["id"]

def review(pg, rid):
    pg.reload(); pg.wait_for_timeout(600); role(pg, "operator"); nav(pg, "resource-approvals")
    pg.click(f'[data-review-resource="{rid}"][data-review-decision=""]'); pg.wait_for_timeout(800)

def blob_type(pg, sel, at):
    return pg.evaluate("([s, a]) => { var e = document.querySelector(s); if (!e) return null; return fetch(e.getAttribute(a)).then(r => r.blob()).then(b => b.type); }", [sel, at])

with sync_playwright() as p:
    b, pg = open_page(p)

    # ----- a web page declared as a PDF
    rid = plant(pg, "application/pdf", DATA_HTML, "deck.pdf")
    review(pg, rid)
    ok(pg.locator("#resPreviewSlot iframe").count() == 1, "A declared PDF is previewed in a frame")
    ok(blob_type(pg, "#resPreviewSlot iframe", "src") == "application/pdf", "...as a PDF, never as the web page hidden inside it")
    ok(blob_type(pg, "#resPreviewSlot a[download]", "href") == "application/pdf", "The Open file link hands over the same PDF-typed file")
    pg.wait_for_timeout(500)
    ok(not pg.evaluate("window.__xss"), "No script from the file runs in the portal")

    # ----- a web page declared as a web page
    rid = plant(pg, "text/html", DATA_HTML, "page.html")
    review(pg, rid)
    ok(pg.locator("#resPreviewSlot iframe, #resPreviewSlot img, #resPreviewSlot video").count() == 0 and "can't be previewed" in pg.inner_text("#resPreviewSlot"), "An HTML file isn't previewed")
    ok(blob_type(pg, "#resPreviewSlot a[download]", "href") == "application/octet-stream", "Opening it only downloads it")

    # ----- SVG (can carry script) is not shown either
    rid = plant(pg, "image/svg+xml", "data:image/svg+xml;base64," + base64.b64encode(b'<svg xmlns="http://www.w3.org/2000/svg"><script>parent.__xss=1</script></svg>').decode(), "logo.svg")
    review(pg, rid)
    ok(pg.locator("#resPreviewSlot img, #resPreviewSlot iframe").count() == 0 and blob_type(pg, "#resPreviewSlot a[download]", "href") == "application/octet-stream", "An SVG upload is a download only")

    # ----- real images still preview
    PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    rid = plant(pg, "image/png", PNG, "shot.png")
    review(pg, rid)
    ok(pg.locator("#resPreviewSlot img").count() == 1 and blob_type(pg, "#resPreviewSlot img", "src") == "image/png", "A PNG still previews as an image")

    # ----- a link to a known video site plays in a locked-down frame
    review(pg, plant(pg, "", "", "", "https://www.youtube.com/watch?v=abcdefgh123"))
    sb = pg.get_attribute("#resPreviewSlot iframe", "sandbox") or ""
    ok("allow-scripts" in sb and "allow-top-navigation" not in sb, "Embedded links play in a sandboxed frame that can't take over the page")
    ok(not pg.evaluate("window.__xss"), "Nothing ran at any point")
    b.close()
report()
