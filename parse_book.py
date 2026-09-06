#!/usr/bin/env python3
"""يحوّل "TBT Amirnet.pdf" إلى data/vocab.json و data/exams.json.

    python parse_book.py

يحتاج pdftotext (Xpdf) على المسار. وضع -table ضروري للقاموس: الوضع
العادي يزيح عمود الترجمة العربية سطراً كاملاً عن الكلمة الإنجليزية.
"""

import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).parent
PDF = ROOT / "content" / "TBT Amirnet.pdf"
DATA = ROOT / "data"

DICT_PAGES = (3, 26)      # صفحات القاموس (1-indexed كما يعدّها pdftotext)
LEVEL_COUNT = 4           # مستويات مرتّبة بالصعوبة، لا شرائح أبجدية

# امتحانات الكتاب محميّة بحقوق نشر، فأُخرجت من التطبيق. تحذير: تشغيل السكربت
# مع False يكتب exams.json بلا تلك الامتحانات، فتُفقد ما لم يُعَد وضع الـPDF
# في content/ ثم تُشغَّل مع True.
PUBLISH_BOOK_EXAMS = False

# كلمات الكتاب محميّة أيضاً، فأُخرجت. القاموس المنشور صار من ملفات
# vocab_extra*.json المكتوبة خصيصاً لهذا التطبيق.
PUBLISH_BOOK_WORDS = False

# الكتاب يستخدم الياء والهاء الفارسيتين
AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
AR_FIX = str.maketrans({"ی": "ي", "ھ": "ه",
                        "ک": "ك", "ى": "ي"})
BIDI = re.compile(r"[‎‏‪-‮⁦-⁩]")
ARABIC = re.compile(r"[؀-ۿ]")
LATIN = re.compile(r"[A-Za-z]")

SEC_TIME = {"sentence-completion": 4, "reading": 15, "restatement": 6}
SEC_TITLE = {"sentence-completion": "إكمال جمل", "reading": "استيعاب مقروء",
             "restatement": "إعادة صياغة"}
SEC_INSTR = {"sentence-completion": "اختر الكلمة أو العبارة الأنسب لإكمال الجملة.",
             "reading": "اقرأ النص التالي وأجب عن الأسئلة.",
             "restatement": "اختر الجملة الأقرب في المعنى للجملة الأصلية."}

# جدول التحويل الرسمي من الكتاب: عدد الأخطاء ← العلامة من ١٥٠
SCORE_TABLE = [150, 145, 140, 134, 130, 127, 122, 117, 113, 108, 103, 99,
               95, 90, 86, 83, 79, 74, 69, 64, 60, 56, 53, 50]


def pdftotext(mode, first, last):
    out = subprocess.run(
        ["pdftotext", mode, "-enc", "UTF-8", "-f", str(first), "-l", str(last),
         str(PDF), "-"],
        capture_output=True, check=True)
    return BIDI.sub("", unicodedata.normalize("NFKC", out.stdout.decode("utf-8")))


# ─────────────────────────── القاموس ───────────────────────────

def book_words():
    """كلمات الكتاب: من الـPDF إن وُجد، وإلا من data/vocab.json المولّدة سابقاً."""
    if not PDF.exists():
        v = json.loads((DATA / "vocab.json").read_text(encoding="utf-8"))
        out = []
        for lv in v["levels"]:
            for w in lv["words"]:
                if not w.get("added"):
                    out.append({k: w[k] for k in ("id", "en", "ar", "synonyms") if k in w})
        return out, False
    return parse_book_words(), True


def parse_book_words():
    raw = pdftotext("-table", *DICT_PAGES)
    skip = re.compile(r"jamal|reserved|prohibited|copying", re.I)

    pairs = []
    for line in raw.splitlines():
        line = line.replace("\x0c", " ").strip()
        if not line or skip.search(line):
            continue
        m = ARABIC.search(line)
        if m and LATIN.search(line[:m.start()]):
            pairs.append([line[:m.start()].strip(), line[m.start():].strip()])
        elif pairs and m and not LATIN.search(line):
            # ترجمة انلفّت على سطر تالٍ
            pairs[-1][1] = (pairs[-1][1].rstrip("/") + "/" + line.lstrip("/")).strip("/")
        elif pairs and line.startswith("(") and LATIN.search(line):
            pairs[-1][0] += " " + line

    words, seen = [], {}
    for en_raw, ar_raw in pairs:
        syns = [s.strip() for g in re.findall(r"\(([^)]*)\)", en_raw)
                for s in g.split("/") if s.strip() and LATIN.search(s)]
        en = re.sub(r"\([^)]*\)", "", en_raw)
        en = re.sub(r"\s+", " ", en).strip(" .,-/\\")   # مسافات مضاعفة و«/» تسبق ترجمة تبدأ بشرطة
        ar = re.sub(r"\s*/\s*", " / ", ar_raw.translate(AR_FIX)).strip(" /")
        if not en or not ar or len(en) > 40:
            continue
        key = en.lower()
        if key in seen:
            prev = words[seen[key]]
            if ar not in prev["ar"]:
                prev["ar"] += " / " + ar
            continue
        seen[key] = len(words)
        w = {"id": "w%03d" % (len(words) + 1), "en": en, "ar": ar}
        if syns:
            w["synonyms"] = syns
        words.append(w)
    return words


def build_levels(words):
    seen = {w["en"].lower(): i for i, w in enumerate(words)}

    # رتّب بالصعوبة ثم قسّم إلى مستويات متساوية، فيصير المستوى ١ أسهل الكلمات فعلاً
    diff = json.loads((DATA / "difficulty.json").read_text(encoding="utf-8"))
    tier_of, labels = {}, diff["labels"]
    for tier, lst in diff["tiers"].items():
        for w in lst:
            tier_of[w.lower()] = int(tier)

    # كلمات مضافة خارج الكتاب — تحمل درجتها معها، وتُتجاهل إن كانت في الكتاب أصلاً
    n_extra = 0
    for extra_path in sorted(DATA.glob("vocab_extra*.json")):
        for x in json.loads(extra_path.read_text(encoding="utf-8"))["words"]:
            key = x["en"].lower()
            if key in seen:
                continue
            seen[key] = len(words)
            tier_of[key] = int(x.get("tier", 4))
            w = {"id": "x%03d" % (n_extra + 1), "en": x["en"], "ar": x["ar"], "added": True}
            for f in ("pos", "example", "exampleAr", "synonyms"):
                if x.get(f):
                    w[f] = x[f]
            words.append(w)
            n_extra += 1

    unrated = [w["en"] for w in words if w["en"].lower() not in tier_of]
    DEFAULT_TIER = 4
    for i, w in enumerate(words):
        w["_tier"] = tier_of.get(w["en"].lower(), DEFAULT_TIER)
        w["_ord"] = i
    words.sort(key=lambda w: (w["_tier"], w["_ord"]))

    levels, per = [], -(-len(words) // LEVEL_COUNT)
    for i in range(0, len(words), per):
        chunk = words[i:i + per]
        n = len(levels) + 1
        tiers = sorted({w["_tier"] for w in chunk})
        for w in chunk:
            del w["_tier"], w["_ord"]
        # الاسم والوصف يُبنيان داخل التطبيق حسب لغة الواجهة
        levels.append({"id": n, "tiers": [tiers[0], tiers[-1]], "words": chunk})
    src = "TBT Amirnet — Jamal Mohammad 2024" if PUBLISH_BOOK_WORDS else None
    out = {"levels": levels}
    if src:
        out["source"] = src
    return out, len(words), unrated, n_extra


# ─────────────────────────── الامتحانات ───────────────────────────

SEC_HEAD = re.compile(r"Section\s+(\d+)\s*:\s*([A-Za-z ]+?)\s*\(Questions[^)]*\)", re.I)
# سطور التعليمات المتكررة تسبق النص المقروء ويجب ألا تُحسب ضمن ترقيم أسطره
INSTR = re.compile(r"^\s*(You have only .*|When the time is up.*)$", re.I | re.M)
ANS_HEAD = re.compile(r"Section\s+(\d+)\s+Answer", re.I)
Q_START = re.compile(r"^\s*(\d{1,2})\.\s+(.*)$")
OPT = re.compile(r"^\s*\((\d)\)\s*(.+?)\s*$")


def clean(line):
    """يزيل مسطرات الإزاحة والنقاط الدخيلة والفواصل."""
    line = line.replace("\x0c", " ")
    line = re.sub(r"^[\s_.]*(?=[A-Za-z“”\"'(\d])", "", line)
    line = re.sub(r"^[\s_]*", "", line)
    line = re.sub(r"[\s_]{4,}$", "", line)
    return line.rstrip()


def section_type(name):
    n = name.lower()
    if "reading" in n:
        return "reading"
    if "restate" in n:
        return "restatement"
    return "sentence-completion"


def parse_answers(text):
    """{رقم القسم: [فهارس الإجابات الصحيحة]}"""
    out = {}
    cur = None
    for line in text.splitlines():
        h = ANS_HEAD.search(line)
        if h:
            cur = int(h.group(1))
            out[cur] = []
            continue
        if cur is None:
            continue
        m = re.match(r"^\s*(\d{1,2})\.\s+([1-4])\s*$", line)
        if m:
            out[cur].append(int(m.group(2)) - 1)
    return out


def parse_questions(block):
    """يقسّم نص قسم إلى أسئلة بخياراتها."""
    questions, cur = [], None
    for line in block.splitlines():
        line = clean(line)
        if not line.strip():
            continue
        o = OPT.match(line)
        if o and cur is not None:
            cur["options"].append(o.group(2))
            continue
        q = Q_START.match(line)
        if q and (cur is None or len(cur["options"]) >= 2):
            if cur:
                questions.append(cur)
            cur = {"text": q.group(2).strip(), "options": []}
            continue
        if cur is not None:
            # سطر تكملة: للنص إن لم تبدأ الخيارات بعد، وإلا لآخر خيار
            if cur["options"]:
                cur["options"][-1] += " " + line.strip()
            else:
                cur["text"] += " " + line.strip()
    if cur:
        questions.append(cur)
    return [q for q in questions if len(q["options"]) == 4]


def parse_passage(block):
    """نص الاستيعاب المقروء مع أرقام أسطره — الأسئلة تشير إلى «line N»."""
    lines = []
    for line in block.splitlines():
        s = line.replace("\x0c", " ").rstrip()
        if not s.strip():
            continue
        if re.match(r"^\s*\(?\d{1,2}\)?\s*$", s):     # رقم صفحة
            continue
        # علامة رقم السطر التي يضعها الكتاب كل ٥ أسطر
        m = re.match(r"^\s*\((\d{1,2})\)\s*(.*)$", s)
        if m:
            lines.append({"n": int(m.group(1)), "t": clean(m.group(2)).strip()})
        else:
            lines.append({"n": None, "t": clean(s).strip()})
    # ترقيم متصل انطلاقاً من العلامات
    n = 0
    for ln in lines:
        n = ln["n"] if ln["n"] else n + 1
        ln["n"] = n
    return [ln for ln in lines if ln["t"]]


def load_overrides():
    p = DATA / "overrides.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("insert", [])


OVERRIDES = load_overrides()


def parse_exams():
    """امتحانات الكتاب: من الـPDF إن وُجد، وإلا من data/exams.json المولّدة سابقاً."""
    problems = []
    exams = []
    # لا نقرأ محتوى الكتاب أصلاً إن كان مستبعَداً من النشر — وإلا فشل البناء
    # على نسخة نظيفة من المستودع، حيث لا وجود لـ exams.json المولَّد.
    if PUBLISH_BOOK_EXAMS:
        if PDF.exists():
            exams, problems = parse_book_exams()
        elif (DATA / "exams.json").exists():
            e = json.loads((DATA / "exams.json").read_text(encoding="utf-8"))
            exams = [x for x in e["exams"] if not x.get("generated")]
    book_only = exams
    exams = (exams if PUBLISH_BOOK_EXAMS else []) + load_generated(problems)
    return ({"source": "مكتوبة خصيصاً لهذا التطبيق",
             "scoreTable": SCORE_TABLE, "exams": exams},
            problems, len(book_only))


def parse_book_exams():
    text = pdftotext("-layout", 27, 182)
    pages = text.split("\x0c")

    starts = [i for i, p in enumerate(pages)
              if re.search(r"Section\s+1\s*:", p, re.I)]
    exams, problems = [], []

    for e, start in enumerate(starts):
        end = starts[e + 1] if e + 1 < len(starts) else len(pages)
        body = "\n".join(pages[start:end])

        answers = parse_answers(body)
        # الأسئلة تسبق مفتاح الإجابات
        first_ans = ANS_HEAD.search(body)
        qbody = body[:first_ans.start()] if first_ans else body

        heads = list(SEC_HEAD.finditer(qbody))
        sections = []
        for h, head in enumerate(heads):
            num = int(head.group(1))
            stype = section_type(head.group(2))
            chunk = qbody[head.end():heads[h + 1].start() if h + 1 < len(heads) else len(qbody)]

            passage = None
            if stype == "reading":
                split = re.split(r"^\s*Questions\s*$", chunk, flags=re.M)
                if len(split) >= 2:
                    passage = parse_passage(INSTR.sub("", split[0]))
                    chunk = "\n".join(split[1:])

            qs = parse_questions(chunk)

            # الإدراج قبل إسناد الإجابات، وإلا انزاح مفتاح الكتاب
            for ov in OVERRIDES:
                if ov["exam"] == e + 1 and ov["section"] == num:
                    qs.insert(ov["position"] - 1, dict(ov["question"]))

            key = answers.get(num, [])
            for i, q in enumerate(qs):
                q["id"] = "e%02ds%dq%d" % (e + 1, num, i + 1)
                q["correct"] = key[i] if i < len(key) else 0
                if i >= len(key):
                    problems.append("امتحان %d قسم %d سؤال %d: بلا إجابة" % (e + 1, num, i + 1))
                for j, o in enumerate(q["options"]):
                    if len(o.strip(" _-.")) < 2:
                        problems.append("امتحان %d قسم %d سؤال %d: الخيار %d شبه فارغ"
                                        % (e + 1, num, i + 1, j + 1))

            sec = {"type": stype, "title": SEC_TITLE[stype],
                   "durationMin": SEC_TIME[stype], "questions": qs}
            if passage:
                sec["passage"] = passage
            sections.append(sec)

        total = sum(len(s["questions"]) for s in sections)
        if len(sections) != 6 or total != 23:
            problems.append("امتحان %d: %d أقسام، %d أسئلة (المتوقع 6 و23)"
                            % (e + 1, len(sections), total))

        exams.append({"id": "e%02d" % (e + 1), "title": "امتحان " + str(e + 1).translate(AR_DIGITS),
                      "sections": sections})

    return exams, problems


def load_generated(problems):
    """امتحانات مكتوبة من الصفر: تُملأ عناوينها وتوقيتها وترقيم أسطر نصوصها."""
    p = DATA / "exams_generated.json"
    if not p.exists():
        return []
    out = []
    for ex in json.loads(p.read_text(encoding="utf-8"))["exams"]:
        for si, sec in enumerate(ex["sections"], 1):
            sec.setdefault("title", SEC_TITLE[sec["type"]])
            sec.setdefault("durationMin", SEC_TIME[sec["type"]])
            sec.setdefault("instructions", SEC_INSTR[sec["type"]])
            if isinstance(sec.get("passage"), list) and sec["passage"] and \
                    isinstance(sec["passage"][0], str):
                sec["passage"] = [{"n": i, "t": t} for i, t in enumerate(sec["passage"], 1)]
            for qi, q in enumerate(sec["questions"], 1):
                q["id"] = "%ss%dq%d" % (ex["id"], si, qi)
                if len(q["options"]) != 4:
                    problems.append("%s قسم %d سؤال %d: %d خيارات"
                                    % (ex["id"], si, qi, len(q["options"])))
        total = sum(len(s["questions"]) for s in ex["sections"])
        if len(ex["sections"]) != 6 or total != 23:
            problems.append("%s: %d أقسام، %d أسئلة (المتوقع 6 و23)"
                            % (ex["id"], len(ex["sections"]), total))
        ex["generated"] = True
        out.append(ex)
    return out


def main():
    DATA.mkdir(exist_ok=True)
    if not PDF.exists():
        print("ملاحظة: %s غير موجود — نُعيد الاستخدام من data/ المولّدة سابقاً.\n"
              % PDF.name)

    words, from_pdf = book_words() if PUBLISH_BOOK_WORDS else ([], False)
    vocab, nwords, unrated, n_extra = build_levels(words)

    (DATA / "vocab.json").write_text(json.dumps(vocab, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print("القاموس: %d كلمة (%d من الكتاب + %d مكتوبة خصيصاً) في %d مستوى"
          % (nwords, nwords - n_extra, n_extra, len(vocab["levels"])))
    labels = json.loads((DATA / "difficulty.json").read_text(encoding="utf-8"))["labels"]
    for lv in vocab["levels"]:
        band = labels[str(lv["tiers"][0])] if lv["tiers"][0] == lv["tiers"][1] else             labels[str(lv["tiers"][0])] + " إلى " + labels[str(lv["tiers"][1])]
        print("  المستوى %-3s %-22s %d كلمة  (%s … %s)"
              % (str(lv["id"]).translate(AR_DIGITS), band, len(lv["words"]),
                 lv["words"][0]["en"], lv["words"][-1]["en"]))
    if unrated:
        print("  بلا درجة صعوبة (%d): %s" % (len(unrated), ", ".join(unrated)))

    exams, problems, n_book = parse_exams()
    (DATA / "exams.json").write_text(json.dumps(exams, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    nq = sum(len(s["questions"]) for e in exams["exams"] for s in e["sections"])
    print("الامتحانات المنشورة: %d امتحان، %d سؤال" % (len(exams["exams"]), nq))
    if not PUBLISH_BOOK_EXAMS and n_book:
        print("  (استُبعدت %d امتحان من الكتاب — لن تبقى في data/exams.json بعد هذه الكتابة)"
              % n_book)

    if problems:
        print("\nمشاكل (%d):" % len(problems))
        for p in problems[:40]:
            print("  -", p)
    else:
        print("بدون مشاكل.")


if __name__ == "__main__":
    main()
