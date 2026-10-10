from harness import *
import os, sys, json, uuid, urllib.parse
if not os.path.exists("/usr/lib/postgresql/16/bin/initdb"):
    print("SKIP: PostgreSQL 16 not installed"); srv.shutdown(); sys.exit(0)
from pgmock import start_pg, stop_pg, PgSupabase
import psycopg2
USERS = { "ops@cloudwav.test": {"password": "op-pass-123", "id": "11111111-0000-0000-0000-000000000001"} }
PORTAL = { USERS["ops@cloudwav.test"]["id"]: {"role": "operator", "entity_id": None, "display_name": "Peter Phelan"} }

class AcctMock(PgSupabase):
    """Adds what account set-up needs: sign-up, password checks against the stored hash, changing your own
    password, and portal_users read from the database (so roles given by portal_setup_account are real)."""
    signups_on = False   # finding 7: public sign-up is off; the database creates company logins
    signup_calls = 0
    def admin(self, q, args=()):
        con = psycopg2.connect(self.dsn); con.autocommit = True; cur = con.cursor(); cur.execute(q, args)
        r = cur.fetchall() if cur.description else None; con.close(); return r
    def handle(self, route):
        req = route.request; u = urllib.parse.urlparse(req.url); path = u.path; qs = urllib.parse.parse_qs(u.query)
        hdr = {"access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*"}
        def j(status, body): route.fulfill(status=status, content_type="application/json", body=json.dumps(body, default=str), headers=hdr)
        if req.method == "OPTIONS": return route.fulfill(status=200, headers=hdr)
        if path == "/auth/v1/signup":
            body = json.loads(req.post_data or "{}"); email = body.get("email", "").lower(); self.signup_calls += 1
            if not self.signups_on: return j(422, {"code": 422, "error_code": "signup_disabled", "msg": "Signups not allowed for this instance"})
            if email not in self.users:
                self.users[email] = {"password": body.get("password"), "id": str(uuid.uuid4())}
                self.admin("insert into auth.users(id,email) values (%s,%s)", (self.users[email]["id"], email))
            return j(200, self.user_obj(email))
        if path == "/auth/v1/token" and qs.get("grant_type") == ["password"]:
            body = json.loads(req.post_data or "{}"); email = body.get("email", "").lower(); pw = body.get("password", "")
            if email not in self.users:   # a login the database created
                row = self.admin("select id from auth.users where lower(email) = %s", (email,))
                if row: self.users[email] = {"password": None, "id": str(row[0][0])}
            if email in self.users:
                h = self.admin("select encrypted_password is null, case when encrypted_password is null then false else encrypted_password = extensions.crypt(%s, encrypted_password) end from auth.users where id=%s", (pw, self.users[email]["id"]))
                good = (h and ((h[0][0] and self.users[email]["password"] == pw) or (not h[0][0] and h[0][1])))
                if good:
                    self.admin("update auth.users set last_sign_in_at = now() where id=%s", (self.users[email]["id"],))
                    return j(200, self.session(email))
            return j(400, {"code": 400, "error_code": "invalid_credentials", "msg": "Invalid login credentials"})
        if path == "/auth/v1/user" and req.method == "PUT":
            uid = self.uid_from_auth(req.headers.get("authorization", "")); body = json.loads(req.post_data or "{}")
            for email, uu in self.users.items():
                if uu["id"] == uid:
                    if body.get("password"): self.admin("update auth.users set encrypted_password = extensions.crypt(%s, extensions.gen_salt('bf')) where id=%s", (body["password"], uid))
                    return j(200, self.user_obj(email))
            return j(401, {"msg": "invalid JWT"})
        if path == "/rest/v1/portal_users":
            uid = self.uid_from_auth(req.headers.get("authorization", ""))
            want = (qs.get("id") or [""])[0].replace("eq.", "")
            rows = self.sql("select * from portal_users where id = %s", (want,), uid=uid) if uid else []
            if "vnd.pgrst.object" in (req.headers.get("accept") or ""):
                return j(200, rows[0]) if rows else j(406, {"code": "PGRST116", "message": "0 rows"})
            return j(200, rows)
        return super().handle(route)

mock = AcctMock(USERS, PORTAL, start_pg())
def db(c): return [r for r in mock.rows_as_operator() if r["collection"] == c]
def pu(email): return mock.admin("select role, entity_id, must_change_password from portal_users where email=%s", (email,))
def login(pg, email, pw):
    pg.fill("#loginEmail", email); pg.fill("#loginPassword", pw); pg.click("#loginSubmit"); pg.wait_for_timeout(1500)
def session(p, email, pw):
    b, ctx, pg = open_page_supabase(p, mock); login(pg, email, pw); return b, ctx, pg
def settle(pg):
    for _ in range(60):
        if not pg.evaluate("CLOUD_PENDING()"): return True
        pg.wait_for_timeout(150)
    return False

with sync_playwright() as p:
    # ----- CloudWAV sets up a vendor from Manage programs: company name + email
    b, ctx, op = session(p, "ops@cloudwav.test", "op-pass-123"); settle(op)
    role(op, "operator"); nav(op, "operator-programs")
    op.click('#scr-operator-programs [data-acct-setup="vendor"]:not([data-acct-entity])'); op.wait_for_timeout(200)
    op.fill("#acctCompany", "AgentID"); op.fill("#acctEmail", "Founder@AgentID.test"); op.fill("#acctContact", "Ann Lee")
    op.click("#acctCreateBtn"); op.wait_for_timeout(2500); settle(op)
    ok(op.locator("#acctTempPw").count() == 1, "A temporary password is shown to CloudWAV")
    temp = op.inner_text("#acctTempPw").strip()
    ok(len(temp) == 12 and any(c.isdigit() for c in temp) and any(c.isupper() for c in temp), "It is 12 characters with letters and digits")
    mail = op.get_attribute("#acctMailBtn", "href")
    ok(mail.startswith("mailto:founder%40agentid.test") and urllib.parse.quote(temp) in mail and "Sign%20in" in mail, "An email draft carries the sign-in page, email and temporary password")
    ok(pu("founder@agentid.test") == [("vendor", "agentid", True)], "The login is a vendor for the new company and must choose a password")
    rec = [r for r in db("programs") if r["id"] == "agentid"]
    ok(len(rec) == 1 and rec[0]["data"]["name"] == "AgentID" and rec[0]["data"]["needsProfile"] is True and rec[0]["writers"] == ["vendor:agentid"], "The company record is saved for that vendor to finish")
    op.click("[data-acct-close]"); op.wait_for_timeout(200)
    nav(op, "operator-accounts"); op.wait_for_timeout(1200)
    row = op.locator("#accountRows tr", has_text="founder@agentid.test")
    ok(row.count() == 1 and "Waiting for first sign-in" in row.inner_text() and "AgentID" in row.inner_text() and "Profile not finished" in row.inner_text(), "Accounts & Logins lists it as waiting for first sign-in")
    ok(op.locator("#accountRows tr", has_text="ops@cloudwav.test").count() == 0, "Operator logins are not listed for changes")

    # ----- the vendor signs in with the temporary password
    b2, ctx2, v = open_page_supabase(p, mock)
    login(v, "founder@agentid.test", "wrong-password")
    ok("don't match" in v.inner_text("#loginError"), "A wrong password is refused")
    login(v, "founder@agentid.test", temp)
    ok(v.locator("#loginPanelNewPassword").is_visible() and "Choose your password" in v.inner_text("#newPasswordTitle") and "temporary password" in v.inner_text("#newPasswordSub"), "First sign-in asks them to choose their own password")
    v.fill("#newPassword", "short"); v.click("#newPasswordSubmit"); v.wait_for_timeout(200)
    ok(v.locator("#newPasswordError").is_visible(), "Too-short passwords are refused")
    v.fill("#newPassword", "my-own-pass-1"); v.click("#newPasswordSubmit"); v.wait_for_timeout(2500); settle(v)
    ok(pu("founder@agentid.test") == [("vendor", "agentid", False)], "Choosing a password clears the flag")
    ok(visible_screen(v) == ["scr-vendor-overview"] and v.locator("#vendorOverviewEditForm").count() == 1, "They land on their own profile, open for editing")
    ok(v.input_value("#vpName") == "AgentID" and v.input_value("#vpDesc") == "", "The name CloudWAV entered is filled in; the rest is theirs to complete")
    v.fill("#vpVertical", "AI agents"); v.fill("#vpOrigin", "Thailand"); v.fill("#vpDesc", "Identity for AI agents.")
    v.locator('#vendorOverviewEditForm [data-vendor-edit-save="agentid"]').first.click(); v.wait_for_timeout(600); settle(v)
    rec = [r for r in db("programs") if r["id"] == "agentid"][0]["data"]
    ok(rec["desc"] == "Identity for AI agents." and rec["needsProfile"] is False and rec["tiers"][0]["rate"] == "To be agreed", "Their profile saves; commission stays as CloudWAV set it")
    # change password from the account menu
    v.click("#accountBtn"); v.wait_for_timeout(150)
    ok(v.locator("#changePwBtn").is_visible() and "AgentID" in v.inner_text("#accountMeta"), "Account menu shows the company and a Change password button")
    v.click("#changePwBtn"); v.wait_for_timeout(150)
    v.fill("#cpwNew", "another-pass-2"); v.fill("#cpwAgain", "different"); v.click("#cpwSave"); v.wait_for_timeout(200)
    ok("don't match" in v.inner_text("#cpwErr"), "The two entries must match")
    v.fill("#cpwAgain", "another-pass-2"); v.click("#cpwSave"); v.wait_for_timeout(900)
    ok(v.locator("#modalBackdrop").count() == 0, "Password changed from the account menu")
    # investment round, private
    nav(v, "vendor-overview"); v.click("[data-funding-edit]"); v.wait_for_timeout(150)
    v.select_option("#fundStatus", "raising"); v.select_option("#fundRound", "Seed"); v.fill("#fundTarget", "USD 500K"); v.click("[data-funding-save]"); v.wait_for_timeout(500); settle(v)
    f = db("fundingProfiles")
    ok(len(f) == 1 and f[0]["id"] == "vendor:agentid" and f[0]["readers"] == ["vendor:agentid"] and f[0]["data"]["round"] == "Seed", "Investment round saved, readable only by the vendor (and CloudWAV)")
    b2.close()
    b3, ctx3, v2 = open_page_supabase(p, mock)
    login(v2, "founder@agentid.test", "my-own-pass-1")
    ok("don't match" in v2.inner_text("#loginError"), "The replaced password no longer works")
    login(v2, "founder@agentid.test", "another-pass-2"); settle(v2)
    ok(visible_screen(v2) == ["scr-vendor-overview"] and v2.locator("#vendorOverviewEditForm").count() == 0 and v2.locator("#loginPanelNewPassword").is_visible() is False, "Next sign-in goes straight to the normal overview")
    b3.close()

    # ----- CloudWAV: sees the round, resets the password, removes access
    op.reload(); op.wait_for_timeout(2500); settle(op)
    nav(op, "operator-programs")
    ok("Raising now" in op.locator("#operatorProgramRows tr", has_text="AgentID").inner_text(), "CloudWAV sees the vendor's round in Manage programs")
    nav(op, "operator-accounts"); op.wait_for_timeout(1200)
    row = op.locator("#accountRows tr", has_text="founder@agentid.test")
    ok("Active" in row.inner_text() and "Profile not finished" not in row.inner_text(), "The login now shows as Active")
    row.locator("[data-acct-reset]").click(); op.wait_for_timeout(200); op.click("[data-acct-reset-go]"); op.wait_for_timeout(1500)
    temp2 = op.inner_text("#acctTempPw").strip()
    ok(temp2 != temp and pu("founder@agentid.test") == [("vendor", "agentid", True)], "Reset password gives a new temporary password")
    op.click("[data-acct-close]"); op.wait_for_timeout(300)
    b4, ctx4, v3 = open_page_supabase(p, mock)
    login(v3, "founder@agentid.test", "another-pass-2")
    ok("don't match" in v3.inner_text("#loginError"), "After a reset the old password stops working")
    login(v3, "founder@agentid.test", temp2)
    ok(v3.locator("#loginPanelNewPassword").is_visible(), "The new temporary password asks for a new password again")
    b4.close()

    # ----- a partner, from Partners & tiers; and a login for a company that already exists
    nav(op, "operator-partners")
    op.click('#scr-operator-partners [data-acct-setup="partner"]'); op.wait_for_timeout(200)
    op.fill("#acctCompany", "Seven Peaks"); op.fill("#acctEmail", "hello@sevenpeaks.test"); op.click("#acctCreateBtn"); op.wait_for_timeout(2500); settle(op)
    tp = op.inner_text("#acctTempPw").strip()
    ok(pu("hello@sevenpeaks.test") == [("partner", "seven-peaks", True)] and any(r["id"] == "seven-peaks" and r["writers"] == ["partner:seven-peaks"] for r in db("partnerProfiles")), "Partner company and login created")
    op.click("[data-acct-close]"); op.wait_for_timeout(200)
    b5, ctx5, pt = open_page_supabase(p, mock)
    login(pt, "hello@sevenpeaks.test", tp); pt.fill("#newPassword", "partner-pass-1"); pt.click("#newPasswordSubmit"); pt.wait_for_timeout(2500); settle(pt)
    ok(visible_screen(pt) == ["scr-partner-profile-editor"] and pt.input_value("#profileName") == "Seven Peaks", "The partner lands on their profile form")
    b5.close()
    nav(op, "operator-programs")
    op.locator("#operatorProgramRows tr", has_text="Botnoi Voice").locator("[data-acct-setup]").click(); op.wait_for_timeout(200)
    ok(op.locator("#acctCompany").count() == 0 and "Botnoi Voice" in op.inner_text(".modal"), "Login button on a vendor row asks only for the email")
    # finding 7: someone registered this email first and signed in: refused, they never get Botnoi's access
    grab = str(uuid.uuid4()); mock.admin("insert into auth.users(id, email, last_sign_in_at) values (%s, 'grab@botnoi.test', now())", (grab,))
    op.fill("#acctEmail", "grab@botnoi.test"); op.click("#acctCreateBtn"); op.wait_for_timeout(2000)
    ok(op.locator("#acctErr").is_visible() and "already has a login that has been used" in op.inner_text("#acctErr") and pu("grab@botnoi.test") == [], "An email someone already signed in with is refused")
    op.fill("#acctEmail", "new@botnoi.test"); op.click("#acctCreateBtn"); op.wait_for_timeout(2500)
    ok(op.locator("#acctTempPw").count() == 1 and pu("new@botnoi.test") == [("vendor", "botnoi", True)], "A new email works with public sign-up switched off")
    ok(mock.signup_calls == 0, "The portal never uses public sign-up")
    op.click("[data-acct-close]"); op.wait_for_timeout(200)
    # finding 9: a company with the same name as an existing one is never matched by name
    nav(op, "operator-partners")
    op.click('#scr-operator-partners [data-acct-setup="partner"]:not([data-acct-entity])'); op.wait_for_timeout(200)
    op.fill("#acctCompany", "seven peaks"); op.fill("#acctEmail", "other@sevenpeaks.test"); op.click("#acctCreateBtn"); op.wait_for_timeout(1500)
    ok(op.locator("#acctErr").is_visible() and "Login button on its row" in op.inner_text("#acctErr") and pu("other@sevenpeaks.test") == [], "A look-alike company name is refused, not matched")
    op.click(".modal .modal-close"); op.wait_for_timeout(200)
    nav(op, "operator-accounts"); op.wait_for_timeout(1200)
    op.locator("#accountRows tr", has_text="new@botnoi.test").locator("[data-acct-remove]").click(); op.wait_for_timeout(200); op.click("[data-acct-remove-go]"); op.wait_for_timeout(1500)
    ok(pu("new@botnoi.test") == [] and op.locator("#accountRows tr", has_text="new@botnoi.test").count() == 0, "Remove access takes the login's role away")
    ok(mock.errors == [], "No database refusals along the way: " + "; ".join(mock.errors[:3]))
    report()
    b.close()
stop_pg()
