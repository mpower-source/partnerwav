// Rules for the event feeds: reading iCal text, deciding which events to keep, and the weekly schedule.
// Pure functions (no network, no database) so they can be tested on their own: tests/events_sync_test.ts.

export type Source = {
  id: string; kind: "ical" | "eventbrite" | "manual"; label?: string; url?: string; orgId?: string;
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
