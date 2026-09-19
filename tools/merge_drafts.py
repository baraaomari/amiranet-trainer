#!/usr/bin/env python3
"""Merge audited draft sets into data/practice.json.

Usage:
  python tools/merge_drafts.py drafts/restatement.json drafts/reading.json ...
  python tools/merge_drafts.py --dry-run drafts/*.json

Every draft question must already carry its Arabic `explain` (added by the Arabic
Tutor agent). Set ids must be new. The merged file is ordered by skill, then level,
then set number, and runs through tools/validate_content.py before it is written.
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRACTICE = ROOT / "data" / "practice.json"
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

    data = json.loads(PRACTICE.read_text(encoding="utf-8"))
    existing = {s["id"] for s in data["sets"]}
    added, problems = [], []
    for path in drafts:
        for s in json.loads(path.read_text(encoding="utf-8")).get("sets", []):
            sid = s.get("id", "?")
            if sid in existing:
                problems.append(f"{path.name}: set id '{sid}' already exists")
                continue
            missing = [i for i, q in enumerate(s.get("questions", []), 1) if not q.get("explain")]
            if missing:
                problems.append(f"{path.name}: {sid} has no explanation for Q{missing}")
                continue
            existing.add(sid)
            added.append(s)
    if problems:
        print("Not merged:")
        for p in problems:
            print("  ✗", p)
        return 1

    data["sets"] = sorted(data["sets"] + added, key=sort_key)
    text = dump(data)

    # validate the result before touching data/
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as tmp:
        tmp.write(text)
    check = subprocess.run([sys.executable, str(ROOT / "tools" / "validate_content.py"), "--require-explain",
                            tmp.name, str(ROOT / "data" / "exams_generated.json")],
                           capture_output=True, text=True, encoding="utf-8")
    Path(tmp.name).unlink(missing_ok=True)
    print(check.stdout.strip())
    if check.returncode != 0:
        print("Validation failed — data/practice.json was not changed.")
        return 1

    by_type = {}
    for s in added:
        by_type[s["type"]] = by_type.get(s["type"], 0) + len(s["questions"])
    print(f"{'Would add' if dry else 'Added'} {len(added)} sets:", ", ".join(f"{k} {v} questions" for k, v in by_type.items()))
    if not dry:
        PRACTICE.write_text(text, encoding="utf-8")
        total = sum(len(s["questions"]) for s in data["sets"])
        print(f"data/practice.json now has {len(data['sets'])} sets, {total} questions.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
