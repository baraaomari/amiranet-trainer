// دالة Edge للمدرّس — تُنشأ من: Supabase → Edge Functions → Deploy a new function → Via Editor
// سمّها: tutor
//
// لماذا دالة على الخادم ولا نضع المفتاح في الصفحة: الصفحة الثابتة يقرأها أي زائر،
// فأي مفتاح فيها مكشوف. المفتاح هنا يبقى في أسرار المشروع ولا يغادر الخادم.
//
// وبما أن التسجيل في الموقع مفتوح للجميع، ولا يكفي التحقق من وجود ترويسة تفويض:
//   • نتحقق من الرمز فعلياً ونستخرج هوية المستخدم منه
//   • ونحدّ عدد أسئلة كل مستخدم يومياً حتى لا يُستنزف رصيد صاحب الموقع
//
// قبل النشر أضف السر: Edge Functions → Secrets →  ANTHROPIC_API_KEY
// (أما SUPABASE_URL و SUPABASE_SERVICE_ROLE_KEY فتوفّرهما Supabase تلقائياً.)

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const MODEL = "claude-sonnet-5";
const MAX_TOKENS = 1024;
const MAX_TURNS = 24;          // آخر ما يُرسل من المحادثة
const MAX_CHARS = 60_000;      // سقف حجم الطلب
const DAILY_LIMIT = 40;        // أسئلة لكل مستخدم في اليوم — ارفعه أو اخفضه كما تشاء

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, "Content-Type": "application/json" },
  });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  const key = Deno.env.get("ANTHROPIC_API_KEY");
  if (!key) return json({ error: "ANTHROPIC_API_KEY is not set" }, 500);

  // ── من هو صاحب الطلب؟ ──
  const auth = req.headers.get("authorization") ?? "";
  const jwt = auth.replace(/^Bearer\s+/i, "").trim();
  if (!jwt) return json({ error: "unauthorized" }, 401);

  const admin = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    { auth: { persistSession: false } },
  );

  const { data: userData, error: userErr } = await admin.auth.getUser(jwt);
  const user = userData?.user;
  if (userErr || !user) return json({ error: "unauthorized" }, 401);

  // ── هل تجاوز حدّه اليومي؟ ──
  const { data: used, error: limitErr } = await admin.rpc("bump_tutor_usage", {
    p_user: user.id,
    p_limit: DAILY_LIMIT,
  });
  if (limitErr) {
    console.error("usage check failed", limitErr.message);
    return json({ error: "usage check failed" }, 500);
  }
  if (used === -1) {
    return json({ error: "daily_limit", limit: DAILY_LIMIT }, 429);
  }

  // ── الرسائل ──
  let messages: { role: string; content: string }[];
  try {
    const body = await req.json();
    messages = Array.isArray(body?.messages) ? body.messages : [];
  } catch {
    return json({ error: "bad json" }, 400);
  }

  messages = messages
    .filter((m) => m && typeof m.content === "string" && m.content.trim())
    .map((m) => ({ role: m.role === "assistant" ? "assistant" : "user", content: m.content }))
    .slice(-MAX_TURNS);

  if (!messages.length) return json({ error: "no messages" }, 400);
  if (messages[messages.length - 1].role !== "user")
    return json({ error: "last message must be from the user" }, 400);

  const size = messages.reduce((n, m) => n + m.content.length, 0);
  if (size > MAX_CHARS) return json({ error: "prompt too large" }, 413);

  // ── اسأل Claude ──
  try {
    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({ model: MODEL, max_tokens: MAX_TOKENS, messages }),
    });

    if (!res.ok) {
      const detail = await res.text();
      console.error("anthropic error", res.status, detail.slice(0, 400));
      return json({ error: "upstream " + res.status }, res.status === 429 ? 429 : 502);
    }

    const data = await res.json();
    const text = (data.content ?? [])
      .filter((b: { type: string }) => b.type === "text")
      .map((b: { text: string }) => b.text)
      .join("")
      .trim();

    if (!text) return json({ error: "empty answer" }, 502);
    return json({ text, used, limit: DAILY_LIMIT });
  } catch (e) {
    console.error("tutor failed", e);
    return json({ error: "request failed" }, 502);
  }
});
