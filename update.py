#!/usr/bin/env python3
"""أمر واحد بعد أي تغيير في المحتوى.

    python update.py

يعيد توليد البيانات، يبني النسختين (Artifact والموقع)، ويحزم ملفاً واحداً
جاهزاً للسحب إلى Netlify. يتوقف عند أول خطأ بدل أن يبني موقعاً مكسوراً.
"""

import subprocess
import sys
from pathlib import Path

for s in (sys.stdout, sys.stderr):
    try:
        s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).parent
STEPS = [
    ("قراءة المحتوى وتصنيفه", "parse_book.py"),
    ("بناء التطبيق", "build.py"),
    ("تجهيز الموقع وحزمه", "build_web.py"),
]


def main():
    for label, script in STEPS:
        print("\n▸ " + label)
        r = subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT)
        if r.returncode != 0:
            print("\nتوقّفنا عند: " + label + " — أصلح الخطأ أعلاه ثم أعد التشغيل.")
            return 1

    zip_path = ROOT / "amirnet-site.zip"
    if not zip_path.exists():
        print("\nلم يُنتج ملف الرفع — راجع رسائل web/config.js أعلاه.")
        return 1

    print("\n" + "─" * 52)
    print("جاهز. اسحب هذا الملف إلى موقعك في Netlify:")
    print("   " + str(zip_path))
    print("   (Netlify ← مشروعك ← Deploys ← منطقة السحب)")
    print("─" * 52)
    return 0


if __name__ == "__main__":
    sys.exit(main())
