from harness import *
import json

# Every public form carries the hidden bot trap; in the browser-only demo a filled-in trap is thanked but not saved.
with sync_playwright() as p:
    b, pg = open_page(p)
    role(pg, "partner"); nav(pg, "partner-pages"); pg.click("[data-pp-new]"); pg.wait_for_timeout(200)
    pg.click('[data-pp-template="demo"]'); pg.wait_for_timeout(300)
    ok(pg.locator("#ppPreview #hp_pp").count() == 0, "The editor preview has no bot trap (sign-ups are off there)")
    pg.click('[data-pp-save="publish"]'); pg.wait_for_timeout(300)
    pid = json.loads(pg.evaluate("localStorage.getItem('partnerWAV_partnerPages')"))[0]["id"]
    leads0 = len(json.loads(pg.evaluate("localStorage.getItem('partnerWAV_leads')") or "[]"))

    pg.goto(URL + "?demo=1&pp=" + pid); pg.wait_for_timeout(700)
    ok(pg.locator("#hp_pp").count() == 1 and pg.get_attribute("#hp_pp", "tabindex") == "-1" and pg.evaluate("document.getElementById('hp_pp').getBoundingClientRect().right < 0"), "Landing page form has the hidden bot trap")
    ok(pg.locator("[data-captcha]").count() == 0, "No CAPTCHA until a site key is saved")
    pg.fill("#ppName", "Bot"); pg.fill("#ppEmail", "bot@spam.test"); pg.fill("#ppCompany", "Spam"); pg.check("#ppConsent")
    pg.evaluate("document.getElementById('hp_pp').value = 'x'"); pg.click("[data-pp-submit]"); pg.wait_for_timeout(300)
    ok(pg.locator("[data-pp-done]").count() == 1, "A bot is thanked")
    ok(len(json.loads(pg.evaluate("localStorage.getItem('partnerWAV_leads')") or "[]")) == leads0, "...but no lead is saved")

    pg.goto(URL + "?demo=1&invite=botnoi-sme-ai-invite"); pg.wait_for_timeout(700)
    ok(pg.locator("#hp_invite").count() == 1, "Invite page form has the hidden bot trap")
    pg.goto(URL + "?demo=1&apply=vendor&vendorId=intelsense"); pg.wait_for_timeout(700)
    ok(pg.locator("#hp_apply").count() == 1, "Partner application form has the hidden bot trap")
    b.close()
report()
