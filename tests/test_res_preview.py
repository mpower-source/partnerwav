from harness import *
import os, tempfile

# a tiny real PDF
PDF = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 55>>stream
BT /F1 18 Tf 20 70 Td (Intelsense Pitch Deck) Tj ET
endstream endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
trailer<</Root 1 0 R>>
%%EOF
"""
tmp = tempfile.mkdtemp()
pdf_path = os.path.join(tmp, "intelsense-pitch.pdf"); open(pdf_path, "wb").write(PDF)
big_path = os.path.join(tmp, "huge.pdf"); open(big_path, "wb").write(b"%PDF-1.4\n" + b"0" * (4 * 1024 * 1024))

def open_editor(pg):
    role(pg, "vendor"); nav(pg, "resource-browse")
    pg.locator('[data-goto-screen="resources-editor"]:visible').first.click(); pg.wait_for_timeout(250)

def fill_basics(pg, title):
    pg.fill("#resourceTitle", title); pg.select_option("#resourceType", "pdf")
    pg.fill("#resourceProgram", "Intelsense AI"); pg.fill("#resourceVendor", "Intelsense")
    pg.fill("#resourceSummary", "Partner-facing overview for " + title)

with sync_playwright() as p:
    b, pg = open_page(p)

    # --- seeded items have nothing attached: operator is told so
    role(pg, "operator"); nav(pg, "resource-approvals")
    card = pg.locator("#approvalQueueGrid .card").filter(has_text="Unisense SaaS Reseller Pitch Deck")
    ok("Nothing attached" in card.inner_text(), "Queue flags submissions with nothing attached")
    card.locator('[data-review-decision=""]').click(); pg.wait_for_timeout(250)
    ok(visible_screen(pg) == ["scr-resource-approvals-editor"] and pg.input_value("#approvalDecision") == "", "View opens the review without pre-picking a decision")
    ok("Nothing attached" in pg.inner_text("#approvalReviewContent") and "Request Revision" in pg.inner_text("#approvalReviewContent"), "Review explains there's nothing to check")

    # --- vendor must attach something
    open_editor(pg)
    ok(pg.locator("#resourceFileUrl").is_visible() and pg.locator("#resourceFileInput").is_visible(), "Submit form has link + upload")
    fill_basics(pg, "No Attachment Test")
    pg.click('#resourceForm button[type=submit]'); pg.wait_for_timeout(200)
    ok(visible_screen(pg) == ["scr-resources-editor"], "Can't submit without a file or link")

    # too-large file rejected with guidance
    pg.set_input_files("#resourceFileInput", big_path); pg.wait_for_timeout(300)
    ok("too large" in pg.inner_text("#resourceFileStatus"), "Oversized upload rejected with guidance")

    # real PDF upload
    pg.set_input_files("#resourceFileInput", pdf_path); pg.wait_for_timeout(400)
    ok("Attached: intelsense-pitch.pdf" in pg.inner_text("#resourceFileStatus"), "PDF attached")
    pg.fill("#resourceTitle", "Intelsense Partner Pitch Deck")
    pg.click('#resourceForm button[type=submit]'); pg.wait_for_timeout(300)

    # link submission (YouTube)
    open_editor(pg); fill_basics(pg, "Unisense Demo Walkthrough")
    pg.select_option("#resourceType", "webinar")
    pg.fill("#resourceFileUrl", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    pg.click('#resourceForm button[type=submit]'); pg.wait_for_timeout(300)

    # --- operator views the PDF
    role(pg, "operator"); nav(pg, "resource-approvals")
    card = pg.locator("#approvalQueueGrid .card").filter(has_text="Intelsense Partner Pitch Deck")
    ok("File attached: intelsense-pitch.pdf" in card.inner_text(), "Queue shows the attachment")
    card.locator('[data-review-decision=""]').click(); pg.wait_for_timeout(400)
    frame = pg.locator("#approvalReviewContent .res-preview iframe")
    ok(frame.count() == 1 and frame.get_attribute("src").startswith("blob:"), "PDF previews inline")
    blob_type = pg.evaluate("async () => { const u = document.querySelector('#approvalReviewContent .res-preview iframe').src; const r = await fetch(u); const b = await r.blob(); return [b.type, (await b.text()).slice(0,8)]; }")
    ok(blob_type == ["application/pdf", "%PDF-1.4"], "Preview is the actual uploaded PDF: " + str(blob_type))
    ok(pg.locator('#approvalReviewContent a:has-text("Open file")').count() == 1, "Open file link available")
    pg.select_option("#approvalDecision", "approve"); pg.click('#approvalForm button[type=submit]'); pg.wait_for_timeout(300)
    ok("Intelsense Partner Pitch Deck" in pg.inner_text("#approvalQueueGrid"), "Approved after viewing")

    # --- operator views the YouTube link embedded
    nav(pg, "resource-approvals")
    card = pg.locator("#approvalQueueGrid .card").filter(has_text="Unisense Demo Walkthrough")
    ok("Link attached" in card.inner_text(), "Queue shows link attached")
    card.locator('[data-review-decision=""]').click(); pg.wait_for_timeout(300)
    src = pg.locator("#approvalReviewContent .res-preview iframe").get_attribute("src")
    ok(src == "https://www.youtube.com/embed/dQw4w9WgXcQ", "YouTube link embedded: " + str(src))
    ok(pg.locator('#approvalReviewContent a:has-text("Open in new tab")').count() == 1, "Open in new tab available")

    # --- persistence of attachment
    pg.reload(); pg.wait_for_timeout(700); role(pg, "operator"); nav(pg, "resource-approvals")
    ok("Link attached" in pg.locator("#approvalQueueGrid .card").filter(has_text="Unisense Demo Walkthrough").inner_text(), "Attachments persist after reload")

    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0, "No horizontal overflow at 390px")
    b.close()
report()
