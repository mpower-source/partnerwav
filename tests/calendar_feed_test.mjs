// Checks the calendar feed text that CloudWAV publishes. The functions are read from partnerwav-v11-merged.html,
// so the test checks the code the app runs. Run: node tests/calendar_feed_test.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(join(here, "..", "partnerwav-v11-merged.html"), "utf8");
const from = html.indexOf("  function icsEsc(");
const to = html.indexOf("  // ----- end of the calendar feed text");
assert.ok(from > 0 && to > from, "calendar feed functions found in the app");
const { icsFeedBuild, icsFold, icsEsc } = new Function(html.slice(from, to) + "\nreturn { icsFeedBuild: icsFeedBuild, icsFold: icsFold, icsEsc: icsEsc };")();

const now = new Date("2026-10-16T02:00:00Z");
const soon = "2026-10-20T11:00:00Z";
const base = { id: "ce-1", title: "AI, Founders & Coffee", start: soon, durationMin: 90, orgName: "Bangkok Entrepreneurs",
  city: "Bangkok", venue: "Example venue, Sukhumvit", price: "Free", link: "https://example.com/signup", desc: "Talks, then networking.", status: "published" };
const events = [
  base,
  { ...base, id: "ce-draft", title: "Draft (not listed)", status: "pending" },
  { ...base, id: "ce-removed", title: "Removed", deletedAt: "2026-10-10" },
  { ...base, id: "ce-old", title: "Last year", start: "2026-01-05T11:00:00Z" },
  { ...base, id: "ce-far", title: "Far away", start: "2028-01-05T11:00:00Z" },
];
const { text, count } = icsFeedBuild(events, now);

assert.ok(text.startsWith("BEGIN:VCALENDAR\r\n"), "starts with VCALENDAR");
assert.ok(text.endsWith("END:VCALENDAR\r\n"), "ends with VCALENDAR");
assert.equal(count, 1, "only the published, upcoming event is counted");
assert.equal((text.match(/BEGIN:VEVENT/g) || []).length, 1, "only the published, upcoming event is listed");
assert.ok(text.includes("UID:ce-1@partnerwav"), "stable UID so calendars update the same event");
assert.ok(text.includes("DTSTART:20261020T110000Z"), "start is written in UTC");
assert.ok(text.includes("DTEND:20261020T123000Z"), "end is start plus the duration (90 minutes)");
assert.ok(text.includes("SUMMARY:AI\\, Founders & Coffee"), "commas in the title are escaped");
assert.ok(text.includes("LOCATION:Example venue\\, Sukhumvit\\, Bangkok"), "location is venue and city");
assert.ok(text.includes("URL:https://example.com/signup"), "signup link is the event URL");
assert.ok(text.includes("Sign up: https://example.com/signup"), "signup link is also in the description");
assert.ok(text.includes("Organizer: Bangkok Entrepreneurs"), "organizer is in the description");
assert.ok(icsFeedBuild([{ ...base, durationMin: undefined }], now).text.includes("DTEND:20261020T130000Z"), "default duration is two hours");

const long = "x".repeat(200);
const folded = icsFold(long);
for (const l of folded.split("\r\n")) assert.ok(new TextEncoder().encode(l).length <= 75, "line within 75 octets");
assert.equal(folded.split("\r\n").map((l, i) => (i ? l.slice(1) : l)).join(""), long, "folding loses nothing");
const thai = "ภาษาไทย".repeat(20);
assert.equal(icsFold(thai).split("\r\n").map((l, i) => (i ? l.slice(1) : l)).join(""), thai, "Thai text survives folding");
assert.equal(icsEsc("a,b;c\\d\ne"), "a\\,b\\;c\\\\d\\ne", "escaping");
const empty = icsFeedBuild([], now).text;
assert.ok(empty.includes("BEGIN:VCALENDAR") && !empty.includes("BEGIN:VEVENT"), "empty calendar is valid");

console.log("calendar feed: all checks passed");
