#!/usr/bin/env python3
"""Find references by name that the compiler does not check, and report the ones that point nowhere.

  find_string_bindings.py --src <dir> [--catalog <Assets.xcassets> ...] [--asset-literals REGEX]
                          [--exclude GLOB ...] [--out report.json]

A rename or a port compiles cleanly and still breaks wherever code is bound by a string. In the run
this was derived from, both of these reached a device: a xib kept the old `customClass` after its
Swift class was renamed (the nib built a plain UIView and an `as!` crashed), and 55 icons loaded with
`Image("name")` were never copied (the panels drew empty boxes, no error anywhere).

Class names (checked against the classes, structs, enums, actors and protocols declared in --src):
  xib / storyboard   customClass="X" (skipped when customModule names another module)
  plist              $(PRODUCT_MODULE_NAME).X (UISceneDelegateClassName, NSExtensionPrincipalClass ...)
  Swift              NSClassFromString("X") / NSClassFromString("Module.X")

Asset names (checked against the sets in every --catalog, namespaced folders included):
  Image("x"), Image("x", bundle:), Image(decorative: "x"), UIImage(named: "x"), Color("x"),
  UIColor(named: "x"), NSDataAsset(name: "x"), ImageResource(name: "x"), ColorResource(name: "x")
  A name with interpolation ("icon_\\(i)") is checked as a pattern: at least one set must match it.
  --asset-literals REGEX: every string literal that fully matches REGEX must name a set too, for
  names kept in arrays and passed in a variable (["beauty_blur", "beauty_smooth"]).

Without --catalog only class names are checked. Exit code 0 = every reference resolves,
1 = something points nowhere (listed with file:line), 2 = usage.
"""
import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from swift_lex import mask, segments  # noqa: E402

DEFAULT_EXCLUDE = ["Pods/*", "*/Pods/*", ".build/*", "*/.build/*", "DerivedData/*", "*/DerivedData/*"]
TYPE_DECL = re.compile(r"\b(?:class|struct|enum|actor|protocol)\s+([A-Za-z_][A-Za-z0-9_]*)")
CUSTOM_CLASS = re.compile(r"<[^>]*\bcustomClass=\"([^\"]+)\"[^>]*>")
PLIST_CLASS = re.compile(r"\$\(PRODUCT_MODULE_NAME\)\.([A-Za-z_][A-Za-z0-9_]*)")
FROM_STRING = re.compile(r'NSClassFromString\(\s*"([^"\\]+)"\s*\)')
ASSET_CALL = re.compile(r"\b(?:Image|UIImage|Color|UIColor|NSDataAsset|ImageResource|ColorResource)\((?!\s*systemName:)")
LITERAL = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
SET_SUFFIXES = (".imageset", ".colorset", ".symbolset", ".dataset")


def walk(root, patterns, exclude):
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_file() and any(fnmatch.fnmatch(p.name, g) for g in patterns) \
                and not any(fnmatch.fnmatch(rel, g) for g in exclude):
            yield rel, p


def line_of(text, offset):
    return text.count("\n", 0, offset) + 1


def catalog_sets(catalog):
    names = set()
    root = Path(catalog)
    for p in root.rglob("*"):
        if p.is_dir() and p.suffix in SET_SUFFIXES:
            prefix, folder = [], root
            for part in p.relative_to(root).parts[:-1]:
                folder = folder / part
                try:
                    if json.loads((folder / "Contents.json").read_text()).get("properties", {}).get("provides-namespace"):
                        prefix.append(part)
                except (OSError, ValueError):
                    pass
            names.add("/".join(prefix + [p.stem]))
    return names


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True)
    ap.add_argument("--catalog", nargs="*", default=[])
    ap.add_argument("--asset-literals")
    ap.add_argument("--exclude", nargs="*", default=[])
    ap.add_argument("--out")
    a = ap.parse_args()

    src = Path(a.src).resolve()
    if not src.is_dir():
        print("error: --src must be a directory"); return 2
    exclude = DEFAULT_EXCLUDE + a.exclude

    swift = {rel: p.read_text(errors="replace") for rel, p in walk(src, ["*.swift"], exclude)}
    declared = set()
    for text in swift.values():
        declared |= set(TYPE_DECL.findall(mask(text)))

    problems, checked = [], {"class_references": 0, "asset_references": 0, "asset_patterns": 0}

    def check_class(rel, line, name, where):
        checked["class_references"] += 1
        if name.split(".")[-1] not in declared:
            problems.append({"kind": "class_not_declared", "file": rel, "line": line, "name": name, "via": where})

    for rel, p in walk(src, ["*.xib", "*.storyboard"], exclude):
        text = p.read_text(errors="replace")
        for m in CUSTOM_CLASS.finditer(text):
            tag = m.group(0)
            module = re.search(r'\bcustomModule="([^"]+)"', tag)
            provider = re.search(r'\bcustomModuleProvider="target"', tag)
            if module and not provider:
                continue  # a class from another module (a pod, a framework)
            check_class(rel, line_of(text, m.start()), m.group(1), "customClass")
    for rel, p in walk(src, ["*.plist"], exclude):
        text = p.read_text(errors="replace")
        for m in PLIST_CLASS.finditer(text):
            check_class(rel, line_of(text, m.start()), m.group(1), "plist")
    for rel, text in swift.items():
        visible = mask(text, keep=("code", "string"))
        for m in FROM_STRING.finditer(visible):
            check_class(rel, line_of(text, m.start()), m.group(1), "NSClassFromString")

    if a.catalog:
        sets = set()
        for c in a.catalog:
            sets |= catalog_sets(c)
        literal_rx = re.compile(a.asset_literals) if a.asset_literals else None

        def check_asset(rel, line, name):
            if "\\(" in name:
                checked["asset_patterns"] += 1
                pattern = re.compile("^" + ".+".join(map(re.escape, re.split(r"\\\([^)]*\)", name))) + "$")
                if not any(pattern.match(s) for s in sets):
                    problems.append({"kind": "asset_pattern_unmatched", "file": rel, "line": line, "name": name})
                return
            checked["asset_references"] += 1
            if name not in sets:
                problems.append({"kind": "asset_missing", "file": rel, "line": line, "name": name})

        for rel, text in swift.items():
            visible = mask(text, keep=("code", "string"))
            seen = set()
            code = mask(text)
            for call in ASSET_CALL.finditer(code):
                depth, end = 1, call.end()
                while end < len(code) and depth:
                    depth += {"(": 1, ")": -1}.get(code[end], 0)
                    end += 1
                for m in LITERAL.finditer(visible, call.end(), end):
                    if m.start(1) in seen:
                        continue
                    seen.add(m.start(1))
                    check_asset(rel, line_of(text, call.start()), m.group(1))
            if literal_rx:
                offset = 0
                for kind, t in segments(text):
                    if kind == "string" and offset not in seen and literal_rx.fullmatch(t):
                        check_asset(rel, line_of(text, offset), t)
                    offset += len(t)

    problems.sort(key=lambda p: (p["file"], p["line"], p["name"]))
    report = {"types_declared": len(declared), **checked, "problems": problems}
    if a.out:
        Path(a.out).write_text(json.dumps(report, indent=2) + "\n")
    for p in problems:
        print(f"{p['kind']:24} {p['file']}:{p['line']}  {p['name']}")
    print(f"{checked['class_references']} class and {checked['asset_references']} asset references "
          f"({checked['asset_patterns']} patterns); {len(problems)} point nowhere")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
