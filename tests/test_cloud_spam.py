from harness import *
import os, sys, json
if not os.path.exists("/usr/lib/postgresql/16/bin/initdb"):
    print("SKIP: PostgreSQL 16 not installed"); srv.shutdown(); sys.exit(0)
import psycopg2
from pgmock import start_pg, stop_pg, PgSupabase
QRJS = qrcode_js()
USERS = {"ops@cloudwav.test": {"password": "op-pass-123", "id": "11111111-0000-0000-0000-000000000001"}}
PORTAL = {USERS["ops@cloudwav.test"]["id"]: {"role": "operator", "entity_id": None, "display_name": "Peter Phelan"}}
OFFER = "botnoi-sme-ai-invite"
mock = PgSupabase(USERS, PORTAL, start_pg())
def db(c): return [r for r in mock.rows_as_operator() if r["collection"] == c]
def su(q):
    con = psycopg2.connect(mock.dsn); con.autocommit = True; con.cursor().execute(q); con.close()
def settle(pg):
    for _ in range(60):
        if not pg.evaluate("CLOUD_PENDING()"): return True
        pg.wait_for_timeout(150)
    return False
# Cloudflare Turnstile stand-in: a button that "solves" the CAPTCHA with window.__token (default: a valid answer)
TURNSTILE = """window.turnstile = { render: function(el, o){ var b = document.createElement('button'); b.type = 'button'; b.textContent = "I'm human";
  b.setAttribute('data-fake-captcha', ''); b.onclick = function(){ o.callback(window.__token || 'good-token-12345'); }; el.appendChild(b); return 1; }, reset: function(){} };"""
def visitor(p, query):
    b, ctx, pg = open_page_supabase(p, mock, query)
    ctx.route("**/cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=QRJS, headers={"access-control-allow-origin": "*"}))
    ctx.route("https://challenges.cloudflare.com/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=TURNSTILE, headers={"access-control-allow-origin": "*"}))
    pg.reload(); pg.wait_for_timeout(1200)
    return b, pg
def fill(pg, name, email):
    pg.fill("#invName", name); pg.fill("#invEmail", email); pg.check("#invConsent")

with sync_playwright() as p:
    # ----- CloudWAV seeds the data and saves the Turnstile site key
    b, ctx, pg = open_page_supabase(p, mock)
    pg.fill("#loginEmail", "ops@cloudwav.test"); pg.fill("#loginPassword", "op-pass-123"); pg.click("#loginSubmit"); pg.wait_for_timeout(2500); settle(pg)
    nav(pg, "integrations"); pg.wait_for_timeout(300)
    card = pg.locator('[data-int="captcha"]')
    ok(card.count() == 1 and "BASIC ONLY" in card.inner_text().upper(), "Operator sees Spam protection, CAPTCHA not on yet")
    pg.fill("#intCaptchaKey", "not a key!"); pg.click('[data-int-save="captcha"]'); pg.wait_for_timeout(200)
    ok("doesn't look like" in pg.inner_text("#intCaptchaError"), "A malformed site key is refused")
    pg.fill("#intCaptchaKey", "0x4AAAAAAAtestSiteKey"); pg.click('[data-int-save="captcha"]'); pg.wait_for_timeout(300); settle(pg)
    pub = [r for r in db("operatorSettings") if r["id"] == "public"]
    ok(pub and pub[0]["is_public"] and pub[0]["data"]["captchaSiteKey"] == "0x4AAAAAAAtestSiteKey" and pub[0]["readers"] == ["*"], "Site key saved to the public settings record")
    ok(not [r for r in db("operatorSettings") if r["id"] == "legal" and r["is_public"]], "Private legal details stay private")
    b.close()

    # ----- the database checks the CAPTCHA once its secret is saved (Cloudflare stubbed in the database)
    su("""create schema if not exists extensions;
      create or replace function extensions.http_post(url text, body text, ctype text) returns table(status int, content text) language sql as $$
        select 200, case when body like '%response=good-token-12345%' and body like 'secret=sekret%' then '{"success":true}' else '{"success":false}' end $$;
      insert into public.portal_secrets(key, value) values ('turnstile_secret', 'sekret') on conflict (key) do update set value = excluded.value;""")
    before = len(db("affiliateSignups"))

    b, pg = visitor(p, "?invite=" + OFFER)
    ok(pg.locator('#inviteForm [data-captcha] [data-fake-captcha]').count() == 1, "The invite form shows the CAPTCHA")
    ok(pg.locator("#hp_invite").count() == 1 and pg.evaluate("document.getElementById('hp_invite').getBoundingClientRect().right < 0") and pg.get_attribute("#hp_invite", "tabindex") == "-1", "Hidden bot trap is on the form, out of sight")
    fill(pg, "Nok Sukjai", "nok@example.co.th"); pg.wait_for_timeout(1600); pg.click("#inviteSubmit"); pg.wait_for_timeout(500)
    ok("security check" in pg.inner_text("#inviteError"), "Can't send before doing the CAPTCHA")
    pg.click("[data-fake-captcha]"); pg.click("#inviteSubmit"); pg.wait_for_timeout(1500)
    ok(len(db("affiliateSignups")) == before + 1, "With the CAPTCHA done, the sign-up is saved")
    row = db("affiliateSignups")[-1]["data"]
    ok("captchaToken" not in row and "hp" not in row, "The CAPTCHA answer and bot trap aren't stored with the sign-up")
    b.close()

    b, pg = visitor(p, "?invite=" + OFFER)
    pg.evaluate("window.__token = 'bad-token-12345'")
    fill(pg, "Fake Person", "fake@example.co.th"); pg.wait_for_timeout(1600); pg.click("[data-fake-captcha]"); pg.click("#inviteSubmit"); pg.wait_for_timeout(1500)
    ok("security check did not pass" in pg.inner_text("#inviteError") and len(db("affiliateSignups")) == before + 1, "A CAPTCHA answer Cloudflare rejects is refused by the database")
    b.close()

    b, pg = visitor(p, "?invite=" + OFFER)
    fill(pg, "Spam Bot", "bot@spam.test"); pg.evaluate("document.getElementById('hp_invite').value = 'http://spam.test'")
    pg.wait_for_timeout(1600); pg.click("[data-fake-captcha]"); pg.click("#inviteSubmit"); pg.wait_for_timeout(1500)
    ok(pg.locator("#inviteForm").count() == 0 and len(db("affiliateSignups")) == before + 1, "A bot that fills the hidden field is thanked, but nothing is saved")
    b.close()

    b, ctx, pg = open_page_supabase(p, mock, "?invite=" + OFFER)
    ctx.route("**/cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=QRJS, headers={"access-control-allow-origin": "*"}))
    ctx.route("https://challenges.cloudflare.com/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=TURNSTILE, headers={"access-control-allow-origin": "*"}))
    pg.reload(); pg.wait_for_selector("[data-fake-captcha]", timeout=10000)
    fill(pg, "Fast Bot", "fast@spam.test"); pg.click("[data-fake-captcha]"); pg.click("#inviteSubmit"); pg.wait_for_timeout(1500)
    ok(len(db("affiliateSignups")) == before + 1, "A form sent faster than a person could fill it is dropped")
    b.close()

    su("delete from public.portal_secrets where key = 'turnstile_secret'")
    b, pg = visitor(p, "?invite=" + OFFER)
    fill(pg, "Nok Sukjai", "nok@example.co.th"); pg.wait_for_timeout(1600); pg.click("[data-fake-captcha]"); pg.click("#inviteSubmit"); pg.wait_for_timeout(1500)
    b.close()
    b, pg = visitor(p, "?invite=" + OFFER)
    fill(pg, "Nok Sukjai", "NOK@example.co.th"); pg.wait_for_timeout(1600); pg.click("[data-fake-captcha]"); pg.click("#inviteSubmit"); pg.wait_for_timeout(1500)
    b.close()
    b, pg = visitor(p, "?invite=" + OFFER)
    fill(pg, "Nok Sukjai", "nok@example.co.th"); pg.wait_for_timeout(1600); pg.click("[data-fake-captcha]"); pg.click("#inviteSubmit"); pg.wait_for_timeout(1500)
    ok("already signed up" in pg.inner_text("#inviteError"), "The same email can't sign up again and again: " + pg.inner_text("#inviteError"))
    b.close()
report()
