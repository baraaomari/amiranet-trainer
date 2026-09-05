#!/usr/bin/env python3
"""يبني نسخة الاستضافة العادية في web/.

    python build_web.py

نفس التطبيق المنشور كـArtifact، ملفوفاً بهيكل HTML كامل ومسبوقاً بـconfig.js.
التطبيق يكتشف بيئته عند التشغيل: داخل صفحة Claude يستعمل قدراتها، وهنا
يستعمل Supabase، وبدون الاثنين يحفظ محلياً.
"""

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

SHELL = """<!doctype html>
<html lang="ar">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="تحضير لامتحان أميرنت: حفظ كلمات، امتحانات محاكاة، ومدرّس.">
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

    (WEB / "index.html").write_text(SHELL.replace("{{APP}}", APP.read_text(encoding="utf-8")), encoding="utf-8")

    cfg = WEB / "config.js"
    if not cfg.exists():
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
        for name in ("index.html", "config.js"):
            z.write(WEB / name, name)
    print("وحُزم كل شيء في: %s  (%.0f KB)"
          % (zip_path.name, zip_path.stat().st_size / 1024))
    print("اسحب هذا الملف الواحد إلى app.netlify.com/drop")


if __name__ == "__main__":
    main()
