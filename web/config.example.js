/* انسخ هذا الملف باسم config.js واملأه من Supabase.
   بدون config.js يبقى الحفظ محلياً على المتصفح فقط.

   من أين تأتي القيم:
   Supabase → Project Settings → API
     • Project URL          →  url
     • anon / public key    →  anonKey

   المفتاح anon مصمَّم ليكون علنياً في الصفحة — الحماية الحقيقية من
   سياسات RLS في schema.sql. لا تضع هنا service_role أبداً.
   ومفتاح Anthropic لا يوضع هنا مطلقاً؛ مكانه أسرار دالة Edge. */

window.SUPABASE_CONFIG = {
  url: "https://xxxxxxxxxxxxxxxx.supabase.co",
  anonKey: "ضع-مفتاح-anon-هنا",

  /* اسم دالة Edge للمدرّس. احذف السطر أو اجعله "" إذا لم تنشرها،
     وسيختفي المدرّس من الواجهة بدل أن يظهر معطّلاً. */
  tutorFunction: "tutor"
};
