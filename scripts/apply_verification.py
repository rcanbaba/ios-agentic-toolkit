#!/usr/bin/env python3
"""Validate verification files and apply their patches to the inventory parts.

Deterministic step of the feature-inventory skill. Reads
  <migration-dir>/verification/<scope>.json      one file per verifier / hunter
  <migration-dir>/inventory/parts/*.json         the parts being corrected
and edits the parts in place, logging to <migration-dir>/verification/applied.json.
scopes.json and applied.json in the verification directory are not patch files.

Gate: every verification file must pass schemas/inventory-verification.schema.json
plus these rules, otherwise the whole file is skipped:
  - replace on a list field names the old item in "old" (its exact text or a unique prefix)
  - flow steps (add/replace) carry file:line evidence inside an existing file, in the
    step text itself, so the inventory keeps it
  - source_files values (add/replace) are existing files from enumerations.json, one per
    item; notes about a file belong in source_file_notes, never in the path
  - identifier fields (api_methods, ws_incoming, ws_outgoing, push_types, app_routes)
    take one exact identifier per item, known in enumerations.json
  - screens take screen objects, new_feature takes a full feature object, scalar
    fields (name, summary, criticality, spec_note) take a string and only action=replace

Patch semantics:
  add      append items not already present (never duplicates)
  remove   remove exact items; an item that is not present is reported
  replace  list field: swap the one item equal to "old", or else the one item that starts
           with "old". Zero or several matches: nothing changes and the patch is listed in
           applied.json "skipped" (why=replace_no_unique_match) for manual review. Never
           appends, never changes more than one item, never collapses the list.
           scalar field: set the value
  new_feature  add the feature to the part whose assigned_paths cover its source files,
           tagged verified_addition=<scope>; an existing id is skipped
Known-issue checks with verdict false_positive/unclear annotate the known_issues entry
whose text equals "issue" or uniquely starts with it, in place, as
"[FALSE_POSITIVE per <scope>: <evidence>] ...". No unique match: nothing is annotated and
the check is listed under "annotate_unmatched". Confirmed ones change nothing.

Features merged by reconcile_inventory.py (log action "merge") are resolved to the kept
id, so patches written against a dropped id still land on the right feature.

Each patch has a fingerprint; patches already in applied.json are skipped, so the
script can be re-run after adding verification files. "skipped" and "annotate_unmatched"
are recomputed on every run: they list what is still outstanding.

Usage: apply_verification.py [--migration-dir <dir>] [--dry-run] [--scope <id>]
  --dry-run   validate and report what would change without writing (verifier self-check)
Exit code 0 = applied, 1 = some files invalid or patches skipped, 2 = usage/IO error.
"""

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import evidence
from reconcile_inventory import part_for_files
from schema_lite import check_schema
from validate_inventory_part import DEFAULT_SCHEMA as PART_SCHEMA
from validate_inventory_part import IDENTIFIER_FIELDS, known_identifiers, load_json, source_files, unknown_in

DEFAULT_SCHEMA = Path(__file__).resolve().parent.parent / "schemas" / "inventory-verification.schema.json"
SCALAR_FIELDS = {"name", "summary", "criticality", "spec_note"}


def fingerprint(scope, patch):
    return hashlib.sha1(json.dumps({"scope": scope, **patch}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def check_patches(doc, known, files, counts, part_schema, errors):
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
        if field == "flow" and action in ("add", "replace"):
            for x in items:
                if isinstance(x, str):
                    evidence.check(x, counts, where + ".value", errors)
        if field == "source_files" and action in ("add", "replace"):
            bad = [x for x in items if isinstance(x, str) and x not in files]
            if bad:
                errors.append(f"{where}: not source files from enumerations.json {bad[:3]}; one path per item, "
                              "notes go to source_file_notes")
        if action == "replace":
            if p.get("old") in (None, ""):
                errors.append(f"{where}: replace on a list field requires 'old' (the item's exact text or a unique prefix)")
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


def apply_patch(scope, patch, feats, parts, aliases, rec):
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
    fid = aliases.get(fid, fid)
    if fid != patch["feature_id"]:
        rec["resolved_to"] = fid
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
    i, candidates = unique_match(cur, patch["old"])
    if i is None:
        rec["why"] = "replace_no_unique_match"
        rec["candidates"] = candidates
        return False
    if cur[i] != patch["old"]:
        rec["matched_prefix"] = cur[i]
    cur[i] = value
    return True


def unique_match(items, old):
    """Index of the one item equal to old, else of the one string item starting with it.

    Returns (index, 0) or (None, number of candidates)."""
    exact = [i for i, x in enumerate(items) if x == old]
    if len(exact) == 1:
        return exact[0], 0
    if exact or not isinstance(old, str) or not old.strip():
        return None, len(exact)
    prefixed = [i for i, x in enumerate(items) if isinstance(x, str) and x.startswith(old.strip())]
    return (prefixed[0], 0) if len(prefixed) == 1 else (None, len(prefixed))


def annotate_known_issue(check, feats, scope):
    """Annotated issue text, or None when no unique known_issues entry matches."""
    f = feats.get(check["feature_id"])
    if not f:
        return None
    issues = f.get("known_issues", [])
    i, _ = unique_match([x for x in issues], check["issue"].strip())
    if i is None or issues[i].startswith("["):
        return None
    issues[i] = f"[{check['verdict'].upper()} per {scope}: {check['evidence']}] {issues[i]}"
    return issues[i]


def merged_ids(inv):
    """{dropped id: kept id} from reconcile_inventory.py's log, chains resolved."""
    rec = inv / "reconciliation.json"
    pairs = {e["drop"]: e["keep"] for e in load_json(rec).get("log", []) if e["action"] == "merge"} if rec.is_file() else {}
    resolved = {}
    for drop in pairs:
        keep, seen = pairs[drop], {drop}
        while keep in pairs and keep not in seen:
            seen.add(keep)
            keep = pairs[keep]
        resolved[drop] = keep
    return resolved


def run(mig, dry_run, only_scope):
    inv, ver = mig / "inventory", mig / "verification"
    schema, part_schema = load_json(DEFAULT_SCHEMA), load_json(PART_SCHEMA)
    enums = load_json(inv / "enumerations.json")
    known = known_identifiers(enums)
    files = source_files(enums)
    aliases = merged_ids(inv)
    part_paths = sorted((inv / "parts").glob("*.json"))
    parts = [load_json(p) for p in part_paths]
    feats = {f["id"]: f for part in parts for f in part["features"]}
    applied_path = ver / "applied.json"
    state = load_json(applied_path) if applied_path.is_file() else {"applied": [], "known_issue_checks": []}
    done = {a["fingerprint"] for a in state["applied"] + state["known_issue_checks"]}
    applied, skipped, checks, unmatched, invalid = [], [], [], [], []

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
            check_patches(doc, known, files, evidence.line_counts(enums), part_schema, errors)
        if errors:
            invalid.append({"file": vp.name, "errors": errors})
            continue
        for patch in doc["patches"]:
            fp = fingerprint(scope, patch)
            if fp in done:
                continue
            rec = {"scope": scope, "fingerprint": fp, **{k: v for k, v in patch.items() if k != "value"},
                   "value_preview": json.dumps(patch["value"], ensure_ascii=False)[:160]}
            (applied if apply_patch(scope, patch, feats, parts, aliases, rec) else skipped).append(rec)
        for check in doc["known_issue_checks"]:
            fp = fingerprint(scope, check)
            if fp in done:
                continue
            rec = {"scope": scope, "fingerprint": fp, **check}
            if check["verdict"] != "confirmed":
                check = {**check, "feature_id": aliases.get(check["feature_id"], check["feature_id"])}
                rec["annotated"] = annotate_known_issue(check, feats, scope)
                if rec["annotated"] is None:
                    unmatched.append(rec)
                    continue
            checks.append(rec)

    if not dry_run:
        for p, part in zip(part_paths, parts):
            p.write_text(json.dumps(part, indent=1, ensure_ascii=False) + "\n")
        state["applied"].extend(applied)
        state["known_issue_checks"].extend(checks)
        state["skipped"] = skipped
        state["annotate_unmatched"] = unmatched
        state["invalid_files"] = invalid
        applied_path.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n")
    return applied, skipped, checks, unmatched, invalid


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
        applied, skipped, checks, unmatched, invalid = run(mig, dry_run, only_scope)
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    mode = "DRY RUN: " if dry_run else ""
    print(f"{mode}applied {len(applied)} {dict(Counter(a['field'] for a in applied))}")
    for a in (a for a in applied if a.get("not_found")):
        print(f"  check: {a['scope']} {a['feature_id']}.{a['field']}: remove did not find {a['not_found']}")
    print(f"{mode}skipped {len(skipped)} {dict(Counter(s['why'] for s in skipped))}")
    for s in (s for s in skipped if s["why"] == "replace_no_unique_match"):
        print(f"  review: {s['scope']} {s['feature_id']}.{s['field']}: old {s['old']!r:.80} matched {s['candidates']} items")
    print(f"{mode}known issue checks {dict(Counter(c['verdict'] for c in checks))}, "
          f"annotated {sum(1 for c in checks if c.get('annotated'))}, unmatched {len(unmatched)}")
    for u in unmatched:
        print(f"  review: {u['scope']} {u['feature_id']}: no unique known_issues entry starts with {u['issue']!r:.80}")
    for inv_file in invalid:
        print(f"INVALID (not applied): {inv_file['file']}")
        for e in inv_file["errors"][:10]:
            print(f"  - {e}")
    if not dry_run:
        print("re-run merge_inventory.py to refresh coverage.json")
    return 1 if invalid or skipped or unmatched else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
