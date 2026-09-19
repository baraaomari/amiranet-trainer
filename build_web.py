#!/usr/bin/env python3
"""يبني نسخة الاستضافة العادية في web/.

    python build_web.py

نفس التطبيق المنشور كـArtifact، ملفوفاً بهيكل HTML كامل ومسبوقاً بـconfig.js.
التطبيق يكتشف بيئته عند التشغيل: داخل صفحة Claude يستعمل قدراتها، وهنا
يستعمل Supabase، وبدون الاثنين يحفظ محلياً.
"""

import os
import shutil
import zipfile
import sys
from pathlib import Path

for s in (sys.stdout, sys.stderr):
    try:
        s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).parent
APP = ROOT / "app.html"
WEB = ROOT / "web"

# عنوان الموقع النهائي — للـcanonical والـsitemap ومعاينات الروابط.
# لو صار عندك دومين: SITE_URL=https://example.com python update.py
SITE = os.environ.get("SITE_URL", "https://amiranet-trainer.netlify.app").rstrip("/")

# رمز Google Search Console (طريقة HTML tag): الصق قيمة content فقط في هذا الملف.
VERIFY_FILE = WEB / "google-site-verification.txt"

TITLE = "مدرّب أميرنت — تحضير مجاني لامتحان أميرنت بالعربي | אמירנט · AMIRNET"
DESCRIPTION = ("تحضير مجاني لامتحان أميرنت (אמירנט / AMIRNET) بالعربي: ٣٥٩ كلمة مع ترجمة ومراجعة ذكية، "
               "٥ امتحانات محاكاة بنفس مبنى الامتحان مع مؤقّت، ٩٦ سؤال تدريب مع شرح بالعربي، "
               "وحاسبة علامة من ١٥٠.")

JSONLD = {
    "@context": "https://schema.org",
    "@type": "WebApplication",
    "name": "مدرّب أميرنت · Amiranet Trainer",
    "alternateName": ["أميرنت", "اميرنت", "אמירנט", "AMIRNET"],
    "url": SITE + "/",
    "description": DESCRIPTION,
    "applicationCategory": "EducationalApplication",
    "operatingSystem": "Web",
    "inLanguage": ["ar", "en"],
    "isAccessibleForFree": True,
    "offers": {"@type": "Offer", "price": "0", "priceCurrency": "ILS"},
}

SHELL = """<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{{TITLE}}</title>
<meta name="description" content="{{DESCRIPTION}}">
<link rel="canonical" href="{{SITE}}/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="مدرّب أميرنت">
<meta property="og:title" content="{{TITLE}}">
<meta property="og:description" content="{{DESCRIPTION}}">
<meta property="og:url" content="{{SITE}}/">
<meta property="og:locale" content="ar_AR">
<meta name="twitter:card" content="summary">
{{VERIFY}}<script type="application/ld+json">{{JSONLD}}</script>
<meta name="theme-color" content="#F1F2F4">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>%F0%9F%93%9A</text></svg>">
<style>
  :root{color-scheme:light}
  *{box-sizing:border-box}
  html,body{margin:0}
  body{background:#F1F2F4}
  img{max-width:100%}
  [hidden]{display:none!important}
</style>
</head>
<body>
<script src="config.js" onerror="console.warn('config.js not found — local storage only')"></script>
{{APP}}
</body>
</html>
"""


def check_config(path):
    """يمسك أخطاء config.js الشائعة قبل أن تتحوّل إلى موقع مكسور."""
    import re
    text = path.read_text(encoding="utf-8")
    problems = []

    for field in ("url", "anonKey"):
        m = re.search(field + r"\s*:\s*([^,\n]+)", text)
        if not m:
            problems.append("الحقل %s غير موجود" % field)
            continue
        raw = m.group(1).strip().rstrip(",")
        if not (raw.startswith('"') and raw.endswith('"')):
            problems.append('%s بلا علامتَي تنصيص — لازم يكون: %s: "القيمة"' % (field, field))
            continue
        val = raw[1:-1].strip()
        if field == "url":
            if re.search(r"x{4,}", val, re.I):
                problems.append("url ما زال القيمة النموذجية")
            elif "/rest/v1" in val or "/auth/v1" in val:
                problems.append("url هو رابط الـAPI لا Project URL — احذف ما بعد ‎.supabase.co")
            elif not re.match(r"^https://[a-z0-9-]+\.supabase\.co/?$", val, re.I):
                problems.append("url غير متوقّع الشكل: %s" % val[:48])
        else:
            if not val.startswith("eyJ"):
                problems.append("anonKey لا يبدأ بـ eyJ — تأكد أنك نسخت مفتاح anon public")
            elif '"role":"service_role"' in val or "service_role" in val:
                problems.append("هذا مفتاح service_role — لا يوضع في الصفحة أبداً؛ استخدم anon public")
    return problems


def main():
    if not APP.exists():
        sys.exit("ملف مفقود: app.html — شغّل build.py أولاً")
    WEB.mkdir(exist_ok=True)

    import html, json, datetime
    token = VERIFY_FILE.read_text(encoding="utf-8").strip() if VERIFY_FILE.exists() else ""
    head = (SHELL
            .replace("{{TITLE}}", html.escape(TITLE))
            .replace("{{DESCRIPTION}}", html.escape(DESCRIPTION))
            .replace("{{SITE}}", SITE)
            .replace("{{VERIFY}}", '<meta name="google-site-verification" content="%s">\n' % html.escape(token) if token else "")
            .replace("{{JSONLD}}", json.dumps(JSONLD, ensure_ascii=False).replace("</", "<\\/")))
    # عنوان القالب القصير خاص بنسخة Claude؛ هون العنوان الكامل بالـhead، فما بدنا عنوانين
    import re
    app = re.sub(r"^\s*<title>.*?</title>\s*", "", APP.read_text(encoding="utf-8"), count=1, flags=re.S)
    (WEB / "index.html").write_text(head.replace("{{APP}}", app), encoding="utf-8")

    # لمحرّكات البحث: مسموح الأرشفة، وهاي خريطة الموقع
    (WEB / "robots.txt").write_text("User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % SITE, encoding="utf-8")
    (WEB / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <url><loc>%s/</loc><lastmod>%s</lastmod></url>\n'
        '</urlset>\n' % (SITE, datetime.date.today().isoformat()), encoding="utf-8")
    if not token:
        print("ملاحظة: لا يوجد رمز Google Search Console بعد (web/google-site-verification.txt).")

    cfg = WEB / "config.js"
    if not cfg.exists():
        # على خادم البناء لا يوجد config.js (مستثنى من المستودع)، فيُبنى
        # من متغيّرات البيئة. محلياً بلا متغيّرات يُنسخ المثال ليُملأ يدوياً.
        env_url = os.environ.get("SUPABASE_URL", "").strip()
        env_key = os.environ.get("SUPABASE_ANON_KEY", "").strip()
        if env_url and env_key:
            cfg.write_text(
                '/* مولَّد وقت البناء من متغيّرات البيئة — لا تعدّله يدوياً. */\n'
                'window.SUPABASE_CONFIG = {\n'
                '  url: "%s",\n'
                '  anonKey: "%s",\n'
                '  tutorFunction: "%s"\n'
                '};\n' % (env_url.rstrip("/"), env_key,
                          os.environ.get("TUTOR_FUNCTION", "tutor").strip()),
                encoding="utf-8")
            print("أُنشئ web/config.js من متغيّرات البيئة.")
        else:
            shutil.copy(WEB / "config.example.js", cfg)
            print("أُنشئ web/config.js من المثال — املأه بقيم مشروعك.")

    size = (WEB / "index.html").stat().st_size / 1024
    print("تم بناء web/index.html  (%.0f KB)" % size)

    problems = check_config(cfg)
    if problems:
        print("\nمشاكل في web/config.js — الموقع لن يعمل قبل إصلاحها:")
        for x in problems:
            print("  •", x)
        print("\nالقيم من: Supabase ← Project Settings ← API")
        return

    # ملف واحد يُسحب إلى Netlify بدل مجلد
    zip_path = ROOT / "amirnet-site.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name in ("index.html", "config.js", "robots.txt", "sitemap.xml"):
            z.write(WEB / name, name)
    print("وحُزم كل شيء في: %s  (%.0f KB)"
          % (zip_path.name, zip_path.stat().st_size / 1024))
    print("لتحديث موقعك القائم: Netlify ← مشروعك ← Deploys ← منطقة السحب")
    print("(‏app.netlify.com/drop ينشئ موقعاً جديداً برابط جديد — للمرة الأولى فقط)")


if __name__ == "__main__":
    main()
