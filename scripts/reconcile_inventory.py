#!/usr/bin/env python3
"""Reconcile inventory parts written by parallel area agents.

Deterministic step of the feature-inventory skill, run after merge_inventory.py
(it needs coverage.json). Edits the parts in place and logs every change to
<migration-dir>/inventory/reconciliation.json. Idempotent.

What it does:
  1. Attach unreferenced identifiers (api_methods, ws_incoming, ws_outgoing, push_types,
     app_routes) to the features owning their call-site files. A call site is a file
     where one of the field's call_site_patterns matches, excluding the files that
     declare the enumerations. Attachment only happens when the file has exactly one
     owning feature; multi-owner files are reported as "ambiguous" for the agent to
     resolve (or forced with --attach-ambiguous). Identifiers with no call site at all
     are recorded as dead_identifiers, not attached anywhere.
  2. Map dangling depends_on ids: overrides map, then the id with a trailing
     "(area note)" stripped, then a close match (difflib >= 0.85); the rest are
     reported as unresolved_depends_on.
  3. Merge duplicate feature ids across parts (kept in the part whose assigned_paths
     cover most of its files) and the pairs listed in overrides.merge_features.
  4. Assign or unassign stray files listed in overrides.

Call-site patterns come from the extractor config ("call_site_patterns": {field: [regex
with {name}]}). Defaults match ".name(" for api methods, "case .name" for incoming
messages, ".name" preceded by a word boundary for outgoing actions and push types,
and "(.name)" / "navigate(to: .name" for routes. Set them to the project's real call
form: matching a bare ".name" attaches sub-routes to hundreds of unrelated features.

Overrides file (optional JSON, written by the agent after reading the report):
  {"depends_on": {"wrong id": "right-id"},
   "merge_features": [["keep-id", "drop-id"]],
   "assign_files": {"path/File.swift": "feature-id"},
   "unassign_files": {"path/File.swift": "reason"}}

Usage: reconcile_inventory.py [--migration-dir <dir>] [--config <enumerations.config.json>]
                              [--overrides <overrides.json>] [--attach-ambiguous]
Exit code 0 = done, 1 = done but ambiguous attachments or unresolved depends_on remain, 2 = usage/IO error.
"""

import difflib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from validate_inventory_part import IDENTIFIER_FIELDS, declaration_files, known_identifiers, load_json, route_tokens

DEFAULT_PATTERNS = {
    "api_methods": [r"\.{name}\("],
    "ws_incoming": [r"case\s+\.{name}\b", r"\.{name}:"],
    "ws_outgoing": [r"\b\.{name}\b"],
    "push_types": [r"\b\.{name}\b"],
    "app_routes": [r"\(\.{name}\b", r"navigate\(to:\s*\.{name}\b", r"route\(\.{name}\b"],
}

LIST_FIELDS = ["user_roles", "entry_points", "screens", "user_actions", "flow", "states_and_edge_cases", "api_methods",
               "ws_incoming", "ws_outgoing", "sdk_usage", "app_routes", "push_types", "settings_flags", "analytics_events",
               "persistence", "localization_keys_sample", "depends_on", "legacy_naming", "known_issues", "source_files"]


def union_into(keep, drop):
    for field in LIST_FIELDS:
        cur = keep.setdefault(field, [])
        for x in drop.get(field, []):
            if x not in cur:
                cur.append(x)
    keep.setdefault("merged_from", []).append(drop["id"])


def part_for_files(parts, files):
    """The part whose assigned_paths cover the most of these files (None if no coverage)."""
    best, best_n = None, 0
    for part in parts:
        paths = [p.rstrip("/") for p in part["assigned_paths"]]
        n = sum(any(f == p or f.startswith(p + "/") for p in paths) for f in files)
        if n > best_n:
            best, best_n = part, n
    return best


def reconcile(mig, config, overrides, attach_ambiguous):
    inv = mig / "inventory"
    enums = load_json(inv / "enumerations.json")
    cov = load_json(inv / "coverage.json")
    root = Path(enums["source_root"])
    if not root.is_absolute():
        root = (inv / root).resolve()
    part_paths = sorted((inv / "parts").glob("*.json"))
    parts = [load_json(p) for p in part_paths]
    log, report = [], {"dead_identifiers": {}, "ambiguous": [], "unresolved_depends_on": []}

    # --- 3a. duplicate ids across parts
    seen = {}
    for part in parts:
        kept = []
        for f in part["features"]:
            if f["id"] in seen:
                other_part, other = seen[f["id"]]
                owner = part_for_files([other_part, part], other["source_files"] + f["source_files"])
                keep, drop, keep_part = (other, f, other_part) if owner is other_part or owner is None else (f, other, part)
                union_into(keep, drop)
                log.append({"action": "merge_duplicate", "id": f["id"], "kept_in": keep_part["area"]})
                if keep is f:
                    other_part["features"].remove(other)
                    seen[f["id"]] = (part, f)
                    kept.append(f)
                continue
            seen[f["id"]] = (part, f)
            kept.append(f)
        part["features"] = kept
    feats = {f["id"]: f for part in parts for f in part["features"]}

    # --- 1. attach unreferenced identifiers by call site
    patterns = {**DEFAULT_PATTERNS, **config.get("call_site_patterns", {})}
    exclude = declaration_files(enums) | set(config.get("exclude_from_call_sites", []))
    files = [c["path"] for c in enums["source_files"]["cases"] if c["path"] not in exclude]
    cache = {}

    def text(path):
        if path not in cache:
            cache[path] = (root / path).read_text(encoding="utf-8", errors="replace") if (root / path).is_file() else ""
        return cache[path]

    owners = defaultdict(list)
    for f in feats.values():
        for s in f["source_files"]:
            owners[s].append(f["id"])
    for field in IDENTIFIER_FIELDS:
        dead = []
        for name in cov["coverage"].get(field, {}).get("unreferenced", []):
            rxs = [re.compile(p.replace("{name}", re.escape(name))) for p in patterns[field]]
            sites = [p for p in files if any(rx.search(text(p)) for rx in rxs)]
            if not sites:
                dead.append(name)
                continue
            attached, ambiguous = [], []
            for site in sites:
                ids = owners.get(site, [])
                if len(ids) == 1 or (ids and attach_ambiguous):
                    for fid in ids:
                        if name not in feats[fid].setdefault(field, []):
                            feats[fid][field].append(name)
                            attached.append(fid)
                elif len(ids) > 1:
                    ambiguous.append({"file": site, "candidates": ids})
            log.append({"action": "attach", "field": field, "identifier": name, "call_sites": sites, "features": sorted(set(attached))})
            if ambiguous and not attached:
                report["ambiguous"].append({"field": field, "identifier": name, "sites": ambiguous})
        report["dead_identifiers"][field] = dead

    # --- 2. dangling depends_on
    dep_map = overrides.get("depends_on", {})
    for f in feats.values():
        new = []
        for d in f.get("depends_on", []):
            if d in feats:
                new.append(d)
                continue
            target = dep_map.get(d)
            if target is None:
                stripped = re.sub(r"\s*\(.*\)\s*$", "", d).strip().lower().replace(" ", "-")
                if stripped in feats:
                    target = stripped
                else:
                    close = difflib.get_close_matches(stripped, list(feats), n=1, cutoff=0.85)
                    target = close[0] if close else None
            log.append({"action": "depends_on", "feature": f["id"], "from": d, "to": target})
            if target and target in feats:
                new.append(target)
            else:
                report["unresolved_depends_on"].append(f"{f['id']} -> {d}")
        f["depends_on"] = list(dict.fromkeys(x for x in new if x != f["id"]))

    # --- 3b. merges requested by the agent (duplicates found during verification)
    for keep_id, drop_id in overrides.get("merge_features", []):
        if keep_id not in feats or drop_id not in feats:
            log.append({"action": "merge_skipped", "keep": keep_id, "drop": drop_id, "why": "already merged or unknown"})
            continue
        union_into(feats[keep_id], feats[drop_id])
        for part in parts:
            part["features"] = [f for f in part["features"] if f["id"] != drop_id]
        del feats[drop_id]
        for f in feats.values():
            f["depends_on"] = list(dict.fromkeys(keep_id if x == drop_id else x for x in f.get("depends_on", []) if x != f["id"]))
        log.append({"action": "merge", "keep": keep_id, "drop": drop_id})

    # --- 4. stray files
    for file, fid in overrides.get("assign_files", {}).items():
        if fid in feats and file not in feats[fid]["source_files"]:
            feats[fid]["source_files"].append(file)
            log.append({"action": "assign_file", "file": file, "feature": fid})
        for part in parts:
            part["unassigned_files"] = [u for u in part["unassigned_files"] if u["file"] != file]
    for file, reason in overrides.get("unassign_files", {}).items():
        part = part_for_files(parts, [file]) or parts[0]
        if not any(u["file"] == file for u in part["unassigned_files"]):
            part["unassigned_files"].append({"file": file, "reason": reason})
            log.append({"action": "unassign_file", "file": file, "part": part["area"]})

    for p, part in zip(part_paths, parts):
        p.write_text(json.dumps(part, indent=1, ensure_ascii=False) + "\n")
    # The log accumulates across runs; only entries that changed a part are kept, so a
    # re-run on an already reconciled inventory leaves the file unchanged.
    previous = load_json(inv / "reconciliation.json").get("log", []) if (inv / "reconciliation.json").is_file() else []
    changes = [e for e in log if e["action"] != "attach" or e["features"]]
    (inv / "reconciliation.json").write_text(json.dumps({**report, "log": previous + changes}, indent=1, ensure_ascii=False) + "\n")
    return report, log


def main(argv):
    args = argv[1:]
    mig, config_path, overrides_path, attach_ambiguous = Path(".migration"), None, None, False
    for flag in ("--migration-dir", "--config", "--overrides"):
        if flag in args:
            i = args.index(flag)
            value = Path(args[i + 1])
            del args[i:i + 2]
            if flag == "--migration-dir":
                mig = value
            elif flag == "--config":
                config_path = value
            else:
                overrides_path = value
    if "--attach-ambiguous" in args:
        attach_ambiguous = True
        args.remove("--attach-ambiguous")
    if args:
        print("usage: reconcile_inventory.py [--migration-dir <dir>] [--config <config.json>] [--overrides <overrides.json>] [--attach-ambiguous]", file=sys.stderr)
        return 2
    config_path = config_path or mig / "enumerations.config.json"
    try:
        config = load_json(config_path) if config_path.is_file() else {}
        overrides = load_json(overrides_path) if overrides_path else {}
        report, log = reconcile(mig, config, overrides, attach_ambiguous)
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"error: {exc} (run merge_inventory.py first?)", file=sys.stderr)
        return 2

    attached = sum(1 for e in log if e["action"] == "attach" and e["features"])
    print(f"log entries: {len(log)}; attached identifiers: {attached}; merged: {sum(1 for e in log if e['action'] in ('merge', 'merge_duplicate'))}")
    for field, dead in report["dead_identifiers"].items():
        if dead:
            print(f"dead {field} (no call site): {dead}")
    for a in report["ambiguous"]:
        print(f"ambiguous {a['field']} {a['identifier']}: " + "; ".join(f"{s['file']} -> {s['candidates']}" for s in a["sites"]))
    for u in report["unresolved_depends_on"]:
        print(f"unresolved depends_on: {u}")
    print("re-run merge_inventory.py to refresh coverage.json")
    return 1 if report["ambiguous"] or report["unresolved_depends_on"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
