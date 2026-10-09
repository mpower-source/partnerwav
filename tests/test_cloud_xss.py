from harness import *
import os, sys, json
if not os.path.exists("/usr/lib/postgresql/16/bin/initdb"):
    print("SKIP: PostgreSQL 16 not installed"); srv.shutdown(); sys.exit(0)
import psycopg2
from pgmock import start_pg, PgSupabase

# Security review finding 3: a company writes crafted values straight into the database (skipping the forms).
# Every text field gets an attribute break-out, every link and image a javascript: address. Nothing may run.
USERS = {"ops@cloudwav.test": {"password": "op-pass-123", "id": "11111111-0000-0000-0000-000000000001"}}
PORTAL = {USERS["ops@cloudwav.test"]["id"]: {"role": "operator", "entity_id": None, "display_name": "Peter Phelan"}}
mock = PgSupabase(USERS, PORTAL, start_pg())
QRJS = qrcode_js()
HIT = "window.__xss=(window.__xss||0)+1"
TEXT = "\"'><img src=x onerror=\"" + HIT + "\"><svg onload=\"" + HIT + "\">"
LINK = "javascript:" + HIT
LINKY = ("website", "link", "url", "logo", "qr", "linkedin", "twitter", "facebook", "booking", "fileurl", "image", "photo", "avatar")
# Fields the portal uses to find and file records; poisoning them would just hide the record
SKIP = ("id", "status", "role", "type", "kind", "template", "theme", "plan", "tier", "collection", "date", "start", "end", "time", "created", "font", "herostyle")

def poison(v, key=""):
    k = key.lower()
    if isinstance(v, dict): return {a: poison(b, a) for a, b in v.items()}
    if isinstance(v, list): return [poison(x, key) for x in v]
    if not isinstance(v, str) or not v: return v
    if k.endswith("id") or k.endswith("key") or k.endswith("at") or k in SKIP or k.startswith("#") or v.startswith("#") and len(v) <= 9: return v
    if any(w in k for w in LINKY) or k.endswith("link") or k.endswith("url"): return LINK
    return v + TEXT

def su(q, args=()):
    con = psycopg2.connect(mock.dsn); con.autocommit = True; cur = con.cursor(); cur.execute(q, args)
    rows = cur.fetchall() if cur.description else None; con.close(); return rows

def settle(pg):
    for _ in range(60):
        if not pg.evaluate("CLOUD_PENDING()"): return True
        pg.wait_for_timeout(150)
    return False

def check(pg, where):
    hits = pg.evaluate("window.__xss || 0")
    bad = pg.evaluate("""[...document.querySelectorAll('*')].filter(e => [...e.attributes].some(a =>
        (/^on/i.test(a.name) && a.value.indexOf('__xss') > -1) ||
        (/^(href|src|action|formaction)$/i.test(a.name) && /^\\s*javascript:/i.test(a.value)))).length""")
    if bad: print("LIVE", where, pg.evaluate("""[...document.querySelectorAll('*')].filter(e => [...e.attributes].some(a => (/^on/i.test(a.name) && a.value.indexOf('__xss') > -1) || (/^(href|src|action|formaction)$/i.test(a.name) && /^\\s*javascript:/i.test(a.value)))).slice(0,8).map(e => e.outerHTML.slice(0,160) + ' @ ' + (e.closest('[id]')||{}).id)"""))
    ok(hits == 0 and bad == 0, where + ": nothing runs (" + str(hits) + " ran, " + str(bad) + " live attributes)")

def routes(ctx):
    ctx.route("**/cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=QRJS, headers={"access-control-allow-origin": "*"}))

with sync_playwright() as p:
    # ----- CloudWAV signs in once so the portal seeds its data into the database
    b, ctx, pg = open_page_supabase(p, mock)
    pg.fill("#loginEmail", "ops@cloudwav.test"); pg.fill("#loginPassword", "op-pass-123"); pg.click("#loginSubmit"); pg.wait_for_timeout(2500); settle(pg)
    b.close()

    # ----- an attacker rewrites every record directly in the database
    rows = su("select collection, id, data from public.portal_records")
    su("alter table public.portal_records disable trigger user")
    for c, i, d in rows:
        su("update public.portal_records set data = %s where collection = %s and id = %s", (json.dumps(poison(d)), c, i))
    su("alter table public.portal_records enable trigger user")
    ok(len(rows) > 20, str(len(rows)) + " records poisoned")

    # ----- CloudWAV opens every screen
    b, ctx, pg = open_page_supabase(p, mock); routes(ctx)
    pg.fill("#loginEmail", "ops@cloudwav.test"); pg.fill("#loginPassword", "op-pass-123"); pg.click("#loginSubmit"); pg.wait_for_timeout(2500)
    screens = pg.evaluate("[...document.querySelectorAll('#navOperator [data-screen]')].map(e => e.getAttribute('data-screen'))")
    ok(len(screens) > 15, "Operator has " + str(len(screens)) + " screens to check")
    for s in screens:
        try: nav(pg, s); pg.wait_for_timeout(250)
        except Exception as e: ok(False, "could not open " + s + ": " + str(e)[:80]); continue
        # open the first detail pop-up on screens that have one
        for sel in ["[data-view-profile]", "[data-view-vendor]", "[data-detail]", "[data-cal-day]", "[data-sow-details]"]:
            el = pg.locator(sel + ":visible").first
            if el.count():
                try: el.click(timeout=1500); pg.wait_for_timeout(250); check(pg, s + " " + sel); pg.evaluate("closeModal()")
                except Exception: pass
                break
        check(pg, s)
    b.close()

    # ----- anonymous visitors on public pages
    ids = {c: [i for cc, i, _ in rows if cc == c] for c in ("affiliatePrograms", "landingPages", "partnerPages")}
    pages = ["?invite=" + x for x in ids["affiliatePrograms"][:3]] + ["?lp=" + x for x in ids["landingPages"][:2]] + ["?apply=vendor&vendorId=intelsense"]
    for q in pages:
        b, ctx, pg = open_page_supabase(p, mock, q); routes(ctx); pg.reload(); pg.wait_for_timeout(1200)
        check(pg, "public page " + q)
        b.close()
report()
