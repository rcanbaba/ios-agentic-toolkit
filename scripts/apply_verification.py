#!/usr/bin/env python3
"""Validate verification files and apply their patches to the inventory parts.

Deterministic step of the feature-inventory skill. Reads
  <migration-dir>/verification/<scope>.json      one file per verifier / hunter
  <migration-dir>/inventory/parts/*.json         the parts being corrected
and edits the parts in place, logging to <migration-dir>/verification/applied.json.
scopes.json and applied.json in the verification directory are not patch files.

Gate: every verification file must pass schemas/inventory-verification.schema.json
plus these rules, otherwise the whole file is skipped:
  - replace on a list field names the exact old item in "old"
  - identifier fields (api_methods, ws_incoming, ws_outgoing, push_types, app_routes)
    take one exact identifier per item, known in enumerations.json
  - screens take screen objects, new_feature takes a full feature object, scalar
    fields (name, summary, criticality) take a string and only action=replace

Patch semantics:
  add      append items not already present (never duplicates)
  remove   remove exact items; an item that is not present is reported
  replace  list field: swap the item equal to "old" (or the most similar one, ratio >= 0.6,
           reported as "matched"); when nothing matches, the value is appended and the patch
           flagged "appended_instead_of_replace". The list is never collapsed.
           scalar field: set the value
  new_feature  add the feature to the part whose assigned_paths cover its source files,
           tagged verified_addition=<scope>; an existing id is skipped
Known-issue checks with verdict false_positive/unclear annotate the matching known_issues
entry in place as "[FALSE_POSITIVE per <scope>: <evidence>] ...". Confirmed ones change nothing.

Each patch has a fingerprint; patches already in applied.json are skipped, so the
script can be re-run after adding verification files.

Usage: apply_verification.py [--migration-dir <dir>] [--dry-run] [--scope <id>]
  --dry-run   validate and report what would change without writing (verifier self-check)
Exit code 0 = applied, 1 = some files invalid or patches skipped, 2 = usage/IO error.
"""

import difflib
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from reconcile_inventory import part_for_files
from schema_lite import check_schema
from validate_inventory_part import DEFAULT_SCHEMA as PART_SCHEMA
from validate_inventory_part import IDENTIFIER_FIELDS, known_identifiers, load_json, unknown_in

DEFAULT_SCHEMA = Path(__file__).resolve().parent.parent / "schemas" / "inventory-verification.schema.json"
SCALAR_FIELDS = {"name", "summary", "criticality"}
SIMILARITY = 0.6


def fingerprint(scope, patch):
    return hashlib.sha1(json.dumps({"scope": scope, **patch}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def check_patches(doc, known, part_schema, errors):
    item_schema = part_schema["properties"]["features"]["items"]
    for i, p in enumerate(doc["patches"]):
        where = f"patches[{i}] ({p['feature_id']}.{p['field']})"
        field, action, value = p["field"], p["action"], p["value"]
        if field == "new_feature":
            if action != "add" or not isinstance(value, dict):
                errors.append(f"{where}: new_feature requires action=add and a feature object")
                continue
            sub = []
            check_schema(value, item_schema, where + ".value", sub)
            errors.extend(sub)
            if isinstance(value, dict) and value.get("id") != p["feature_id"]:
                errors.append(f"{where}: feature_id must equal value.id")
            continue
        if field in SCALAR_FIELDS:
            if action != "replace" or not isinstance(value, str):
                errors.append(f"{where}: scalar field takes action=replace with a string value")
            if field == "criticality" and value not in ("core", "high", "medium", "low"):
                errors.append(f"{where}: invalid criticality {value!r}")
            continue
        items = value if isinstance(value, list) else [value]
        if field == "screens":
            if not all(isinstance(x, dict) and x.get("name") and x.get("file") for x in items):
                errors.append(f"{where}: screens take objects with name and file")
        elif not all(isinstance(x, str) and x.strip() for x in items):
            errors.append(f"{where}: list field takes a string or a list of strings")
        else:
            # "[field] text" (seen in a real run) or "field: text" for a real feature field;
            # flow steps like "open: ..." stay valid.
            prefixed = [x for x in items if re.match(r"^\[\w+\]\s", x)
                        or ((m := re.match(r"^(\w+)\s*:", x)) and m.group(1) in item_schema["properties"])]
            if prefixed:
                errors.append(f"{where}: value looks like another field encoded as text {prefixed[:2]}; use that field name instead")
        if action == "replace":
            if p.get("old") in (None, ""):
                errors.append(f"{where}: replace on a list field requires 'old' (the exact item being replaced)")
            if isinstance(value, list):
                errors.append(f"{where}: replace takes exactly one value; use add/remove for several items")
        if field in IDENTIFIER_FIELDS and all(isinstance(x, str) for x in items):
            item_pattern = item_schema["properties"][field]["items"]
            for x in items:
                sub = []
                check_schema(x, item_pattern, where + ".value", sub)
                errors.extend(sub)
            if known[field]:
                unknown = unknown_in(field, [x for x in items if isinstance(x, str)], known)
                if unknown:
                    errors.append(f"{where}: unknown identifiers {sorted(set(unknown))}")
    missing_new = len(doc["missing_features"]) - sum(1 for p in doc["patches"] if p["field"] == "new_feature")
    if missing_new > 0:
        errors.append(f"missing_features lists {missing_new} feature(s) without a new_feature patch")


def apply_patch(scope, patch, feats, parts, rec):
    fid, field, action, value = patch["feature_id"], patch["field"], patch["action"], patch["value"]
    if field == "new_feature":
        if fid in feats:
            rec["why"] = "id exists"
            return False
        feature = {**value, "verified_addition": scope}
        part = part_for_files(parts, feature["source_files"]) or parts[0]
        part["features"].append(feature)
        feats[fid] = feature
        rec["part"] = part["area"]
        return True
    if fid not in feats:
        rec["why"] = "unknown feature"
        return False
    f = feats[fid]
    if field in SCALAR_FIELDS:
        rec["replaced"] = f.get(field)
        f[field] = value
        return True
    cur = f.setdefault(field, [])
    items = value if isinstance(value, list) else [value]
    if action == "add":
        added = [x for x in items if x not in cur]
        cur.extend(added)
        rec["added"] = len(added)
        return True
    if action == "remove":
        missing = [x for x in items if x not in cur]
        f[field] = [x for x in cur if x not in items]
        if missing:
            rec["not_found"] = missing
        return True
    old = patch["old"]
    if old in cur:
        cur[cur.index(old)] = value
        return True
    scores = [difflib.SequenceMatcher(None, str(x)[:300], str(old)[:300]).ratio() for x in cur]
    if scores and max(scores) >= SIMILARITY:
        i = scores.index(max(scores))
        rec["matched"] = cur[i]
        cur[i] = value
        return True
    if value not in cur:
        cur.append(value)
    rec["appended_instead_of_replace"] = True
    return True


def annotate_known_issue(check, feats, scope):
    f = feats.get(check["feature_id"])
    if not f or check["verdict"] == "confirmed":
        return None
    key = check["issue"].strip()
    for i, issue in enumerate(f.get("known_issues", [])):
        if issue.startswith("["):
            continue
        if issue.startswith(key[:40]) or key[:40] in issue or difflib.SequenceMatcher(None, issue[:200], key[:200]).ratio() >= SIMILARITY:
            f["known_issues"][i] = f"[{check['verdict'].upper()} per {scope}: {check['evidence']}] {issue}"
            return issue
    return None


def run(mig, dry_run, only_scope):
    inv, ver = mig / "inventory", mig / "verification"
    schema, part_schema = load_json(DEFAULT_SCHEMA), load_json(PART_SCHEMA)
    enums = load_json(inv / "enumerations.json")
    known = known_identifiers(enums)
    part_paths = sorted((inv / "parts").glob("*.json"))
    parts = [load_json(p) for p in part_paths]
    feats = {f["id"]: f for part in parts for f in part["features"]}
    applied_path = ver / "applied.json"
    state = load_json(applied_path) if applied_path.is_file() else {"applied": [], "skipped": [], "known_issue_checks": [], "invalid_files": []}
    done = {a["fingerprint"] for a in state["applied"] + state["known_issue_checks"]}
    applied, skipped, checks, invalid = [], [], [], []

    for vp in sorted(ver.glob("*.json")):
        if vp.name in ("scopes.json", "applied.json"):
            continue
        doc = load_json(vp)
        scope = doc.get("scope", vp.stem)
        if only_scope and scope != only_scope:
            continue
        errors = []
        check_schema(doc, schema, "$", errors)
        if not errors:
            check_patches(doc, known, part_schema, errors)
        if errors:
            invalid.append({"file": vp.name, "errors": errors})
            continue
        for patch in doc["patches"]:
            fp = fingerprint(scope, patch)
            if fp in done:
                continue
            rec = {"scope": scope, "fingerprint": fp, **{k: v for k, v in patch.items() if k != "value"},
                   "value_preview": json.dumps(patch["value"], ensure_ascii=False)[:160]}
            (applied if apply_patch(scope, patch, feats, parts, rec) else skipped).append(rec)
        for check in doc["known_issue_checks"]:
            fp = fingerprint(scope, check)
            if fp in done:
                continue
            rec = {"scope": scope, "fingerprint": fp, **check, "annotated": annotate_known_issue(check, feats, scope)}
            checks.append(rec)

    if not dry_run:
        for p, part in zip(part_paths, parts):
            p.write_text(json.dumps(part, indent=1, ensure_ascii=False) + "\n")
        state["applied"].extend(applied)
        state["skipped"].extend(skipped)
        state["known_issue_checks"].extend(checks)
        state["invalid_files"] = invalid
        applied_path.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n")
    return applied, skipped, checks, invalid


def main(argv):
    args = argv[1:]
    mig, dry_run, only_scope = Path(".migration"), False, None
    if "--migration-dir" in args:
        i = args.index("--migration-dir")
        mig = Path(args[i + 1])
        del args[i:i + 2]
    if "--scope" in args:
        i = args.index("--scope")
        only_scope = args[i + 1]
        del args[i:i + 2]
    if "--dry-run" in args:
        dry_run = True
        args.remove("--dry-run")
    if args:
        print("usage: apply_verification.py [--migration-dir <dir>] [--dry-run] [--scope <id>]", file=sys.stderr)
        return 2
    try:
        applied, skipped, checks, invalid = run(mig, dry_run, only_scope)
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    mode = "DRY RUN: " if dry_run else ""
    print(f"{mode}applied {len(applied)} {dict(Counter(a['field'] for a in applied))}")
    flagged = [a for a in applied if a.get("appended_instead_of_replace") or a.get("matched") or a.get("not_found")]
    for a in flagged:
        note = "appended instead of replace" if a.get("appended_instead_of_replace") else ("matched " + repr(a.get("matched"))[:80] if a.get("matched") else f"not found {a.get('not_found')}")
        print(f"  check: {a['scope']} {a['feature_id']}.{a['field']}: {note}")
    print(f"{mode}skipped {len(skipped)} {dict(Counter(s['why'] for s in skipped))}")
    print(f"{mode}known issue checks {dict(Counter(c['verdict'] for c in checks))}, annotated {sum(1 for c in checks if c['annotated'])}")
    for inv_file in invalid:
        print(f"INVALID (not applied): {inv_file['file']}")
        for e in inv_file["errors"][:10]:
            print(f"  - {e}")
    if not dry_run:
        print("re-run merge_inventory.py to refresh coverage.json")
    return 1 if invalid or skipped else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
