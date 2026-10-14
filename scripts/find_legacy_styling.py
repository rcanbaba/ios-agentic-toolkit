#!/usr/bin/env python3
"""Find view code that still uses the legacy app's styling, group it by feature and split it into batches.

Deterministic step of the ui-port skill, used twice: before restyling, to size the work and
partition it between parallel agents; after, as the gate that says what is left. Patterns
are per project (the legacy font, color, gradient and asset forms, plus forms the new design
system forbids), kept in a JSON config next to the porting ledger.

config.json:
  {
    "src": "App",                                    # relative to this file; scanned for *.swift
    "group_depth": 2,                                # "Features/Profile/..." -> "Features/Profile"
    "exclude": ["App/DesignSystem/*", "App/**/Generated/*"],
    "patterns": {"legacy-font": "\\.font\\(\\.Brand\\.", "named-color": "Color\\(\\\"", ...},
    "keep": [{"path": "App/Features/Wallet/*", "reason": "deferred to the end of the port"}]
  }

Paths in "exclude", "keep" and the report start with the folder name of src ("App/..."),
wherever the config lives (for example ".migration/port/" with "src": "../../App").
A match in a file listed under "keep" (glob) is reported as kept, with its reason, and does not
count against the gate. Batches are balanced by line count (longest-processing-time greedy):
each group (feature folder) goes whole to the currently smallest batch, so one agent owns a
feature end to end.

Usage: find_legacy_styling.py <config.json> [--batches N] [--out <report.json>]
Exit code 0 = no unkept match, 1 = matches remain, 2 = usage/IO error.
"""

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config")
    ap.add_argument("--batches", type=int, default=0)
    ap.add_argument("--out")
    args = ap.parse_args()

    try:
        cfg = json.loads(Path(args.config).read_text())
        patterns = {k: re.compile(v) for k, v in cfg["patterns"].items()}
    except (OSError, KeyError, ValueError, re.error) as exc:
        print(f"bad config: {exc}", file=sys.stderr)
        return 2
    base = Path(args.config).parent
    src = (base / cfg.get("src", ".")).resolve()
    root = src.parent  # reported paths and globs start with src's own folder name ("App/...")
    if not src.is_dir():
        print(f"src not found: {src}", file=sys.stderr)
        return 2
    depth = int(cfg.get("group_depth", 2))
    excludes = cfg.get("exclude", [])
    keeps = cfg.get("keep", [])

    files, kept, groups = [], [], {}
    for path in sorted(src.rglob("*.swift")):
        rel = path.resolve().relative_to(root).as_posix()
        if any(fnmatch.fnmatch(rel, g) for g in excludes):
            continue
        text = path.read_text(errors="ignore")
        hits = []
        for lineno, line in enumerate(text.splitlines(), 1):
            for name, pat in patterns.items():
                if pat.search(line):
                    hits.append({"line": lineno, "pattern": name})
        if not hits:
            continue
        keep = next((k for k in keeps if fnmatch.fnmatch(rel, k["path"])), None)
        entry = {"path": rel, "lines": text.count("\n") + 1, "matches": len(hits),
                 "patterns": sorted({h["pattern"] for h in hits}), "first": hits[0]["line"]}
        if keep:
            kept.append({**entry, "reason": keep.get("reason", "")})
            continue
        files.append(entry)
        in_src = path.resolve().relative_to(src).parts
        group = "/".join(in_src[:depth]) if len(in_src) > depth else "/".join(in_src[:-1]) or "."
        g = groups.setdefault(group, {"group": group, "files": 0, "lines": 0, "matches": 0})
        g["files"] += 1
        g["lines"] += entry["lines"]
        g["matches"] += entry["matches"]

    ordered = sorted(groups.values(), key=lambda g: (-g["lines"], g["group"]))
    batches = []
    if args.batches > 0:
        batches = [{"batch": i + 1, "groups": [], "files": 0, "lines": 0} for i in range(args.batches)]
        for g in ordered:
            b = min(batches, key=lambda b: (b["lines"], b["batch"]))
            b["groups"].append(g["group"])
            b["files"] += g["files"]
            b["lines"] += g["lines"]
        batches = [b for b in batches if b["groups"]]

    report = {"src": cfg.get("src", "."), "files": files, "groups": ordered, "batches": batches, "kept": kept,
              "totals": {"files": len(files), "lines": sum(f["lines"] for f in files),
                         "matches": sum(f["matches"] for f in files), "kept_files": len(kept)}}
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(text)
    else:
        sys.stdout.write(text)
    t = report["totals"]
    print(f"{t['files']} files · {t['lines']} lines · {t['matches']} matches in {len(ordered)} groups · "
          f"{t['kept_files']} kept", file=sys.stderr)
    return 1 if files else 0


if __name__ == "__main__":
    sys.exit(main())
