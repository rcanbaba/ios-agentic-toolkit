#!/usr/bin/env python3
"""Extract enumerable sources of truth from an app's source as the inventory baseline.

Deterministic first step of the feature-inventory skill. Agents claim features
against this baseline; merge_inventory.py reports what they missed.

Config (JSON, written per project by the skill):
  {
    "source_root": "App",                       relative to the config's directory's parent or absolute
    "project_root": ".",                        same base; where Podfile.lock, the .xcodeproj, plists live
    "file_extensions": [".swift"],
    "exclude_dirs": ["Pods", ".build"],
    "extract": [
      {"key": "api_client_methods", "kind": "methods", "field": "api_methods",
       "file": "Networking/APIClient.swift", "type": "APIClient",
       "path_pattern": "path:\\s*\\.(\\w+)", "include_private": false,
       "exclude": ["fetchData", "cancelAll\\w*", "\\w*Multipart\\w*"]},
      {"key": "ws_incoming_message_types", "kind": "enum", "field": "ws_incoming",
       "enum": "MessageType", "hint_dir": "Realtime"},
      {"key": "app_routes", "kind": "enum", "field": "app_routes", "enum": "AppRoute", "hint_dir": "Navigation"},
      {"key": "deeplink_actions", "kind": "enum", "field": null, "enum": "DeeplinkAction", "hint_dir": ""},
      {"key": "analytics_events", "kind": "regex", "field": "analytics_events",
       "pattern": "Analytics\\.log\\(\"([^\"]+)\"", "hint_dir": ""}
    ],
    "call_site_patterns": {...}                 used by reconcile_inventory.py, ignored here
  }

  kind=enum         top-level cases of a Swift enum found by brace matching (name + raw value)
  kind=methods      every non-private func declared at the top level of a type's body (and its
                    extensions in that file). path_pattern is searched in the method's whole
                    text, so multi-line calls match; it never crosses into the next method.
                    "exclude": name regexes for helpers that are not API methods (generic
                    fetch/download helpers, multipart body builders, cancel-all); they are
                    listed under "excluded", not in cases.
  kind=regex        distinct first-capture-group values across all source files under
                    hint_dir. "counts": {label: regex with {name}} adds per-case counts over all
                    source files (e.g. posters/observers of Notification.Name constants).
  kind=conformance  funcs implemented in types/extensions conforming to "protocol"; with
                    "requirements" (globs under project_root, .h or .swift, e.g. a pod's
                    header) also "not_implemented". Selectors are compared as name + argument
                    labels, so NS_SWIFT_NAME renames can show up as both; review the list.
  kind=dependencies third-party SDKs: Podfile.lock pods, Swift packages referenced in
                    *.pbxproj, vendored *.xcframework / *.framework directories
  kind=plist        top-level keys of plist files ("files": globs under project_root:
                    Info.plist, *.entitlements, PrivacyInfo.xcprivacy)
  kind=strings      localization keys from *.strings / *.xcstrings ("files": globs)
  kind=unconsumed   cases of enum key "of" that no file outside its declaration consumes;
                    consumption is a switch arm (grouped cases too), an == / != comparison,
                    or membership in an array literal of cases ([.a, .b]). "consumers" holds
                    the count per case. Use it for parsed-but-unconsumed realtime messages.
  kind=difference   cases of key "of" whose name is not an "attr" value of key "minus"'s
                    cases (e.g. API paths with no client method: of=api_paths,
                    minus=api_client_methods, attr=path)
  Derived kinds (unconsumed, difference) must come after the keys they read.
  "field" names the inventory feature field this key backs (null = informational only);
  merge_inventory.py and reconcile_inventory.py read it from the output.
  Every source file is always listed under "source_files".

Usage: extract_enumerations.py <config.json> --out <enumerations.json>
Exit code 0 = ok, 1 = a configured enum/type/file was not found, 2 = usage/IO error.
"""

import json
import os
import plistlib
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
        for stmt in strip_comment(line).split(";"):
            cm = re.match(r"\s*(?:indirect\s+)?case\s+(.+)$", stmt)
            if cm:
                cases.extend(case_names(cm.group(1)))
    return cases


def strip_comment(line):
    """The line without a trailing // comment; "//" inside a string literal is kept."""
    in_string = False
    for i, ch in enumerate(line):
        if ch == '"' and (i == 0 or line[i - 1] != "\\"):
            in_string = not in_string
        elif not in_string and line.startswith("//", i):
            return line[:i]
    return line


def case_names(decl):
    """Names and raw values of one case declaration ("a = \"x\", b(Int)")."""
    cases = []
    for part in re.split(r",(?![^(]*\))", decl):
        name = re.match(r"\s*`?(\w+)`?", part)
        raw = re.search(r'=\s*"([^"]*)"', part)
        if name:
            cases.append({"name": name.group(1), "raw": raw.group(1) if raw else None})
    return cases


def type_methods(src, type_name, path_pattern, include_private, exclude=()):
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
            if any(re.fullmatch(x, name) for x in exclude):
                methods.append({"name": name, "access": access, "excluded": True})
                continue
            end = starts[i + 1][0] if i + 1 < len(starts) else len(body)
            chunk = body[start:end]  # the method's own text only: never match across function boundaries
            entry = {"name": name, "access": access}
            if path_pattern:
                pm = re.search(path_pattern, chunk)
                entry["path"] = pm.group(1) if pm else None
            methods.append(entry)
    return methods


def balanced(src, start, open_ch="(", close_ch=")"):
    """Text between src[start] == open_ch and its matching close_ch."""
    depth, i = 1, start + 1
    while depth and i < len(src):
        depth += {open_ch: 1, close_ch: -1}.get(src[i], 0)
        i += 1
    return src[start + 1:i - 1]


def swift_selector(name, params):
    """name:label2:label3: for a Swift func, comparable with an Objective-C selector."""
    parts = [x.strip() for x in re.split(r",(?![^(<\[]*[)>\]])", params) if x.strip()]
    if not parts:
        return name
    labels = [re.match(r"(\w+)", x).group(1) for x in parts[1:] if re.match(r"(\w+)", x)]
    return name + ":" + "".join(label + ":" for label in labels)


def protocol_requirements(text, protocol):
    """Selectors declared by a protocol in an Objective-C header or Swift file."""
    m = re.search(r"@protocol\s+" + re.escape(protocol) + r"\b(.*?)@end", text, re.S)
    if m:
        out = []
        for decl in re.findall(r"^\s*[-+]\s*\([^)]*\)\s*([^;]+);", m.group(1), re.M):
            pieces = re.findall(r"(\w+)\s*:", decl)
            out.append("".join(p + ":" for p in pieces) if pieces else decl.split()[0])
        return out
    m = re.search(r"\bprotocol\s+" + re.escape(protocol) + r"\b[^{]*\{", text)
    if not m:
        return []
    body, _ = brace_body(text, m.end() - 1)
    return [swift_selector(fm.group(1), balanced(body, fm.end() - 1))
            for fm in re.finditer(r"\bfunc\s+(\w+)\s*(?:<[^>]*>)?\s*\(", body)]


def implemented_methods(src, protocol):
    rx = re.compile(r"\b(?:class|struct|actor|extension)\s+\w+(?:<[^>]*>)?\s*:[^{]*\b" + re.escape(protocol) + r"\b[^{]*\{")
    out = []
    for m in rx.finditer(src):
        body, _ = brace_body(src, m.end() - 1)
        offset = 0
        for line, top in top_level_lines(body):
            fm = re.match(r"\s*(?:@\w+(?:\([^)]*\))?\s+)*" + ACCESS + r"(?:override\s+)?func\s+(\w+)\s*(?:<[^>]*>)?\s*\(", line) if top else None
            if fm:
                out.append(swift_selector(fm.group(1), balanced(body, offset + fm.end() - 1)))
            offset += len(line) + 1
    return out


CONSUMERS = [
    r"^\s*case\s+([^:\n]+):",                                   # switch arm, grouped cases too
    r"\bcase\s+\.(\w+)\b[^:\n]*=",                                # if case .name = x
    r"[=!]=\s*\.(\w+)\b",                                       # x == .name
    r"\.(\w+)\s*[=!]=",                                          # .name == x
    r"\[\s*(\.\w+(?:\s*,\s*\.\w+)*)\s*,?\s*\]",                    # [.a, .b]
]


def consumption(text, names):
    counts = dict.fromkeys(names, 0)
    for rx in CONSUMERS:
        for m in re.finditer(rx, text, re.M):
            for tok in re.findall(r"\.(\w+)", m.group(0)) if m.group(0).lstrip().startswith(("case", "[")) else [m.group(1)]:
                if tok in counts:
                    counts[tok] += 1
    return counts


def dependencies(project_root):
    found = {}
    for lock in sorted(project_root.glob("**/Podfile.lock")):
        text = read(lock)
        head = text.split("\nDEPENDENCIES:")[0]
        for name, version in re.findall(r"^  - ([^\s/(]+)(?:/\S+)? \(([^)]+)\)", head, re.M):
            found.setdefault(name, {"name": name, "via": "cocoapods", "version": version, "file": str(lock.relative_to(project_root))})
    for pbx in sorted(project_root.glob("**/*.xcodeproj/project.pbxproj")):
        for url in re.findall(r"repositoryURL\s*=\s*\"?([^\";]+)\"?;", read(pbx)):
            name = url.rstrip("/").split("/")[-1].removesuffix(".git")
            found.setdefault(name, {"name": name, "via": "spm", "version": None, "file": str(pbx.relative_to(project_root))})
    for fw in sorted(project_root.glob("**/*.xcframework")) + sorted(project_root.glob("**/*.framework")):
        rel = fw.relative_to(project_root)
        if any(part in ("Pods", "DerivedData", ".build", "build") or part.endswith((".xcframework", ".app")) for part in rel.parts[:-1]):
            continue
        found.setdefault(fw.stem, {"name": fw.stem, "via": "vendored", "version": None, "file": str(rel)})
    return sorted(found.values(), key=lambda c: c["name"].lower())


def globbed(project_root, patterns, include_vendor=False):
    seen = []
    for pattern in patterns:
        for f in sorted(project_root.glob(pattern)):
            parts = f.relative_to(project_root).parts
            # Dependencies and bundles (a vendored framework's own Info.plist) are not the app.
            vendor = any(p in ("Pods", "DerivedData", ".build", "Carthage") or p.endswith((".xcframework", ".framework", ".bundle", ".app"))
                         for p in parts[:-1])
            if f.is_file() and f not in seen and (include_vendor or not vendor):
                seen.append(f)
    return seen


def plist_keys(project_root, patterns):
    cases = []
    for f in globbed(project_root, patterns):
        try:
            data = plistlib.loads(f.read_bytes())
        except Exception:  # noqa: BLE001 - reported as a case so it is visible
            cases.append({"name": "<unreadable>", "file": str(f.relative_to(project_root))})
            continue
        cases += [{"name": k, "file": str(f.relative_to(project_root))} for k in sorted(data)] if isinstance(data, dict) else []
    return cases


def string_keys(project_root, patterns):
    keys = {}
    for f in globbed(project_root, patterns):
        rel = str(f.relative_to(project_root))
        if f.suffix == ".xcstrings":
            names = json.loads(read(f)).get("strings", {}).keys()
        else:
            names = [n.replace('\\"', '"') for n in re.findall(r'^\s*"((?:[^"\\]|\\.)*)"\s*=', read(f), re.M)]
        for n in names:
            keys.setdefault(n, rel)
    return [{"name": n, "first_seen": f} for n, f in sorted(keys.items())]


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
    project_root = Path(config.get("project_root", "."))
    if not project_root.is_absolute():
        project_root = (config_path.parent.parent / project_root).resolve()
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
            entry["type"] = spec["enum"]
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
                found = type_methods(read(root / f), spec["type"], spec.get("path_pattern"),
                                     spec.get("include_private", False), spec.get("exclude", []))
                entry.update(source=f, cases=[c for c in found if not c.get("excluded")])
                excluded = [c["name"] for c in found if c.get("excluded")]
                if excluded:
                    entry["excluded"] = excluded
                if not found:
                    missing.append(f"{key}: no methods found for type {spec['type']} in {f}")
            else:
                missing.append(f"{key}: file {f} not found")
        elif kind == "regex":
            seen = {}
            rx = re.compile(spec["pattern"])
            for f in candidates:
                for m in rx.finditer(read(root / f)):
                    seen.setdefault(m.group(1), f)
            cases = [{"name": n, "first_seen": f} for n, f in sorted(seen.items())]
            if spec.get("counts"):
                texts = [read(root / f) for f in files]
                for c in cases:
                    for label, pattern in spec["counts"].items():
                        crx = re.compile(pattern.replace("{name}", re.escape(c["name"])))
                        c[label] = sum(len(crx.findall(t)) for t in texts)
            entry.update(source=hint or ".", cases=cases)
        elif kind == "conformance":
            impl = {}
            for f in candidates:
                for sel in implemented_methods(read(root / f), spec["protocol"]):
                    impl.setdefault(sel, f)
            entry.update(source=hint or ".", cases=[{"name": n, "file": f} for n, f in sorted(impl.items())])
            if spec.get("requirements"):
                req = []
                for f in globbed(project_root, spec["requirements"], include_vendor=True):
                    req += [r for r in protocol_requirements(read(f), spec["protocol"]) if r not in req]
                if not req:
                    missing.append(f"{key}: protocol {spec['protocol']} not found in {spec['requirements']}")
                entry["not_implemented"] = sorted(set(req) - set(impl))
        elif kind == "dependencies":
            entry.update(source=str(project_root.relative_to(project_root)), cases=dependencies(project_root))
        elif kind == "plist":
            entry.update(source=", ".join(spec["files"]), cases=plist_keys(project_root, spec["files"]))
        elif kind == "strings":
            entry.update(source=", ".join(spec["files"]), cases=string_keys(project_root, spec["files"]))
        elif kind in ("unconsumed", "difference"):
            base = result["keys"].get(spec["of"])
            other = result["keys"].get(spec.get("minus")) if kind == "difference" else True
            if base is None or other is None:
                missing.append(f"{key}: key {spec['of'] if base is None else spec['minus']} must be extracted first")
            elif kind == "unconsumed":
                names = [c["name"] for c in base["cases"]]
                totals = dict.fromkeys(names, 0)
                for f in files:
                    if f != base["source"]:
                        for n, k in consumption(read(root / f), names).items():
                            totals[n] += k
                entry.update(source=base["source"], cases=[{"name": n} for n in names if not totals[n]], consumers=totals)
            else:
                taken = {c.get(spec["attr"]) for c in other["cases"]}
                entry.update(source=base["source"], cases=[c for c in base["cases"] if c["name"] not in taken])
        else:
            missing.append(f"{key}: unknown kind {kind}")
        entry["count"] = len(entry["cases"])
        result["keys"][key] = entry

    result["source_files"] = {
        "count": len(files),
        "cases": [{"path": f, "lines": len(read(root / f).splitlines())} for f in files],
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
