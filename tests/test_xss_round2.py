from harness import *
import json

# Second security review, findings 1-4 and 13: values a member (or an anonymous visitor) controls in
# vendor assessments, resources, software referrals and the partner map must never run as code,
# and the Supabase library only runs if it is the exact pinned file.
HIT = "window.__xss=(window.__xss||0)+1"
TXT = "\"'><img src=x onerror=\"" + HIT + "\">"

def check(pg, where):
    pg.wait_for_timeout(300)
    hits = pg.evaluate("window.__xss || 0")
    bad = pg.evaluate("""[...document.querySelectorAll('*')].filter(e => [...e.attributes].some(a =>
        /^on/i.test(a.name) && a.value.indexOf('__xss') > -1)).length""")
    ok(hits == 0 and bad == 0, where + ": nothing runs (" + str(hits) + " ran, " + str(bad) + " live attributes)")

ASSESS = [{"id": "va-evil", "company": "Evil Co", "contactName": "Eve", "email": "eve@evil.test", "consent": True, "status": "new",
           "source": "vendor-link", "createdAt": "2026-10-11 09:00", "partners": "11-50", "needs": [], "markets": [], "productTypes": [], "partnerTypes": [],
           "addons": ["investor", "<img src=x onerror=" + HIT + ">"],
           "roi": {"partners": "\"><img src=x onerror=" + HIT + ">", "dealValue": TXT}}]
RES = {"resources": [{"id": "res-evil", "title": "Deck", "type": "pdf", "uploadedBy": "Intelsense", "program": "Unisense", "vendor": "Intelsense AI",
                      "status": "published", "summary": "Deck", "fileSize": "<img src=x onerror=" + HIT + ">", "uploadedDate": "today"},
                     {"id": "res-evil2", "title": "Webinar", "type": "webinar", "uploadedBy": "Intelsense", "program": "Unisense", "vendor": "Intelsense AI",
                      "status": "published", "summary": "Webinar", "webinarPlatform": TXT, "duration": TXT, "uploadedDate": "today"}], "pending": []}

with sync_playwright() as p:
    # ----- demo mode: plant the hostile records, open the screens as CloudWAV and as a partner
    b, pg = open_page(p)
    pg.evaluate("v => localStorage.setItem('partnerWAV_vendorAssessments', v)", json.dumps(ASSESS))
    pg.evaluate("v => localStorage.setItem('partnerWAV_resourceData', v)", json.dumps(RES))
    pg.reload(); pg.wait_for_timeout(700)
    role(pg, "operator"); nav(pg, "operator-assessments"); pg.wait_for_timeout(300)
    check(pg, "Vendor Assessments list (finding 1)")
    if pg.locator('[data-va-open="va-evil"]').count():
        pg.locator('[data-va-open="va-evil"]').first.click(); pg.wait_for_timeout(400)
    ok("Evil Co" in pg.inner_text("body"), "The hostile assessment is open")
    check(pg, "Assessment detail with ROI (finding 1)")
    nav(pg, "operator-overview"); pg.wait_for_timeout(300)
    check(pg, "Operator overview with a hostile resource listed (finding 2)")
    role(pg, "partner"); nav(pg, "resource-browse"); pg.wait_for_timeout(300)
    ok("Deck" in pg.inner_text("body"), "The hostile resources are listed")
    check(pg, "Resource Library as a partner (finding 2)")

    # software referral with a hostile currency and hostile fee terms
    role(pg, "operator"); nav(pg, "referrals"); pg.wait_for_timeout(300)
    house = {"id": "sh-demo", "name": "Demo Software House Co.", "city": "Bangkok", "status": "active", "contactName": "Team", "contactEmail": "t@example.com"}
    refs = [{"id": "ref-evil", "houseId": "sh-demo", "referrerKey": "partner:siam-digital", "level": "referral", "cosellLead": "partner",
             "client": {"company": "Riverside Hotels", "contact": "Ops", "email": "", "phone": ""}, "need": "Guest app", "budget": 1200000,
             "currency": "<img src=x onerror=" + HIT + ">", "timeline": "Q4", "disclosed": True, "status": "won", "registeredAt": "2026-07-01",
             "respondBy": "2026-07-08", "acceptedAt": "2026-07-03", "protectedUntil": "2027-01-03", "contractValue": 1200000, "wonAt": "2026-08-01",
             "payments": [{"id": "pay-1", "date": "2026-08-15", "amount": 400000, "maintenance": False, "note": "Deposit"}], "payouts": [], "thread": [],
             "termsSnapshot": {"referralRate": 10, "windowMonths": TXT, "stepDownRate": TXT, "stepDownMonths": TXT, "cosellMonths": TXT}}]
    d = {"houses": [house], "referrals": refs}
    pg.evaluate("v => localStorage.setItem('partnerWAV_softwareReferrals', v)", json.dumps(d))
    pg.reload(); pg.wait_for_timeout(700); role(pg, "operator"); nav(pg, "referrals"); pg.wait_for_timeout(300)
    check(pg, "Software referrals list (finding 3)")
    pg.locator("[data-ref-view]").first.click(); pg.wait_for_timeout(400)
    check(pg, "Software referral detail (finding 3)")
    b.close()

    # ----- the partner map's hover label (finding 4): a hostile company name from the map view
    class MapMock(MockSupabase):
        def handle(self, route):
            if "/rest/v1/v_partner_map_data" in route.request.url:
                return route.fulfill(status=200, content_type="application/json", headers={"access-control-allow-origin": "*"},
                    body=json.dumps([{"id": "evil", "company_name": "<img src=x onerror=" + HIT + ">", "city": "Bangkok", "country": "Thailand", "lat": 13.75, "lng": 100.5, "status": "active"}]))
            return super().handle(route)
    UID = "11111111-0000-0000-0000-000000000001"
    mock = MapMock({"ops@cloudwav.test": {"password": "op-pass-123", "id": UID}}, {UID: {"role": "operator", "entity_id": None, "display_name": "Peter"}})
    b, ctx, pg = open_page_supabase(p, mock)
    import os
    LF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "leaflet")
    if os.path.exists(os.path.join(LF, "leaflet.js")):
        for n, ct in (("leaflet.js", "application/javascript"), ("leaflet.css", "text/css")):
            body = open(os.path.join(LF, n), "rb").read()
            def serve(body, ct):
                return lambda r: r.fulfill(status=200, content_type=ct, body=body, headers={"access-control-allow-origin": "*"})
            ctx.route("**/cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/" + n, serve(body, ct))
        ctx.route("**/tile.openstreetmap.org/**", lambda r: r.fulfill(status=404, body=""))
        pg.fill("#loginEmail", "ops@cloudwav.test"); pg.fill("#loginPassword", "op-pass-123"); pg.click("#loginSubmit"); pg.wait_for_timeout(1500)
        nav(pg, "operator-partner-map"); pg.wait_for_timeout(1500)
        markers = pg.locator("#partnerMapContainer path.leaflet-interactive")
        ok(markers.count() >= 1, "Map markers drawn: " + str(markers.count()))
        for i in range(markers.count()):
            try: markers.nth(i).hover(timeout=1500); pg.wait_for_timeout(150)
            except Exception: pass
        check(pg, "Partner map hover labels (finding 4)")
    else:
        ok(False, "Leaflet test files missing (run tests/test_map.py once)")
    b.close()

    # ----- finding 13: the Supabase library only runs if it is the exact pinned file
    b = p.chromium.launch(); ctx = b.new_context()
    ctx.route("**/cdn.jsdelivr.net/npm/@supabase/**", lambda r: r.fulfill(status=200, content_type="application/javascript",
              body="window.__tampered = 1; window.supabase = { createClient: function(){ return {}; } };", headers={"access-control-allow-origin": "*"}))
    pg = ctx.new_page(); pg.goto(URL); pg.wait_for_timeout(800)
    ok(not pg.evaluate("window.__tampered"), "A changed Supabase library is refused by the integrity check")
    src = pg.evaluate("document.querySelector('script[src*=\"supabase-js\"]').outerHTML")
    ok("@2.117.2/" in src and 'integrity="sha384-' in src and 'crossorigin="anonymous"' in src, "The library is pinned to one version with an integrity hash")
    b.close()
report()
