// PartnerWAV: AI writer for vendor incentive flyers.
//
// The vendor portal calls this with the incentive's terms; Claude writes flyer copy using ONLY those
// terms (no invented figures). The portal falls back to its built-in writer if this isn't deployed.
//
// Deploy (once):
//   supabase secrets set ANTHROPIC_API_KEY=sk-ant-...        # from console.anthropic.com
//   supabase functions deploy flyer-assist
// Optional: supabase secrets set ANTHROPIC_MODEL=claude-sonnet-5
//
// Only signed-in vendors and operators (rows in portal_users) can use it.

import { createClient } from "npm:@supabase/supabase-js@2";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });

const SYSTEM = `You write one-page promotional flyers that software vendors send to their channel partners (MSPs, VARs, resellers) to promote a partner incentive (SPIF, MDF, trial credits, contest).

Rules:
- Use ONLY the facts in the incentive terms you are given. Never invent amounts, percentages, dates, prizes, eligibility or payout details. If something isn't in the terms, leave it out.
- No absolute or high-pressure claims ("guaranteed", "risk-free", "unlimited", "get rich").
- Be specific and scannable. Headline max 9 words. Sub-headline one sentence.
- Match the requested tone. Creative angles are welcome as long as the offer stays accurate.
- The fine print states the dates, who is eligible, any budget cap and payout timing that appear in the terms, and ends with "Full terms in the <vendor> partner program on PartnerWAV."

Reply with JSON only, no markdown:
{"headline": string, "subheadline": string, "offer": string (one line: what it's worth),
 "benefits": string[] (3-5 short bullets), "qualify": string (who can take part),
 "steps": string[] (3 short steps: how to take part / claim), "cta": string (max 8 words),
 "finePrint": string}`;

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json(405, { error: "POST only" });

  const apiKey = Deno.env.get("ANTHROPIC_API_KEY");
  if (!apiKey) return json(503, { error: "AI writer not configured (ANTHROPIC_API_KEY missing)" });

  // who is calling?
  const auth = req.headers.get("Authorization") ?? "";
  const sb = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, {
    global: { headers: { Authorization: auth } },
  });
  const { data: userData } = await sb.auth.getUser();
  if (!userData?.user) return json(401, { error: "Sign in first" });
  const { data: pu } = await sb.from("portal_users").select("role").eq("id", userData.user.id).maybeSingle();
  if (!pu || !["vendor", "operator"].includes(pu.role)) return json(403, { error: "Vendors only" });

  let body: { vendor?: string; tone?: string; notes?: string; incentive?: Record<string, unknown> };
  try { body = await req.json(); } catch { return json(400, { error: "Bad JSON" }); }
  if (!body.incentive || typeof body.incentive !== "object") return json(400, { error: "incentive is required" });

  const user = `Vendor: ${String(body.vendor ?? "").slice(0, 120)}
Tone: ${String(body.tone ?? "Professional").slice(0, 60)}
Vendor's notes (angle to emphasise, not new facts): ${String(body.notes ?? "").slice(0, 500) || "none"}
Incentive terms (the only facts you may use):
${JSON.stringify(body.incentive).slice(0, 6000)}`;

  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "x-api-key": apiKey, "anthropic-version": "2023-06-01", "content-type": "application/json" },
    body: JSON.stringify({
      model: Deno.env.get("ANTHROPIC_MODEL") ?? "claude-sonnet-5",
      max_tokens: 1200,
      system: SYSTEM,
      messages: [{ role: "user", content: user }],
    }),
  });
  if (!r.ok) return json(502, { error: "AI request failed", status: r.status });
  const out = await r.json();
  const text: string = (out.content ?? []).map((c: { text?: string }) => c.text ?? "").join("");
  const m = text.match(/\{[\s\S]*\}/);
  if (!m) return json(502, { error: "AI reply wasn't JSON" });
  try {
    const copy = JSON.parse(m[0]);
    if (!copy.headline) throw new Error("no headline");
    return json(200, copy);
  } catch {
    return json(502, { error: "AI reply wasn't valid JSON" });
  }
});
