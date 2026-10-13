// PartnerWAV: brings tech events in from public event feeds for the Thailand event calendar.
//
// What it can read (the sources CloudWAV lists in Community partners > Event sources):
//   - iCal links: any public Luma calendar or Luma city page (Subscribe > copy the iCal link), Meetup
//     group calendars, Google calendars, and any other .ics feed.
//   - Eventbrite organizers: their upcoming events through the Eventbrite API (needs EVENTBRITE_TOKEN).
//     Eventbrite closed its public event search in 2019, so only organizers you list can be read.
// Meetup's own API is only for paid Meetup Pro accounts and Zipevent has no public API, so those are
// checked by hand on the weekly Saturday check and pasted in from the portal.
//
// Every event found waits in "Waiting for review" (import_community_events in supabase/portal_records.sql);
// nothing goes on the public calendar until CloudWAV approves it. The same event is never added twice,
// and one CloudWAV removed is not brought back.
//
// Deploy (once):
//   supabase secrets set EVENTS_SYNC_SECRET=<a long random string>   # for the Saturday schedule
//   supabase secrets set EVENTBRITE_TOKEN=<private token>              # optional, eventbrite.com/platform
//   supabase functions deploy events-sync --no-verify-jwt   # it checks the caller itself (below)
// The function needs SUPABASE_SERVICE_ROLE_KEY, which Supabase provides to Edge Functions automatically.
//
// Every Saturday at 08:00 Bangkok time (01:00 UTC), with pg_cron and pg_net switched on (Database > Extensions)
// and the same secret saved in Vault as events_sync_secret (Project Settings > Vault), run once in the SQL editor:
//   select cron.schedule('events-sync-saturday', '0 1 * * 6', $$
//     select net.http_post(
//       url := 'https://<your-project-ref>.supabase.co/functions/v1/events-sync',
//       headers := jsonb_build_object('Content-Type', 'application/json', 'x-sync-secret',
//         (select decrypted_secret from vault.decrypted_secrets where name = 'events_sync_secret')),
//       body := '{}'::jsonb) $$);
//
// Who can run it: CloudWAV (signed in as an operator, from the portal's "Check sources now" button),
// or the schedule, sending the header  x-sync-secret: <EVENTS_SYNC_SECRET>.

import { createClient } from "npm:@supabase/supabase-js@2";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-sync-secret",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });

type Source = {
  id: string; kind: "ical" | "eventbrite" | "manual"; label?: string; url?: string; orgId?: string;
  city?: string; allTech?: boolean; active?: boolean; source?: string;
};
type Row = {
  source: string; uid: string; title: string; start: string; durationMin: number; city: string;
  venue: string; price: string; link: string; desc: string; orgName: string; category: string;
};

const DEFAULT_KEYWORDS = ["tech", "startup", "ai", "artificial intelligence", "machine learning", "data", "developer",
  "dev", "software", "saas", "cloud", "cyber", "security", "blockchain", "web3", "fintech", "product", "hackathon",
  "pitch", "founder", "venture", "investor", "devops", "python", "javascript", "coding", "gdg", "aws", "llm"];
const CITIES = ["Bangkok", "Chiang Mai", "Phuket", "Pattaya", "Khon Kaen", "Hua Hin"];
const DAYS_AHEAD = 90;
const MAX_BYTES = 3_000_000;

function safeEqual(a: string, b: string) {
  if (!a || !b || a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

// only public https addresses (no IPs, no local names)
function okUrl(u: string) {
  try {
    const x = new URL(u);
    if (x.protocol !== "https:") return false;
    const h = x.hostname.toLowerCase();
    if (!h.includes(".") || h.endsWith(".local") || h.endsWith(".internal") || h === "localhost") return false;
    if (/^[0-9.]+$/.test(h) || h.includes(":")) return false;
    return true;
  } catch { return false; }
}

async function getText(url: string, headers: Record<string, string> = {}) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 15000);
  try {
    const r = await fetch(url, { headers: { "User-Agent": "PartnerWAV-events/1.0", ...headers }, signal: ctl.signal, redirect: "follow" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const len = Number(r.headers.get("content-length") || 0);
    if (len > MAX_BYTES) throw new Error("feed too large");
    const text = await r.text();
    if (text.length > MAX_BYTES) throw new Error("feed too large");
    return text;
  } finally { clearTimeout(t); }
}

// ----- iCal -----
function unfold(ics: string) { return ics.replace(/\r\n/g, "\n").replace(/\n[ \t]/g, ""); }
function icsText(v: string) { return v.replace(/\\n/gi, "\n").replace(/\\([,;\\])/g, "$1").trim(); }

// minutes to add to a wall-clock time in tz to get UTC
function tzOffsetMin(utcMs: number, tz: string) {
  const f = new Intl.DateTimeFormat("en-US", { timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const p: Record<string, number> = {};
  for (const x of f.formatToParts(new Date(utcMs))) if (x.type !== "literal") p[x.type] = Number(x.value);
  return (Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second) - utcMs) / 60000;
}
function icsDate(params: string, value: string): Date | null {
  const m = value.match(/^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2})?(Z)?)?$/);
  if (!m) return null;
  const [, y, mo, d, h = "00", mi = "00", s = "00", z] = m;
  const wall = Date.UTC(+y, +mo - 1, +d, +h, +mi, +s);
  if (z) return new Date(wall);
  let tz = (params.match(/TZID=([^;:]+)/i) || [])[1] || "Asia/Bangkok";   // floating times: Thailand
  tz = tz.replace(/^"|"$/g, "");
  try { return new Date(wall - tzOffsetMin(wall, tz) * 60000); } catch { return new Date(wall - 7 * 3600000); }
}
function parseIcs(ics: string) {
  const out: { uid: string; title: string; start: Date | null; end: Date | null; location: string; url: string; desc: string; org: string }[] = [];
  const blocks = unfold(ics).split("BEGIN:VEVENT").slice(1);
  for (const b of blocks) {
    const body = b.split("END:VEVENT")[0];
    const f: Record<string, { p: string; v: string }> = {};
    for (const line of body.split("\n")) {
      const i = line.indexOf(":");
      if (i < 1) continue;
      const head = line.slice(0, i), v = line.slice(i + 1);
      const [name, ...ps] = head.split(";");
      const k = name.toUpperCase();
      if (!f[k]) f[k] = { p: ps.join(";"), v };
    }
    if ((f["STATUS"]?.v || "").toUpperCase() === "CANCELLED") continue;
    const desc = icsText(f["DESCRIPTION"]?.v || "");
    out.push({
      uid: (f["UID"]?.v || "").trim(),
      title: icsText(f["SUMMARY"]?.v || ""),
      start: f["DTSTART"] ? icsDate(f["DTSTART"].p, f["DTSTART"].v.trim()) : null,
      end: f["DTEND"] ? icsDate(f["DTEND"].p, f["DTEND"].v.trim()) : null,
      location: icsText(f["LOCATION"]?.v || ""),
      url: (f["URL"]?.v || "").trim() || (desc.match(/https:\/\/[^\s"<>)]+/) || [""])[0],
      desc,
      org: icsText((f["ORGANIZER"]?.p.match(/CN=([^;:]+)/i) || [])[1] || "").replace(/^"|"$/g, ""),
    });
  }
  return out;
}

// ----- shared rules -----
function hasKeyword(text: string, kws: string[]) {
  const t = " " + text.toLowerCase().replace(/[^a-z0-9ก-๙]+/g, " ") + " ";
  return kws.some((k) => {
    const w = k.toLowerCase().replace(/[^a-z0-9ก-๙]+/g, " ").trim();
    return w && (w.length <= 3 ? t.includes(" " + w + " ") : t.includes(w));
  });
}
function whereIs(location: string, fallbackCity: string): string | null {
  const l = location.toLowerCase();
  if (!l) return fallbackCity || "Other";
  if (/zoom|google meet|meet\.google|teams|online|virtual|livestream|youtube|webinar|discord/.test(l)) return "Online";
  for (const c of CITIES) if (l.includes(c.toLowerCase())) return c;
  if (l.includes("thailand") || /[ก-๙]/.test(l) || l.includes("กรุงเทพ")) return "Other";
  return fallbackCity ? fallbackCity : null;   // somewhere else in the world: skip unless the source is a Thai one
}
function kindOf(text: string) {
  const t = text.toLowerCase();
  if (/hackathon|hack day|buildathon/.test(t)) return "hackathon";
  if (/pitch|demo day|investor night/.test(t)) return "pitch";
  if (/open call|call for (startups|applications)|applications open/.test(t)) return "opencall";
  return "community";
}

async function fromIcal(src: Source, kws: string[], until: number): Promise<Row[]> {
  if (!src.url || !okUrl(src.url)) throw new Error("not a public https iCal link");
  const items = parseIcs(await getText(src.url, { Accept: "text/calendar" }));
  const now = Date.now(), rows: Row[] = [];
  const tag = src.source || (/lu\.ma|luma\.com/.test(src.url) ? "luma" : /meetup\.com/.test(src.url) ? "meetup" : "ical");
  for (const e of items) {
    if (!e.title || !e.start || e.start.getTime() < now || e.start.getTime() > until) continue;
    if (!src.allTech && !hasKeyword(e.title + " " + e.desc, kws)) continue;
    const city = whereIs(e.location, src.city || "");
    if (!city) continue;
    const link = okUrl(e.url) ? e.url : (src.url.startsWith("https://") ? src.url.replace(/\.ics.*$/, "") : "");
    if (!link) continue;
    const dur = e.end ? Math.round((e.end.getTime() - e.start.getTime()) / 60000) : 120;
    rows.push({ source: tag, uid: e.uid || link + "#" + e.start.toISOString(), title: e.title, start: e.start.toISOString(),
      durationMin: dur, city, venue: city === "Online" ? "Online" : e.location.split("\n")[0].slice(0, 160), price: "",
      link, desc: e.desc.slice(0, 800), orgName: e.org || src.label || "", category: kindOf(e.title + " " + e.desc) });
  }
  return rows;
}

async function fromEventbrite(src: Source, kws: string[], until: number): Promise<Row[]> {
  const token = Deno.env.get("EVENTBRITE_TOKEN");
  if (!token) throw new Error("EVENTBRITE_TOKEN is not set");
  if (!src.orgId || !/^[0-9]{3,20}$/.test(src.orgId)) throw new Error("the Eventbrite organizer id should be digits");
  const rows: Row[] = [];
  let cont = "";
  for (let page = 0; page < 3; page++) {
    const u = `https://www.eventbriteapi.com/v3/organizations/${src.orgId}/events/?status=live&order_by=start_asc&expand=venue,organizer&page_size=50` + (cont ? "&continuation=" + encodeURIComponent(cont) : "");
    const d = JSON.parse(await getText(u, { Authorization: "Bearer " + token }));
    for (const e of d.events || []) {
      const start = new Date(e.start?.utc || ""), end = new Date(e.end?.utc || "");
      if (isNaN(start.getTime()) || start.getTime() < Date.now() || start.getTime() > until) continue;
      const title = e.name?.text || "", desc = e.summary || e.description?.text || "";
      if (!src.allTech && !hasKeyword(title + " " + desc, kws)) continue;
      const loc = e.online_event ? "online" : [e.venue?.name, e.venue?.address?.city, e.venue?.address?.country === "TH" ? "Thailand" : ""].filter(Boolean).join(", ");
      const city = whereIs(loc, src.city || "");
      if (!city || !okUrl(e.url || "")) continue;
      rows.push({ source: "eventbrite", uid: "eb-" + e.id, title, start: start.toISOString(),
        durationMin: isNaN(end.getTime()) ? 120 : Math.round((end.getTime() - start.getTime()) / 60000), city,
        venue: city === "Online" ? "Online" : (e.venue?.name || "").slice(0, 160), price: e.is_free ? "Free" : "",
        link: e.url, desc: String(desc).slice(0, 800), orgName: e.organizer?.name || src.label || "", category: kindOf(title + " " + desc) });
    }
    if (!d.pagination?.has_more_items || !d.pagination?.continuation) break;
    cont = d.pagination.continuation;
  }
  return rows;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json(405, { error: "POST only" });
  const url = Deno.env.get("SUPABASE_URL")!, service = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!service) return json(503, { error: "SUPABASE_SERVICE_ROLE_KEY is not available" });

  // the Saturday schedule (shared secret) or CloudWAV signed in
  const secret = Deno.env.get("EVENTS_SYNC_SECRET") || "";
  let allowed = safeEqual(req.headers.get("x-sync-secret") || "", secret);
  if (!allowed) {
    const sb = createClient(url, Deno.env.get("SUPABASE_ANON_KEY")!, { global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } } });
    const { data: u } = await sb.auth.getUser();
    if (!u?.user) return json(401, { error: "Sign in first" });
    const { data: pu } = await sb.from("portal_users").select("role").eq("id", u.user.id).maybeSingle();
    allowed = pu?.role === "operator";
    if (!allowed) return json(403, { error: "CloudWAV only" });
  }

  let body: { sourceId?: string } = {};
  try { body = await req.json(); } catch { /* empty body is fine */ }

  const admin = createClient(url, service, { auth: { persistSession: false } });
  const { data: rec, error: e1 } = await admin.from("portal_records").select("data")
    .eq("collection", "operatorSettings").eq("id", "eventSources").maybeSingle();
  if (e1) return json(500, { error: "Could not read the event sources" });
  const cfg = (rec?.data || {}) as { sources?: Source[]; keywords?: string[] };
  const kws = (cfg.keywords && cfg.keywords.length ? cfg.keywords : DEFAULT_KEYWORDS).slice(0, 200);
  const sources = (cfg.sources || []).filter((s) => s && s.active !== false && s.kind !== "manual" && (!body.sourceId || s.id === body.sourceId)).slice(0, 40);
  const until = Date.now() + DAYS_AHEAD * 86400000;

  const rows: Row[] = [], report: { id: string; label: string; found: number; error?: string }[] = [];
  for (const s of sources) {
    try {
      const got = s.kind === "eventbrite" ? await fromEventbrite(s, kws, until) : await fromIcal(s, kws, until);
      rows.push(...got);
      report.push({ id: s.id, label: s.label || "", found: got.length });
    } catch (err) {
      report.push({ id: s.id, label: s.label || "", found: 0, error: String((err as Error)?.message || err).slice(0, 200) });
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
