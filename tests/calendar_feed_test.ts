// Checks the calendar feed text. Run: node --experimental-strip-types tests/calendar_feed_test.ts
import assert from "node:assert/strict";
import { buildIcs, foldLine, icsText, type FeedEvent } from "../supabase/functions/calendar-feed/ics.ts";

const now = new Date("2026-10-16T02:00:00Z");
const soon = "2026-10-20T11:00:00Z";
const base: FeedEvent = { id: "ce-1", title: "AI, Founders & Coffee", start: soon, durationMin: 90, orgName: "Bangkok Entrepreneurs",
  city: "Bangkok", venue: "Example venue, Sukhumvit", price: "Free", link: "https://example.com/signup", desc: "Talks, then networking.", status: "published" };
const events: FeedEvent[] = [
  base,
  { ...base, id: "ce-draft", title: "Draft (not listed)", status: "pending" },
  { ...base, id: "ce-removed", title: "Removed", deletedAt: "2026-10-10" },
  { ...base, id: "ce-old", title: "Last year", start: "2026-01-05T11:00:00Z" },
  { ...base, id: "ce-far", title: "Far away", start: "2028-01-05T11:00:00Z" },
];
const ics = buildIcs(events, now);

assert.ok(ics.startsWith("BEGIN:VCALENDAR\r\n"), "starts with VCALENDAR");
assert.ok(ics.endsWith("END:VCALENDAR\r\n"), "ends with VCALENDAR");
assert.equal((ics.match(/BEGIN:VEVENT/g) || []).length, 1, "only the published, upcoming event is listed");
assert.ok(ics.includes("UID:ce-1@partnerwav"), "stable UID so calendars update the same event");
assert.ok(ics.includes("DTSTART:20261020T110000Z"), "start is written in UTC");
assert.ok(ics.includes("DTEND:20261020T123000Z"), "end is start plus the duration (90 minutes)");
assert.ok(ics.includes("SUMMARY:AI\\, Founders & Coffee"), "commas in the title are escaped");
assert.ok(ics.includes("LOCATION:Example venue\\, Sukhumvit\\, Bangkok"), "location is venue and city");
assert.ok(ics.includes("URL:https://example.com/signup"), "signup link is kept as the event URL");
assert.ok(ics.includes("Sign up: https://example.com/signup"), "signup link is also in the description");
assert.ok(ics.includes("Organizer: Bangkok Entrepreneurs"), "organizer is in the description");

// a missing duration defaults to two hours
const noDur = buildIcs([{ ...base, durationMin: undefined }], now);
assert.ok(noDur.includes("DTEND:20261020T130000Z"), "default duration is two hours");

// line folding: no line is longer than 75 octets, and joining the folds gives back the text
const long = "x".repeat(200);
const folded = foldLine(long);
for (const l of folded.split("\r\n")) assert.ok(new TextEncoder().encode(l).length <= 75, "line within 75 octets");
assert.equal(folded.split("\r\n").map((l, i) => (i ? l.slice(1) : l)).join(""), long, "folding loses nothing");

// Thai text stays whole when folded
const thai = "ภาษาไทย".repeat(20);
const thaiFolded = foldLine(thai);
assert.equal(thaiFolded.split("\r\n").map((l, i) => (i ? l.slice(1) : l)).join(""), thai, "Thai text survives folding");

assert.equal(icsText("a,b;c\\d\ne"), "a\\,b\\;c\\\\d\\ne", "escaping");

// an empty list is still a valid calendar
const empty = buildIcs([], now);
assert.ok(empty.includes("BEGIN:VCALENDAR") && !empty.includes("BEGIN:VEVENT"), "empty calendar is valid");

console.log("calendar feed: all checks passed");
