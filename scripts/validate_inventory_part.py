#!/usr/bin/env python3
"""Validate one feature-inventory part against the contract and the deterministic baseline.

Self-check for area agents before hand-off, and the per-part gate inside
merge_inventory.py. Two layers:
  1. Structural: schema_lite subset applied to schemas/feature-inventory-part.schema.json
     (identifier fields are one identifier per item; multi-value strings fail the pattern).
  2. Semantic: identifiers exist in enumerations.json (api methods, realtime messages,
     push types, routes and sub-routes), source_files exist, every source file under
     assigned_paths is claimed or listed unassigned, core/high features have a flow
     whose every step carries file:line evidence inside an existing file, unique ids
     within the part, screens' files are claimed, source_file_notes name claimed files.

Usage: validate_inventory_part.py <part.json> [--enumerations <enumerations.json>] [--schema <schema.json>]
  --enumerations defaults to ../enumerations.json next to the parts/ directory.
Exit code 0 = valid, 1 = invalid, 2 = usage/IO error.
"""

import json
import re
import sys
from pathlib import Path

import evidence
from schema_lite import check_schema

DEFAULT_SCHEMA = Path(__file__).resolve().parent.parent / "schemas" / "feature-inventory-part.schema.json"

IDENTIFIER_FIELDS = ["api_methods", "ws_incoming", "ws_outgoing", "push_types", "app_routes"]
ROUTE_RX = re.compile(r"^(\w+)(?:\(\.(\w+)\))?$")


def load_json(path):
    return json.loads(Path(path).read_text())


def known_identifiers(enums):
    """{inventory field: set of exact names} from the enumerations' field tags."""
    known = {f: set() for f in IDENTIFIER_FIELDS}
    for entry in enums.get("keys", {}).values():
        field = entry.get("field")
        if field in known:
            known[field].update(c["name"] for c in entry["cases"])
    return known


def source_files(enums):
    return {c["path"] for c in enums.get("source_files", {}).get("cases", [])}


def declaration_files(enums):
    """Files that declare the enumerations (never call sites)."""
    return {e["source"] for e in enums.get("keys", {}).values() if e.get("kind") in ("enum", "methods") and e.get("source")}


def route_tokens(item):
    m = ROUTE_RX.match(item)
    return [t for t in m.groups() if t] if m else [item]


def unknown_in(field, items, known):
    out = []
    for item in items:
        tokens = route_tokens(item) if field == "app_routes" else [item]
        out.extend(t for t in tokens if t not in known[field])
    return out


def check_part(part, enums, errors, warnings):
    known = known_identifiers(enums)
    all_files = source_files(enums)
    counts = evidence.line_counts(enums)
    ids = [f["id"] for f in part["features"]]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        errors.append(f"duplicate feature ids within part: {dupes}")

    claimed = set()
    unbacked = set()
    for f in part["features"]:
        fid = f["id"]
        for field in IDENTIFIER_FIELDS:
            items = f.get(field, [])
            if items and not known[field]:
                unbacked.add(field)
                continue
            unknown = unknown_in(field, items, known)
            if unknown:
                errors.append(f"{fid}.{field}: unknown identifiers {sorted(set(unknown))} (use exact names from enumerations.json)")
        if f["criticality"] in ("core", "high"):
            if not f.get("flow"):
                errors.append(f"{fid}: criticality {f['criticality']} requires a non-empty flow")
            for i, step in enumerate(f.get("flow", [])):
                evidence.check(step, counts, f"{fid}.flow[{i}]", errors)
        for note_file in f.get("source_file_notes", {}):
            if note_file not in f["source_files"]:
                errors.append(f"{fid}.source_file_notes: {note_file} is not in source_files")
        for s in f["source_files"]:
            if s not in all_files:
                errors.append(f"{fid}.source_files: {s} does not exist in the source tree")
            claimed.add(s)
        for scr in f.get("screens", []):
            if scr["file"] not in f["source_files"]:
                warnings.append(f"{fid}: screen {scr['name']} file {scr['file']} is not in source_files")
        if fid in f.get("depends_on", []):
            errors.append(f"{fid}: depends_on itself")

    for field in sorted(unbacked):
        warnings.append(f"no enumeration key backs '{field}'; its identifiers were not checked (add one to the extractor config)")

    for u in part["unassigned_files"]:
        if u["file"] not in all_files:
            errors.append(f"unassigned_files: {u['file']} does not exist in the source tree")
        if u["file"] in claimed:
            warnings.append(f"unassigned_files: {u['file']} is also claimed by a feature")
        claimed.add(u["file"])

    assigned = [p.rstrip("/") for p in part["assigned_paths"]]
    in_scope = {f for f in all_files if any(f == p or f.startswith(p + "/") for p in assigned)}
    if not in_scope:
        errors.append(f"assigned_paths {assigned} match no source files")
    uncovered = sorted(in_scope - claimed)
    if uncovered:
        errors.append(f"{len(uncovered)} file(s) under assigned_paths are neither claimed nor unassigned: {uncovered[:15]}{' ...' if len(uncovered) > 15 else ''}")
    outside = sorted(claimed - in_scope)
    if outside:
        warnings.append(f"{len(outside)} claimed file(s) are outside assigned_paths (allowed, reported for reconciliation): {outside[:10]}")


def validate_part(part, enums, schema):
    errors, warnings = [], []
    check_schema(part, schema, "$", errors)
    if not errors:
        check_part(part, enums, errors, warnings)
    return errors, warnings


def find_enumerations(part_path):
    p = Path(part_path).resolve()
    for candidate in (p.parent.parent / "enumerations.json", p.parent / "enumerations.json"):
        if candidate.is_file():
            return candidate
    return None


def main(argv):
    args = argv[1:]
    schema_path, enums_path = DEFAULT_SCHEMA, None
    for flag in ("--schema", "--enumerations"):
        if flag in args:
            i = args.index(flag)
            if flag == "--schema":
                schema_path = Path(args[i + 1])
            else:
                enums_path = Path(args[i + 1])
            del args[i:i + 2]
    if len(args) != 1:
        print("usage: validate_inventory_part.py <part.json> [--enumerations <enumerations.json>] [--schema <schema.json>]", file=sys.stderr)
        return 2
    enums_path = enums_path or find_enumerations(args[0])
    if enums_path is None:
        print("error: enumerations.json not found; pass --enumerations", file=sys.stderr)
        return 2
    try:
        schema, enums, part = load_json(schema_path), load_json(enums_path), load_json(args[0])
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    errors, warnings = validate_part(part, enums, schema)
    print(f"{'INVALID' if errors else 'VALID'}: {args[0]}")
    for e in errors:
        print(f"  - error: {e}")
    for w in warnings:
        print(f"  - warning: {w}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
