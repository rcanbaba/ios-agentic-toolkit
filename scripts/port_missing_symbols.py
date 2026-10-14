#!/usr/bin/env python3
"""Plan (and optionally apply) the next build-error-driven port step: which legacy files to copy.

Deterministic step of the port-code skill. Porting copies legacy code verbatim into the
new app, builds, and lets the compiler say what is still missing. This script reads one
build log and, for every missing symbol, finds the legacy file that declares it:

  cannot find type 'X' in scope / cannot find 'X' in scope
      -> the unique legacy file that declares X (type, func, var, let, case, typealias)
  type 'T' has no member 'm' / value of type 'T' has no member 'm'
      -> the unique legacy file that declares m inside `extension T` or the declaration of T
         (a file that merely declares some `m` elsewhere is not a match)
  ImageResource / ColorResource has no member 'm'
      -> not code: listed under asset_members for port_assets.py
  invalid redeclaration / is ambiguous for type lookup / ambiguous use of
      -> listed under duplicates with every target file that declares the name, so the
         temporary copy (an extracted type, a shim) can be removed once the original arrives

A symbol is copied only when exactly one legacy file declares it and no file with the same
basename is already in the target or already planned from another legacy file (one target
cannot hold two files with the same name); anything else is listed as unresolved with
candidates for an agent to read. Destinations come from --path-map (first matching legacy prefix);
unmapped files go under --fallback.

Usage:
  port_missing_symbols.py --legacy <dir> --target <dir> --errors <build.log>
                          [--path-map <map.json>] [--fallback <dir>] [--exclude <glob> ...]
                          [--apply] [--out <report.json>]
  map.json: [["Scenes/Features/", "Features/"], ["Common/", "UI/Common/"]]
Exit code 0 = nothing unresolved and no duplicates, 1 = unresolved or duplicates remain,
2 = usage/IO error. Without --apply nothing is written except --out.
"""

import argparse
import fnmatch
import json
import re
import shutil
import sys
from pathlib import Path

ERROR_LINE = re.compile(r"^(?P<file>[^:\n]+\.swift):(?P<line>\d+):(?P<col>\d+): error: (?P<msg>.*)$")
MISSING = re.compile(r"cannot find (?:type )?'(\w+)' in scope")
MEMBER = re.compile(r"(?:value of )?type '([^']+)' has no member '(\w+)'")
DUPLICATE = [
    re.compile(r"invalid redeclaration of '(\w+)"),
    re.compile(r"'(\w+)' is ambiguous for type lookup in this context"),
    re.compile(r"ambiguous use of '(\w+)"),
]
ASSET_OWNERS = {"ImageResource", "ColorResource", "DeveloperToolsSupport.ImageResource",
                "DeveloperToolsSupport.ColorResource"}
MODIFIERS = r"(?:(?:@\w+(?:\([^)]*\))?\s+)|(?:public|private|fileprivate|internal|open|static|class|final|" \
            r"override|mutating|nonmutating|lazy|weak|unowned|indirect|convenience|required|nonisolated)\s+)*"
DECL_KINDS = r"(?:func|var|let|class|struct|enum|protocol|typealias|actor|case)"


def decl_pattern(name, kinds=DECL_KINDS):
    return re.compile(r"^[ \t]*" + MODIFIERS + kinds + r"\s+" + re.escape(name) + r"\b", re.M)


def case_list_pattern(name):
    # `case a, b, c` declares b and c too
    return re.compile(r"^[ \t]*(?:indirect\s+)?case\s+[^\n]*?[,\s]" + re.escape(name) + r"\b(?![\"'(:])", re.M)


def owner_name(type_text):
    base = type_text.split("<", 1)[0].strip().rstrip("?!")
    return base.split(".")[-1]


def type_bodies(text, owner):
    """Bodies of `extension Owner ...{}` and `struct/class/enum Owner ...{}` (brace-matched)."""
    head = re.compile(r"^[ \t]*" + MODIFIERS + r"(?:extension|class|struct|enum|actor|protocol)\s+"
                      r"(?:\w+\.)*" + re.escape(owner) + r"\b[^{\n]*\{", re.M)
    for m in head.finditer(text):
        depth, i = 1, m.end()
        while i < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        yield text[m.end():i]


def load_errors(path):
    out = []
    for raw in Path(path).read_text(errors="ignore").splitlines():
        m = ERROR_LINE.match(raw.strip())
        if m:
            out.append(m.group("msg"))
    return out


def swift_files(root, excludes):
    for p in sorted(root.rglob("*.swift")):
        rel = p.relative_to(root).as_posix()
        if any(fnmatch.fnmatch(rel, g) for g in excludes):
            continue
        yield rel, p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--legacy", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--errors", required=True)
    ap.add_argument("--path-map")
    ap.add_argument("--fallback", default="Ported/")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()

    legacy, target = Path(args.legacy), Path(args.target)
    if not legacy.is_dir() or not target.is_dir() or not Path(args.errors).is_file():
        print("legacy/target must be directories and --errors a file", file=sys.stderr)
        return 2
    path_map = json.loads(Path(args.path_map).read_text()) if args.path_map else []

    legacy_files = {rel: p.read_text(errors="ignore") for rel, p in swift_files(legacy, args.exclude)}
    target_files = {rel: p.read_text(errors="ignore") for rel, p in swift_files(target, [])}
    target_basenames = {Path(rel).name for rel in target_files}

    missing, members, asset_members, duplicates = set(), set(), set(), set()
    for msg in load_errors(args.errors):
        if m := MISSING.search(msg):
            missing.add(m.group(1))
        elif m := MEMBER.search(msg):
            owner = m.group(1)
            if owner in ASSET_OWNERS or owner_name(owner) in {"ImageResource", "ColorResource"}:
                asset_members.add(m.group(2))
            else:
                members.add((owner_name(owner), m.group(2)))
        for d in DUPLICATE:
            if m := d.search(msg):
                duplicates.add(m.group(1))

    def destination(rel):
        for src, dst in path_map:
            if rel.startswith(src):
                return dst + rel[len(src):]
        return args.fallback.rstrip("/") + "/" + rel

    plan, unresolved, already_present = [], [], []

    def resolve(label, hits):
        fresh = [h for h in hits if Path(h).name not in target_basenames]
        if hits and not fresh:
            already_present.append({"symbol": label, "legacy_files": hits})
            return
        if len(fresh) == 1:
            rel = fresh[0]
            same = [item for item in plan if Path(item["legacy"]).name == Path(rel).name]
            if same and same[0]["legacy"] == rel:
                same[0]["symbols"].append(label)
                return
            if same:  # two files with one basename cannot both be in a target
                unresolved.append({"symbol": label, "candidates": [rel], "candidate_count": 1,
                                   "why": f"basename already planned from {same[0]['legacy']}"})
                return
            plan.append({"symbols": [label], "legacy": rel, "target": destination(rel)})
        else:
            unresolved.append({"symbol": label, "candidates": fresh[:5], "candidate_count": len(fresh)})

    for name in sorted(missing):
        pat, cases = decl_pattern(name), case_list_pattern(name)
        resolve(name, [rel for rel, t in legacy_files.items() if pat.search(t) or cases.search(t)])

    for owner, member in sorted(members):
        pat, cases = decl_pattern(member), case_list_pattern(member)
        hits = [rel for rel, t in legacy_files.items()
                if any(pat.search(body) or cases.search(body) for body in type_bodies(t, owner))]
        resolve(f"{owner}.{member}", hits)

    dup_report = []
    for name in sorted(duplicates):
        pat = decl_pattern(name, r"(?:class|struct|enum|protocol|actor|typealias|func|var|let)")
        files = sorted(rel for rel, t in target_files.items() if pat.search(t))
        dup_report.append({"symbol": name, "target_files": files})

    copied = []
    if args.apply:
        for item in plan:
            dst = target / item["target"]
            if dst.exists():
                item["skipped"] = "destination exists"
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy / item["legacy"], dst)
            copied.append(item["target"])

    report = {
        "errors_read": len(load_errors(args.errors)),
        "plan": plan,
        "applied": args.apply,
        "copied": copied,
        "unresolved": unresolved,
        "already_present": already_present,
        "asset_members": sorted(asset_members),
        "duplicates": dup_report,
    }
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(text)
    else:
        sys.stdout.write(text)
    print(f"plan {len(plan)} · copied {len(copied)} · unresolved {len(unresolved)} · "
          f"already present {len(already_present)} · asset members {len(asset_members)} · "
          f"duplicates {len(dup_report)}", file=sys.stderr)
    return 1 if unresolved or dup_report else 0


if __name__ == "__main__":
    sys.exit(main())
