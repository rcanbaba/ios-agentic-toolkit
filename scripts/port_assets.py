#!/usr/bin/env python3
"""Plan (and optionally apply) copying the legacy asset-catalog entries that ported code uses.

Deterministic step of the port-code skill. Ported code refers to assets in two ways:
generated symbols (`Image(.chatSend)`, `ImageResource.chatSend`, `Color(.brandPrimary)`) and
string names (`Image("chat-send")`, `UIImage(named:)`, `Color("brand-primary")`). The compiler
reports missing generated symbols as `type 'ImageResource' has no member 'chatSend'`; string
names fail only at run time. This script indexes the legacy catalogs under both the set name
and the symbol Xcode generates for it, then copies the sets the target needs into one
catalog folder (for example `Assets.xcassets/Legacy`, removed when the UI is rebuilt).

Generated symbol rule (Xcode): split the set name on non-alphanumerics, lowerCamelCase the
parts, drop a trailing "Image" (image sets) or "Color" (color sets), and prefix "_" when the
result starts with a digit (`1x-boost` -> `_1XBoost`).

Never copied: AccentColor and app icons (the new app owns them; a legacy AccentColor silently
recolors every default control) and sets whose name already exists in any target catalog.
Wanted names come from the build log (asset members) and, with --scan, from asset call forms
in the target sources; a scanned name counts only when a legacy set has that name, so
`Image(.init(...))` or an SF Symbol never matches.

Usage:
  port_assets.py --legacy-catalog <dir.xcassets> [--legacy-catalog ...] --target-src <dir>
                 --into <dir inside a target .xcassets> [--errors <build.log>] [--scan]
                 [--apply] [--out <report.json>]
Exit code 0 = every asset member from the build log was found, 1 = some were not,
2 = usage/IO error. Without --apply nothing is written except --out.
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

SET_SUFFIXES = (".imageset", ".colorset", ".dataset", ".symbolset")
NEVER_COPY = {"AccentColor.colorset"}
ASSET_MEMBER = re.compile(r"type '(?:DeveloperToolsSupport\.)?(?:ImageResource|ColorResource)' has no member '(\w+)'")
SYMBOL_FORMS = [
    re.compile(r"\b(?:Image|UIImage|Color|UIColor)\(\s*(?:resource:\s*)?\.(\w+)\s*\)"),
    re.compile(r"\b(?:ImageResource|ColorResource)\.(\w+)"),
]
STRING_FORMS = [
    re.compile(r"\b(?:Image|Color)\(\s*\"([^\"]+)\""),
    re.compile(r"\b(?:UIImage|UIColor)\(\s*named:\s*\"([^\"]+)\""),
]


def generated_symbol(set_dir_name):
    base, kind = set_dir_name.rsplit(".", 1)
    parts = [p for p in re.split(r"[^0-9A-Za-z]+", base) if p]
    if not parts:
        return None
    symbol = parts[0][:1].lower() + parts[0][1:] + "".join(p[:1].upper() + p[1:] for p in parts[1:])
    suffix = {"imageset": "Image", "colorset": "Color"}.get(kind)
    if suffix and symbol.endswith(suffix) and len(symbol) > len(suffix):
        symbol = symbol[: -len(suffix)]
    if symbol[:1].isdigit():
        symbol = "_" + symbol[:1] + symbol[1:2].upper() + symbol[2:]
    return symbol


def asset_sets(catalog):
    for p in sorted(catalog.rglob("*")):
        if p.is_dir() and p.name.endswith(SET_SUFFIXES):
            yield p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--legacy-catalog", action="append", required=True)
    ap.add_argument("--target-src", required=True)
    ap.add_argument("--into", required=True)
    ap.add_argument("--errors")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()

    target_src, into = Path(args.target_src), Path(args.into)
    catalogs = [Path(c) for c in args.legacy_catalog]
    if not target_src.is_dir() or not all(c.is_dir() for c in catalogs):
        print("--target-src and every --legacy-catalog must be directories", file=sys.stderr)
        return 2

    by_symbol, by_name, skipped = {}, {}, []
    for catalog in catalogs:
        for s in asset_sets(catalog):
            if s.name in NEVER_COPY or s.name.endswith(".appiconset"):
                skipped.append(s.name)
                continue
            by_name.setdefault(s.name.rsplit(".", 1)[0], s)
            sym = generated_symbol(s.name)
            if sym:
                by_symbol.setdefault(sym, s)

    existing = {s.name.rsplit(".", 1)[0] for c in target_src.rglob("*.xcassets") for s in asset_sets(c)}

    from_errors = set()
    if args.errors:
        for line in Path(args.errors).read_text(errors="ignore").splitlines():
            if m := ASSET_MEMBER.search(line):
                from_errors.add(m.group(1))

    scanned_symbols, scanned_names = set(), set()
    if args.scan:
        for f in sorted(target_src.rglob("*.swift")):
            text = f.read_text(errors="ignore")
            for form in SYMBOL_FORMS:
                scanned_symbols.update(n for n in form.findall(text) if n in by_symbol)
            for form in STRING_FORMS:
                scanned_names.update(n for n in form.findall(text) if n in by_name)

    wanted = {}
    for sym in sorted(from_errors | scanned_symbols):
        if sym in by_symbol:
            wanted[by_symbol[sym]] = sym
    for name in sorted(scanned_names):
        wanted.setdefault(by_name[name], name)

    plan, present = [], []
    for src, ref in sorted(wanted.items(), key=lambda kv: kv[0].name):
        if src.name.rsplit(".", 1)[0] in existing:
            present.append(src.name)
            continue
        plan.append({"reference": ref, "set": src.name, "from": str(src)})
    not_found = sorted(n for n in from_errors if n not in by_symbol)

    copied = []
    if args.apply and plan:
        into.mkdir(parents=True, exist_ok=True)
        contents = into / "Contents.json"
        if not contents.exists() and not into.name.endswith(".xcassets"):
            contents.write_text(json.dumps({"info": {"author": "xcode", "version": 1},
                                            "properties": {"provides-namespace": False}}, indent=2) + "\n")
        for item in plan:
            dst = into / item["set"]
            if not dst.exists():
                shutil.copytree(item["from"], dst)
                copied.append(item["set"])

    report = {
        "legacy_sets_indexed": len(by_name),
        "never_copied": sorted(set(skipped)),
        "plan": plan,
        "applied": args.apply,
        "copied": copied,
        "already_in_target": present,
        "not_found": not_found,
    }
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(text)
    else:
        sys.stdout.write(text)
    print(f"plan {len(plan)} · copied {len(copied)} · already in target {len(present)} · "
          f"not found {len(not_found)}", file=sys.stderr)
    return 1 if not_found else 0


if __name__ == "__main__":
    sys.exit(main())
