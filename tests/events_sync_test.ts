// Checks the event feed rules: reading an iCal feed, deciding which events to keep, and the weekly schedule.
// Run: node --experimental-strip-types tests/events_sync_test.ts
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

// The rules live in the function's index.ts (one file, so it deploys with one paste). Load that block as a module.
const here = dirname(fileURLToPath(import.meta.url));
const indexText = readFileSync(join(here, "..", "supabase", "functions", "events-sync", "index.ts"), "utf8");
const from = indexText.indexOf("// ===== rules:"), to = indexText.indexOf("// ===== end of rules =====");
if (from < 0 || to < from) throw new Error("the rules block is missing from index.ts");
const rulesDir = mkdtempSync(join(tmpdir(), "events-rules-"));
const rulesFile = join(rulesDir, "rules.ts");
writeFileSync(rulesFile, indexText.slice(from, to));
const { DEFAULT_KEYWORDS, newDiag, parseIcs, icalRow, isCalendar, scheduleDue, parseEventPage, bkkDate } = await import(pathToFileURL(rulesFile).href);
type Source = { id: string; kind: string; label?: string; url?: string; orgId?: string; city?: string; allTech?: boolean; active?: boolean; source?: string };

const now = Date.parse("2026-10-16T00:00:00Z");
const until = now + 90 * 86400000;
const kws = DEFAULT_KEYWORDS;
const src: Source = { id: "src-luma", kind: "ical", label: "Luma: Bangkok", url: "https://lu.ma/bangkok/ical", city: "Bangkok", active: true };

// A Luma-style calendar: CRLF line endings, a folded description line, an escaped comma, and a floating time
const ics = [
  "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Luma//EN",
  "BEGIN:VEVENT", "UID:evt-1@lu.ma", "DTSTART;TZID=Asia/Bangkok:20261020T180000", "DTEND;TZID=Asia/Bangkok:20261020T200000",
  "SUMMARY:AI, Startup Founders Night", "LOCATION:Example venue\\, Sukhumvit\\, Bangkok",
  "DESCRIPTION:Talks from founders using AI in small business and then open networking for every guest who",
  " comes along.", "URL:https://lu.ma/ai-founders", "STATUS:CONFIRMED", "END:VEVENT",
  "BEGIN:VEVENT", "UID:evt-2@lu.ma", "DTSTART:20260105T100000Z", "SUMMARY:Last January tech meetup", "LOCATION:Bangkok", "URL:https://lu.ma/old", "END:VEVENT",
  "BEGIN:VEVENT", "UID:evt-3@lu.ma", "DTSTART:20281005T100000Z", "SUMMARY:Far away AI summit", "LOCATION:Bangkok", "URL:https://lu.ma/far", "END:VEVENT",
  "BEGIN:VEVENT", "UID:evt-4@lu.ma", "DTSTART:20261021T100000Z", "SUMMARY:Yoga on the lawn", "DESCRIPTION:Relax and stretch", "LOCATION:Bangkok", "URL:https://lu.ma/yoga", "END:VEVENT",
  "BEGIN:VEVENT", "UID:evt-5@lu.ma", "DTSTART:20261022T100000Z", "SUMMARY:Startup pitch in Berlin", "LOCATION:Berlin, Germany", "URL:https://lu.ma/berlin", "END:VEVENT",
  "BEGIN:VEVENT", "UID:evt-6@lu.ma", "DTSTART:20261023T100000Z", "SUMMARY:Cancelled AI meetup", "STATUS:CANCELLED", "LOCATION:Bangkok", "URL:https://lu.ma/x", "END:VEVENT",
  "BEGIN:VEVENT", "UID:evt-7@lu.ma", "DTSTART:20261024T100000Z", "SUMMARY:Yoga for AI founders", "LOCATION:Bangkok", "END:VEVENT",
  "END:VCALENDAR", "",
].join("\r\n");

assert.ok(isCalendar(ics), "a calendar file is recognised");
assert.ok(!isCalendar("<html><body>luma.com/bangkok</body></html>"), "a web page is not a calendar (the case that gave zero events)");

const diag = newDiag();
const items = parseIcs(ics, diag);
diag.read = items.length;
assert.equal(diag.cancelled, 1, "cancelled events are counted");
assert.equal(items.length, 6, "six events are read (one cancelled is left out)");

const kept: string[] = [], drops: Record<string, number> = {};
for (const e of items) {
  const r = icalRow(e, src, kws, until, now);
  if ("row" in r) kept.push(r.row.title); else drops[r.drop] = (drops[r.drop] || 0) + 1;
}
assert.deepEqual(kept, ["AI, Startup Founders Night", "Yoga for AI founders"], "the AI events in Bangkok are kept (the yoga one has the keyword AI)");
assert.equal(drops.past, 1, "the January event is past");
assert.equal(drops.window, 1, "the 2028 event is outside the 90-day window");
assert.equal(drops.keyword, 1, "the yoga event with no keyword is dropped");
assert.equal(drops.city, 1, "the Berlin event is not in a listed city");
assert.equal(drops.nodate ?? 0, 0, "every event has a date");

// the first event's details
const first = icalRow(items[0], src, kws, until, now);
assert.ok("row" in first, "the Luma event is kept");
if ("row" in first) {
  assert.equal(first.row.start, "2026-10-20T11:00:00.000Z", "Bangkok 18:00 is 11:00 UTC");
  assert.equal(first.row.durationMin, 120, "duration is end minus start");
  assert.equal(first.row.city, "Bangkok", "city is Bangkok");
  assert.equal(first.row.link, "https://lu.ma/ai-founders", "signup link is the event URL");
  assert.equal(first.row.venue, "Example venue, Sukhumvit, Bangkok", "venue keeps its commas");
  assert.ok(first.row.desc.includes("comes along"), "folded description lines are joined");
  assert.equal(first.row.source, "luma", "the source is recorded as Luma");
}

// "include everything from this calendar" keeps the yoga event
const all = icalRow(items[3], { ...src, allTech: true }, kws, until, now);
assert.ok("row" in all, "with the include-everything switch, the yoga event is kept");

// an event with no signup link is dropped unless the calendar itself is a usable link
const noLink = icalRow(items[5], { ...src, url: "http://insecure.example/cal.ics" }, kws, until, now);
assert.ok("drop" in noLink && noLink.drop === "link", "no usable signup link: dropped");

// the weekly schedule (Bangkok time): Saturday 08:00 is Saturday 01:00 UTC
const sat0800 = new Date("2026-10-17T01:00:00Z");
assert.equal(scheduleDue({ enabled: true, weekday: 6, hour: 8 }, sat0800), true, "Saturday 08:00 Bangkok is due");
assert.equal(scheduleDue({ enabled: true, weekday: 6, hour: 8 }, new Date("2026-10-17T02:00:00Z")), false, "Saturday 09:00 is not due");
assert.equal(scheduleDue({ enabled: true, weekday: 6, hour: 8 }, new Date("2026-10-16T01:00:00Z")), false, "Friday 08:00 is not due");
assert.equal(scheduleDue({ enabled: false, weekday: 6, hour: 8 }, sat0800), false, "a switched-off schedule never runs");
assert.equal(scheduleDue(undefined, sat0800), false, "no schedule saved: nothing runs");
assert.equal(scheduleDue({ enabled: true, weekday: 1, hour: 19 }, new Date("2026-10-19T12:00:00Z")), true, "a Monday 19:00 schedule runs on Monday 19:00 Bangkok");


// ----- a single event page (Luma event link): its details come from the page's schema.org Event block -----
const page = `<!doctype html><html><head><meta property="og:title" content="Fallback title"><meta property="og:description" content="Fallback text">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Event","name":"AI Founders &amp; Coffee #tech","startDate":"2026-10-22T18:30:00+07:00","endDate":"2026-10-22T20:30:00+07:00","location":{"@type":"Place","name":"Example Cafe","address":{"@type":"PostalAddress","addressLocality":"Bangkok","addressCountry":"TH"}},"url":"https://luma.com/jdyxq8zp","description":"Meetup for #tech builders in Bangkok.","organizer":{"@type":"Organization","name":"Bangkok Tech Club"}}</script>
</head><body>Event page</body></html>`;
const pageEvents = parseEventPage(page, "https://luma.com/jdyxq8zp");
assert.equal(pageEvents.length, 1, "one event on the page");
const pe = pageEvents[0];
assert.equal(pe.title, "AI Founders & Coffee #tech", "title is read and decoded (the #tech hashtag stays in the title)");
assert.equal(pe.start?.toISOString(), "2026-10-22T11:30:00.000Z", "18:30 at +07:00 is 11:30 UTC");
assert.equal(pe.end?.toISOString(), "2026-10-22T13:30:00.000Z", "end time is read");
assert.equal(pe.location, "Example Cafe, Bangkok, TH", "location is the place and its address");
assert.equal(pe.url, "https://luma.com/jdyxq8zp", "the event link is kept");
assert.equal(pe.org, "Bangkok Tech Club", "organizer is read");
const pageRow = icalRow(pe, { id: "src-page", kind: "page", url: "https://luma.com/jdyxq8zp", city: "Bangkok", active: true }, DEFAULT_KEYWORDS, until, now);
assert.ok("row" in pageRow, "the #tech event is kept by the keyword check");

// a floating time (no offset) is Bangkok time; an @graph wrapper is read too
const floating = `<script type="application/ld+json">{"@graph":[{"@type":"WebPage","name":"x"},{"@type":["Event"],"name":"Floating time","startDate":"2026-10-22T18:30:00","location":"Bangkok"}]}</script>`;
const fl = parseEventPage(floating, "https://example.com/e");
assert.equal(fl.length, 1, "the event inside @graph is found");
assert.equal(fl[0].start?.toISOString(), "2026-10-22T11:30:00.000Z", "no offset: Bangkok time");
assert.equal(fl[0].location, "Bangkok", "a text location is kept");
assert.equal(bkkDate("2026-10-22T18:30:00Z")?.toISOString(), "2026-10-22T18:30:00.000Z", "a UTC time stays as it is");

// a page with no event block gives nothing (the sync reports that for the source)
assert.equal(parseEventPage("<html><head><meta property='og:title' content='A list of events'></head></html>", "https://luma.com/bangkok").length, 0, "a list page has no event details");

// places written the way Luma writes them: Bangkok as "Krung Thep Maha Nakhon", Thailand as "TH"
const luma = (location: string) => icalRow({ uid: "x", title: "AI meetup", start: new Date(now + 86400000), end: null, location, url: "https://luma.com/x", desc: "", org: "" }, { id: "s", kind: "page", url: "https://luma.com/x", active: true }, kws, until, now);
const lumaPlace = luma("True Digital Park, True Digital Park, Krung Thep Maha Nakhon, TH");
assert.ok("row" in lumaPlace && lumaPlace.row.city === "Bangkok", "Krung Thep Maha Nakhon, TH is Bangkok, even with no City set on the source");
assert.ok("row" in luma("Thai HealthTech Association, Krung Thep Maha Nakhon, TH"), "a Thai health venue in Bangkok is kept");
assert.ok("drop" in luma("Berlin, Germany") && luma("Berlin, Germany").drop === "city", "Berlin is still dropped");

console.log("event feed rules: all checks passed");
