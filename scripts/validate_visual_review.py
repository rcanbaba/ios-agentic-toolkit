#!/usr/bin/env python3
"""Validate a visual-review contract and optionally render it as Markdown.

Deterministic gate after the review agent. Two layers:
  1. Structural: schema_lite subset applied to schemas/visual-review.schema.json.
  2. Semantic: unique ids; findings point at a known screen; the rule exists (an id from the
     skill's ux-rules.md, DS-GUIDE with a guideline quoted verbatim from the contract, or
     LINT:<check_ds_usage rule>); screenshot evidence is one of that screen's screenshots and the
     file exists; code evidence is path:line inside an existing file; lint and palette reports
     exist; a "seen" finding has screenshot evidence; a screen the user accepted before only gets
     blocker and major findings.

Paths resolve against the review file's directory; code paths against --src when given.

Usage: validate_visual_review.py <review.json> [--src <dir>] [--rules <ux-rules.md>] [--md <out.md>]
Exit code 0 = valid, 1 = invalid, 2 = usage/IO error.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from schema_lite import check_schema

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA = ROOT / "schemas" / "visual-review.schema.json"
DEFAULT_RULES = ROOT / "skills" / "visual-review" / "ux-rules.md"
LINT_RULES = {
    "literal-color", "literal-font", "unknown-token", "row-text-style", "system-color",
    "system-text-style", "literal-spacing", "literal-radius", "fixed-size-in-row",
}
RULE_ROW = re.compile(r"^\|\s*`([A-Z0-9]+(?:-[A-Z0-9]+)+)`\s*\|")
CODE_REF = re.compile(r"^(.+):(\d+)$")
SEVERITY_ORDER = {"blocker": 0, "major": 1, "minor": 2}


def rule_ids(path):
    return {m.group(1) for line in Path(path).read_text().splitlines() if (m := RULE_ROW.match(line))}


def check_semantics(doc, base, src, rules, errors, warnings):
    screens = {s["id"]: s for s in doc["screens"]}
    for group, ids in (("screens", [s["id"] for s in doc["screens"]]), ("findings", [f["id"] for f in doc["findings"]])):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            errors.append(f"{group}: duplicate ids {dupes}")

    guidelines = None
    contract = base / doc["contract"]
    if contract.is_file():
        c = json.loads(contract.read_text())
        guidelines = c.get("guidelines", {}).get("do", []) + c.get("guidelines", {}).get("dont", [])
    else:
        warnings.append(f"contract {doc['contract']} not found; DS-GUIDE quotes not checked")

    for s in doc["screens"]:
        for shot in s["screenshots"]:
            if not (base / shot["file"]).is_file():
                errors.append(f"screen {s['id']}: screenshot {shot['file']} not found")

    for f in doc["findings"]:
        where = f"finding {f['id']}"
        screen = screens.get(f["screen"])
        if screen is None:
            errors.append(f"{where}: unknown screen '{f['screen']}'")

        rule = f["rule"]
        if rule == "DS-GUIDE":
            quote = f.get("guideline")
            if not quote:
                errors.append(f"{where}: DS-GUIDE needs the guideline quoted in 'guideline'")
            elif guidelines is not None and quote not in guidelines:
                errors.append(f"{where}: guideline not found verbatim in the contract: {quote!r}")
        elif rule.startswith("LINT:"):
            if rule[5:] not in LINT_RULES:
                errors.append(f"{where}: unknown check_ds_usage rule '{rule[5:]}'")
        elif rule not in rules:
            errors.append(f"{where}: unknown rule '{rule}'")

        if screen is not None and screen.get("accepted_before") and f["severity"] == "minor":
            errors.append(f"{where}: screen '{screen['id']}' was accepted before; report only blocker or major")

        shots = {s["file"] for s in screen["screenshots"]} if screen else set()
        kinds = set()
        for e in f["evidence"]:
            kinds.add(e["kind"])
            ref = e["ref"]
            if e["kind"] == "screenshot":
                if screen is not None and ref not in shots:
                    errors.append(f"{where}: screenshot {ref} is not one of screen '{screen['id']}''s screenshots")
            elif e["kind"] == "code":
                m = CODE_REF.match(ref)
                if not m:
                    errors.append(f"{where}: code evidence '{ref}' is not path:line")
                    continue
                path = (src or base) / m.group(1)
                if not path.is_file():
                    errors.append(f"{where}: code evidence file {m.group(1)} not found")
                elif not 1 <= int(m.group(2)) <= len(path.read_text(errors="replace").splitlines()):
                    errors.append(f"{where}: code evidence line {m.group(2)} is outside {m.group(1)}")
            elif not (base / ref).is_file():
                errors.append(f"{where}: {e['kind']} report {ref} not found")
        if f["confidence"] == "seen" and "screenshot" not in kinds:
            errors.append(f"{where}: 'seen' needs screenshot evidence; use 'inferred' otherwise")

    if not doc["findings"]:
        warnings.append("no findings; say in not_checked what was not reviewed")


def render_md(doc):
    out = [f"# Visual review: {doc['app']}", "", f"Contract: `{doc['contract']}`", ""]
    counts = {}
    for f in doc["findings"]:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    out.append("Findings: " + (", ".join(f"{counts[s]} {s}" for s in SEVERITY_ORDER if s in counts) or "none"))
    out.append("")
    for s in doc["screens"]:
        findings = sorted((f for f in doc["findings"] if f["screen"] == s["id"]),
                          key=lambda f: (SEVERITY_ORDER[f["severity"]], f["id"]))
        out.append(f"## {s['name']}" + (" (accepted before)" if s.get("accepted_before") else ""))
        out.append("")
        out.append("Screenshots: " + ", ".join(f"`{x['file']}` ({x['variant']})" for x in s["screenshots"]))
        out.append("")
        if not findings:
            out.append("No findings.")
            out.append("")
            continue
        out.append("| Id | Severity | Rule | Observation | Fix | Evidence | Decision |")
        out.append("|---|---|---|---|---|---|---|")
        for f in findings:
            rule = f["rule"] + (f": “{f['guideline']}”" if f.get("guideline") else "")
            evidence = "<br>".join(f"{e['kind']}: `{e['ref']}`" for e in f["evidence"])
            observation = f["observation"] + (" *(inferred)*" if f["confidence"] == "inferred" else "")
            if f.get("siblings"):
                observation += "<br>Also check: " + ", ".join(f"`{x}`" for x in f["siblings"])
            cells = [f["id"], f["severity"], rule, observation, f["suggested_fix"], evidence, f.get("decision", "open")]
            out.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
        out.append("")
    if doc["not_checked"]:
        out.append("## Not checked")
        out.append("")
        out += [f"- {x}" for x in doc["not_checked"]]
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("review")
    ap.add_argument("--src")
    ap.add_argument("--rules", default=str(DEFAULT_RULES))
    ap.add_argument("--md")
    args = ap.parse_args()
    try:
        schema = json.loads(DEFAULT_SCHEMA.read_text())
        doc = json.loads(Path(args.review).read_text())
        rules = rule_ids(args.rules)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    errors, warnings = [], []
    check_schema(doc, schema, "$", errors)
    if not errors:
        check_semantics(doc, Path(args.review).resolve().parent, Path(args.src).resolve() if args.src else None,
                        rules, errors, warnings)

    print(f"{'INVALID' if errors else 'VALID'}: {args.review}")
    for e in errors:
        print(f"  - error: {e}")
    for w in warnings:
        print(f"  - warning: {w}")
    if args.md and not errors:
        Path(args.md).write_text(render_md(doc) + "\n")
        print(f"wrote {args.md}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
