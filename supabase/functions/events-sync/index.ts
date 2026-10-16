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

// ===== rules: the feed rules (tested by tests/events_sync_test.ts; keep this block as it is) =====
// Rules for the event feeds: reading iCal text, deciding which events to keep, and the weekly schedule.
// Pure functions (no network, no database) so they can be tested on their own: tests/events_sync_test.ts.

export type Source = {
  id: string; kind: "ical" | "eventbrite" | "page" | "manual"; label?: string; url?: string; orgId?: string;
  city?: string; allTech?: boolean; active?: boolean; source?: string;
};
export type Row = {
  source: string; uid: string; title: string; start: string; durationMin: number; city: string;
  venue: string; price: string; link: string; desc: string; orgName: string; category: string;
};
// How many events each source gave, and why the others were left out
export type Diag = {
  read: number; cancelled: number; nodate: number; past: number; window: number; keyword: number; city: number; link: number; kept: number;
};
export type Schedule = { enabled?: boolean; weekday?: number; hour?: number };
export type ParsedEvent = { uid: string; title: string; start: Date | null; end: Date | null; location: string; url: string; desc: string; org: string };

export function newDiag(): Diag {
  return { read: 0, cancelled: 0, nodate: 0, past: 0, window: 0, keyword: 0, city: 0, link: 0, kept: 0 };
}

export const DEFAULT_KEYWORDS = ["tech", "startup", "ai", "artificial intelligence", "machine learning", "data", "developer",
  "dev", "software", "saas", "cloud", "cyber", "security", "blockchain", "web3", "fintech", "product", "hackathon",
  "pitch", "founder", "venture", "investor", "devops", "python", "javascript", "coding", "gdg", "aws", "llm",
  "entrepreneur", "business owner", "sme", "marketing", "growth", "e-commerce", "digital", "innovation", "incubator", "accelerator", "angel", "vc",
  "summit", "conference", "expo", "trade show", "exhibition", "forum", "depa", "nia", "boi", "tceb", "microsoft", "google", "techsauce"];
export const CITIES = ["Bangkok", "Chiang Mai", "Phuket", "Pattaya", "Khon Kaen", "Hua Hin"];
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
export function parseIcs(ics: string, diag?: Diag) {
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
    if ((f["STATUS"]?.v || "").toUpperCase() === "CANCELLED") { if (diag) diag.cancelled++; continue; }
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
export function hasKeyword(text: string, kws: string[]) {
  const t = " " + text.toLowerCase().replace(/[^a-z0-9ก-๙]+/g, " ") + " ";
  return kws.some((k) => {
    const w = k.toLowerCase().replace(/[^a-z0-9ก-๙]+/g, " ").trim();
    return w && (w.length <= 3 ? t.includes(" " + w + " ") : t.includes(w));
  });
}
const FOREIGN = /\b(germany|united states|usa|u\.s\.|united kingdom|england|france|singapore|vietnam|malaysia|indonesia|philippines|india|china|japan|korea|australia|canada|hong kong|taiwan|cambodia|myanmar|laos)\b/;
function whereIs(location: string, fallbackCity: string): string | null {
  const l = location.toLowerCase();
  if (!l) return fallbackCity || "Other";
  if (/zoom|google meet|meet\.google|teams|online|virtual|livestream|youtube|webinar|discord/.test(l)) return "Online";
  for (const c of CITIES) if (l.includes(c.toLowerCase())) return c;
  if (l.includes("thailand") || /[ก-๙]/.test(l) || l.includes("กรุงเทพ")) return "Other";
  // named places outside Thailand: skip, even on a Thai city calendar
  if (FOREIGN.test(l)) return null;
  return fallbackCity ? fallbackCity : null;   // somewhere else in the world: skip unless the source is a Thai one
}
function kindOf(text: string) {
  const t = text.toLowerCase();
  if (/hackathon|hack day|buildathon/.test(t)) return "hackathon";
  if (/pitch|demo day|investor night/.test(t)) return "pitch";
  if (/open call|call for (startups|applications)|applications open/.test(t)) return "opencall";
  if (/\b(depa|nia|boi|tceb|ministry|government)\b/.test(t)) return "government";
  if (/summit|conference|expo|exhibition|trade show|forum/.test(t)) return "conference";
  return "community";
}


// A calendar link that returns a web page (for example luma.com/bangkok) has no events in it
export function isCalendar(text: string): boolean {
  return /BEGIN:VCALENDAR/i.test(text);
}

// Keep one event from an iCal feed, or say which rule dropped it
export function icalRow(e: ParsedEvent, src: Source, kws: string[], until: number, now: number): { row: Row } | { drop: keyof Diag } {
  if (!e.title || !e.start) return { drop: "nodate" };
  if (e.start.getTime() < now) return { drop: "past" };
  if (e.start.getTime() > until) return { drop: "window" };
  if (!src.allTech && !hasKeyword(e.title + " " + e.desc, kws)) return { drop: "keyword" };
  const city = whereIs(e.location, src.city || "");
  if (!city) return { drop: "city" };
  const link = okUrl(e.url) ? e.url : (src.url && src.url.startsWith("https://") ? src.url.replace(/\.ics.*$/, "") : "");
  if (!link) return { drop: "link" };
  const dur = e.end ? Math.round((e.end.getTime() - e.start.getTime()) / 60000) : 120;
  const tag = src.source || (/lu\.ma|luma\.com/.test(src.url || "") ? "luma" : /meetup\.com/.test(src.url || "") ? "meetup" : "ical");
  return { row: { source: tag, uid: e.uid || link + "#" + e.start.toISOString(), title: e.title, start: e.start.toISOString(),
    durationMin: dur, city, venue: city === "Online" ? "Online" : e.location.split("\n")[0].slice(0, 160), price: "",
    link, desc: e.desc.slice(0, 800), orgName: e.org || src.label || "", category: kindOf(e.title + " " + e.desc) } };
}

// The weekly schedule is set in the portal, in Bangkok time (no daylight saving). The hourly tick runs the sync when it is due.
export function scheduleDue(sch: Schedule | null | undefined, now: Date): boolean {
  if (!sch || !sch.enabled) return false;
  const bkk = new Date(now.getTime() + 7 * 3600000);
  return bkk.getUTCDay() === Number(sch.weekday ?? 6) && bkk.getUTCHours() === Number(sch.hour ?? 8);
}

// Only public https addresses (no IPs, no local names)
export function okUrl(u: string): boolean {
  try {
    const x = new URL(u);
    if (x.protocol !== "https:") return false;
    const h = x.hostname.toLowerCase();
    if (!h.includes(".") || h.endsWith(".local") || h.endsWith(".internal") || h === "localhost") return false;
    if (/^[0-9.]+$/.test(h) || h.includes(":")) return false;
    return true;
  } catch { return false; }
}

// ----- single event pages (a Luma or Eventbrite event link, not a calendar) -----
// Event pages carry their details in a standard block (schema.org "Event", as JSON-LD). Times with no
// offset are Bangkok time, the portal's default.
export function decodeEntities(t: string): string {
  return t.replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#39;|&#x27;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&nbsp;/g, " ");
}
export function bkkDate(v: string): Date | null {
  if (!v) return null;
  if (/([zZ]|[+-]\d{2}:?\d{2})$/.test(v)) { const d = new Date(v); return isNaN(d.getTime()) ? null : d; }
  const m = v.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?/);
  if (!m) return null;
  return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] || 0)) - 7 * 3600000);
}
export function jsonLdEvents(html: string): Record<string, unknown>[] {
  const out: Record<string, unknown>[] = [];
  const re = /<script[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
  let m: RegExpExecArray | null;
  while ((m = re.exec(html))) {
    let data: unknown;
    try { data = JSON.parse(m[1].trim()); } catch { continue; }
    const stack: unknown[] = [data];
    while (stack.length) {
      const x = stack.shift() as Record<string, unknown> | unknown[] | null;
      if (Array.isArray(x)) { stack.push(...x); continue; }
      if (!x || typeof x !== "object") continue;
      if (x["@graph"]) stack.push(x["@graph"]);
      const t = x["@type"];
      const types = Array.isArray(t) ? t : [t];
      if (types.some((y) => typeof y === "string" && /Event$/.test(y))) out.push(x);
    }
  }
  return out;
}
export function metaContent(html: string, prop: string): string {
  const a = html.match(new RegExp('<meta[^>]+(?:property|name)=["\']' + prop + '["\'][^>]*content=["\']([^"\']*)["\']', "i"));
  if (a) return decodeEntities(a[1]);
  const b = html.match(new RegExp('<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']' + prop + '["\']', "i"));
  return b ? decodeEntities(b[1]) : "";
}
export function parseEventPage(html: string, pageUrl: string): ParsedEvent[] {
  const out: ParsedEvent[] = [];
  for (const e of jsonLdEvents(html)) {
    const loc = Array.isArray(e.location) ? e.location[0] : e.location;
    let where = "";
    if (typeof loc === "string") where = loc;
    else if (loc && typeof loc === "object") {
      const L = loc as Record<string, unknown>;
      const addr = L.address;
      let a = "";
      if (typeof addr === "string") a = addr;
      else if (addr && typeof addr === "object") {
        const A = addr as Record<string, unknown>;
        a = [A.streetAddress, A.addressLocality, A.addressRegion, A.addressCountry].filter((v) => typeof v === "string" && v).join(", ");
      }
      where = [typeof L.name === "string" ? L.name : "", a].filter(Boolean).join(", ");
    }
    const org = Array.isArray(e.organizer) ? e.organizer[0] : e.organizer;
    const orgName = org && typeof org === "object" ? String((org as Record<string, unknown>).name || "") : typeof org === "string" ? org : "";
    const desc = typeof e.description === "string" ? e.description : metaContent(html, "og:description");
    out.push({
      uid: String(e.identifier || e.url || pageUrl),
      title: decodeEntities(String(e.name || metaContent(html, "og:title") || "")).trim(),
      start: bkkDate(String(e.startDate || "")),
      end: bkkDate(String(e.endDate || "")),
      location: decodeEntities(where),
      url: typeof e.url === "string" ? e.url : pageUrl,
      desc: decodeEntities(desc),
      org: decodeEntities(orgName),
    });
  }
  return out;
}
// ===== end of rules =====

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

async function fromPage(src: Source, kws: string[], until: number): Promise<{ rows: Row[]; diag: Diag }> {
  if (!src.url || !okUrl(src.url)) throw new Error("not a public https event link");
  const html = await getText(src.url, { Accept: "text/html" });
  const events = parseEventPage(html, src.url);
  if (!events.length) throw new Error("no event details found on this page. Check that it is the event's own link (not a list of events)");
  const diag = newDiag();
  diag.read = events.length;
  const now = Date.now(), rows: Row[] = [];
  for (const e of events) {
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
      const got = s.kind === "eventbrite" ? await fromEventbrite(s, kws, until) : s.kind === "page" ? await fromPage(s, kws, until) : await fromIcal(s, kws, until);
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
