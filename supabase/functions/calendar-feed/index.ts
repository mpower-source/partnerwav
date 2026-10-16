// PartnerWAV calendar feed: a private link each signed-in login can subscribe to in Google Calendar or Outlook.
// Calendar apps poll the link and pick up new and changed events on their own.
//
// The link is  https://<project>.supabase.co/functions/v1/calendar-feed?token=<token>
// The token is kept in portal_records as a 'calendarFeeds' record (id = the login, e.g. partner:siam-digital).
// Only the login that owns it can read that record; this function reads it with the service role.
// A login resets its link in the portal, which replaces the token, so the old link stops working.
//
// Deploy (once):   supabase functions deploy calendar-feed --no-verify-jwt
// (calendar apps can't send a login, so the token in the link is the only check; the function needs no other secret.)

import { createClient } from "npm:@supabase/supabase-js@2";
import { buildIcs, type FeedEvent } from "./ics.ts";

const TOKEN = /^[A-Za-z0-9]{32,128}$/;

Deno.serve(async (req: Request) => {
  if (req.method !== "GET") return new Response("Method not allowed", { status: 405 });
  const token = new URL(req.url).searchParams.get("token") || "";
  if (!TOKEN.test(token)) return new Response("Not found", { status: 404 });

  const sb = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
  const feed = await sb.from("portal_records").select("data").eq("collection", "calendarFeeds")
    .filter("data->>token", "eq", token).maybeSingle();
  if (feed.error) return new Response("Could not read the calendar", { status: 500 });
  if (!feed.data) return new Response("Not found", { status: 404 });

  const events = await sb.from("portal_records").select("id,data").eq("collection", "communityEvents");
  if (events.error) return new Response("Could not read the events", { status: 500 });

  const list: FeedEvent[] = (events.data || []).map((r: { id: string; data: FeedEvent }) => ({ ...r.data, id: r.id }));
  return new Response(buildIcs(list, new Date()), {
    headers: {
      "Content-Type": "text/calendar; charset=utf-8",
      "Cache-Control": "private, max-age=900",
      "X-Robots-Tag": "noindex",
    },
  });
});
