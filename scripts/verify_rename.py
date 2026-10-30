#!/usr/bin/env python3
"""Prove that a rename changed names and nothing else, against a copy taken before it.

  verify_rename.py <map.json> [<map.json> ...] --src <dir> --baseline <copy of dir> [--out report.json]

For every .swift file the script finds its baseline: the same relative path, or the path with the
map's renames reversed in its folder and file names (Features/Mixtape/MixtapeView.swift ->
Features/Playlist/PlaylistView.swift), or an explicit "files": {"old/rel.swift": "new/rel.swift"}
entry in a map. Then, per file:

  strings    the sequence of string literal contents is identical (wire names, keys, text)
  lines      the line count is identical (a rename never adds or removes lines)
  tokens     every changed token on a changed line is old -> new from the maps ("_old" -> "_new" too)

and over the whole tree: the multiset of all string literals is identical, every baseline file has a
counterpart and every current file has a baseline. A file split, a moved declaration or a refactor
is not a rename; verify those with check_split.py or a review, after the rename is verified.

Exit code 0 = only mapped renames, 1 = anything else (report lists each), 2 = usage.
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from swift_lex import segments  # noqa: E402

TOKEN = re.compile(r"[A-Za-z0-9_]+|[^A-Za-z0-9_]")
SKIP = ("Pods/", ".build/", "DerivedData/")


def swift_files(root):
    return {p.relative_to(root).as_posix(): p for p in sorted(root.rglob("*.swift"))
            if not any(s in p.relative_to(root).as_posix() + "/" for s in SKIP)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("maps", nargs="+")
    ap.add_argument("--src", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()

    ren, moved = {}, {}
    for m in a.maps:
        data = json.loads(Path(m).read_text())
        ren.update(data.get("rename", {}))
        moved.update({new: old for old, new in data.get("files", {}).items()})
    back = {new: old for old, new in ren.items()}
    back_word = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(sorted(map(re.escape, back), key=len, reverse=True)) + r")(?![A-Za-z0-9_])") if back else None

    src, base = Path(a.src).resolve(), Path(a.baseline).resolve()
    cur, old = swift_files(src), swift_files(base)
    problems, matched = [], set()
    changed_files = changed_lines = 0

    def baseline_of(rel):
        if rel in moved:
            return moved[rel]
        if rel in old:
            return rel
        if back_word:
            guess = back_word.sub(lambda m: back[m.group(1)], rel)
            if guess in old:
                return guess
        return None

    def same_token(t, u):
        if t == u:
            return True
        if ren.get(t) == u:
            return True
        return t.startswith("_") and u.startswith("_") and ren.get(t[1:]) == u[1:]

    for rel, path in cur.items():
        b = baseline_of(rel)
        if b is None:
            problems.append({"file": rel, "kind": "no_baseline", "detail": "new file or a move the maps do not explain"})
            continue
        matched.add(b)
        before, after = old[b].read_text(), path.read_text()
        if before == after:
            continue
        changed_files += 1
        if [t for k, t in segments(before) if k == "string"] != [t for k, t in segments(after) if k == "string"]:
            problems.append({"file": rel, "kind": "strings", "detail": "string literal contents changed"})
        bl, al = before.splitlines(), after.splitlines()
        if len(bl) != len(al):
            problems.append({"file": rel, "kind": "lines", "detail": f"{len(bl)} -> {len(al)} lines"})
            continue
        for n, (x, y) in enumerate(zip(bl, al), 1):
            if x == y:
                continue
            changed_lines += 1
            tx, ty = TOKEN.findall(x), TOKEN.findall(y)
            if len(tx) != len(ty) or not all(same_token(t, u) for t, u in zip(tx, ty)):
                problems.append({"file": rel, "kind": "tokens", "line": n, "detail": f"- {x.strip()}  + {y.strip()}"})

    for b in sorted(set(old) - matched):
        problems.append({"file": b, "kind": "missing", "detail": "baseline file has no counterpart"})

    count = lambda files: collections.Counter(t for p in files.values() for k, t in segments(p.read_text()) if k == "string")
    sb, sc = count(old), count(cur)
    if sb != sc:
        only_b = sorted((sb - sc).elements())[:10]
        only_c = sorted((sc - sb).elements())[:10]
        problems.append({"file": "*", "kind": "string_multiset", "detail": f"only in baseline {only_b}, only now {only_c}"})

    report = {
        "files": len(cur),
        "files_changed": changed_files,
        "lines_changed": changed_lines,
        "string_literals": sum(sc.values()),
        "problems": problems,
    }
    if a.out:
        Path(a.out).write_text(json.dumps(report, indent=2) + "\n")
    for p in problems:
        print(f"{p['kind']:15} {p['file']}{':' + str(p['line']) if 'line' in p else ''}  {p['detail']}")
    print(f"{changed_files} files, {changed_lines} lines changed; {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
