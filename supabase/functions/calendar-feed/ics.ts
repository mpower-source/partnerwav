// Builds the iCalendar (.ics) text for the Thailand community events. Pure: no network, no database,
// so it can be tested on its own (tests/calendar_feed_test.mjs).
//
// What goes in each event: title, start and end (Bangkok time is stored as UTC), location (venue and city),
// the signup link (URL), and the organizer, price and description. Only events that are published and not
// removed are included, and only the next 180 days plus yesterday.

export type FeedEvent = {
  id: string;
  title?: string;
  start?: string;
  durationMin?: number;
  orgName?: string;
  city?: string;
  venue?: string;
  price?: string;
  link?: string;
  desc?: string;
  status?: string;
  deletedAt?: string | null;
};

const DAY = 86400000;
const enc = new TextEncoder();

// Escape text for an iCalendar value: backslash, comma, semicolon, and line breaks
export function icsText(v: string): string {
  return String(v || "").replace(/\\/g, "\\\\").replace(/\r?\n/g, "\\n").replace(/([,;])/g, "\\$1");
}

// Lines are at most 75 octets (UTF-8); longer lines continue on the next line, starting with a space
export function foldLine(line: string): string {
  const out: string[] = [];
  let cur = "", bytes = 0, limit = 75;
  for (const ch of line) {
    const n = enc.encode(ch).length;
    if (bytes + n > limit) { out.push(cur); cur = " " + ch; bytes = 1 + n; limit = 75; }
    else { cur += ch; bytes += n; }
  }
  out.push(cur);
  return out.join("\r\n");
}

// 20240131T130000Z
export function icsStamp(d: Date): string {
  return d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
}

export function buildIcs(events: FeedEvent[], now: Date): string {
  const from = now.getTime() - DAY, to = now.getTime() + 180 * DAY;
  const list = events
    .filter(e => e && e.status === "published" && !e.deletedAt && e.start && e.title)
    .map(e => ({ e, t: new Date(e.start as string).getTime() }))
    .filter(x => !isNaN(x.t) && x.t >= from && x.t <= to)
    .sort((a, b) => a.t - b.t)
    .slice(0, 500);

  const lines: string[] = [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//PartnerWAV//Thailand events//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
    "X-WR-CALNAME:PartnerWAV: Thailand events", "REFRESH-INTERVAL;VALUE=DURATION:PT6H", "X-PUBLISHED-TTL:PT6H",
  ];
  for (const { e, t } of list) {
    const start = new Date(t);
    const end = new Date(t + (Number(e.durationMin) || 120) * 60000);
    const where = [e.venue, e.city].filter(Boolean).join(", ");
    const desc = [e.desc, e.orgName ? "Organizer: " + e.orgName : "", e.price ? "Entry: " + e.price : "", e.link ? "Sign up: " + e.link : ""]
      .filter(Boolean).join("\n");
    lines.push("BEGIN:VEVENT", "UID:" + icsText(e.id) + "@partnerwav", "DTSTAMP:" + icsStamp(now),
      "DTSTART:" + icsStamp(start), "DTEND:" + icsStamp(end), "SUMMARY:" + icsText(e.title as string));
    if (desc) lines.push("DESCRIPTION:" + icsText(desc));
    if (where) lines.push("LOCATION:" + icsText(where));
    if (e.link && /^https?:\/\//i.test(e.link)) lines.push("URL:" + e.link);
    lines.push("END:VEVENT");
  }
  lines.push("END:VCALENDAR");
  return lines.map(foldLine).join("\r\n") + "\r\n";
}
