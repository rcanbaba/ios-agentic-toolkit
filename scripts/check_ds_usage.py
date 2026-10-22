#!/usr/bin/env python3
"""Check SwiftUI files against a design-system contract: tokens only, row-safe text, no row overflow.

Deterministic gate of the ui-implementation workflow, and evidence for visual review. It reads
the contract (design-system.json) for the token names, the spacing scale and each text style's
size and `uses`, then scans Swift files line by line.

Rules (severity):
  literal-color      error    Color(red:/white:/hue:), Color("asset"), Color(hex...), #colorLiteral, UIColor(red:/named:)
  literal-font       error    .font(.system(size: <number>...)), Font.system(size: <number>), .font(.custom(...))
                              on text; sizing an SF Symbol (a modifier chain on Image(...)) is not text
  unknown-token      error    DS.<Group>.<name> or .dsFont(.<style>) that neither the contract nor an
                              `extension DS` / `extension DS.<Group>` in the scanned files declares
  row-text-style     error    in a row file, a style whose `uses` exclude "row"
                     warning  in a row file, a style without `uses` above 20pt
  system-color       warning  Color.red, .foregroundStyle(.blue), ... (system palette instead of tokens)
  system-text-style  warning  .font(.headline), .font(.title2), ... (Apple text styles instead of .dsFont)
  literal-spacing    warning  .padding(12), spacing: 10 (names the token when the value is on the scale)
  literal-radius     warning  cornerRadius: 14
  fixed-size-in-row  warning  .fixedSize() in a row file: the text refuses to shrink and pushes the row
                              past the screen width

A row file is a Swift file whose name matches --row-files (default: ends in Row, Cell or Item,
optionally followed by View). Lines that are comments are skipped. Suppress one finding with
`// ds-lint: allow <rule> <reason>` on the same line or the line above; a reason is required.

Usage: check_ds_usage.py <design-system.json> <file-or-dir>... [--exclude GLOB]... [--row-files REGEX]
                         [--out report.json]
Exit code 0 = no errors (warnings allowed), 1 = errors, 2 = usage/IO error.
"""

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

ROW_MAX_SIZE = 20
DEFAULT_ROW_FILES = r"(Row|Cell|Item)(View)?\.swift$"

GROUPS = {
    "Colors": "colors",
    "Spacing": "spacing",
    "Radius": "radii",
    "Shapes": "radii",
    "Shadows": "shadows",
    "Borders": "borders",
    "Gradients": "gradients",
    "Overlays": "overlays",
    "Components": "components",
}

SYSTEM_COLORS = r"(red|orange|yellow|green|mint|teal|cyan|blue|indigo|purple|pink|brown|gray|grey|black|white)"
APPLE_TEXT_STYLES = r"(largeTitle|title|title2|title3|headline|subheadline|body|callout|footnote|caption|caption2)"
NUMBER = r"(\d+(?:\.\d+)?)"

LINE_RULES = [
    ("literal-color", "error", re.compile(
        r"Color\(\s*(red|white|hue)\s*:|Color\(\s*\"|Color\(\s*hex|#colorLiteral|UIColor\(\s*(red|named|hex)\s*:"),
     "literal color; use a DS.Colors token"),
    ("literal-font", "error", re.compile(
        r"\.font\(\s*\.system\(\s*size:\s*\d|Font\.system\(\s*size:\s*\d|\.font\(\s*\.custom\("),
     "literal font; use .dsFont(.<style>)"),
    ("system-color", "warning", re.compile(
        r"Color\." + SYSTEM_COLORS + r"\b|\.(foregroundStyle|foregroundColor|background|fill|tint|stroke|strokeBorder)\(\s*\."
        + SYSTEM_COLORS + r"\b"),
     "system color; use a DS.Colors token"),
    ("system-text-style", "warning", re.compile(r"\.font\(\s*\.?" + APPLE_TEXT_STYLES + r"\b(?!\s*:)"),
     "Apple text style; use .dsFont(.<style>)"),
    ("literal-radius", "warning", re.compile(r"cornerRadius:\s*" + NUMBER),
     "literal corner radius; use DS.Radius / DS.Shapes"),
]

PADDING = re.compile(r"\.padding\(\s*(?:\.[A-Za-z]+\s*,\s*|\[[^\]]*\]\s*,\s*)?" + NUMBER + r"\s*\)")
STACK_SPACING = re.compile(r"\bspacing:\s*" + NUMBER + r"\b")
DS_TOKEN = re.compile(r"\bDS\.(" + "|".join(GROUPS) + r")\.([A-Za-z_][A-Za-z0-9_]*)")
DS_FONT = re.compile(r"\.dsFont\(\s*\.([A-Za-z_][A-Za-z0-9_]*)")
FIXED_SIZE = re.compile(r"\.fixedSize\(\s*(\)|horizontal:\s*true)")
ALLOW = re.compile(r"//\s*ds-lint:\s*allow\s+([a-z-]+)\s+\S")
EXTENSION_DS = re.compile(r"^\s*extension\s+DS\s*\{")
EXTENSION_GROUP = re.compile(r"^\s*extension\s+DS\.(\w+)\s*\{")
ENUM = re.compile(r"^\s*(?:public\s+|internal\s+)?enum\s+(\w+)\s*\{")
STATIC = re.compile(r"^\s*(?:public\s+|internal\s+)?static\s+(?:let|var)\s+(\w+)")
STYLE_EXTRA = re.compile(r"^\s*(?:public\s+|internal\s+)?static\s+(?:let|var)\s+(\w+)\s*(?::\s*DSTextStyle\b|=\s*DSTextStyle\.)")


def load_contract(path):
    doc = json.loads(Path(path).read_text())
    tokens = {group: set() for group in GROUPS}
    for group, key in GROUPS.items():
        for item in doc.get(key, []):
            tokens[group].add(item["name"])
    styles = {s["name"]: s for s in doc["typography"]["styles"]}
    scale = {}
    for s in doc["spacing"]:
        scale.setdefault(float(s["value"]), s["name"])
    return tokens, styles, scale


def swift_files(paths, excludes):
    found = []
    for p in paths:
        p = Path(p)
        candidates = [p] if p.is_file() else sorted(p.rglob("*.swift"))
        for f in candidates:
            rel = f.as_posix()
            if f.suffix == ".swift" and not any(fnmatch.fnmatch(rel, g) for g in excludes):
                found.append(f)
    return sorted(set(found))


def declared_extras(files):
    """Names declared in `extension DS { enum <Group> { static let ... } }` or
    `extension DS.<Group> { static let ... }` in the scanned files."""
    extras = {group: set() for group in GROUPS}
    styles = set()
    for f in files:
        lines = f.read_text(errors="replace").splitlines()
        in_ext, group, depth = False, None, 0
        for line in lines:
            m = STYLE_EXTRA.match(line)
            if m:
                styles.add(m.group(1))
            if not in_ext and EXTENSION_DS.match(line):
                in_ext, depth = True, 0
            m = None if in_ext else EXTENSION_GROUP.match(line)
            if m and m.group(1) in GROUPS:
                in_ext, group, depth = True, m.group(1), 0
            if in_ext:
                m = ENUM.match(line)
                if m and m.group(1) in GROUPS:
                    group = m.group(1)
                m = STATIC.match(line)
                if m and group:
                    extras[group].add(m.group(1))
                depth += line.count("{") - line.count("}")
                if depth <= 0 and "}" in line:
                    in_ext, group = False, None
    return extras, styles


def on_image(lines, i):
    """True when line i belongs to a modifier chain that starts at an Image(...): symbol sizing, not text."""
    j = i
    while j >= 0:
        stripped = lines[j].strip()
        if "Image(" in stripped:
            return True
        if j < i and not stripped.startswith("."):
            return False
        j -= 1
    return False


def allowed(lines, i, rule):
    for j in (i, i - 1):
        if j >= 0:
            m = ALLOW.search(lines[j])
            if m and m.group(1) == rule:
                return True
    return False


def scan(f, lines, ctx, row_re):
    tokens, styles, scale, extra_styles = ctx
    is_row = bool(row_re.search(f.name))
    out = []

    def add(i, rule, severity, message):
        if not allowed(lines, i, rule):
            out.append({"file": f.as_posix(), "line": i + 1, "rule": rule, "severity": severity,
                        "message": message, "text": lines[i].strip()})

    for i, line in enumerate(lines):
        code = line.split("//", 1)[0] if "//" in line and '"' not in line.split("//", 1)[0] else line
        if not code.strip():
            continue
        for rule, severity, pattern, message in LINE_RULES:
            if pattern.search(code):
                if rule == "literal-font" and on_image(lines, i):
                    continue
                add(i, rule, severity, message)

        for pattern in (PADDING, STACK_SPACING):
            for m in pattern.finditer(code):
                value = float(m.group(1))
                if value == 0:
                    continue
                token = scale.get(value)
                if token:
                    add(i, "literal-spacing", "warning", f"literal {m.group(1)}; use DS.Spacing.{token}")
                else:
                    add(i, "literal-spacing", "warning",
                        f"literal {m.group(1)} is off the spacing scale ({', '.join(f'{v:g}' for v in sorted(scale))})")

        for m in DS_TOKEN.finditer(code):
            group, name = m.group(1), m.group(2)
            if name not in tokens[group]:
                add(i, "unknown-token", "error", f"DS.{group}.{name} is not in the contract or an extension DS")

        for m in DS_FONT.finditer(code):
            name = m.group(1)
            style = styles.get(name)
            if style is None:
                if name not in extra_styles:
                    add(i, "unknown-token", "error", f".dsFont(.{name}) is not a contract text style")
                continue
            if not is_row:
                continue
            uses = style.get("uses")
            if uses is not None and "row" not in uses:
                add(i, "row-text-style", "error",
                    f".{name} ({style['size']:g}pt) is for {', '.join(uses)}, not rows")
            elif uses is None and style["size"] > ROW_MAX_SIZE:
                add(i, "row-text-style", "warning",
                    f".{name} is {style['size']:g}pt; above {ROW_MAX_SIZE}pt it crowds a dense row")

        if is_row and FIXED_SIZE.search(code):
            add(i, "fixed-size-in-row", "warning",
                "fixedSize in a row: the text cannot shrink or truncate and can push the row past the screen width")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("contract")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--row-files", default=DEFAULT_ROW_FILES)
    ap.add_argument("--out")
    args = ap.parse_args()

    try:
        tokens, styles, scale = load_contract(args.contract)
        row_re = re.compile(args.row_files)
    except (OSError, KeyError, ValueError, re.error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    missing = [p for p in args.paths if not Path(p).exists()]
    if missing:
        print(f"error: not found: {', '.join(missing)}", file=sys.stderr)
        return 2

    files = swift_files(args.paths, args.exclude)
    extras, extra_styles = declared_extras(files)
    for group in GROUPS:
        tokens[group] |= extras[group]
    ctx = (tokens, styles, scale, extra_styles)

    findings = []
    for f in files:
        findings += scan(f, f.read_text(errors="replace").splitlines(), ctx, row_re)

    summary = {}
    for x in findings:
        key = f"{x['severity']}:{x['rule']}"
        summary[key] = summary.get(key, 0) + 1
    errors = sum(1 for x in findings if x["severity"] == "error")
    report = {
        "contract": Path(args.contract).as_posix(),
        "files_scanned": len(files),
        "errors": errors,
        "warnings": len(findings) - errors,
        "summary": dict(sorted(summary.items())),
        "findings": findings,
    }
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    for x in findings:
        print(f"{x['file']}:{x['line']}: {x['severity']}: [{x['rule']}] {x['message']}")
    print(f"{len(files)} file(s), {errors} error(s), {len(findings) - errors} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
