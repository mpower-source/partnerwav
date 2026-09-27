from playwright.sync_api import sync_playwright
import http.server, threading, functools, socketserver, os
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
H=functools.partial(Q, directory=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
socketserver.TCPServer.allow_reuse_address=True
srv=http.server.ThreadingHTTPServer(("127.0.0.1",8766),H); threading.Thread(target=srv.serve_forever,daemon=True).start()
URL="http://localhost:8766/partnerwav-v11-merged.html"
errs=[]; R=[]
def ok(c,m): R.append(("PASS " if c else "FAIL ")+m)
def open_page(p, query=""):
    b=p.chromium.launch(); ctx=b.new_context(viewport={"width":1280,"height":900}); ctx.grant_permissions(["clipboard-read","clipboard-write"])
    pg=ctx.new_page()
    pg.on("pageerror",lambda e: errs.append(str(e))); pg.on("dialog",lambda d:d.accept())
    pg.on("console",lambda m: errs.append(m.text) if m.type=="error" and "Failed to load resource" not in m.text else None)
    pg.goto(URL+query); pg.wait_for_timeout(600); return b,pg
def nav(pg, screen):
    pg.locator(f'[data-screen="{screen}"]:visible').first.click(); pg.wait_for_timeout(200)
def role(pg, r):
    pg.locator(f'[data-role="{r}"]').first.click(); pg.wait_for_timeout(200)
def visible_screen(pg):
    return pg.evaluate("[...document.querySelectorAll('[id^=\"scr-\"]')].filter(e=>!e.hidden).map(e=>e.id)")
def report():
    srv.shutdown(); print("\n".join(R)); print("JS ERRORS:",errs)
