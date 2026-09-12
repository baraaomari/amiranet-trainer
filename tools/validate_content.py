#!/usr/bin/env python3
"""Structural and quality checks for Amiranet Trainer question content.

Usage:
  python tools/validate_content.py                      # data/practice.json + data/exams_generated.json
  python tools/validate_content.py drafts/new.json      # any file with a top-level "sets" or "exams"
  python tools/validate_content.py --require-explain FILE

Errors break the app or would teach something wrong, and make the exit code 1.
Warnings are quality signals for the Quality Checker agent to judge.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILES = [ROOT / "data" / "practice.json", ROOT / "data" / "exams_generated.json"]

TYPES = {"restatement", "reading", "sentence-completion"}
LEVELS = {"easy", "medium", "hard"}
EXAM_TYPES = ["sentence-completion", "sentence-completion", "reading",
              "restatement", "restatement", "sentence-completion"]
EXAM_COUNTS = [4, 4, 5, 3, 3, 4]

# (line 12) · lines 3-5 · (السطر ١٢) · السطران ١–٢ · الأسطر ٩–١٢ · السطور 19–23
LINE_REF = re.compile(
    r"\blines?\s+(\d+)(?:\s*[-–]\s*(\d+))?"
    r"|(?:السطر|السطران|السطرين|الأسطر|السطور)\s*(\d+)(?:\s*[-–]\s*(\d+))?",
    re.IGNORECASE)
KULLAMA = r"(?<![ء-ي])كلما(?![ء-ي])"
DOUBLE_KULLAMA = re.compile(KULLAMA + r"[^.؛\n]{0,80}?" + KULLAMA)
LETTER_REF = re.compile(r"الخيار\s+[A-D](?![A-Za-z])")


class Report:
    def __init__(self, name):
        self.name, self.errors, self.warnings, self.questions = name, [], [], 0

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}")


def passage_lines(passage):
    if not passage:
        return 0
    if isinstance(passage, str):
        return 0   # plain-text passages have no line numbers to check
    return max((x.get("n", i + 1) if isinstance(x, dict) else i + 1) for i, x in enumerate(passage))


def check_explain(rep, where, ex, correct):
    for key in ("translation", "why"):
        if not isinstance(ex.get(key), str) or not ex[key].strip():
            rep.err(where, f"explain.{key} is missing")
    lines = ex.get("options")
    if not isinstance(lines, list) or len(lines) != 4:
        rep.err(where, "explain.options needs exactly 4 lines")
    else:
        ticks = [i for i, line in enumerate(lines) if isinstance(line, str) and line.lstrip().startswith("✓")]
        if ticks != [correct]:
            rep.err(where, "✓ must mark only the correct option %s (found %s)"
                    % ("ABCD"[correct], ",".join("ABCD"[i] for i in ticks) or "none"))
    vocab = ex.get("vocab")
    if not isinstance(vocab, list) or len(vocab) < 3 or \
            not all(isinstance(v, list) and len(v) == 2 and all(isinstance(x, str) for x in v) for v in vocab):
        rep.err(where, "explain.vocab needs 3+ [english, arabic] pairs")
    blob = json.dumps(ex, ensure_ascii=False)
    if DOUBLE_KULLAMA.search(blob):
        rep.warn(where, "Arabic: 'كلما ... كلما' — use كلما once")
    if LETTER_REF.search(blob):
        rep.warn(where, "explanation names an option letter; it breaks if options are reordered")


def check_question(rep, where, q, qtype, nlines, require_explain):
    """Returns the answer letter, or None when the item is too broken to judge."""
    rep.questions += 1
    options, correct, text = q.get("options"), q.get("correct"), q.get("text") or ""
    if not text.strip():
        rep.err(where, "empty question text")
    if not isinstance(options, list) or len(options) != 4 or \
            not all(isinstance(o, str) and o.strip() for o in options):
        rep.err(where, "needs exactly 4 non-empty options")
        return None
    if len({o.strip().lower() for o in options}) != 4:
        rep.err(where, "two options are identical")
    if not isinstance(correct, int) or isinstance(correct, bool) or not 0 <= correct < 4:
        rep.err(where, "correct must be an integer 0-3")
        return None
    if qtype == "sentence-completion" and not re.search(r"_{3,}", text):
        rep.err(where, "sentence completion needs a ____ blank")
    if qtype == "reading" and not nlines:
        rep.err(where, "reading question without a numbered passage")

    lengths = sorted(len(o) for o in options)
    gap = len(options[correct]) - lengths[-2]
    if len(options[correct]) == lengths[-1] and gap > 8:
        rep.warn(where, f"correct option is the longest by {gap} characters")

    ex = q.get("explain")
    if ex is None:
        if require_explain:
            rep.err(where, "missing explain")
    elif not isinstance(ex, dict):
        rep.err(where, "explain must be an object")
    else:
        check_explain(rep, where, ex, correct)

    if nlines:
        blob = text + " " + (json.dumps(ex, ensure_ascii=False) if isinstance(ex, dict) else "")
        for m in LINE_REF.finditer(blob):
            for n in (int(g) for g in m.groups() if g):
                if not 1 <= n <= nlines:
                    rep.err(where, f"line reference '{m.group(0)}' is outside the passage (1-{nlines})")
    return "ABCD"[correct]


def check_keys(rep, where, keys, runs=True):
    """keys in the order students meet them; runs=False for pooled lists where order means nothing."""
    n = len(keys)
    if n < 8:
        return
    count = Counter(keys)
    for letter in "ABCD":
        share = count[letter] / n
        skewed = (share > 0.4 or share < 0.1) if n >= 16 else (count[letter] == 0 or share > 0.5)
        if skewed:
            rep.warn(where, f"answer {letter} is correct {count[letter]}/{n} times — rebalance positions")
    if runs:
        for i in range(n - 2):
            if keys[i] == keys[i + 1] == keys[i + 2]:
                rep.warn(where, f"answer {keys[i]} three times in a row (items {i + 1}-{i + 3})")
                break


def validate(path, require_explain):
    rep = Report(path.name)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        rep.err(path.name, f"cannot read JSON: {e}")
        return rep, {}
    ids, texts = Counter(), {}

    def note_text(q, where):
        # Stem plus options: generic stems such as "What is the passage mainly about?" repeat legitimately.
        parts = [q.get("text") or ""] + sorted(o for o in (q.get("options") or []) if isinstance(o, str))
        t = re.sub(r"\s+", " ", " | ".join(parts).strip().lower())
        if (q.get("text") or "").strip():
            texts.setdefault(t, []).append(where)

    if isinstance(data.get("sets"), list):
        by_type = {}
        for s in data["sets"]:
            sid = s.get("id", "?")
            where = f"{sid}"
            ids[sid] += 1
            stype = s.get("type")
            if stype not in TYPES:
                rep.err(where, f"type must be one of {sorted(TYPES)}")
            if s.get("level") not in LEVELS:
                rep.err(where, "level must be easy, medium or hard")
            questions = s.get("questions") or []
            if not questions:
                rep.err(where, "set has no questions")
            if stype == "reading" and questions and len(questions) != 5:
                rep.warn(where, f"reading sets use 5 questions per passage (found {len(questions)})")
            nlines = passage_lines(s.get("passage"))
            keys = []
            for i, q in enumerate(questions, 1):
                letter = check_question(rep, f"{where} Q{i}", q, stype, nlines, require_explain)
                note_text(q, f"{path.name} {where} Q{i}")
                if letter:
                    keys.append(letter)
                    by_type.setdefault(stype, []).append(letter)
            check_keys(rep, where, keys)
        for stype, keys in by_type.items():
            check_keys(rep, f"all {stype} sets", keys, runs=False)

    if isinstance(data.get("exams"), list):
        for ex in data["exams"]:
            eid = ex.get("id", "?")
            ids[eid] += 1
            sections = ex.get("sections") or []
            if [s.get("type") for s in sections] != EXAM_TYPES or \
                    [len(s.get("questions") or []) for s in sections] != EXAM_COUNTS:
                rep.warn(eid, "sections differ from the official layout (SC4, SC4, RC5, RS3, RS3, SC4)")
            by_type, order = {}, []
            for si, sec in enumerate(sections, 1):
                nlines = passage_lines(sec.get("passage"))
                for qi, q in enumerate(sec.get("questions") or [], 1):
                    letter = check_question(rep, f"{eid} S{si}Q{qi}", q, sec.get("type"), nlines, require_explain)
                    note_text(q, f"{path.name} {eid} S{si}Q{qi}")
                    if letter:
                        order.append(letter)
                        by_type.setdefault(sec.get("type"), []).append(letter)
            check_keys(rep, eid, order)
            check_keys(rep, f"{eid} sentence completion", by_type.get("sentence-completion", []), runs=False)

    if not isinstance(data.get("sets"), list) and not isinstance(data.get("exams"), list):
        rep.err(path.name, 'expected a top-level "sets" or "exams" array')
    for i, n in ids.items():
        if n > 1:
            rep.err(path.name, f"duplicate id '{i}'")
    for t, places in texts.items():
        if len(places) > 1:
            rep.warn(path.name, f"same question text used {len(places)} times ({places[0]} …)")
    return rep, texts


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    require_explain = "--require-explain" in argv
    files = [Path(a) for a in argv if not a.startswith("--")] or DEFAULT_FILES
    failed = False
    all_texts = {}
    for f in files:
        if not f.exists():
            print(f"skip (missing): {f}")
            continue
        rep, texts = validate(f, require_explain)
        failed |= bool(rep.errors)
        print(f"{f.name} — {rep.questions} questions · {len(rep.errors)} errors · {len(rep.warnings)} warnings")
        for e in rep.errors:
            print(f"  ✗ {e}")
        for w in rep.warnings:
            print(f"  ! {w}")
        for t, places in texts.items():
            all_texts.setdefault(t, set()).add(f.name)
    shared = [t for t, names in all_texts.items() if len(names) > 1]
    if shared:
        failed = True
        print(f"✗ {len(shared)} question(s) appear in more than one file — practice must not reuse exam items:")
        for t in shared[:10]:
            print(f"  · {t[:80]}")
    print("FAILED" if failed else "OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
