#!/usr/bin/env python3
"""يبني app.html من القالب + ملفات المحتوى.

    python build.py

يقرأ src/app.template.html ويستبدل العلامتين __VOCAB_DATA__ و __EXAMS_DATA__
بمحتوى data/vocab.json و data/exams.json، ثم يكتب app.html.

شغّله من جديد كل مرة يتغيّر فيها المحتوى أو القالب.
"""

import json
import sys
from pathlib import Path

# كونسول ويندوز يفتح بترميز cp1252 فيختنق على العربية — أجبره على UTF-8.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).parent
TEMPLATE = ROOT / "src" / "app.template.html"
OUT = ROOT / "app.html"

SLOTS = {
    "__VOCAB_DATA__": ROOT / "data" / "vocab.json",
    "__EXAMS_DATA__": ROOT / "data" / "exams.json",
    "__PRACTICE_DATA__": ROOT / "data" / "practice.json",
}


def load(path):
    """يقرأ JSON ويعيده كنص مضغوط، مع رسالة خطأ واضحة عند الفشل."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        if path.name == "practice.json":   # اختياري: بلا أسئلة تدريب إضافية
            return '{"sets":[]}'
        sys.exit(f"ملف مفقود: {path.relative_to(ROOT)}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"JSON غير صالح في {path.relative_to(ROOT)} — سطر {e.lineno}: {e.msg}")
    # المحتوى يُحقن داخل <script type="application/json">، فإغلاق الوسم يجب ألا يظهر حرفياً.
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def main():
    if not TEMPLATE.exists():
        sys.exit(f"ملف مفقود: {TEMPLATE.relative_to(ROOT)}")
    html = TEMPLATE.read_text(encoding="utf-8")

    for slot, path in SLOTS.items():
        if slot not in html:
            sys.exit(f"العلامة {slot} غير موجودة في القالب")
        html = html.replace(slot, load(path))

    OUT.write_text(html, encoding="utf-8")

    vocab = json.loads(SLOTS["__VOCAB_DATA__"].read_text(encoding="utf-8"))
    exams = json.loads(SLOTS["__EXAMS_DATA__"].read_text(encoding="utf-8"))
    levels = vocab.get("levels", [])
    words = sum(len(lv.get("words", [])) for lv in levels)
    questions = sum(
        len(sec.get("questions", []))
        for ex in exams.get("exams", [])
        for sec in ex.get("sections", [])
    )

    print(f"تم بناء {OUT.name}  ({OUT.stat().st_size / 1024:.0f} KB)")
    print(f"  {words} كلمة في {len(levels)} مستويات")
    print(f"  {len(exams.get('exams', []))} امتحان، {questions} سؤال")
    if vocab.get("_placeholder") or exams.get("_placeholder"):
        print("  تنبيه: المحتوى لا يزال عيّنة مؤقتة")


if __name__ == "__main__":
    main()
