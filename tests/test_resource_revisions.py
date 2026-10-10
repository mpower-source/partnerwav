from harness import *
import json

# Second security review, finding 3: changes to a published resource go through review and,
# once approved, replace the published version in place (same id, so links keep working).
PUB = {"id": "res-pub", "title": "Unisense Partner Deck", "type": "pdf", "uploadedBy": "Intelsense", "program": "Unisense",
       "vendor": "Intelsense AI", "status": "published", "summary": "The deck partners use today.", "fileUrl": "https://example.com/v1.pdf",
       "ownerKey": "vendor:intelsense", "uploadedDate": "last week"}
REV = {"id": "res-rev1", "replacesId": "res-pub", "title": "Unisense Partner Deck (Q4)", "type": "pdf", "uploadedBy": "Intelsense",
       "program": "Unisense", "vendor": "Intelsense AI", "status": "pending", "submittedDate": "just now", "summary": "Updated for Q4 pricing.",
       "previewText": "Updated for Q4 pricing.", "reason": "awaiting_review", "fileUrl": "https://example.com/v2.pdf", "ownerKey": "vendor:intelsense"}

def data(pg):
    return json.loads(pg.evaluate("localStorage.getItem('partnerWAV_resourceData')"))

with sync_playwright() as p:
    b, pg = open_page(p)
    pg.evaluate("v => localStorage.setItem('partnerWAV_resourceData', v)", json.dumps({"resources": [PUB], "pending": [REV]}))
    pg.reload(); pg.wait_for_timeout(600); role(pg, "operator"); nav(pg, "resource-approvals")
    card = pg.locator("#approvalQueueGrid .card").filter(has_text="Unisense Partner Deck (Q4)")
    ok(card.count() == 1 and "Changes to a published resource: Unisense Partner Deck" in card.inner_text(), "The queue shows it is a change to a published resource")
    card.locator('[data-review-decision=""]').click(); pg.wait_for_timeout(300)
    pg.select_option("#approvalDecision", "approve"); pg.click('#approvalForm button[type=submit]'); pg.wait_for_timeout(300)
    d = data(pg)
    pub = [r for r in d["resources"] if r["id"] == "res-pub"]
    ok(len(d["resources"]) == 1 and pub and pub[0]["title"] == "Unisense Partner Deck (Q4)" and pub[0]["fileUrl"] == "https://example.com/v2.pdf",
       "Approving replaces the published version, keeping its id")
    ok(pub and pub[0]["ownerKey"] == "vendor:intelsense" and "replacesId" not in pub[0] and pub[0]["status"] == "published", "It keeps its owner and is published")
    ok(not [r for r in d["pending"] if r["id"] == "res-rev1"], "The change leaves the review queue")
    b.close()
report()
