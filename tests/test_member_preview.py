from harness import *
import os, sys
if not os.path.exists("/usr/lib/postgresql/16/bin/initdb"):
    print("SKIP: PostgreSQL 16 not installed"); srv.shutdown(); sys.exit(0)
from pgmock import start_pg, stop_pg, PgSupabase

# CloudWAV, signed in to the live portal, switches to a member (or promoter) it set up -- no second sign-in needed.
OP = "11111111-0000-0000-0000-000000000001"
USERS = {"cto@cloudwavconsulting.com": {"password": "op-pass-123", "id": OP}}
PORTAL = {OP: {"role": "operator", "entity_id": None, "display_name": "Peter Phelan"}}
mock = PgSupabase(USERS, PORTAL, start_pg())
mock.sql("""insert into portal_records(collection,id,data,readers,writers) values
  ('memberProfiles','peter-phelan','{"id":"peter-phelan","name":"Peter Phelan","headline":"Founder, CloudWAV","topics":["AI"]}','{members}','{member:peter-phelan}'),
  ('mediaProfiles','zipevent','{"id":"zipevent","name":"ZipEvent","status":"approved","kinds":["events"]}','{*}','{media:zipevent}')""", fetch=False, uid=OP)

with sync_playwright() as p:
    b, ctx, pg = open_page_supabase(p, mock)
    pg.fill("#loginEmail", "cto@cloudwavconsulting.com"); pg.fill("#loginPassword", "op-pass-123"); pg.click("#loginSubmit"); pg.wait_for_timeout(2500)
    pg.click('.role-btn[data-role="member"]'); pg.wait_for_timeout(300)
    opts = pg.locator("#previewEntity option").all_inner_texts()
    ok(any("Peter Phelan" in o for o in opts), "The Member button lists the members CloudWAV set up: " + str(opts))
    pg.select_option("#previewEntity", "peter-phelan"); pg.click("#previewGo"); pg.wait_for_timeout(500)
    ok(visible_screen(pg) == ["scr-member-overview"] and "Welcome, Peter" in pg.inner_text("#memberOverviewContent"), "Switching opens Peter's member space, without signing in again")
    ok("Peter Phelan" in pg.inner_text("#previewBanner"), "The banner shows whose space it is")
    nav(pg, "member-profile"); pg.wait_for_timeout(300)
    ok(pg.input_value("#memHeadline") == "Founder, CloudWAV", "His own profile is there to edit")
    pg.click('.role-btn[data-role="media"]'); pg.wait_for_timeout(300)
    ok(any("ZipEvent" in o for o in pg.locator("#previewEntity option").all_inner_texts()), "The Promoter button lists promoters too")
    pg.click("#previewGo"); pg.wait_for_timeout(500)
    ok(visible_screen(pg) == ["scr-media-overview"] and "ZipEvent" in pg.inner_text("#mediaOverviewContent"), "...and opens their workspace")
    pg.click("[data-preview-exit]"); pg.wait_for_timeout(300)
    ok(visible_screen(pg) == ["scr-operator-overview"], "Back to Operator in one click")
    b.close()
report()
