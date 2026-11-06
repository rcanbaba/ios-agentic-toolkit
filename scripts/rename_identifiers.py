#!/usr/bin/env python3
"""Rename Swift identifiers across a source tree without touching string literals.

  rename_identifiers.py <map.json> --src <dir> [--files F ...] [--exclude GLOB ...] [--dry-run] [--out report.json]

map.json:
  {
    "rename":    {"OldName": "NewName", ...},
    "protected": ["playlistId", ...],   Swift names that double as wire names (JSON keys, CodingKeys
                                        cases without raw values, push types); never renamed
    "banned":    ["premium", "deluxe"]    optional; words no new name may contain (case-insensitive)
  }

Whole-word renames in code, comments and inside string interpolations \\( ... ). The text of string
literals is never changed (server values, keys, analytics names and user-visible text live there),
nor are file paths in comments ("Features/Old/OldView.swift"). A leading "_" (property wrapper
storage, `_viewModel`) is renamed with the name.

Refuses to write anything (exit 1) when:
  - a protected name is in the rename map, or a new name contains a banned word;
  - an old or new name is a single character (half-applied renames of one-letter names were the
    defects reviewers had to catch by hand);
  - in a file that is about to change, a new name already occurs as a bare identifier in code (not
    after a dot): after the rename a reference could bind to a different declaration.

Warns (does not refuse) when a renamed name is declared as an enum case in a file that turns cases
into text (String(describing:), "\\(self)", .rawValue-less descriptions): asset names, keys or log
values built from case names change silently.

--files limits the rename to those files (a scoped rename, for example one of two view models that
hold same-named copies). Exit code 0 = done (or would be, with --dry-run), 1 = refused, 2 = usage.
"""
import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from swift_lex import segments  # noqa: E402

DEFAULT_EXCLUDE = ["Pods/*", "*/Pods/*", ".build/*", "*/.build/*", "DerivedData/*", "*/DerivedData/*"]
TO_TEXT = re.compile(r'String\(describing:|"\\\(self\)"|\\\(self\)')


def load_maps(paths):
    ren, protected, banned = {}, set(), set()
    for p in paths:
        data = json.loads(Path(p).read_text())
        for old, new in data.get("rename", {}).items():
            if old in ren and ren[old] != new:
                raise ValueError(f"'{old}' renamed to both '{ren[old]}' and '{new}'")
            ren[old] = new
        protected |= set(data.get("protected", []))
        banned |= {w.lower() for w in data.get("banned", [])}
    return ren, protected, banned


def word_pattern(names):
    alt = "|".join(sorted(map(re.escape, names), key=len, reverse=True))
    return re.compile(r"(?<![A-Za-z0-9_])_?(" + alt + r")(?![A-Za-z0-9_])")


def map_problems(ren, protected, banned):
    problems = []
    for name in sorted(set(ren) & protected):
        problems.append(f"protected name in the rename map: {name}")
    for old, new in sorted(ren.items()):
        if len(old) == 1 or len(new) == 1:
            problems.append(f"single-character name: {old} -> {new}")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", new):
            problems.append(f"not an identifier: {new}")
        for w in sorted(banned):
            if w in new.lower():
                problems.append(f"banned word '{w}' in new name: {old} -> {new}")
    return problems


def rename_text(text, ren, word):
    sub = lambda t: word.sub(lambda m: m.group(0)[:-len(m.group(1))] + ren[m.group(1)], t)

    def comment(t):
        parts = re.split(r"(\S+\.swift\b)", t)
        return "".join(p if i % 2 else sub(p) for i, p in enumerate(parts))

    return "".join(t if k == "string" else comment(t) if k == "comment" else sub(t) for k, t in segments(text))


def swift_files(src, files, exclude):
    if files:
        return [Path(f).resolve() for f in files]
    out = []
    for p in sorted(src.rglob("*.swift")):
        rel = p.relative_to(src).as_posix()
        if not any(fnmatch.fnmatch(rel, g) for g in exclude):
            out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("maps", nargs="+")
    ap.add_argument("--src", required=True)
    ap.add_argument("--files", nargs="*")
    ap.add_argument("--exclude", nargs="*", default=[])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()

    src = Path(a.src).resolve()
    try:
        ren, protected, banned = load_maps(a.maps)
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print("error:", e); return 2
    if not ren:
        print("error: empty rename map"); return 2

    word = word_pattern(ren)
    errors = map_problems(ren, protected, banned)
    warnings, changes = [], {}
    for path in swift_files(src, a.files, DEFAULT_EXCLUDE + a.exclude):
        rel = path.relative_to(src).as_posix() if path.is_relative_to(src) else str(path)
        text = path.read_text()
        segs = segments(text)
        if "".join(t for _, t in segs) != text:
            errors.append(f"{rel}: lexer round-trip failed"); continue
        code = "".join(t if k == "code" else " " * len(t) for k, t in segs)
        olds = set(word.findall("".join(t if k != "string" else " " * len(t) for k, t in segs)))
        if not olds:
            continue
        for old in sorted(olds):
            new = ren[old]
            if re.search(r"(?<![A-Za-z0-9_.])" + re.escape(new) + r"(?![A-Za-z0-9_])", code):
                errors.append(f"{rel}: '{new}' already used here (renaming '{old}')")
            if TO_TEXT.search(code) and re.search(r"\bcase\b[^\n]*(?<![A-Za-z0-9_])" + re.escape(old) + r"(?![A-Za-z0-9_])", code):
                warnings.append(f"{rel}: enum case '{old}' in a file that turns values into text; check names built from cases")
        new_text = rename_text(text, ren, word)
        if new_text != text:
            changes[path] = (rel, new_text)

    if not errors and not a.dry_run:
        for path, (_, new_text) in changes.items():
            path.write_text(new_text)
    report = {
        "renames": len(ren),
        "files_changed": sorted(rel for rel, _ in changes.values()),
        "written": not errors and not a.dry_run,
        "errors": errors,
        "warnings": sorted(set(warnings)),
    }
    if a.out:
        Path(a.out).write_text(json.dumps(report, indent=2) + "\n")
    for e in errors:
        print("error:", e)
    for w in report["warnings"]:
        print("warning:", w)
    verb = "refused" if errors else ("dry run" if a.dry_run else "renamed")
    print(f"{verb}: {len(changes)} files, {len(ren)} names")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
