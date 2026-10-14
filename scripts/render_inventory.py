#!/usr/bin/env python3
"""Render the merged inventory into a readable INVENTORY.md.

Deterministic step of the feature-inventory skill. Reads
  <migration-dir>/inventory/inventory.json        from merge_inventory.py
  <migration-dir>/inventory/coverage.json         from merge_inventory.py
  <migration-dir>/inventory/reconciliation.json   optional, from reconcile_inventory.py
  <migration-dir>/inventory/parts/*.json          for open questions
and writes <migration-dir>/inventory/INVENTORY.md with: completeness against the
baseline (identifier fields, files, text mentions of informational keys), dead
identifiers, the feature list per area, core flows, core/high features without a flow
spec and why, known issues, source file notes and open questions. The Markdown is derived; edit the parts, not the rendering.

Usage: render_inventory.py [--migration-dir <dir>] [--title <text>]
Exit code 0 = rendered, 2 = usage/IO error.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

RANK = {"core": 0, "high": 1, "medium": 2, "low": 3}


def cell(text):
    return str(text).replace("|", "/").replace("\n", " ")


def render(mig, title):
    inv = mig / "inventory"
    inventory = json.loads((inv / "inventory.json").read_text())
    cov = json.loads((inv / "coverage.json").read_text())
    rec_path = inv / "reconciliation.json"
    rec = json.loads(rec_path.read_text()) if rec_path.is_file() else {}
    parts = [json.loads(p.read_text()) for p in sorted((inv / "parts").glob("*.json"))]
    features = inventory["features"]
    areas = [(a["area"], a.get("title") or a["area"]) for a in inventory["areas"]]
    by_area = defaultdict(list)
    for f in features:
        by_area[f["area"]].append(f)
    crit = Counter(f["criticality"] for f in features)

    L = [f"# {title}", "",
         f"{len(features)} features · core {crit['core']} · high {crit['high']} · medium {crit['medium']} · low {crit['low']}", "",
         "## Completeness against the code baseline", "", "| Baseline (from code) | Referenced by features |", "|---|---|"]
    for field, c in cov["coverage"].items():
        L.append(f"| {field} | {c['referenced']}/{c['known']} |")
    fl = cov["files"]
    L.append(f"| source files | {fl['covered']}/{fl['total']} |")
    L.append("")
    text = {k: c for k, c in cov.get("text_coverage", {}).items() if c["known"]}
    if text:
        L += ["| Informational baseline | Mentioned in features | In specs | Specs only | Not mentioned |", "|---|---|---|---|---|"]
        L += [f"| {k} | {c['referenced_in_inventory']}/{c['known']} | {c['referenced_in_specs']} | {len(c['in_specs_only'])} | "
              + (", ".join(f"`{n}`" for n in c["unreferenced"][:8]) + (" ..." if len(c["unreferenced"]) > 8 else "") if c["unreferenced"] else "0") + " |"
              for k, c in text.items()]
        L.append("")
    dead = {k: v for k, v in rec.get("dead_identifiers", {}).items() if v}
    if dead:
        L += ["**Identifiers with no caller in the app (candidates for not porting):**", ""]
        L += [f"- {field}: " + ", ".join(f"`{n}`" for n in names) for field, names in dead.items()]
        L.append("")
    issues = []
    if cov.get("dangling_depends_on"):
        issues.append(f"{len(cov['dangling_depends_on'])} dangling depends_on")
    if cov.get("duplicate_ids"):
        issues.append(f"{len(cov['duplicate_ids'])} duplicate ids")
    if cov.get("core_high_without_flow"):
        issues.append(f"{len(cov['core_high_without_flow'])} core/high features without a flow")
    if cov.get("core_high_without_spec"):
        issues.append(f"{len(cov['core_high_without_spec'])} core/high features without a flow spec or spec_note")
    if cov.get("problems"):
        issues.append(f"{len(cov['problems'])} invalid parts")
    if issues:
        L += ["**Open coverage problems:** " + "; ".join(issues) + " (see coverage.json)", ""]

    L += ["## Feature list", ""]
    for area, heading in areas:
        fs = sorted(by_area[area], key=lambda f: (RANK[f["criticality"]], f["id"]))
        L += [f"### {heading} ({len(fs)})", "", "| Feature | Criticality | Roles | Summary |", "|---|---|---|---|"]
        for f in fs:
            L.append(f"| `{f['id']}` {cell(f['name'])} | {f['criticality']} | {cell(', '.join(f.get('user_roles', [])))} | {cell(f['summary'])} |")
        L.append("")

    L += ["## Core flows", ""]
    for area, heading in areas:
        for f in sorted(by_area[area], key=lambda f: f["id"]):
            if f["criticality"] != "core":
                continue
            L += [f"### `{f['id']}` — {f['name']}", "", f["summary"], ""]
            L += [f"{i}. {s}" for i, s in enumerate(f.get("flow", []), 1)]
            if f.get("states_and_edge_cases"):
                L += ["", "**Edge cases:** " + "; ".join(f["states_and_edge_cases"])]
            if f.get("depends_on"):
                L += ["", "**Depends on:** " + ", ".join(f"`{d}`" for d in f["depends_on"])]
            L.append("")

    noted = [f for f in features if f.get("spec_note")]
    if noted:
        L += ["## Core and high features without a flow spec", ""] + [f"- `{f['id']}`: {f['spec_note']}" for f in noted] + [""]

    L += ["## Known issues found during inventory", ""]
    for area, heading in areas:
        items = [(f["id"], k) for f in by_area[area] for k in f.get("known_issues", [])]
        if items:
            L += [f"### {heading} ({len(items)})", ""] + [f"- `{i}`: {k}" for i, k in items] + [""]

    notes = [(f["id"], path, note) for f in features for path, note in f.get("source_file_notes", {}).items()]
    if notes:
        L += ["## Source file notes", ""] + [f"- `{path}` ({fid}): {note}" for fid, path, note in notes] + [""]

    L += ["## Open questions", ""]
    for part in parts:
        qs = part.get("open_questions", [])
        if qs:
            heading = dict(areas).get(part["area"], part["area"])
            L += [f"### {heading} ({len(qs)})", ""] + [f"- {q}" for q in qs] + [""]

    out = inv / "INVENTORY.md"
    out.write_text("\n".join(L).rstrip() + "\n")
    return out, len(L), len(features)


def main(argv):
    args = argv[1:]
    mig, title = Path(".migration"), "Feature inventory"
    for flag in ("--migration-dir", "--title"):
        if flag in args:
            i = args.index(flag)
            value = args[i + 1]
            del args[i:i + 2]
            if flag == "--migration-dir":
                mig = Path(value)
            else:
                title = value
    if args:
        print("usage: render_inventory.py [--migration-dir <dir>] [--title <text>]", file=sys.stderr)
        return 2
    try:
        out, lines, n = render(mig, title)
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"error: {exc} (run merge_inventory.py first?)", file=sys.stderr)
        return 2
    print(f"wrote {out}: {lines} lines, {n} features")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
