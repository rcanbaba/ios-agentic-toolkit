#!/usr/bin/env python3
"""Validate a design-system JSON contract.

Deterministic gate before SwiftUI code generation. Two layers:
  1. Structural: schema_lite subset applied to schemas/design-system.schema.json.
  2. Semantic: unique Swift-safe names, token references resolve, required
     color roles exist, WCAG contrast of text/foreground pairs in light and
     dark mode, bundled fonts have PostScript names.

Contrast below 3:1 is an error; below 4.5:1 is a warning (fine for large or
bold text only).

Usage: validate_design_system.py <design-system.json> [--schema <schema.json>]
Exit code 0 = valid (warnings allowed), 1 = invalid, 2 = usage/IO error.
"""

import json
import sys
from pathlib import Path

from schema_lite import check_schema

DEFAULT_SCHEMA = Path(__file__).resolve().parent.parent / "schemas" / "design-system.schema.json"

REQUIRED_ROLES = ["background", "surface", "text_primary", "text_secondary", "accent", "text_on_accent"]

# Text roles checked against these background roles.
CONTRAST_PAIRS = [
    ("text_primary", "background"),
    ("text_primary", "surface"),
    ("text_secondary", "background"),
    ("text_secondary", "surface"),
    ("text_on_accent", "accent"),
]

ERROR_RATIO = 3.0
WARN_RATIO = 4.5

SWIFT_KEYWORDS = {
    "associatedtype", "class", "deinit", "enum", "extension", "func", "import", "init", "inout",
    "let", "operator", "protocol", "static", "struct", "subscript", "typealias", "var", "break",
    "case", "continue", "default", "defer", "do", "else", "fallthrough", "for", "guard", "if",
    "in", "repeat", "return", "switch", "where", "while", "as", "catch", "false", "is", "nil",
    "self", "super", "throw", "throws", "true", "try", "any", "some", "internal", "private",
    "public", "open", "fileprivate", "rethrows", "Self", "Type", "Protocol",
}


def parse_hex(value):
    v = value.lstrip("#")
    r, g, b = (int(v[i:i + 2], 16) / 255 for i in (0, 2, 4))
    alpha = int(v[6:8], 16) / 255 if len(v) == 8 else 1.0
    return (r, g, b), alpha


def luminance(rgb):
    def channel(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(hex_a, hex_b):
    la = luminance(parse_hex(hex_a)[0])
    lb = luminance(parse_hex(hex_b)[0])
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def check_pair(label, fg, bg, errors, warnings):
    for mode in ("light", "dark"):
        if parse_hex(fg[mode])[1] < 1 or parse_hex(bg[mode])[1] < 1:
            warnings.append(f"{label} ({mode}): translucent color, contrast not checked")
            continue
        ratio = contrast(fg[mode], bg[mode])
        message = f"{label} ({mode}): contrast {ratio:.2f}:1 ({fg[mode]} on {bg[mode]})"
        if ratio < ERROR_RATIO:
            errors.append(message + f" is below {ERROR_RATIO}:1")
        elif ratio < WARN_RATIO:
            warnings.append(message + f" is below {WARN_RATIO}:1; use only for large/bold text")


def check_semantics(doc, errors, warnings):
    colors = {c["name"]: c for c in doc["colors"]}
    families = {f["id"]: f for f in doc["typography"]["families"]}
    styles = {s["name"]: s for s in doc["typography"]["styles"]}
    spacing = {s["name"] for s in doc["spacing"]}
    radii = {r["name"] for r in doc["radii"]}
    shadows = {s["name"] for s in doc["shadows"]}
    borders = {b["name"] for b in doc["borders"]}
    reference_ids = {r["id"] for r in doc["references"]}

    groups = {
        "colors": [c["name"] for c in doc["colors"]],
        "typography.families": [f["id"] for f in doc["typography"]["families"]],
        "typography.styles": [s["name"] for s in doc["typography"]["styles"]],
        "spacing": [s["name"] for s in doc["spacing"]],
        "radii": [r["name"] for r in doc["radii"]],
        "shadows": [s["name"] for s in doc["shadows"]],
        "borders": [b["name"] for b in doc["borders"]],
        "components": [c["name"] for c in doc["components"]],
        "references": [r["id"] for r in doc["references"]],
    }
    for group, names in groups.items():
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            errors.append(f"{group}: duplicate names {dupes}")
        reserved = sorted(n for n in names if n in SWIFT_KEYWORDS)
        if reserved:
            errors.append(f"{group}: names are Swift keywords {reserved}")

    by_role = {}
    for c in doc["colors"]:
        by_role.setdefault(c["role"], []).append(c)
        if c.get("reference") and c["reference"] not in reference_ids:
            errors.append(f"color {c['name']}: unknown reference {c['reference']}")
        if c["origin"] == "sampled" and not c.get("reference"):
            warnings.append(f"color {c['name']}: sampled color without a reference id")
    for role in REQUIRED_ROLES:
        if role not in by_role:
            errors.append(f"colors: missing required role '{role}'")

    for fg_role, bg_role in CONTRAST_PAIRS:
        for fg in by_role.get(fg_role, []):
            for bg in by_role.get(bg_role, []):
                check_pair(f"{fg['name']} on {bg['name']}", fg, bg, errors, warnings)

    for s in doc["typography"]["styles"]:
        family = families.get(s["family"])
        if family is None:
            errors.append(f"text style {s['name']}: unknown family '{s['family']}'")
        elif family["kind"] == "bundled" and not s.get("postscript_name"):
            errors.append(f"text style {s['name']}: bundled family requires postscript_name")
    for f in doc["typography"]["families"]:
        if f["kind"] == "system" and "system_design" not in f:
            warnings.append(f"family {f['id']}: system family without system_design, using default")

    values = [s["value"] for s in doc["spacing"]]
    if values != sorted(values):
        warnings.append("spacing: values are not in ascending order")

    for s in doc["shadows"]:
        if s["color"] not in colors:
            errors.append(f"shadow {s['name']}: unknown color '{s['color']}'")
    for b in doc["borders"]:
        if b["color"] not in colors:
            errors.append(f"border {b['name']}: unknown color '{b['color']}'")

    for c in doc["components"]:
        refs = [
            ("background", c["background"], colors),
            ("foreground", c["foreground"], colors),
            ("text_style", c["text_style"], styles),
            ("radius", c["radius"], radii),
            ("padding_h", c["padding_h"], spacing),
            ("padding_v", c["padding_v"], spacing),
        ]
        if c.get("border") is not None:
            refs.append(("border", c["border"], borders))
        if c.get("shadow") is not None:
            refs.append(("shadow", c["shadow"], shadows))
        for field, value, pool in refs:
            if value not in pool:
                errors.append(f"component {c['name']}: unknown {field} token '{value}'")
        if c["foreground"] in colors and c["background"] in colors:
            check_pair(f"component {c['name']}", colors[c["foreground"]], colors[c["background"]], errors, warnings)
        if c.get("min_height", 44) < 44:
            warnings.append(f"component {c['name']}: min_height below 44pt; not suitable as a tap target")


def main(argv):
    args = argv[1:]
    schema_path = DEFAULT_SCHEMA
    if "--schema" in args:
        i = args.index("--schema")
        schema_path = Path(args[i + 1])
        del args[i:i + 2]
    if len(args) != 1:
        print("usage: validate_design_system.py <design-system.json> [--schema <schema.json>]", file=sys.stderr)
        return 2
    try:
        schema = json.loads(Path(schema_path).read_text())
        doc = json.loads(Path(args[0]).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    errors, warnings = [], []
    check_schema(doc, schema, "$", errors)
    if not errors:
        check_semantics(doc, errors, warnings)

    print(f"{'INVALID' if errors else 'VALID'}: {args[0]}")
    for e in errors:
        print(f"  - error: {e}")
    for w in warnings:
        print(f"  - warning: {w}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
