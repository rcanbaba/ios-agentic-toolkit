#!/usr/bin/env python3
"""Reconcile inventory parts written by parallel area agents.

Deterministic step of the feature-inventory skill, run after merge_inventory.py
(it needs coverage.json). Edits the parts in place and logs every change to
<migration-dir>/inventory/reconciliation.json. Idempotent.

What it does:
  0. Normalize: a source_files item "path (note)" whose path exists becomes "path", and the
     note moves to source_file_notes {path: note}. Nothing is dropped.
  1. Attach unreferenced identifiers (api_methods, ws_incoming, ws_outgoing, push_types,
     app_routes) to the features owning their call-site files. A call site is a file
     where one of the field's call_site_patterns matches, excluding the files that
     declare the enumerations. Attachment only happens at call-site files with exactly
     one owning feature, and only when the call-site files belong to at most two
     features in total; otherwise the identifier is reported as "ambiguous" for the
     agent to resolve (or forced with --attach-ambiguous). Identifiers with no call
     site at all are recorded as dead_identifiers, not attached anywhere.
  2. Map dangling depends_on ids: overrides map, then the id with a trailing
     "(area note)" stripped, then a close match (difflib >= 0.85); the rest are
     reported as unresolved_depends_on.
  3. Merge duplicate feature ids across parts (kept in the part whose assigned_paths
     cover most of its files) and the pairs listed in overrides.merge_features. Lists
     are unioned; criticality takes the higher value; the dropped summary is appended
     as "Merged from <id>: ..."; fields the kept feature lacks are copied. A dropped id
     is replaced by the kept id in depends_on, verification/scopes.json and the
     related_features of flow-specs/*.json (re-render those specs afterwards);
     apply_verification.py resolves it in verification files.
  4. Assign or unassign stray files listed in overrides.

Call-site patterns come from the extractor config ("call_site_patterns": {field: [regex
with {name}, and {type} for the declaring enum]}). Defaults match ".name(" for api
methods, "case .name" and "== .name" for incoming messages, ".name" preceded by a word
boundary for outgoing actions and push types, and only route-shaped uses for routes:
"Type.name", "navigate(to: .name", "route: .name", "(.name)". A bare ".name" pattern for
app_routes is refused: route names collide with SwiftUI tokens (.main, .center,
.cancel) and get attached to hundreds of unrelated features.

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
    "ws_incoming": [r"case\s+\.{name}\b", r"==\s*\.{name}\b"],
    "ws_outgoing": [r"\b\.{name}\b"],
    "push_types": [r"\b\.{name}\b"],
    "app_routes": [r"\b{type}\.{name}\b", r"navigate\(to:\s*\.{name}\b", r"route:\s*\.{name}\b", r"\(\.{name}\)"],
}
BARE_ROUTE = re.compile(r"^(\\b)?\\\.\{name\}(\\b)?$")
MAX_OWNERS = 2
CRITICALITY = ["low", "medium", "high", "core"]

LIST_FIELDS = ["user_roles", "entry_points", "screens", "user_actions", "flow", "states_and_edge_cases", "api_methods",
               "ws_incoming", "ws_outgoing", "sdk_usage", "app_routes", "push_types", "settings_flags", "analytics_events",
               "persistence", "localization_keys_sample", "depends_on", "legacy_naming", "known_issues", "source_files"]


def union_into(keep, drop):
    """Merge drop into keep without losing anything."""
    for field in LIST_FIELDS:
        cur = keep.setdefault(field, [])
        for x in drop.get(field, []):
            if x not in cur:
                cur.append(x)
    if CRITICALITY.index(drop["criticality"]) > CRITICALITY.index(keep["criticality"]):
        keep["criticality"] = drop["criticality"]
    if drop["summary"] != keep["summary"]:
        keep["summary"] = f"{keep['summary']} Merged from {drop['id']}: {drop['summary']}"
    notes = keep.setdefault("source_file_notes", {})
    for k, v in drop.get("source_file_notes", {}).items():
        notes.setdefault(k, v)
    if not notes:
        del keep["source_file_notes"]
    for k, v in drop.items():
        if k not in keep and k != "id":
            keep[k] = v
    keep.setdefault("merged_from", []).append(drop["id"])


def normalize_source_files(f, known_files, log):
    """Move "path (note)" annotations into source_file_notes instead of dropping them."""
    fixed = []
    for s in f["source_files"]:
        m = re.match(r"^(\S+?)\s*\((.+)\)\s*$", s)
        if m and s not in known_files and m.group(1) in known_files:
            f.setdefault("source_file_notes", {}).setdefault(m.group(1), m.group(2))
            log.append({"action": "normalize_source_file", "feature": f["id"], "from": s, "to": m.group(1)})
            s = m.group(1)
        if s not in fixed:
            fixed.append(s)
    f["source_files"] = fixed


def rewrite_references(mig, renames, log):
    """Replace merged (dropped) ids in scopes.json and the specs' related_features."""
    if not renames:
        return
    targets = [mig / "verification" / "scopes.json"] + sorted((mig / "flow-specs").glob("*.json"))
    for path in (t for t in targets if t.is_file()):
        doc = load_json(path)
        lists = [v["features"] for v in doc.values()] if path.name == "scopes.json" else [doc.get("related_features", [])]
        changed = False
        for ids in lists:
            new = list(dict.fromkeys(renames.get(i, i) for i in ids))
            if new != ids:
                ids[:] = new
                changed = True
        if changed:
            path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
            log.append({"action": "rewrite_references", "file": str(path.relative_to(mig)), "renames": renames})

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

    # --- 0. normalize annotated source file paths
    known_files = {c["path"] for c in enums["source_files"]["cases"]}
    for part in parts:
        for f in part["features"]:
            normalize_source_files(f, known_files, log)

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
    types = defaultdict(set)
    for entry in enums["keys"].values():
        for c in entry["cases"]:
            if entry.get("type"):
                types[c["name"]].add(entry["type"])
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
            rxs = [re.compile(p.replace("{name}", re.escape(name)).replace("{type}", "(?:" + "|".join(map(re.escape, sorted(types[name]))) + ")"))
                   for p in patterns[field] if "{type}" not in p or types[name]]
            sites = [p for p in files if any(rx.search(text(p)) for rx in rxs)]
            if not sites:
                dead.append(name)
                continue
            attached, ambiguous = [], []
            candidates = {fid for site in sites for fid in owners.get(site, [])}
            if len(candidates) > MAX_OWNERS and not attach_ambiguous:
                report["ambiguous"].append({"field": field, "identifier": name, "candidates": sorted(candidates),
                                            "sites": [{"file": s, "candidates": owners.get(s, [])} for s in sites],
                                            "why": f"call sites belong to {len(candidates)} features"})
                log.append({"action": "attach", "field": field, "identifier": name, "call_sites": sites, "features": []})
                continue
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
    renames = {}
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
        renames = {k: (keep_id if v == drop_id else v) for k, v in renames.items()}
        renames[drop_id] = keep_id
    rewrite_references(mig, renames, log)

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
        bare = [p for p in config.get("call_site_patterns", {}).get("app_routes", []) if BARE_ROUTE.match(p)]
        if bare:
            print(f"error: bare route patterns {bare} match SwiftUI tokens like .main or .center; "
                  "use route-shaped forms (Type.{name}, navigate(to: .{name}, route: .{name}, (.{name}))", file=sys.stderr)
            return 2
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
