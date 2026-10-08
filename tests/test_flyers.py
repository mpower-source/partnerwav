from harness import *
import subprocess, tempfile, tarfile, glob

JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "jspdf.umd.min.js")
def jspdf():
    if not os.path.exists(JS):
        d = tempfile.mkdtemp()
        subprocess.run(["npm", "pack", "jspdf@2.5.2", "--silent"], cwd=d, check=True, capture_output=True)
        os.makedirs(os.path.dirname(JS), exist_ok=True)
        with tarfile.open(glob.glob(os.path.join(d, "*.tgz"))[0]) as t:
            open(JS, "wb").write(t.extractfile("package/dist/jspdf.umd.min.js").read())
    return open(JS, "rb").read()

def open_fly(p):
    body = jspdf()
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True)
    ctx.route("**/cdn.jsdelivr.net/npm/jspdf@2.5.2/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=body, headers={"access-control-allow-origin": "*"}))
    pg = ctx.new_page(); from harness import _wire; _wire(pg)
    pg.goto(URL + "?demo=1"); pg.wait_for_timeout(600)
    return b, pg

with sync_playwright() as p:
    b, pg = open_fly(p)
    role(pg, "vendor"); nav(pg, "vendor-incentives")
    ok(pg.locator("#vendorFlyersContent").is_visible() and "No flyers yet" in pg.inner_text("#vendorFlyersContent"), "Flyers section on Partner Incentives")
    pg.click('[data-flyer-new="inc-2"]'); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-vendor-flyer-editor"], "Create flyer opens the editor")
    pg.click('[data-fly-save="draft"]'); pg.wait_for_timeout(150)
    ok("headline" in pg.inner_text("#flyError"), "Can't save an empty flyer")
    pg.select_option("#flyTone", "bold"); pg.click("[data-fly-ai]"); pg.wait_for_timeout(400)
    ok(pg.input_value("#fly_headline") == "Your marketing, our budget." and "$5,000" in pg.input_value("#fly_offer"), "AI draft (built-in writer in demo) fills the copy from the MDF terms")
    ok("built-in writer" in pg.inner_text("#flyAiNote"), "Says which writer drafted it")
    prev = pg.inner_text("#flyPreview")
    ok("Your marketing, our budget." in prev and "DRAFT" in prev and "What you get" in prev.title() or "WHAT YOU GET" in prev.upper(), "Live preview with DRAFT mark")
    checks = pg.inner_text(".fly-checks")
    ok("All figures match" in checks, "Figures check passes on AI copy")
    # vendor edits in a figure that isn't in the terms + a risky claim
    pg.fill("#fly_offer", "Guaranteed $8,000 in co-marketing funds every quarter"); pg.wait_for_timeout(150)
    checks = pg.inner_text(".fly-checks")
    ok("$8,000" in checks and "guaranteed" in checks.lower(), "Flags figures not in the terms and absolute claims: " + checks.replace("\n"," | ")[:200])
    ok("Guaranteed $8,000" in pg.inner_text("#flyPreview"), "Preview updates as you type")
    pg.click('[data-fly-theme="teal"]'); pg.wait_for_timeout(100)
    ok("#0f766e" in pg.locator("#flyPreview .flyer").get_attribute("style"), "Colour choice applies")
    # draft PDF
    with pg.expect_download() as dl:
        pg.click("[data-fly-download]")
    path = dl.value.path(); data = open(path, "rb").read()
    ok(data[:5] == b"%PDF-" and b"Guaranteed $8,000" in data and b"DRAFT - not yet reviewed" in data, "Draft PDF downloads with the copy and a DRAFT line (" + str(len(data)) + " bytes)")
    ok(dl.value.suggested_filename.endswith(".pdf") and "intelsense" in dl.value.suggested_filename, "PDF file name: " + dl.value.suggested_filename)
    pg.click('[data-fly-save="submit"]'); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-vendor-incentives"] and "NEEDS REVIEW" in pg.inner_text("#vendorFlyersContent").upper(), "Submitted -> Needs review")
    ok(pg.locator('[data-flyer-new="inc-2"]').inner_text() == "Open flyer", "Incentive shows Open flyer")

    # a second flyer, Thai text -> PDF download points to print
    pg.click('[data-flyer-new="inc-3"]'); pg.wait_for_timeout(300); pg.click("[data-fly-ai]"); pg.wait_for_timeout(300)
    pg.fill("#fly_headline", "ทดลองใช้ฟรี 30 วัน"); pg.click("[data-fly-download]"); pg.wait_for_timeout(200)
    ok("Print / save as PDF" in pg.inner_text("#flyError"), "Thai text: explains to use Print / save as PDF")
    pg.click('[data-fly-save="draft"]'); pg.wait_for_timeout(250)

    # --- operator
    role(pg, "operator"); nav(pg, "operator-marketing-approvals")
    ok("Incentive Flyers" in pg.inner_text("#scr-operator-marketing-approvals"), "Marketing Materials tab is now Incentive Flyers")
    ok(pg.locator("#marketingApprovalsContent").is_visible(), "Flyers tab shows by default")
    c = pg.inner_text("#marketingApprovalsContent")
    ok("Needs review (1)" in c and "ทดลอง" not in c, "Queue has the submitted flyer only (drafts stay private)")
    pg.click("#marketingApprovalsContent [data-review-flyer]"); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-operator-flyer-review"], "Review screen opens")
    auto = pg.inner_text("#flyerReviewContent .fly-checks")
    ok("$8,000" in auto and "incentive itself is approved" in auto, "Operator sees automatic checks")
    ok(pg.locator("[data-fly-check]").count() == 8, "8-point second-look checklist")
    for k in ("offer","who","dates","how","terms","next"): pg.check(f'[data-fly-check="{k}"]')
    pg.wait_for_timeout(100)
    ok("(6/8)" in pg.inner_text("#flyCheckCount"), "Checklist progress")
    pg.click('[data-fly-template="gaps"]'); pg.wait_for_timeout(100)
    msg = pg.input_value("#flyMessage")
    ok("Nothing is promised" in msg and "$8,000" in msg and "your call" in msg, "Template lists unticked items + automatic flags, and says style is theirs")
    with pg.expect_download() as dl2:
        pg.click("[data-fly-download-id]")
    ok(open(dl2.value.path(), "rb").read()[:5] == b"%PDF-", "Operator can download the PDF")
    pg.click('[data-fly-action="changes"]'); pg.wait_for_timeout(300)
    ok("Changes requested (1)" in pg.inner_text("#marketingApprovalsContent"), "Changes requested")

    # --- vendor fixes + resubmits
    role(pg, "vendor"); nav(pg, "vendor-incentives")
    ok("PartnerWAV:" in pg.inner_text("#vendorFlyersContent"), "Vendor sees CloudWAV's note")
    pg.locator("#vendorFlyersContent [data-flyer-row]").filter(has_text="MDF - Marketing Co-op Fund").locator("[data-flyer-edit]").click(); pg.wait_for_timeout(300)
    ok("PartnerWAV:" in pg.inner_text("#flyerEditorContent") and pg.input_value("#fly_offer").startswith("Guaranteed"), "Editor shows feedback and saved copy")
    pg.fill("#fly_offer", "Up to $5,000 in co-marketing funds per quarter"); pg.wait_for_timeout(100)
    ok("All figures match" in pg.inner_text(".fly-checks") and "No absolute" in pg.inner_text(".fly-checks"), "Checks clear after the fix")
    pg.click('[data-fly-save="submit"]'); pg.wait_for_timeout(300)

    # --- operator approves
    role(pg, "operator"); nav(pg, "operator-marketing-approvals")
    pg.click("#marketingApprovalsContent [data-review-flyer]"); pg.wait_for_timeout(300)
    ok("resubmitted" in pg.inner_text("#flyThread"), "Thread shows the resubmission")
    pg.click('[data-fly-action="approve"]'); pg.wait_for_timeout(300)
    ok("Approved (1)" in pg.inner_text("#marketingApprovalsContent"), "Approved")

    # approved: clean PDF for vendor; partners can download it from the vendor profile
    role(pg, "vendor"); nav(pg, "vendor-incentives")
    ok("Download PDF" in pg.inner_text("#vendorFlyersContent"), "Vendor gets the final PDF")
    with pg.expect_download() as dl3:
        pg.locator('#vendorFlyersContent [data-flyer-pdf]:has-text("Download PDF")').click()
    data = open(dl3.value.path(), "rb").read()
    ok(b"DRAFT" not in data and b"Up to $5,000" in data, "Approved PDF has no DRAFT mark")
    role(pg, "partner"); nav(pg, "vendor-network")
    pg.locator('[data-view-vendor="intelsense"]:visible').first.click(); pg.wait_for_timeout(300)
    ok(pg.locator('#vendorProfileContent [data-flyer-pdf]').count() == 1, "Partners can download the approved flyer from the vendor profile")

    # an incentive that isn't approved can't have its flyer approved
    role(pg, "vendor"); nav(pg, "vendor-incentives")
    pg.click('[data-flyer-new="inc-4"]'); pg.wait_for_timeout(300); pg.click("[data-fly-ai]"); pg.wait_for_timeout(300)
    pg.click('[data-fly-save="submit"]'); pg.wait_for_timeout(300)
    role(pg, "operator"); nav(pg, "operator-marketing-approvals")
    pg.click("#marketingApprovalsContent [data-review-flyer]"); pg.wait_for_timeout(300)
    pg.click('[data-fly-action="approve"]'); pg.wait_for_timeout(150)
    ok("Approve the incentive itself first" in pg.inner_text("#flyMsgError"), "Blocks approving a flyer for an unapproved incentive")

    pg.reload(); pg.wait_for_timeout(700); role(pg, "vendor"); nav(pg, "vendor-incentives")
    ok(pg.locator("#vendorFlyersContent [data-flyer-row]").count() == 3, "Flyers persist after reload")
    pg.set_viewport_size({"width": 390, "height": 844}); pg.click('[data-flyer-new="inc-2"]'); pg.wait_for_timeout(300)
    ok(pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0, "Editor fits at 390px")
    b.close()

# --- signed in (Supabase): the AI writer Edge Function is used when it's deployed
class FnMock(MockSupabase):
    def __init__(self, *a, fail=False):
        super().__init__(*a); self.fail = fail; self.fn_bodies = []
    def handle(self, route):
        req = route.request
        if "/functions/v1/flyer-assist" in req.url and req.method == "POST":
            self.fn_bodies.append((json.loads(req.post_data or "{}"), req.headers.get("authorization", "")))
            if self.fail: return route.fulfill(status=503, content_type="application/json", body='{"error":"not configured"}', headers={"access-control-allow-origin": "*"})
            return route.fulfill(status=200, content_type="application/json", headers={"access-control-allow-origin": "*"},
                body=json.dumps({"headline": "Close more, earn up to 15% extra", "subheadline": "A Q4 bonus on top of your Intelsense commission.",
                    "offer": "Up to 15% bonus on Q4 deals", "benefits": ["5% bonus up to $10k", "10% bonus from $10k", "15% bonus above $25k"],
                    "qualify": "Enrolled Intelsense AI partners", "steps": ["Register the deal", "Close by 31 Dec", "Bonus paid on your tier"],
                    "cta": "Register your next deal", "finePrint": "Valid 1 Oct - 31 Dec 2026. Full terms in the Intelsense AI partner program on PartnerWAV."}))
        return super().handle(route)
UID = "11111111-0000-0000-0000-000000000002"
for fail in (False, True):
    with sync_playwright() as p:
        mock = FnMock({"vendor@intelsense.test": {"password": "vend-pass-123", "id": UID}}, {UID: {"role": "vendor", "entity_id": "intelsense", "display_name": "Intelsense Admin"}}, fail=fail)
        b, ctx, pg = open_page_supabase(p, mock)
        pg.fill("#loginEmail", "vendor@intelsense.test"); pg.fill("#loginPassword", "vend-pass-123"); pg.click("#loginSubmit"); pg.wait_for_timeout(900)
        # signed-in sessions start with no demo incentives: create the SPIF first
        nav(pg, "vendor-incentives"); pg.locator('[data-goto-screen="vendor-incentive-editor"]:visible').first.click(); pg.wait_for_timeout(250)
        pg.select_option("#incType", "spif"); pg.fill("#incTitle", "Q4 Sales Acceleration SPIF"); pg.fill("#incDesc", "Earn extra commissions based on monthly sales volume")
        pg.click("[data-inc-add-tier]"); pg.click("[data-inc-add-tier]"); pg.wait_for_timeout(100)
        for i, (th, bo) in enumerate([("$0-10k", "5%"), ("$10k-25k", "10%"), ("$25k+", "15%")]):
            pg.locator("#spifTiersContainer .spifThreshold").nth(i).fill(th); pg.locator("#spifTiersContainer .spifBonus").nth(i).fill(bo)
        pg.fill("#incValidFrom", "2026-10-01"); pg.fill("#incValidUntil", "2026-12-31"); pg.fill("#incClaimProcess", "Register deals in the portal; bonus paid on the tier reached.")
        pg.click('#vendorIncentiveForm button[type=submit]'); pg.wait_for_timeout(300)
        pg.locator("[data-flyer-new]").first.click(); pg.wait_for_timeout(300)
        pg.select_option("#flyTone", "friendly"); pg.fill("#flyNotes", "aimed at hotel IT teams"); pg.click("[data-fly-ai]"); pg.wait_for_timeout(1200)
        if not fail:
            body, auth = mock.fn_bodies[0]
            ok(body["incentive"]["title"] == "Q4 Sales Acceleration SPIF" and body["tone"] == "Friendly" and body["notes"] == "aimed at hotel IT teams" and auth.startswith("Bearer ") and "sig-" in auth, "Signed in: calls the flyer-assist AI function with the terms, tone, notes and the user's token")
            ok(pg.input_value("#fly_headline") == "Close more, earn up to 15% extra" and "Register the deal" in pg.input_value("#fly_steps"), "AI copy fills the flyer")
            ok("Drafted by AI" in pg.inner_text("#flyAiNote"), "Says AI drafted it")
            ok("All figures match" in pg.inner_text(".fly-checks"), "AI figures checked against terms")
        else:
            ok(len(mock.fn_bodies) == 1 and pg.input_value("#fly_headline") != "" and "built-in writer" in pg.inner_text("#flyAiNote"), "AI function not deployed: falls back to the built-in writer")
        b.close()
report()
