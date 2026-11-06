#!/usr/bin/env python3
"""Measure how much of a fork's Swift code still occurs in the app it came from, without pairing files.

  similarity.py --original <dir> --fork <dir> [--renames MAP ...] [--string-renames MAP ...]
                [--exclude GLOB ...] [--area-depth N] [--out report.json] [--md report.md]

Pairing a fork file with "its" original file under-counts: a renamed, moved or split file pairs
with nothing and scores 0 %. In the run this was derived from, a file-pair metric showed 22 % while
the code was still over half the same. This script compares each fork line and fingerprint with
the whole original tree instead:

  line overlap         share of the fork's meaningful lines (whitespace-normalized, comments
                       removed, at least 12 characters, not a lone brace/return/import) that occur
                       anywhere in the original
  fingerprint overlap  share of the fork's token 8-gram fingerprints (winnowing, window 4, as in
                       MOSS) found in the original; catches copied code whose lines were rewrapped

Both are reported "raw" (as written) and "normalized": identifiers renamed by --renames maps and
string literals renamed by --string-renames maps (localization keys) mapped back to their original
names. Raw minus normalized is what the renames bought; normalized is what is still shared logic.

Matched raw lines are also broken down by kind, to show which part cannot fall: "generic" lines
occur 5 or more times in the original ("guard let self else { return }", ".padding()"), model
fields and CodingKeys follow the wire format, the rest is carried-over logic. Per area (the first
--area-depth folders, default 2) for where to work next.

Exit code 0 always (it measures; the human decides what is enough), 2 = usage.
"""
import argparse
import fnmatch
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from swift_lex import segments  # noqa: E402

DEFAULT_EXCLUDE = ["Pods/*", "*/Pods/*", ".build/*", "*/.build/*", "DerivedData/*", "*/DerivedData/*"]
TRIVIAL = re.compile(r"^[\s{}()\[\],;]*$|^(import|@MainActor|@Published|return|break|default:|else|case \.|\}\s*else)\b")
TOKEN = re.compile(r'[A-Za-z_][A-Za-z0-9_]*|\d+|"(?:[^"\\\n]|\\.)*"|\S')
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
KINDS = [
    ("model field", re.compile(r"^(public |private |fileprivate )?(let|var) [A-Za-z_][A-Za-z0-9_]*\s*:\s*[A-Za-z\[\]<>.?!, :]+$")),
    ("enum / CodingKeys case", re.compile(r'^case [A-Za-z_][A-Za-z0-9_]*( = "[^"]*")?(, [A-Za-z_][A-Za-z0-9_]*( = "[^"]*")?)*$')),
    ("Codable line", re.compile(r"decodeIfPresent|\.decode\(|encodeIfPresent|\.encode\(|container\(keyedBy")),
    ("SwiftUI modifier", re.compile(r"^\.")),
    ("control flow", re.compile(r"^(guard|if|else|switch|for|while|return|Task|await|try|DispatchQueue|defer)\b")),
]


def load_rename_back(paths):
    back = {}
    for p in paths or []:
        for old, new in json.loads(Path(p).read_text()).get("rename", {}).items():
            back.setdefault(new, old)
    return back


def files(root, exclude):
    out = []
    for p in sorted(root.rglob("*.swift")):
        rel = p.relative_to(root).as_posix()
        if not any(fnmatch.fnmatch(rel, g) for g in exclude):
            out.append((rel, p))
    return out


def prepare(text, ids=None, strs=None):
    """Comments removed; with maps, identifiers and string literals mapped back to original names."""
    out = []
    for kind, t in segments(text):
        if kind == "comment":
            out.append(" " if "\n" not in t else "\n" * t.count("\n"))
        elif kind == "string":
            out.append(strs.get(t, t) if strs else t)
        else:
            out.append(IDENT.sub(lambda m: ids.get(m.group(0), m.group(0)), t) if ids else t)
    return "".join(out)


def lines(text):
    out = []
    for l in text.splitlines():
        s = re.sub(r"\s+", " ", l).strip()
        if len(s) >= 12 and not TRIVIAL.match(s):
            out.append(s)
    return out


def fingerprints(text, k=8, w=4):
    toks = TOKEN.findall(text)
    hs = [hashlib.md5(" ".join(toks[i:i + k]).encode()).hexdigest()[:12] for i in range(len(toks) - k + 1)]
    return {min(hs[i:i + w]) for i in range(max(len(hs) - w + 1, 1)) if hs[i:i + w]}


def kind(line, generic):
    if generic:
        return "generic (5+ times in the original)"
    for name, rx in KINDS:
        if rx.search(line):
            return name
    return "other logic"


def pct(a, b):
    return round(100.0 * a / b, 1) if b else 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--original", required=True)
    ap.add_argument("--fork", required=True)
    ap.add_argument("--renames", nargs="*", default=[])
    ap.add_argument("--string-renames", nargs="*", default=[])
    ap.add_argument("--exclude", nargs="*", default=[])
    ap.add_argument("--area-depth", type=int, default=2)
    ap.add_argument("--out")
    ap.add_argument("--md")
    a = ap.parse_args()

    exclude = DEFAULT_EXCLUDE + a.exclude
    orig_root, fork_root = Path(a.original).resolve(), Path(a.fork).resolve()
    if not orig_root.is_dir() or not fork_root.is_dir():
        print("error: --original and --fork must be directories"); return 2
    ids = load_rename_back(a.renames)
    strs = load_rename_back(a.string_renames)

    orig_text = "\n".join(prepare(p.read_text(errors="replace")) for _, p in files(orig_root, exclude))
    orig_count = Counter(lines(orig_text))
    orig_lines, orig_fp = set(orig_count), fingerprints(orig_text)

    totals = {m: [0, 0, 0, 0] for m in ("raw", "normalized")}
    areas = defaultdict(lambda: {m: [0, 0, 0, 0] for m in ("raw", "normalized")})
    kinds = Counter()
    kind_totals = Counter()
    for rel, p in files(fork_root, exclude):
        text = p.read_text(errors="replace")
        parts = rel.split("/")[:-1]
        area = "/".join(parts[:a.area_depth]) or "."
        for mode, prepared in (("raw", prepare(text)), ("normalized", prepare(text, ids, strs))):
            ls, fp = lines(prepared), fingerprints(prepared)
            hit = [l for l in ls if l in orig_lines]
            row = [len(ls), len(hit), len(fp), len(fp & orig_fp)]
            for i in range(4):
                totals[mode][i] += row[i]
                areas[area][mode][i] += row[i]
            if mode == "raw":
                for l in ls:
                    k = kind(l, orig_count.get(l, 0) >= 5)
                    kind_totals[k] += 1
                    if l in orig_lines:
                        kinds[k] += 1

    t = totals
    report = {
        "fork_lines": t["raw"][0],
        "raw": {"line_overlap": pct(t["raw"][1], t["raw"][0]), "fingerprint_overlap": pct(t["raw"][3], t["raw"][2])},
        "normalized": {"line_overlap": pct(t["normalized"][1], t["normalized"][0]),
                       "fingerprint_overlap": pct(t["normalized"][3], t["normalized"][2])},
        "matched_raw_lines_by_kind": [
            {"kind": k, "matched": kinds[k], "points": pct(kinds[k], t["raw"][0]), "share_of_kind": pct(kinds[k], kind_totals[k])}
            for k in sorted(kind_totals, key=lambda k: (-kinds[k], k))
        ],
        "areas": [
            {"area": name, "lines": v["raw"][0],
             "raw_line": pct(v["raw"][1], v["raw"][0]), "raw_fingerprint": pct(v["raw"][3], v["raw"][2]),
             "normalized_line": pct(v["normalized"][1], v["normalized"][0]),
             "normalized_fingerprint": pct(v["normalized"][3], v["normalized"][2])}
            for name, v in sorted(areas.items(), key=lambda kv: (-kv[1]["raw"][1], kv[0]))
        ],
    }
    if a.out:
        Path(a.out).write_text(json.dumps(report, indent=2) + "\n")
    md = [
        "# Similarity\n",
        f"{report['fork_lines']} meaningful fork lines.\n",
        "| | Line overlap | Fingerprint overlap |", "|---|---|---|",
        f"| Raw | {report['raw']['line_overlap']} % | {report['raw']['fingerprint_overlap']} % |",
        f"| Normalized (renames reversed) | {report['normalized']['line_overlap']} % | {report['normalized']['fingerprint_overlap']} % |",
        "", "Matched raw lines by kind (points of the raw line overlap):", "",
        "| Kind | Points | Share of such lines matched |", "|---|---|---|",
        *[f"| {r['kind']} | {r['points']} | {r['share_of_kind']} % |" for r in report["matched_raw_lines_by_kind"]],
        "", "| Area | Lines | Raw line | Raw fp | Norm line | Norm fp |", "|---|---|---|---|---|---|",
        *[f"| {r['area']} | {r['lines']} | {r['raw_line']} % | {r['raw_fingerprint']} % | {r['normalized_line']} % | {r['normalized_fingerprint']} % |"
          for r in report["areas"]],
    ]
    if a.md:
        Path(a.md).write_text("\n".join(md) + "\n")
    print("\n".join(md[2:6]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
