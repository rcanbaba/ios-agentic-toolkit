#!/usr/bin/env python3
"""Extract enumerable sources of truth from an app's source as the inventory baseline.

Deterministic first step of the feature-inventory skill. Agents claim features
against this baseline; merge_inventory.py reports what they missed.

Config (JSON, written per project by the skill):
  {
    "source_root": "App",                       relative to the config's directory's parent or absolute
    "file_extensions": [".swift"],
    "exclude_dirs": ["Pods", ".build"],
    "extract": [
      {"key": "api_client_methods", "kind": "methods", "field": "api_methods",
       "file": "Networking/APIClient.swift", "type": "APIClient",
       "path_pattern": "path:\\s*\\.(\\w+)", "include_private": false},
      {"key": "ws_incoming_message_types", "kind": "enum", "field": "ws_incoming",
       "enum": "MessageType", "hint_dir": "Realtime"},
      {"key": "app_routes", "kind": "enum", "field": "app_routes", "enum": "AppRoute", "hint_dir": "Navigation"},
      {"key": "deeplink_actions", "kind": "enum", "field": null, "enum": "DeeplinkAction", "hint_dir": ""},
      {"key": "analytics_events", "kind": "regex", "field": "analytics_events",
       "pattern": "Analytics\\.log\\(\"([^\"]+)\"", "hint_dir": ""}
    ],
    "call_site_patterns": {...}                 used by reconcile_inventory.py, ignored here
  }

  kind=enum     top-level cases of a Swift enum found by brace matching (name + raw value)
  kind=methods  every non-private func declared at the top level of a type's body, with an
                optional capture (path_pattern) searched only inside that method's own text
  kind=regex    distinct first-capture-group values across all source files under hint_dir
  "field" names the inventory feature field this key backs (null = informational only);
  merge_inventory.py and reconcile_inventory.py read it from the output.
  Every source file is always listed under "source_files".

Usage: extract_enumerations.py <config.json> --out <enumerations.json>
Exit code 0 = ok, 1 = a configured enum/type/file was not found, 2 = usage/IO error.
"""

import json
import os
import re
import sys
from pathlib import Path

ACCESS = r"(?:(?:public|internal|open|private|fileprivate|package)(?:\(set\))?\s+)*"


def read(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def brace_body(src, start):
    """Return (body, end) for the brace block that opens at src[start] == '{'."""
    depth, i = 1, start + 1
    while depth and i < len(src):
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        i += 1
    return src[start + 1:i - 1], i


def top_level_lines(body):
    """Yield (line, is_top_level) so nested blocks inside the body are skipped."""
    depth = 0
    for line in body.splitlines():
        yield line, depth == 0
        depth += line.count("{") - line.count("}")


def enum_cases(src, enum_name):
    m = re.search(r"\benum\s+" + re.escape(enum_name) + r"\b[^{]*\{", src)
    if not m:
        return None
    body, _ = brace_body(src, m.end() - 1)
    cases = []
    for line, top in top_level_lines(body):
        if not top:
            continue
        cm = re.match(r"\s*(?:indirect\s+)?case\s+(.+)$", line)
        if not cm:
            continue
        for part in re.split(r",(?![^(]*\))", cm.group(1)):
            name = re.match(r"\s*`?(\w+)`?", part)
            raw = re.search(r'=\s*"([^"]*)"', part)
            if name:
                cases.append({"name": name.group(1), "raw": raw.group(1) if raw else None})
    return cases


def type_methods(src, type_name, path_pattern, include_private):
    """Every func declared at the top level of the type's body (and its extensions in the same file)."""
    pattern = re.compile(r"\b(?:class|struct|actor|enum|extension)\s+" + re.escape(type_name) + r"\b[^{]*\{")
    methods = []
    for m in pattern.finditer(src):
        body, _ = brace_body(src, m.end() - 1)
        starts = []
        offset = 0
        for line, top in top_level_lines(body):
            if top:
                fm = re.match(r"\s*(" + ACCESS + r"(?:static\s+|class\s+)?(?:override\s+)?func\s+(\w+))", line)
                if fm:
                    access = re.match(r"\s*(public|internal|open|private|fileprivate|package)", line)
                    starts.append((offset, fm.group(2), access.group(1) if access else "internal"))
            offset += len(line) + 1
        for i, (start, name, access) in enumerate(starts):
            if access in ("private", "fileprivate") and not include_private:
                continue
            end = starts[i + 1][0] if i + 1 < len(starts) else len(body)
            chunk = body[start:end]  # the method's own text only: never match across function boundaries
            entry = {"name": name, "access": access}
            if path_pattern:
                pm = re.search(path_pattern, chunk)
                entry["path"] = pm.group(1) if pm else None
            methods.append(entry)
    return methods


def walk(root, extensions, exclude_dirs):
    for dp, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in exclude_dirs and not d.startswith("."))
        for f in sorted(files):
            if any(f.endswith(e) for e in extensions):
                yield os.path.relpath(os.path.join(dp, f), root)


def main(argv):
    args = argv[1:]
    out = None
    if "--out" in args:
        i = args.index("--out")
        out = Path(args[i + 1])
        del args[i:i + 2]
    if len(args) != 1 or out is None:
        print("usage: extract_enumerations.py <config.json> --out <enumerations.json>", file=sys.stderr)
        return 2
    config_path = Path(args[0]).resolve()
    try:
        config = json.loads(config_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    root = Path(config["source_root"])
    if not root.is_absolute():
        root = (config_path.parent.parent / root).resolve()
    if not root.is_dir():
        print(f"error: source_root {root} is not a directory", file=sys.stderr)
        return 2
    extensions = config.get("file_extensions", [".swift"])
    exclude_dirs = set(config.get("exclude_dirs", []))
    files = list(walk(root, extensions, exclude_dirs))

    out = out.resolve()
    # Stored relative to the output file so the migration directory can be moved or shared.
    result = {"schema_version": "1.0", "source_root": os.path.relpath(root, out.parent), "keys": {}}
    missing = []
    for spec in config.get("extract", []):
        key, kind, hint = spec["key"], spec["kind"], spec.get("hint_dir", "")
        entry = {"kind": kind, "field": spec.get("field"), "source": None, "count": 0, "cases": []}
        candidates = [f for f in files if f.startswith(hint)] if hint else files
        if kind == "enum":
            for f in candidates:
                cases = enum_cases(read(root / f), spec["enum"])
                if cases is not None:
                    entry.update(source=f, cases=cases)
                    break
            else:
                missing.append(f"{key}: enum {spec['enum']} not found under '{hint or '.'}'")
        elif kind == "methods":
            f = spec["file"]
            if (root / f).is_file():
                cases = type_methods(read(root / f), spec["type"], spec.get("path_pattern"), spec.get("include_private", False))
                entry.update(source=f, cases=cases)
                if not cases:
                    missing.append(f"{key}: no methods found for type {spec['type']} in {f}")
            else:
                missing.append(f"{key}: file {f} not found")
        elif kind == "regex":
            seen = {}
            rx = re.compile(spec["pattern"])
            for f in candidates:
                for m in rx.finditer(read(root / f)):
                    seen.setdefault(m.group(1), f)
            entry.update(source=hint or ".", cases=[{"name": n, "first_seen": f} for n, f in sorted(seen.items())])
        else:
            missing.append(f"{key}: unknown kind {kind}")
        entry["count"] = len(entry["cases"])
        result["keys"][key] = entry

    result["source_files"] = {
        "count": len(files),
        "cases": [{"path": f, "lines": read(root / f).count("\n")} for f in files],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")

    for key, entry in result["keys"].items():
        print(f"{key:34} {entry['count']:5}  {entry['source'] or ''}")
    print(f"{'source_files':34} {len(files):5}")
    for m in missing:
        print(f"  - not found: {m}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
