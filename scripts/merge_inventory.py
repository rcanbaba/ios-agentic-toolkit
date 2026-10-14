#!/usr/bin/env python3
"""Merge inventory parts into one inventory and report coverage against the baseline.

Deterministic step of the feature-inventory skill, re-run after every change to
the parts (authoring, reconciliation, verification). Reads
  <migration-dir>/inventory/enumerations.json   baseline from extract_enumerations.py
  <migration-dir>/inventory/parts/*.json        one part per area agent
and writes
  <migration-dir>/inventory/inventory.json      all features, each tagged with its area
  <migration-dir>/inventory/coverage.json       per-field coverage, unknown identifiers,
                                                file coverage, dangling depends_on, duplicate
                                                ids, core/high features without a flow,
                                                per-part validation problems

Coverage counts an identifier as referenced when some feature lists it in the
matching field (api_methods, ws_incoming, ws_outgoing, push_types, app_routes; routes
by their route and sub-route tokens only). Informational keys (field null: API paths,
SDKs, notification names, plist keys, ...) get text coverage: a case is
referenced_in_inventory / referenced_in_specs when its name occurs as a whole word in
the features or in flow-specs/*.json; in_specs_only and unreferenced list the names.
Once flow specs exist, core/high features that no spec covers and that have no
spec_note are listed under core_high_without_spec (an error with --coverage-only, the
flow-spec stage's check).

--coverage-only reads the existing inventory.json instead of the parts and writes only
coverage.json: use it to re-measure after flow specs change without rebuilding the
inventory.

Usage: merge_inventory.py [--migration-dir <dir>] [--coverage-only]    (default dir: .migration)
Exit code 0 = merged without problems, 1 = merged with problems (see coverage.json), 2 = usage/IO error.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from validate_inventory_part import (DEFAULT_SCHEMA, IDENTIFIER_FIELDS, known_identifiers, load_json,
                                     route_tokens, source_files, validate_part)


def text_coverage(enums, features, specs):
    """Whole-word occurrences of informational keys' case names in features and specs."""
    inv_text = json.dumps(features, ensure_ascii=False)
    spec_text = json.dumps(specs, ensure_ascii=False)
    inv_words, spec_words = set(re.findall(r"\w+", inv_text)), set(re.findall(r"\w+", spec_text))

    def occurs(name, text, words):
        if re.fullmatch(r"\w+", name):
            return name in words
        return re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text) is not None

    out = {}
    for key, entry in enums.get("keys", {}).items():
        if entry.get("field"):
            continue
        names = sorted({c["name"] for c in entry["cases"]})
        in_inv = {n for n in names if occurs(n, inv_text, inv_words)}
        in_specs = {n for n in names if specs and occurs(n, spec_text, spec_words)}
        out[key] = {
            "known": len(names),
            "referenced_in_inventory": len(in_inv),
            "referenced_in_specs": len(in_specs),
            "in_specs_only": sorted(in_specs - in_inv),
            "unreferenced": sorted(set(names) - in_inv - in_specs),
        }
    return out


def merge(mig, coverage_only=False):
    inv = mig / "inventory"
    enums = load_json(inv / "enumerations.json")
    schema = load_json(DEFAULT_SCHEMA)
    specs = [load_json(p) for p in sorted((mig / "flow-specs").glob("*.json"))]
    if coverage_only:
        existing = load_json(inv / "inventory.json")
        report = coverage(enums, existing["features"], existing.get("unassigned_files", []), [], specs, existing.get("areas", []))
        (inv / "coverage.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
        return report
    part_paths = sorted((inv / "parts").glob("*.json"))
    if not part_paths:
        raise FileNotFoundError(f"no parts in {inv / 'parts'}")

    parts, problems, features = [], [], []
    for p in part_paths:
        part = load_json(p)
        errors, _ = validate_part(part, enums, schema)
        if errors:
            problems.append({"part": p.name, "errors": errors})
        parts.append(part)
        for f in part.get("features", []):
            features.append({**f, "area": part.get("area", p.stem)})

    areas = [{"area": p.get("area"), "title": p.get("title", p.get("area")), "feature_count": len(p.get("features", []))} for p in parts]
    unassigned = [{**u, "area": p.get("area")} for p in parts for u in p.get("unassigned_files", [])]
    report = coverage(enums, features, unassigned, problems, specs, areas)
    inventory = {
        "schema_version": "1.0",
        "feature_count": len(features),
        "areas": areas,
        "features": features,
        "unassigned_files": unassigned,
    }
    (inv / "inventory.json").write_text(json.dumps(inventory, indent=1, ensure_ascii=False) + "\n")
    (inv / "coverage.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    return report


def coverage(enums, features, unassigned, problems, specs, areas):
    by_id = defaultdict(list)
    for f in features:
        by_id[f["id"]].append(f["area"])
    duplicate_ids = {fid: areas for fid, areas in by_id.items() if len(areas) > 1}

    known = known_identifiers(enums)
    coverage, unknown = {}, {}
    for field in IDENTIFIER_FIELDS:
        used = defaultdict(list)
        for f in features:
            for item in f.get(field, []):
                for tok in (route_tokens(item) if field == "app_routes" else [item]):
                    used[tok].append(f["id"])
        k = known[field]
        coverage[field] = {
            "known": len(k),
            "referenced": len(k & used.keys()),
            "unreferenced": sorted(k - used.keys()),
        }
        unknown[field] = sorted(set(used) - k) if k else []

    all_files = source_files(enums)
    claimed = defaultdict(list)
    for f in features:
        for s in f.get("source_files", []):
            claimed[s].append(f["id"])
    for u in unassigned:
        claimed[u["file"]].append("UNASSIGNED")
    files = {
        "total": len(all_files),
        "covered": len(all_files & claimed.keys()),
        "uncovered": sorted(all_files - claimed.keys()),
        "nonexistent_claimed": sorted(set(claimed) - all_files),
        "claimed_by_multiple": {f: ids for f, ids in sorted(claimed.items()) if len([i for i in ids if i != "UNASSIGNED"]) > 1},
    }

    in_specs = {fid for spec in specs for fid in spec.get("related_features", [])}
    report = {
        "schema_version": "1.0",
        "parts": [a["area"] for a in areas],
        "feature_count": len(features),
        "coverage": coverage,
        "text_coverage": text_coverage(enums, features, specs),
        "unknown_identifiers": unknown,
        "files": files,
        "dangling_depends_on": sorted({f"{f['id']} -> {d}" for f in features for d in f.get("depends_on", []) if d not in by_id}),
        "duplicate_ids": duplicate_ids,
        "core_high_without_flow": sorted(f["id"] for f in features if f.get("criticality") in ("core", "high") and not f.get("flow")),
        "core_high_without_spec": sorted(f["id"] for f in features if specs and f.get("criticality") in ("core", "high")
                                         and f["id"] not in in_specs and not f.get("spec_note")),
        "problems": problems,
    }
    return report


def main(argv):
    args = argv[1:]
    mig, coverage_only = Path(".migration"), False
    if "--migration-dir" in args:
        i = args.index("--migration-dir")
        mig = Path(args[i + 1])
        del args[i:i + 2]
    if "--coverage-only" in args:
        coverage_only = True
        args.remove("--coverage-only")
    if args:
        print("usage: merge_inventory.py [--migration-dir <dir>] [--coverage-only]", file=sys.stderr)
        return 2
    try:
        r = merge(mig, coverage_only)
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"parts: {r['parts']}\nfeatures: {r['feature_count']}")
    for field, c in r["coverage"].items():
        print(f"{field:12} {c['referenced']}/{c['known']} referenced, unreferenced {len(c['unreferenced'])}, unknown used {len(r['unknown_identifiers'][field])}")
    for key, c in r["text_coverage"].items():
        print(f"{key:12} {c['referenced_in_inventory']}/{c['known']} in inventory, {c['referenced_in_specs']} in specs, "
              f"specs only {len(c['in_specs_only'])}, unreferenced {len(c['unreferenced'])} (text)")
    fl = r["files"]
    print(f"files        {fl['covered']}/{fl['total']} covered, uncovered {len(fl['uncovered'])}, nonexistent {len(fl['nonexistent_claimed'])}, multi-owner {len(fl['claimed_by_multiple'])}")
    print(f"dangling depends_on: {len(r['dangling_depends_on'])}, duplicate ids: {len(r['duplicate_ids'])}, "
          f"core/high without flow: {len(r['core_high_without_flow'])}, core/high without spec: {len(r['core_high_without_spec'])}, "
          f"invalid parts: {len(r['problems'])}")
    for p in r["problems"]:
        print(f"  {p['part']}:")
        for e in p["errors"][:8]:
            print(f"    - {e}")
    bad = r["problems"] or r["duplicate_ids"] or r["dangling_depends_on"] or any(r["unknown_identifiers"].values())
    bad = bad or (coverage_only and r["core_high_without_spec"])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
