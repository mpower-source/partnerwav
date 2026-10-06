from playwright.sync_api import sync_playwright
import http.server, threading, functools, socketserver, os, json, time, uuid, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
H = functools.partial(Q, directory=ROOT)
socketserver.TCPServer.allow_reuse_address = True
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8766), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://localhost:8766/partnerwav-v11-merged.html"
SUPABASE_HOST = "lnawgyaapcpyrvdtkarp.supabase.co"

# supabase-js v2 UMD build for the mocked-backend tests. tests/vendor/supabase.js is used
# if present; otherwise it's fetched once from npm (npm pack @supabase/supabase-js@2).
def supabase_umd():
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "supabase.js")
    if os.path.exists(local):
        return open(local, encoding="utf8").read()
    import subprocess, tempfile, tarfile, glob
    d = tempfile.mkdtemp()
    subprocess.run(["npm", "pack", "@supabase/supabase-js@2", "--silent"], cwd=d, check=True, capture_output=True)
    tgz = glob.glob(os.path.join(d, "*.tgz"))[0]
    with tarfile.open(tgz) as t:
        return t.extractfile("package/dist/umd/supabase.js").read().decode("utf8")

def qrcode_js():
    """qrcode-generator 1.4.4 (the QR library the portal loads): tests/vendor/ if present, else fetched once via npm pack."""
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "qrcode-generator")
    f = os.path.join(d, "qrcode.js")
    if not os.path.exists(f):
        import subprocess, tempfile, tarfile, glob
        t = tempfile.mkdtemp()
        subprocess.run(["npm", "pack", "qrcode-generator@1.4.4", "--silent"], cwd=t, check=True, capture_output=True)
        os.makedirs(d, exist_ok=True)
        with tarfile.open(glob.glob(os.path.join(t, "*.tgz"))[0]) as z:
            open(f, "wb").write(z.extractfile("package/qrcode.js").read())
    return open(f, encoding="utf8").read()

errs = []; R = []
def ok(c, m): R.append(("PASS " if c else "FAIL ") + m)

IGNORED_ERRORS = ("Failed to load resource", "realtime/v1/websocket")

def _wire(pg):
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and not any(x in m.text for x in IGNORED_ERRORS) else None)

def open_page(p, query="", demo=True):
    """Demo mode (?demo=1) by default: role switcher, no sign-in, Supabase CDN unreachable."""
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 1280, "height": 900})
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    pg = ctx.new_page(); _wire(pg)
    q = query.lstrip("?")
    parts = (["demo=1"] if demo else []) + ([q] if q else [])
    pg.goto(URL + ("?" + "&".join(parts) if parts else "")); pg.wait_for_timeout(600)
    return b, pg

class MockSupabase:
    """Answers supabase-js auth + PostgREST calls for the project host, in-browser."""
    def __init__(self, users, portal_users):
        self.users = users                  # email -> {"password","id"}
        self.portal_users = portal_users    # id -> row
        self.calls = []
    def user_obj(self, email):
        u = self.users[email]
        return {"id": u["id"], "aud": "authenticated", "role": "authenticated", "email": email,
                "app_metadata": {"provider": "email"}, "user_metadata": {}, "created_at": "2026-09-27T00:00:00Z"}
    def jwt(self, email):
        import base64
        def b64(d): return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
        now = int(time.time()); uid = self.users[email]["id"]
        return b64({"alg": "HS256", "typ": "JWT"}) + "." + b64({"sub": uid, "email": email, "role": "authenticated",
            "aud": "authenticated", "iat": now, "exp": now + 3600, "session_id": "s-" + uid}) + ".sig-" + uid
    def session(self, email):
        now = int(time.time())
        return {"access_token": self.jwt(email), "token_type": "bearer", "expires_in": 3600,
                "expires_at": now + 3600, "refresh_token": "ref-" + self.users[email]["id"], "user": self.user_obj(email)}
    def uid_from_auth(self, auth):
        for uu in self.users.values():
            if auth.endswith("sig-" + uu["id"]): return uu["id"]
        return None
    def handle(self, route):
        req = route.request; u = urllib.parse.urlparse(req.url); path = u.path
        qs = urllib.parse.parse_qs(u.query)
        self.calls.append((req.method, path, req.headers.get("authorization", "")))
        def j(status, body): route.fulfill(status=status, content_type="application/json", body=json.dumps(body),
                                           headers={"access-control-allow-origin": "*"})
        if req.method == "OPTIONS":
            return route.fulfill(status=200, headers={"access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*"})
        if path == "/auth/v1/token" and qs.get("grant_type") == ["password"]:
            body = json.loads(req.post_data or "{}"); email = body.get("email", "")
            if email in self.users and self.users[email]["password"] == body.get("password"):
                return j(200, self.session(email))
            return j(400, {"code": 400, "error_code": "invalid_credentials", "msg": "Invalid login credentials"})
        if path == "/auth/v1/logout": return route.fulfill(status=204, headers={"access-control-allow-origin": "*"})
        if path == "/auth/v1/recover": return j(200, {})
        if path == "/auth/v1/user":
            uid = self.uid_from_auth(req.headers.get("authorization", ""))
            for email, uu in self.users.items():
                if uu["id"] == uid: return j(200, self.user_obj(email))
            return j(401, {"msg": "invalid JWT"})
        if path == "/rest/v1/portal_users":
            auth = req.headers.get("authorization", "")
            want = (qs.get("id") or [""])[0].replace("eq.", "")
            row = self.portal_users.get(want)
            # emulate RLS: a user can only read their own row
            if row and self.uid_from_auth(auth) == want:
                return j(200, [row])
            return j(200, [])
        if path.startswith("/rest/v1/"): return j(200, [])
        return j(404, {"msg": "not mocked: " + path})

def open_page_supabase(p, mock, query="", ctx=None, viewport=None):
    """Real supabase-js v2 served locally, with the Supabase project mocked. No demo mode."""
    b = None
    if ctx is None:
        b = p.chromium.launch(); ctx = b.new_context(viewport=viewport or {"width": 1280, "height": 900})
        umd = supabase_umd()
        ctx.route("**/cdn.jsdelivr.net/npm/@supabase/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=umd))
        ctx.route(f"https://{SUPABASE_HOST}/**", mock.handle)
        ctx.route_web_socket(f"wss://{SUPABASE_HOST}/**", lambda ws: None)
    pg = ctx.new_page(); _wire(pg)
    pg.goto(URL + query); pg.wait_for_timeout(900)
    return b, ctx, pg

def open_menu(pg, screen):
    """Menu items live in collapsible sections: open the one holding this screen."""
    if pg.locator(f'[data-screen="{screen}"]:visible').count() == 0:
        head = pg.locator(f'nav.navgroup:not([hidden]) .navsec:has([data-screen="{screen}"]) .navsec-head')
        if head.count(): head.first.click(); pg.wait_for_timeout(100)
def in_menu(pg, screen):
    open_menu(pg, screen)
    return pg.locator(f'[data-screen="{screen}"]:visible').count() == 1
def nav(pg, screen):
    open_menu(pg, screen)
    pg.locator(f'[data-screen="{screen}"]:visible').first.click(); pg.wait_for_timeout(200)
def role(pg, r):
    pg.locator(f'[data-role="{r}"]').first.click(); pg.wait_for_timeout(200)
def visible_screen(pg):
    return pg.evaluate("[...document.querySelectorAll('[id^=\"scr-\"]')].filter(e=>!e.hidden).map(e=>e.id)")
def report():
    srv.shutdown(); print("\n".join(R)); print("JS ERRORS:", errs)
