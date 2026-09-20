#!/usr/bin/env python3
"""Merge audited drafts into data/practice.json (sets) or data/exams_generated.json (exams).

Usage:
  python tools/merge_drafts.py drafts/restatement.json drafts/reading.json ...
  python tools/merge_drafts.py drafts/exam-g6.json drafts/exam-g7.json
  python tools/merge_drafts.py --dry-run drafts/*.json

Every draft question must already carry its Arabic `explain` (added by the Arabic
Tutor agent). Set and exam ids must be new. Practice sets are ordered by skill, then
level, then set number; exams keep their given order. Both files run through
tools/validate_content.py before anything is written.
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRACTICE = ROOT / "data" / "practice.json"
EXAMS = ROOT / "data" / "exams_generated.json"
TYPE_ORDER = {"restatement": 0, "reading": 1, "sentence-completion": 2}
LEVEL_ORDER = {"easy": 0, "medium": 1, "hard": 2}


def sort_key(s):
    m = re.search(r"(\d+)$", s.get("id", ""))
    return (TYPE_ORDER.get(s.get("type"), 9), LEVEL_ORDER.get(s.get("level"), 9), int(m.group(1)) if m else 0)


def dump(data):
    out = json.dumps(data, ensure_ascii=False, indent=2)
    # vocab pairs on one line, as in the rest of the file
    return re.sub(r'\[\s*\n\s*("(?:[^"\\]|\\.)*"),\s*\n\s*("(?:[^"\\]|\\.)*")\s*\n\s*\]', r"[\1, \2]", out) + "\n"


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    dry = "--dry-run" in argv
    drafts = [Path(a) for a in argv if not a.startswith("--")]
    if not drafts:
        print(__doc__)
        return 2

    practice = json.loads(PRACTICE.read_text(encoding="utf-8"))
    exams = json.loads(EXAMS.read_text(encoding="utf-8"))
    ids = {s["id"] for s in practice["sets"]} | {e["id"] for e in exams["exams"]}
    new_sets, new_exams, problems = [], [], []

    def explained(item, questions):
        missing = [i for i, q in enumerate(questions, 1) if not q.get("explain")]
        if missing:
            problems.append(f"{item} has no explanation for Q{missing}")
        return not missing

    for path in drafts:
        draft = json.loads(path.read_text(encoding="utf-8"))
        for s in draft.get("sets", []):
            sid = s.get("id", "?")
            if sid in ids:
                problems.append(f"{path.name}: set id '{sid}' already exists")
            elif explained(f"{path.name}: {sid}", s.get("questions", [])):
                ids.add(sid)
                new_sets.append(s)
        for e in draft.get("exams", []):
            eid = e.get("id", "?")
            qs = [q for sec in e.get("sections", []) for q in sec.get("questions", [])]
            if eid in ids:
                problems.append(f"{path.name}: exam id '{eid}' already exists")
            elif explained(f"{path.name}: {eid}", qs):
                ids.add(eid)
                new_exams.append(e)
        if not draft.get("sets") and not draft.get("exams"):
            problems.append(f'{path.name}: no top-level "sets" or "exams"')
    if problems:
        print("Not merged:")
        for p in problems:
            print("  ✗", p)
        return 1

    practice["sets"] = sorted(practice["sets"] + new_sets, key=sort_key)
    exams["exams"] = exams["exams"] + new_exams
    texts = {PRACTICE: dump(practice), EXAMS: dump(exams)}

    # validate the result before touching data/
    tmps = {}
    for path, text in texts.items():
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as tmp:
            tmp.write(text)
        tmps[path] = tmp.name
    check = subprocess.run([sys.executable, str(ROOT / "tools" / "validate_content.py"), "--require-explain",
                            *tmps.values()], capture_output=True, text=True, encoding="utf-8")
    for tmp in tmps.values():
        Path(tmp).unlink(missing_ok=True)
    print(check.stdout.strip())
    if check.returncode != 0:
        print("Validation failed — nothing in data/ was changed.")
        return 1

    by_type = {}
    for s in new_sets:
        by_type[s["type"]] = by_type.get(s["type"], 0) + len(s["questions"])
    verb = "Would add" if dry else "Added"
    if new_sets:
        print(f"{verb} {len(new_sets)} practice sets:", ", ".join(f"{k} {v} questions" for k, v in by_type.items()))
    if new_exams:
        n = sum(len(sec["questions"]) for e in new_exams for sec in e["sections"])
        print(f"{verb} {len(new_exams)} exams ({n} questions):", ", ".join(e["id"] for e in new_exams))
    if not dry:
        if new_sets:
            PRACTICE.write_text(texts[PRACTICE], encoding="utf-8")
            total = sum(len(s["questions"]) for s in practice["sets"])
            print(f"data/practice.json now has {len(practice['sets'])} sets, {total} questions.")
        if new_exams:
            EXAMS.write_text(texts[EXAMS], encoding="utf-8")
            total = sum(len(sec["questions"]) for e in exams["exams"] for sec in e["sections"])
            print(f"data/exams_generated.json now has {len(exams['exams'])} exams, {total} questions.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
