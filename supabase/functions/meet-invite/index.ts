// PartnerWAV: intro meeting invites from partnerwav@gmail.com with a Google Meet link.
//
// For each invite it
//   1. creates an event with a Google Meet link on the PartnerWAV Google Calendar (and, if asked, adds the
//      guests, so Google also sends them its calendar invitation), then
//   2. sends the invite email (CloudWAV's template, filled in for the company) from partnerwav@gmail.com
//      through Gmail, with the Meet link in it.
// "Send a test" does the same but only to partnerwav@gmail.com itself, with no guests on the event.
//
// Set up once (full steps are on the portal's Intro Meetings > Google connection tab):
//   - Google Cloud project owned by partnerwav@gmail.com, with the Google Calendar API and Gmail API on.
//   - OAuth client (Web application) and a refresh token for partnerwav@gmail.com with these two scopes:
//       https://www.googleapis.com/auth/calendar.events   https://www.googleapis.com/auth/gmail.send
//   - supabase secrets set GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... GOOGLE_REFRESH_TOKEN=... GOOGLE_SENDER=partnerwav@gmail.com
//     (optional: GOOGLE_CALENDAR_ID, default "primary")
//   - supabase functions deploy meet-invite
// The secrets stay in Supabase; nothing about the Google account is kept in the portal page.
//
// Only CloudWAV (portal_users.role = operator) can use it.

import { createClient } from "npm:@supabase/supabase-js@2";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });

const SCOPES = ["https://www.googleapis.com/auth/calendar.events", "https://www.googleapis.com/auth/gmail.send"];
const EMAIL = /^[^\s@<>",;:()\[\]\\]{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}$/;
const oneLine = (s: unknown, max: number) => String(s ?? "").replace(/[\r\n\t]+/g, " ").replace(/[<>"]/g, "").trim().slice(0, max);

type Person = { email: string; name?: string };

async function accessToken() {
  const r = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: Deno.env.get("GOOGLE_CLIENT_ID") || "",
      client_secret: Deno.env.get("GOOGLE_CLIENT_SECRET") || "",
      refresh_token: Deno.env.get("GOOGLE_REFRESH_TOKEN") || "",
      grant_type: "refresh_token",
    }),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok || !d.access_token) {
    const why = d.error === "invalid_grant"
      ? "Google refused the saved sign-in (refresh token). It expires after 7 days while the Google app is in Testing mode, or if the password changed or access was removed. Make a new refresh token (Google connection tab, step 5)."
      : "Google sign-in failed (" + (d.error || r.status) + "). Check GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and GOOGLE_REFRESH_TOKEN.";
    throw new Error(why);
  }
  return d.access_token as string;
}

// MIME helpers
const enc = new TextEncoder();
function b64(bytes: Uint8Array) { let s = ""; for (const b of bytes) s += String.fromCharCode(b); return btoa(s); }
const b64url = (s: string) => b64(enc.encode(s)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const word = (s: string) => /^[\x20-\x7e]*$/.test(s) ? s : "=?UTF-8?B?" + b64(enc.encode(s)) + "?=";
const addr = (p: Person) => p.name ? `"${word(oneLine(p.name, 80))}" <${p.email}>` : p.email;
function wrap76(s: string) { return s.replace(/.{1,76}/g, "$&\r\n"); }
function escHtml(s: string) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }

// PartnerWAV's colours (the same as the portal's light theme), so every invite matches the brand
const BRAND = { bg: "#f7f6fb", card: "#ffffff", soft: "#f3f1fb", line: "#eceaf4", ink: "#231f3a", inkSoft: "#5b5675", inkFaint: "#8c88a3",
  accent: "#6c4cf1", accentStrong: "#5135d8", accentSoft: "#efebff" };
const FONT = "Inter, 'Segoe UI', Helvetica, Arial, sans-serif", HEAD_FONT = "'Space Grotesk', Inter, 'Segoe UI', Helvetica, Arial, sans-serif";

function htmlBody(text: string, meetLink: string, senderName: string) {
  const B = BRAND;
  const parts = escHtml(text).split(/\n{2,}/).map((p) =>
    `<p style="margin:0 0 14px;">` + p.replace(/\n/g, "<br>").replace(/https:\/\/[^\s<&]+/g, (u) => `<a href="${u}" style="color:${B.accent};text-decoration:underline;">${u}</a>`) + "</p>").join("");
  const button = meetLink
    ? `<table role="presentation" cellpadding="0" cellspacing="0" style="margin:6px 0 22px;"><tr><td style="background:${B.accent};border-radius:10px;">`
      + `<a href="${escHtml(meetLink)}" style="display:inline-block;padding:12px 22px;color:#ffffff;text-decoration:none;font-weight:600;font-family:${FONT};font-size:15px;">Join with Google Meet</a></td></tr></table>`
    : "";
  return `<!doctype html><html><head><meta charset="utf-8"><meta name="color-scheme" content="light"></head>`
    + `<body style="margin:0;padding:0;background:${B.bg};">`
    + `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:${B.bg};"><tr><td align="center" style="padding:28px 14px;">`
    + `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:${B.card};border:1px solid ${B.line};border-radius:14px;">`
    + `<tr><td style="height:6px;background:${B.accent};border-radius:14px 14px 0 0;font-size:0;line-height:0;">&nbsp;</td></tr>`
    + `<tr><td style="padding:22px 30px 6px;"><table role="presentation" cellpadding="0" cellspacing="0"><tr>`
      + `<td style="width:30px;height:30px;background:${B.accent};border-radius:8px;color:#ffffff;font-family:${HEAD_FONT};font-weight:700;font-size:17px;text-align:center;vertical-align:middle;">P</td>`
      + `<td style="padding-left:10px;font-family:${HEAD_FONT};font-weight:700;font-size:20px;color:${B.accent};">PartnerWAV</td></tr></table></td></tr>`
    + `<tr><td style="padding:16px 30px 8px;font-family:${FONT};font-size:15px;line-height:1.6;color:${B.ink};">${parts}${button}</td></tr>`
    + `<tr><td style="padding:14px 30px 20px;border-top:1px solid ${B.line};background:${B.soft};border-radius:0 0 14px 14px;font-family:${FONT};font-size:12px;line-height:1.5;color:${B.inkSoft};">`
      + `Sent by ${escHtml(senderName)} from <a href="https://partnerwav.com" style="color:${B.accent};text-decoration:none;font-weight:600;">PartnerWAV</a> by CloudWAV</td></tr>`
    + `</table></td></tr></table></body></html>`;
}
function mime(from: Person, to: Person[], subject: string, text: string, html: string) {
  const boundary = "pw-" + crypto.randomUUID();
  return [
    "From: " + addr(from), "To: " + to.map(addr).join(", "), "Reply-To: " + from.email,
    "Subject: " + word(subject), "MIME-Version: 1.0", `Content-Type: multipart/alternative; boundary="${boundary}"`, "",
    "--" + boundary, "Content-Type: text/plain; charset=UTF-8", "Content-Transfer-Encoding: base64", "", wrap76(b64(enc.encode(text))),
    "--" + boundary, "Content-Type: text/html; charset=UTF-8", "Content-Transfer-Encoding: base64", "", wrap76(b64(enc.encode(html))),
    "--" + boundary + "--", "",
  ].join("\r\n");
}

async function google(token: string, url: string, init: RequestInit = {}) {
  const r = await fetch(url, { ...init, headers: { Authorization: "Bearer " + token, "Content-Type": "application/json", ...(init.headers || {}) } });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((d.error && (d.error.message || d.error)) || ("Google returned " + r.status));
  return d;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json(405, { error: "POST only" });

  // CloudWAV only
  const sb = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, {
    global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } },
  });
  const { data: u } = await sb.auth.getUser();
  if (!u?.user) return json(401, { error: "Sign in first" });
  const { data: pu } = await sb.from("portal_users").select("role").eq("id", u.user.id).maybeSingle();
  if (pu?.role !== "operator") return json(403, { error: "CloudWAV only" });

  const sender = (Deno.env.get("GOOGLE_SENDER") || "").trim();
  if (!Deno.env.get("GOOGLE_CLIENT_ID") || !Deno.env.get("GOOGLE_REFRESH_TOKEN") || !EMAIL.test(sender)) {
    return json(503, { error: "Google isn't connected yet: set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN and GOOGLE_SENDER in Supabase secrets." });
  }

  let body: Record<string, unknown>;
  try { body = await req.json(); } catch { return json(400, { error: "Bad JSON" }); }

  let token: string;
  try { token = await accessToken(); } catch (e) { return json(502, { error: (e as Error).message }); }

  if (body.action === "status") {
    const info = await fetch("https://oauth2.googleapis.com/tokeninfo?access_token=" + encodeURIComponent(token)).then((r) => r.json()).catch(() => ({}));
    const have = String(info.scope || "").split(" ");
    const missing = SCOPES.filter((s) => !have.includes(s));
    return json(200, { ok: missing.length === 0, sender, missing });
  }

  // ----- send an invite -----
  const test = body.test === true;
  const list = (v: unknown) => (Array.isArray(v) ? v : []).slice(0, 10).map((p: any) => ({ email: String(p?.email || "").trim().toLowerCase(), name: oneLine(p?.name, 80) }));
  const to: Person[] = test ? [{ email: sender, name: "PartnerWAV test" }] : list(body.to);
  const guests: Person[] = test ? [] : list(body.guests);
  if (!to.length || [...to, ...guests].some((p) => !EMAIL.test(p.email))) return json(400, { error: "Check the email addresses" });
  const subject = oneLine(body.subject, 200), text = String(body.body || "").replace(/\r\n/g, "\n").slice(0, 8000);
  const title = oneLine(body.title, 200) || subject;
  const tz = oneLine(body.timeZone, 60) || "UTC";
  const start = new Date(String(body.start || "")), dur = Math.min(480, Math.max(10, Number(body.durationMin) || 30));
  if (!subject || !text.trim()) return json(400, { error: "The subject and message are needed" });
  if (isNaN(start.getTime()) || start.getTime() < Date.now() - 5 * 60000 || start.getTime() > Date.now() + 400 * 86400000) return json(400, { error: "Choose a meeting time in the future" });
  try { new Intl.DateTimeFormat("en-US", { timeZone: tz }); } catch { return json(400, { error: "Unknown time zone" }); }
  const senderName = oneLine(body.senderName, 80) || "The PartnerWAV team";
  const addGuests = !test && body.addGuests !== false;

  try {
    // 1. the calendar event with a Meet link
    const cal = encodeURIComponent(Deno.env.get("GOOGLE_CALENDAR_ID") || "primary");
    const end = new Date(start.getTime() + dur * 60000);
    const ev = await google(token, `https://www.googleapis.com/calendar/v3/calendars/${cal}/events?conferenceDataVersion=1&sendUpdates=${addGuests ? "all" : "none"}`, {
      method: "POST",
      body: JSON.stringify({
        summary: (test ? "[Test] " : "") + title,
        description: text.replace(/\{\{\s*meet_link\s*\}\}/g, "(the Google Meet link in this invitation)"),
        start: { dateTime: start.toISOString(), timeZone: tz }, end: { dateTime: end.toISOString(), timeZone: tz },
        attendees: addGuests ? [...to, ...guests].map((p) => ({ email: p.email, displayName: p.name || undefined })) : [],
        conferenceData: { createRequest: { requestId: crypto.randomUUID(), conferenceSolutionKey: { type: "hangoutsMeet" } } },
        guestsCanModify: false,
      }),
    });
    let meetLink: string = ev.hangoutLink || "";
    for (let i = 0; !meetLink && i < 4; i++) {   // Google sometimes finishes making the Meet link a moment later
      await new Promise((r) => setTimeout(r, 900));
      const again = await google(token, `https://www.googleapis.com/calendar/v3/calendars/${cal}/events/${encodeURIComponent(ev.id)}`);
      meetLink = again.hangoutLink || "";
    }
    if (!meetLink) return json(502, { error: "The calendar event was made but Google didn't return a Meet link", eventId: ev.id, eventLink: ev.htmlLink });

    // 2. the email, from partnerwav@gmail.com
    const fill = (s: string) => s.replace(/\{\{\s*meet_link\s*\}\}/g, meetLink);
    const finalText = fill(text), finalSubject = (test ? "[Test] " : "") + fill(subject);
    const raw = b64url(mime({ email: sender, name: senderName }, [...to, ...guests], finalSubject, finalText, htmlBody(finalText, meetLink, senderName)));
    const sent = await google(token, "https://gmail.googleapis.com/gmail/v1/users/me/messages/send", { method: "POST", body: JSON.stringify({ raw }) });

    return json(200, { ok: true, test, meetLink, eventId: ev.id, eventLink: ev.htmlLink, messageId: sent.id, calendarInvite: addGuests });
  } catch (e) {
    return json(502, { error: "Google: " + String((e as Error).message || e).slice(0, 300) });
  }
});
