"""Supabase stand-in for end-to-end tests: Auth is mocked (harness.MockSupabase) and PostgREST calls to
portal_records run against a real local PostgreSQL 16 with supabase/portal_records.sql loaded, so
row-level security and the guard trigger are the real ones."""
import os, json, subprocess, time, urllib.parse
import psycopg2, psycopg2.extras
from harness import MockSupabase, ROOT

PGDIR = "/var/tmp/partnerwav-pg-e2e"; PORT = 55433; BIN = "/usr/lib/postgresql/16/bin"

def start_pg():
    subprocess.run(f"su postgres -c '{BIN}/pg_ctl -D {PGDIR}/data stop -m fast'", shell=True, capture_output=True)
    subprocess.run(["rm", "-rf", PGDIR]); os.makedirs(PGDIR); subprocess.run(["chown", "postgres", PGDIR])
    subprocess.run(f"su postgres -c '{BIN}/initdb -D {PGDIR}/data -A trust -U postgres'", shell=True, check=True, capture_output=True)
    subprocess.run(f"su postgres -c \"{BIN}/pg_ctl -D {PGDIR}/data -o '-p {PORT} -k {PGDIR}' -l {PGDIR}/log start\"", shell=True, check=True, capture_output=True)
    time.sleep(1.5)
    psql = ["psql", "-h", PGDIR, "-p", str(PORT), "-U", "postgres", "-q", "-v", "ON_ERROR_STOP=1"]
    subprocess.run(psql + ["-f", os.path.join(ROOT, "tests/sql/supabase_shim.sql")], check=True, capture_output=True)
    users_sql = open(os.path.join(ROOT, "supabase/portal_users.sql")).read().split("\nwith wanted")[0]
    subprocess.run(psql, input=users_sql.encode(), check=True, capture_output=True)
    subprocess.run(psql + ["-f", os.path.join(ROOT, "supabase/portal_records.sql")], check=True, capture_output=True)
    return f"host={PGDIR} port={PORT} user=postgres dbname=postgres"

def stop_pg():
    subprocess.run(f"su postgres -c '{BIN}/pg_ctl -D {PGDIR}/data stop -m fast'", shell=True, capture_output=True)

class PgSupabase(MockSupabase):
    def __init__(self, users, portal_users, dsn):
        super().__init__(users, portal_users)
        self.dsn = dsn; self.errors = []
        con = psycopg2.connect(dsn); con.autocommit = True; cur = con.cursor()
        cur.execute("delete from auth.users where email like '%.test'")
        for email, u in users.items():
            cur.execute("insert into auth.users(id,email) values (%s,%s) on conflict do nothing", (u["id"], email))
            row = portal_users.get(u["id"])
            if row:
                cur.execute("insert into public.portal_users(id,email,role,entity_id,display_name) values (%s,%s,%s,%s,%s) on conflict (id) do update set role=excluded.role, entity_id=excluded.entity_id",
                            (u["id"], email, row["role"], row["entity_id"], row["display_name"]))
        con.close()

    def sql(self, q, args=(), fetch=True, uid=None):
        """Run as the caller: role anon or authenticated, with auth.uid() = uid."""
        con = psycopg2.connect(self.dsn)
        try:
            cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("set local role " + ("authenticated" if uid else "anon"))
            cur.execute("select set_config('request.jwt.claim.sub', %s, true)", (uid or "",))
            cur.execute(q, args)
            rows = cur.fetchall() if fetch else cur.rowcount
            con.commit(); return rows
        finally: con.close()

    def rows_as_operator(self):
        con = psycopg2.connect(self.dsn); cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("select * from portal_records order by collection, id"); r = cur.fetchall(); con.close(); return r

    files = {}   # "bucket/path" -> (bytes, content type)

    def handle_storage(self, route):
        req = route.request; u = urllib.parse.urlparse(req.url)
        hdr = {"access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*", "access-control-expose-headers": "*"}
        if req.method == "OPTIONS": return route.fulfill(status=200, headers=hdr)
        uid = self.uid_from_auth(req.headers.get("authorization", ""))
        path = urllib.parse.unquote(u.path[len("/storage/v1/object/"):])
        def js(body, status=200): route.fulfill(status=status, content_type="application/json", body=json.dumps(body), headers=hdr)
        try:
            if path.startswith("sign/") and req.method == "POST":
                bucket, name = path[5:].split("/", 1)
                rows = self.sql("select name from storage.objects where bucket_id=%s and name=%s", (bucket, name), uid=uid)
                if not rows: return js({"statusCode": "404", "error": "not_found", "message": "Object not found"}, 400)
                return js({"signedURL": f"/object/sign/{bucket}/{urllib.parse.quote(name)}?token=t-{uid}"})
            if path.startswith("sign/") and req.method == "GET":
                bucket, name = path[5:].split("/", 1)
                data, ctype = self.files.get(bucket + "/" + name, (b"", "application/octet-stream"))
                return route.fulfill(status=200, body=data, headers={**hdr, "content-type": ctype})
            if req.method in ("POST", "PUT"):
                bucket, name = path.split("/", 1)
                raw = req.post_data_buffer or b""; ctype = req.headers.get("content-type", "")
                if ctype.startswith("multipart/form-data"):
                    boundary = ctype.split("boundary=")[1].encode()
                    for part in raw.split(b"--" + boundary):
                        if b"filename=" in part or (b'name=""' in part and b"\r\n\r\n" in part):
                            head, _, body = part.partition(b"\r\n\r\n")
                            if b"cacheControl" in head: continue
                            raw = body[:-2] if body.endswith(b"\r\n") else body
                            m = [l for l in head.split(b"\r\n") if l.lower().startswith(b"content-type:")]
                            ctype = m[0].split(b":", 1)[1].strip().decode() if m else "application/octet-stream"
                            break
                upsert = (req.headers.get("x-upsert") or "") == "true"
                exists = self.sql("select 1 from storage.objects where bucket_id=%s and name=%s", (bucket, name), uid=uid)
                if exists and upsert:
                    n = self.sql("update storage.objects set name = name where bucket_id=%s and name=%s", (bucket, name), fetch=False, uid=uid)
                    if not n: raise psycopg2.Error("new row violates row-level security policy")
                else:
                    self.sql("insert into storage.objects(bucket_id, name) values (%s, %s)", (bucket, name), fetch=False, uid=uid)
                self.files[bucket + "/" + name] = (raw, ctype)
                return js({"Id": name, "Key": bucket + "/" + name})
        except psycopg2.Error as e:
            msg = ((getattr(e, "pgerror", None) or str(e)).strip().split("\n")[0]).replace("ERROR:  ", "")
            self.errors.append("storage: " + msg)
            return js({"statusCode": "403", "error": "Unauthorized", "message": msg}, 400)
        return js({"message": "not mocked"}, 404)

    def handle(self, route):
        req = route.request; u = urllib.parse.urlparse(req.url)
        if u.path.startswith("/storage/v1/object/"): return self.handle_storage(route)
        if u.path != "/rest/v1/portal_records": return super().handle(route)
        hdr = {"access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*", "access-control-expose-headers": "*"}
        if req.method == "OPTIONS": return route.fulfill(status=200, headers=hdr)
        uid = self.uid_from_auth(req.headers.get("authorization", ""))
        qs = urllib.parse.parse_qs(u.query)
        where, args = [], []
        for k, vals in qs.items():
            if k in ("select", "order", "offset", "limit", "on_conflict", "columns"): continue
            v = vals[0]
            if v.startswith("eq."): where.append(f"{k} = %s"); args.append(v[3:])
            elif v.startswith("in.("): items = [x.strip('"') for x in v[4:-1].split(",")]; where.append(f"{k} = any(%s)"); args.append(items)
        wsql = (" where " + " and ".join(where)) if where else ""
        def ok_json(body, status=200): route.fulfill(status=status, content_type="application/json", body=json.dumps(body, default=str), headers=hdr)
        try:
            if req.method == "GET":
                cols = (qs.get("select") or ["*"])[0]
                cols = ",".join(c for c in cols.split(",") if c in ("collection", "id", "data", "readers", "writers", "is_public", "updated_at")) or "*"
                lim = int((qs.get("limit") or ["100000"])[0]); off = int((qs.get("offset") or ["0"])[0])
                rng = req.headers.get("range")
                if rng and "-" in rng: a, b2 = rng.split("-"); off = int(a); lim = int(b2) - int(a) + 1
                rows = self.sql(f"select {cols} from portal_records{wsql} order by collection, id limit {lim} offset {off}", args, uid=uid)
                if "vnd.pgrst.object" in (req.headers.get("accept") or ""):
                    return ok_json(rows[0] if rows else None) if rows else route.fulfill(status=406, content_type="application/json", headers=hdr, body=json.dumps({"code": "PGRST116", "message": "JSON object requested, multiple (or no) rows returned", "details": "The result contains 0 rows"}))
                return ok_json(rows)
            if req.method == "POST":
                body = json.loads(req.post_data or "[]"); body = body if isinstance(body, list) else [body]
                ignore = "ignore-duplicates" in (req.headers.get("prefer") or "")
                for r in body:
                    self.sql("insert into portal_records(collection,id,data,readers,writers,is_public) values (%s,%s,%s,%s,%s,%s) on conflict (collection,id) do "
                             + ("nothing" if ignore else "update set data=excluded.data, readers=excluded.readers, writers=excluded.writers, is_public=excluded.is_public"),
                             (r["collection"], r["id"], json.dumps(r["data"]), r.get("readers") or [], r.get("writers") or [], bool(r.get("is_public"))), fetch=False, uid=uid)
                return route.fulfill(status=201, headers=hdr, body="")
            if req.method == "DELETE":
                self.sql(f"delete from portal_records{wsql}", args, fetch=False, uid=uid)
                return route.fulfill(status=204, headers=hdr, body="")
        except psycopg2.Error as e:
            msg = (e.pgerror or str(e)).strip().split("\n")[0].replace("ERROR:  ", "")
            self.errors.append(msg)
            return ok_json({"code": e.pgcode or "42501", "message": msg, "details": None, "hint": None}, 403 if (e.pgcode or "").startswith("42") else 400)
        return ok_json({"message": "not mocked"}, 404)
