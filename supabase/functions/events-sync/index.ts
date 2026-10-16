// PartnerWAV: brings tech events in from public event feeds for the Thailand event calendar.
//
// What it can read (the sources CloudWAV lists in Community partners > Event sources):
//   - iCal links: any public Luma calendar or Luma city page (Subscribe > copy the iCal link), Meetup
//     group calendars, Google calendars, and any other .ics feed.
//   - Eventbrite organizers: their upcoming events through the Eventbrite API (needs EVENTBRITE_TOKEN).
// Every event found waits in "Waiting for review" (import_community_events in supabase/portal_records.sql);
// nothing goes on the public calendar until CloudWAV approves it. The same event is never added twice,
// and one CloudWAV removed is not brought back.
//
// Who can run it:
//   - CloudWAV, signed in, from "Check sources now" (Community Partners > Event sources).
//   - The weekly schedule: an hourly tick sends the header  x-sync-secret: <EVENTS_SYNC_SECRET> with
//     {"scheduled": true}. This function runs the sync only when the schedule set in the portal is due
//     (Bangkok time), and only the sources that are switched on.
//
// Each run records, for every source, how many events it read and why others were left out
// (past, outside the window, no matching keyword, not in a listed city, no signup link), or the error.
//
// Deploy (once, from the Supabase dashboard: Edge Functions > events-sync, paste this file, Deploy).
// Secrets (Edge Functions > Secrets): EVENTS_SYNC_SECRET (the same value saved in Vault for the tick),
// and EVENTBRITE_TOKEN if Eventbrite organizers are used. SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are provided.

import { createClient } from "npm:@supabase/supabase-js@2";
import { type Source, type Row, type Diag, type Schedule, DEFAULT_KEYWORDS, newDiag, hasKeyword, parseIcs, icalRow, isCalendar, okUrl, scheduleDue } from "./rules.ts";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-sync-secret",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });

const DAYS_AHEAD = 90;
const MAX_BYTES = 3_000_000;

function safeEqual(a: string, b: string) {
  if (!a || !b || a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

async function getText(url: string, headers: Record<string, string> = {}) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 15000);
  try {
    const r = await fetch(url, { headers: { "User-Agent": "PartnerWAV-events/1.0", ...headers }, signal: ctl.signal, redirect: "follow" });
    if (!r.ok) throw new Error("the site answered HTTP " + r.status);
    const len = Number(r.headers.get("content-length") || 0);
    if (len > MAX_BYTES) throw new Error("the feed is too large");
    const text = await r.text();
    if (text.length > MAX_BYTES) throw new Error("the feed is too large");
    return text;
  } finally { clearTimeout(t); }
}

async function fromIcal(src: Source, kws: string[], until: number): Promise<{ rows: Row[]; diag: Diag }> {
  if (!src.url || !okUrl(src.url)) throw new Error("not a public https iCal link");
  const text = await getText(src.url, { Accept: "text/calendar" });
  if (!isCalendar(text)) throw new Error("this link returned a web page, not a calendar. Use the iCal (.ics) link from the calendar's Subscribe option");
  const diag = newDiag();
  const items = parseIcs(text, diag);
  diag.read = items.length;
  const now = Date.now(), rows: Row[] = [];
  for (const e of items) {
    const r = icalRow(e, src, kws, until, now);
    if ("row" in r) rows.push(r.row); else diag[r.drop]++;
  }
  diag.kept = rows.length;
  return { rows, diag };
}

async function fromEventbrite(src: Source, kws: string[], until: number): Promise<{ rows: Row[]; diag: Diag }> {
  const token = Deno.env.get("EVENTBRITE_TOKEN");
  if (!token) throw new Error("the EVENTBRITE_TOKEN secret is not set");
  if (!src.orgId || !/^[0-9]{3,20}$/.test(src.orgId)) throw new Error("the Eventbrite organizer id should be digits");
  const diag = newDiag();
  const rows: Row[] = [];
  let cont = "";
  for (let page = 0; page < 3; page++) {
    const u = `https://www.eventbriteapi.com/v3/organizations/${src.orgId}/events/?status=live&order_by=start_asc&expand=venue,organizer&page_size=50` + (cont ? "&continuation=" + encodeURIComponent(cont) : "");
    const d = JSON.parse(await getText(u, { Authorization: "Bearer " + token }));
    for (const e of d.events || []) {
      diag.read++;
      const start = new Date(e.start?.utc || ""), end = new Date(e.end?.utc || "");
      if (isNaN(start.getTime())) { diag.nodate++; continue; }
      if (start.getTime() < Date.now()) { diag.past++; continue; }
      if (start.getTime() > until) { diag.window++; continue; }
      const title = e.name?.text || "", desc = e.summary || e.description?.text || "";
      if (!src.allTech && !hasKeyword(title + " " + desc, kws)) { diag.keyword++; continue; }
      const loc = e.online_event ? "online" : [e.venue?.name, e.venue?.address?.city, e.venue?.address?.country === "TH" ? "Thailand" : ""].filter(Boolean).join(", ");
      const r = icalRow({ uid: "eb-" + e.id, title, start, end: isNaN(end.getTime()) ? null : end, location: loc, url: e.url || "", desc: String(desc), org: e.organizer?.name || "" }, { ...src, source: "eventbrite" }, kws, until, Date.now());
      if ("row" in r) rows.push(r.row); else diag[r.drop]++;
    }
    if (!d.pagination?.has_more_items || !d.pagination?.continuation) break;
    cont = d.pagination.continuation;
  }
  diag.kept = rows.length;
  return { rows, diag };
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json(405, { error: "POST only" });
  const url = Deno.env.get("SUPABASE_URL")!, service = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!service) return json(503, { error: "SUPABASE_SERVICE_ROLE_KEY is not available" });

  let body: { sourceId?: string; scheduled?: boolean } = {};
  try { body = await req.json(); } catch { /* an empty body is fine */ }

  const secret = Deno.env.get("EVENTS_SYNC_SECRET") || "";
  const secretOk = safeEqual(req.headers.get("x-sync-secret") || "", secret);
  // the schedule can only be run with the secret; "Check sources now" needs a signed-in CloudWAV login
  if (body.scheduled === true && !secretOk) return json(403, { error: "the schedule needs the sync secret" });
  let allowed = secretOk;
  if (!allowed) {
    const sb = createClient(url, Deno.env.get("SUPABASE_ANON_KEY")!, { global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } } });
    const { data: u } = await sb.auth.getUser();
    if (!u?.user) return json(401, { error: "Sign in first" });
    const { data: pu } = await sb.from("portal_users").select("role").eq("id", u.user.id).maybeSingle();
    allowed = pu?.role === "operator";
    if (!allowed) return json(403, { error: "CloudWAV only" });
  }

  const admin = createClient(url, service, { auth: { persistSession: false } });
  const { data: rec, error: e1 } = await admin.from("portal_records").select("data")
    .eq("collection", "operatorSettings").eq("id", "eventSources").maybeSingle();
  if (e1) return json(500, { error: "Could not read the event sources" });
  const cfg = (rec?.data || {}) as { sources?: Source[]; keywords?: string[]; schedule?: Schedule };

  if (body.scheduled === true && !scheduleDue(cfg.schedule, new Date())) return json(200, { skipped: "not due" });

  const kws = (cfg.keywords && cfg.keywords.length ? cfg.keywords : DEFAULT_KEYWORDS).slice(0, 200);
  const sources = (cfg.sources || []).filter((s) => s && s.active !== false && s.kind !== "manual" && (!body.sourceId || s.id === body.sourceId)).slice(0, 40);
  const until = Date.now() + DAYS_AHEAD * 86400000;

  const rows: Row[] = [];
  const report: Record<string, unknown>[] = [];
  for (const s of sources) {
    const checkedAt = new Date().toISOString();
    try {
      const got = s.kind === "eventbrite" ? await fromEventbrite(s, kws, until) : await fromIcal(s, kws, until);
      rows.push(...got.rows);
      report.push({ id: s.id, label: s.label || "", found: got.rows.length, checkedAt, ...got.diag });
    } catch (err) {
      report.push({ id: s.id, label: s.label || "", found: 0, checkedAt, error: String((err as Error)?.message || err).slice(0, 240) });
    }
  }
  // the same event listed by two feeds: keep the first
  const seen = new Set<string>(), unique = rows.filter((r) => {
    const k = r.title.toLowerCase().replace(/\W+/g, "") + "|" + r.start.slice(0, 13);
    if (seen.has(k)) return false; seen.add(k); return true;
  }).slice(0, 500);

  const { data: res, error: e2 } = await admin.rpc("import_community_events", { p_rows: unique, p_run: { sources: report } });
  if (e2) return json(500, { error: "Could not save the events", detail: e2.message, sources: report });
  return json(200, { ...(res as Record<string, number>), sources: report });
});
