#!/usr/bin/env python3
"""Check that every legacy feature from the inventory still exists in the new app.

Deterministic gate at the end of the App Port workflow. The feature inventory
(feature-inventory skill) says, per feature, which legacy files implement it and which
enumerable symbols it uses (API client methods, realtime message types, routes, push types,
localization keys...). This script looks for each of them in the new app's sources:

  files    a legacy source file counts as present when its path_map destination exists, or
           when a file with the same basename exists anywhere in the new sources (ported files
           move between folders but keep their names); entries that are not paths (notes such
           as "Feature/X (other area)") are listed as unchecked_entries
  symbols  per enumeration key, a "declared" regex (the symbol is defined) and/or a "used"
           regex (something calls or reads it), with {name} replaced by the escaped name.
           Declared but never used is reported separately: a ported API method that no screen
           calls is a lost feature that still compiles.

Every enumeration case is checked too, not only those a feature lists, so symbols no feature
claimed are covered. With "legacy_src", each symbol is checked against the legacy sources the
same way first: a symbol that was already unused (or never declared) in the legacy app is
reported as "inherited", not as a gap, so dead legacy code does not hide real losses. Deliberate gaps (deferred features, removed dead code) go into "allow"
with a reason; they are reported as allowed and do not fail the gate.

config.json (paths relative to the config file):
  {
    "legacy_src": "../LegacyApp",                         optional; enables "inherited"
    "legacy_exclude": ["Pods/*"],                          optional
    "new_src": "../NewApp/App",
    "inventory": "inventory/inventory.json",
    "enumerations": "inventory/enumerations.json",          optional
    "path_map": [["Scenes/Features/", "Features/"]],        optional, legacy prefix -> new prefix
    "exclude": ["Pods/*", "*/Generated/*"],                 globs relative to new_src
    "symbols": {
      "api_client_methods": {"attr": "method", "declared": "func\\\\s+{name}\\\\b", "used": "\\\\.{name}\\\\("},
      "app_routes": {"attr": "case", "declared": "case\\\\b[^\\\\n]*\\\\b{name}\\\\b"},
      "localization_keys": {"attr": "key", "used": "\\"{name}\\""}
    },
    "feature_fields": {"api_methods": "api_client_methods", "app_routes": "app_routes",
                       "localization_keys_sample": "localization_keys"},
    "allow": [{"match": "feature:wallet-*", "reason": "deferred to the end of the port"},
              {"match": "api_client_methods:legacyPing", "reason": "dead in the legacy app"},
              {"match": "file:Scenes/Features/Wallet/*", "reason": "deferred"}]
  }

"attr" names the field of an enumeration case that holds the name (cases may also be plain
strings). Feature field values may carry notes ("APP_CHECK_TOKEN (logError)"); the leading
identifier is used. Allow matches are fnmatch globs: "feature:<id>", "file:<legacy path>",
"<enumeration key>:<name>".

Usage: parity_check.py <config.json> [--out <report.json>] [--md <report.md>]
Exit code 0 = no unexplained gap, 1 = gaps remain, 2 = usage/IO error.
"""

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

CRITICALITY_ORDER = {"core": 0, "important": 1, "secondary": 2, "minor": 3}
LEADING_NAME = re.compile(r"[A-Za-z_][\w.\-]*")
# inventory entries are sometimes notes ("Feature/X (other area)"); only real paths are checked
PATH_LIKE = re.compile(r"^[^\s()]+\.\w+$")


def fail(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


def load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as e:
        fail(f"cannot read {path}: {e}")


def case_name(case, attr):
    if isinstance(case, str):
        return case
    if isinstance(case, dict):
        value = case.get(attr)
        return value if isinstance(value, str) else None
    return None


def leading_name(value):
    if not isinstance(value, str):
        return None
    m = LEADING_NAME.match(value.strip())
    return m.group(0) if m else None


class Corpus:
    """All Swift sources of the new app, searched once per symbol."""

    def __init__(self, root, exclude):
        self.root = root
        self.files = []
        for path in sorted(root.rglob("*.swift")):
            rel = path.relative_to(root).as_posix()
            if any(fnmatch.fnmatch(rel, g) for g in exclude):
                continue
            self.files.append(rel)
        self.text = "\n".join((root / f).read_text(errors="replace") for f in self.files)
        # basenames of every file (plists, entitlements, resources too), for the file check
        self.by_basename = {}
        for path in root.rglob("*"):
            if path.is_file():
                rel = path.relative_to(root).as_posix()
                if not any(fnmatch.fnmatch(rel, g) for g in exclude):
                    self.by_basename.setdefault(path.name, []).append(rel)
        self._cache = {}

    def matches(self, template, name):
        if not template:
            return None
        key = (template, name)
        if key not in self._cache:
            # cheap prefilter: the bare name must occur somewhere
            if name not in self.text:
                self._cache[key] = False
            else:
                pattern = template.replace("{name}", re.escape(name))
                self._cache[key] = re.search(pattern, self.text) is not None
        return self._cache[key]


class Allow:
    def __init__(self, rules):
        self.rules = [(r["match"], r.get("reason", "")) for r in rules]

    def reason(self, kind, name):
        target = f"{kind}:{name}"
        for pattern, reason in self.rules:
            if fnmatch.fnmatch(target, pattern):
                return reason or "allowed"
        return None


def symbol_status(spec, name, corpus):
    declared = corpus.matches(spec.get("declared"), name)
    used = corpus.matches(spec.get("used"), name)
    if declared is False and used in (None, False):
        return "missing"
    if declared is None and used is False:
        return "missing"
    if declared and used is False:
        return "declared_unused"
    return "present"


def find_file(legacy_rel, path_map, new_root, corpus):
    for old, new in path_map:
        if legacy_rel.startswith(old):
            mapped = new + legacy_rel[len(old):]
            if (new_root / mapped).is_file():
                return [mapped]
    return corpus.by_basename.get(Path(legacy_rel).name, [])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config")
    ap.add_argument("--out")
    ap.add_argument("--md")
    args = ap.parse_args()

    config_path = Path(args.config).resolve()
    cfg = load_json(config_path)
    base = config_path.parent
    for required in ("new_src", "inventory", "symbols"):
        if required not in cfg:
            fail(f"config is missing '{required}'")

    new_root = (base / cfg["new_src"]).resolve()
    if not new_root.is_dir():
        fail(f"new_src not found: {new_root}")
    inventory = load_json(base / cfg["inventory"])
    features = inventory["features"] if isinstance(inventory, dict) else inventory
    enumerations = load_json(base / cfg["enumerations"]) if cfg.get("enumerations") else {}
    path_map = cfg.get("path_map", [])
    symbols = cfg["symbols"]
    feature_fields = cfg.get("feature_fields", {})
    allow = Allow(cfg.get("allow", []))
    corpus = Corpus(new_root, cfg.get("exclude", []))
    legacy = None
    if cfg.get("legacy_src"):
        legacy_root = (base / cfg["legacy_src"]).resolve()
        if not legacy_root.is_dir():
            fail(f"legacy_src not found: {legacy_root}")
        legacy = Corpus(legacy_root, cfg.get("legacy_exclude", []))

    # every enumeration case
    enum_report = {}
    for key, spec in symbols.items():
        entry = enumerations.get(key)
        if entry is None:
            continue
        cases = entry.get("cases", []) if isinstance(entry, dict) else entry
        names = sorted({n for n in (case_name(c, spec.get("attr", "name")) for c in cases) if n})
        bucket = {"total": len(names), "present": 0, "declared_unused": [], "missing": [], "allowed": [],
                  "inherited": []}
        for name in names:
            reason = allow.reason(key, name)
            status = symbol_status(spec, name, corpus)
            if status == "present":
                bucket["present"] += 1
            elif legacy and symbol_status(spec, name, legacy) != "present":
                bucket["inherited"].append({"name": name, "status": status})
            elif reason:
                bucket["allowed"].append({"name": name, "status": status, "reason": reason})
            else:
                bucket[status].append(name)
        enum_report[key] = bucket

    # per feature
    feature_report = []
    for feature in features:
        fid = feature.get("id", "?")
        feature_reason = allow.reason("feature", fid)
        files = list(feature.get("source_files", []))
        for screen in feature.get("screens", []):
            if isinstance(screen, dict) and screen.get("file"):
                files.append(screen["file"])
        unchecked = sorted({f for f in files if not PATH_LIKE.match(f)})
        files = sorted({f for f in files if PATH_LIKE.match(f)})
        missing_files, allowed_files = [], []
        for legacy_rel in files:
            if find_file(legacy_rel, path_map, new_root, corpus):
                continue
            reason = allow.reason("file", legacy_rel)
            (allowed_files if reason else missing_files).append(legacy_rel)

        missing_symbols, unused_symbols = {}, {}
        for field, key in feature_fields.items():
            spec = symbols.get(key)
            if not spec:
                continue
            for value in feature.get(field, []) or []:
                name = leading_name(value)
                if not name:
                    continue
                status = symbol_status(spec, name, corpus)
                if status == "present" or allow.reason(key, name):
                    continue
                if legacy and symbol_status(spec, name, legacy) != "present":
                    continue
                target = missing_symbols if status == "missing" else unused_symbols
                target.setdefault(field, []).append(name)

        has_gap = missing_files or missing_symbols or unused_symbols
        if feature_reason:
            status = "allowed"
        elif not has_gap:
            status = "ported"
        elif files and len(missing_files) == len(files):
            status = "missing"
        else:
            status = "partial"
        record = {"id": fid, "name": feature.get("name", ""), "criticality": feature.get("criticality", ""),
                  "status": status}
        if feature_reason:
            record["reason"] = feature_reason
        if missing_files:
            record["missing_files"] = missing_files
        if allowed_files:
            record["allowed_files"] = allowed_files
        if unchecked:
            record["unchecked_entries"] = unchecked
        if missing_symbols:
            record["missing_symbols"] = missing_symbols
        if unused_symbols:
            record["declared_unused"] = unused_symbols
        feature_report.append(record)

    feature_report.sort(key=lambda r: (r["status"] == "ported", r["status"] == "allowed",
                                       CRITICALITY_ORDER.get(r["criticality"], 9), r["id"]))
    counts = {}
    for r in feature_report:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    enum_gaps = sum(len(b["missing"]) + len(b["declared_unused"]) for b in enum_report.values())
    gaps = counts.get("partial", 0) + counts.get("missing", 0) + enum_gaps

    report = {
        "new_src": new_root.name,
        "swift_files_scanned": len(corpus.files),
        "summary": {"features": len(feature_report), **counts, "enumeration_gaps": enum_gaps},
        "enumerations": enum_report,
        "features": feature_report,
    }
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    if args.md:
        Path(args.md).write_text(render_md(report))

    s = report["summary"]
    print(f"features: {s['features']}  ported: {s.get('ported', 0)}  partial: {s.get('partial', 0)}  "
          f"missing: {s.get('missing', 0)}  allowed: {s.get('allowed', 0)}")
    for key, b in enum_report.items():
        print(f"  {key}: {b['present']}/{b['total']} present, {len(b['missing'])} missing, "
              f"{len(b['declared_unused'])} declared but unused, {len(b['allowed'])} allowed, "
              f"{len(b['inherited'])} inherited")
    return 1 if gaps else 0


def render_md(report):
    s = report["summary"]
    lines = ["# Parity report", "",
             f"Features: {s['features']} · ported {s.get('ported', 0)} · partial {s.get('partial', 0)} · "
             f"missing {s.get('missing', 0)} · allowed {s.get('allowed', 0)} · "
             f"enumeration gaps {s['enumeration_gaps']}", "",
             "## Enumerations", "", "| Key | Present | Missing | Declared, unused | Allowed | Inherited |", "|---|---|---|---|---|---|"]
    for key, b in report["enumerations"].items():
        lines.append(f"| {key} | {b['present']}/{b['total']} | {len(b['missing'])} | "
                     f"{len(b['declared_unused'])} | {len(b['allowed'])} | {len(b['inherited'])} |")
    for key, b in report["enumerations"].items():
        if b["missing"] or b["declared_unused"]:
            lines += ["", f"### {key}", ""]
            if b["missing"]:
                lines.append("Missing: " + ", ".join(f"`{n}`" for n in b["missing"]))
            if b["declared_unused"]:
                lines.append("Declared, never used: " + ", ".join(f"`{n}`" for n in b["declared_unused"]))
    lines += ["", "## Features with gaps", ""]
    for r in report["features"]:
        if r["status"] not in ("partial", "missing"):
            continue
        lines.append(f"- **{r['id']}** ({r['criticality']}, {r['status']}): {r['name']}")
        for f in r.get("missing_files", []):
            lines.append(f"  - file `{f}`")
        for field, names in r.get("missing_symbols", {}).items():
            lines.append(f"  - {field} missing: " + ", ".join(f"`{n}`" for n in names))
        for field, names in r.get("declared_unused", {}).items():
            lines.append(f"  - {field} declared, never used: " + ", ".join(f"`{n}`" for n in names))
    allowed = [r for r in report["features"] if r["status"] == "allowed"]
    if allowed:
        lines += ["", "## Allowed", ""]
        lines += [f"- {r['id']}: {r.get('reason', '')}" for r in allowed]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
