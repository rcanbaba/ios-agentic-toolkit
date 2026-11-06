#!/usr/bin/env python3
"""Prove that splitting a Swift file into several files moved code without changing it.

  check_split.py --baseline <original file> --parts <file> [<file> ...] [--out report.json]

--baseline is a copy of the file before the split; --parts are every file its code went to (the
remaining original included). A split moves members of a type into `extension Type { }` blocks in
new files ("ViewModel+Chat.swift"), so the comparison is per member, not per file:

  members   every member (property, method, nested type, #if block) of every type or extension, with
            its attributes, compared as a multiset after whitespace normalization; comments ignored.
            Dropping `private` / `fileprivate` for cross-file access is allowed and counted
            (access_relaxed): read the list, since a relaxed private overload can change which
            overload a call binds to.
  headers   every type/extension header of the baseline still exists; new headers may only be
            `extension T` for a type T the baseline declared or extended
  top level other top-level declarations identical; parts import nothing the baseline did not
  strings   the multiset of string literals is identical

Exit code 0 = the split moved code only, 1 = a difference (listed), 2 = usage or lexing failure.
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from swift_lex import mask, string_literals  # noqa: E402

CONT = re.compile(r"^\s*(\.|\+|-(?!>)|\*|/(?!/)|\?\?|\?|:|&&|\|\||->|where\b|\{|=(?!=)|throws\b|async\b|rethrows\b)")
ATTR_ONLY = re.compile(r"^@\w+(\([^)]*\))?$")
DECL = re.compile(r"\b(class|struct|enum|actor|extension|protocol)\s+([A-Za-z_][A-Za-z0-9_.]*)")
ACCESS = re.compile(r"\b(private|fileprivate)(\(set\))?\s+")


class Source:
    def __init__(self, text):
        self.code = mask(text).split("\n")                         # strings and comments blanked
        self.text = mask(text, keep=("code", "string")).split("\n")  # comments blanked
        self.start, self.end = [], []
        depth = 0
        for line in self.code:
            self.start.append(depth)
            for c in line:
                if c in "{([":
                    depth += 1
                elif c in "})]":
                    depth -= 1
            self.end.append(depth)

    def has_code(self, i):
        return bool(self.code[i].strip())

    def leading(self, i):
        s = self.code[i].strip()
        return not s or bool(ATTR_ONLY.match(s))

    def body(self, lo, hi, base):
        """Split lines [lo, hi) at depth `base` into members; returns (first, last) inclusive."""
        out, i = [], lo
        while i < hi:
            if not self.has_code(i):
                i += 1; continue
            first = i
            while i < hi and self.leading(i) and self.start[i] == base:
                i += 1
            if i >= hi:
                break
            if self.code[i].strip().startswith("#if"):
                level = 0
                while i < hi:
                    s = self.code[i].strip()
                    level += s.startswith("#if")
                    level -= s.startswith("#endif")
                    if level == 0:
                        break
                    i += 1
                out.append((first, i)); i += 1
                continue
            while i < hi:
                if self.end[i] == base:
                    j = i + 1
                    while j < hi and not self.has_code(j):
                        j += 1
                    if j < hi and CONT.match(self.code[j]):
                        i = j; continue
                    break
                i += 1
            out.append((first, min(i, hi - 1)))
            i += 1
        return out

    def norm(self, a, b, keep_access=True):
        lines = [re.sub(r"\s+", " ", l).strip() for l in self.text[a:b + 1]]
        lines = [l for l in lines if l]
        if not keep_access:
            lines = [ACCESS.sub("", l) for l in lines]
        return "\n".join(lines)


def analyse(text):
    s = Source(text)
    r = {k: collections.Counter() for k in ("members", "members_exact", "headers", "imports", "other")}
    for a, b in s.body(0, len(s.code), 0):
        open_line = next((k for k in range(a, b + 1)
                          if s.start[k] == 0 and s.end[k] == 1 and s.code[k].rstrip().endswith("{")), None)
        if open_line is not None and s.code[b].strip() == "}" and s.start[b] == 1:
            r["headers"][s.norm(a, open_line)] += 1
            for x, y in s.body(open_line + 1, b, 1):
                r["members"][s.norm(x, y, keep_access=False)] += 1
                r["members_exact"][s.norm(x, y)] += 1
        else:
            t = s.norm(a, b)
            r["imports" if t.startswith("import ") else "other"][t] += 1
    return r


def type_names(headers):
    return {m.group(2).split(".")[0] for h in headers for m in [DECL.search(h)] if m}


def short(t):
    return t.replace("\n", " | ")[:160]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--parts", nargs="+", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()

    try:
        base_text = Path(a.baseline).read_text()
        base = analyse(base_text)
        parts = {p: Path(p).read_text() for p in a.parts}
        new = {k: collections.Counter() for k in base}
        problems = []
        for p, text in parts.items():
            r = analyse(text)
            for k in new:
                new[k] += r[k]
            for imp in sorted(set(r["imports"]) - set(base["imports"])):
                problems.append({"kind": "import", "file": p, "detail": imp})
    except (OSError, IndexError) as e:
        print("error:", e); return 2

    missing, extra = base["members"] - new["members"], new["members"] - base["members"]
    problems += [{"kind": "member_missing", "detail": short(t)} for t in sorted(missing.elements())]
    problems += [{"kind": "member_extra", "detail": short(t)} for t in sorted(extra.elements())]
    relaxed = sum((base["members_exact"] - new["members_exact"]).values()) - sum(missing.values())
    for h in sorted((base["headers"] - new["headers"]).elements()):
        problems.append({"kind": "header_missing", "detail": short(h)})
    known = type_names(base["headers"])
    for h in sorted((new["headers"] - base["headers"]).elements()):
        m = re.match(r"^(@\S+\s+)*extension\s+([A-Za-z_][A-Za-z0-9_.]*)", h.split("\n")[-1])
        if not m or m.group(2).split(".")[0] not in known:
            problems.append({"kind": "header_new", "detail": short(h)})
    for t in sorted((base["other"] - new["other"]).elements()):
        problems.append({"kind": "top_level_missing", "detail": short(t)})
    for t in sorted((new["other"] - base["other"]).elements()):
        problems.append({"kind": "top_level_extra", "detail": short(t)})
    sb = collections.Counter(string_literals(base_text))
    sn = collections.Counter(s for t in parts.values() for s in string_literals(t))
    if sb != sn:
        problems.append({"kind": "strings", "detail": f"only in baseline {sorted((sb - sn).elements())[:5]}, only in parts {sorted((sn - sb).elements())[:5]}"})

    report = {
        "baseline": a.baseline,
        "parts": a.parts,
        "members": sum(base["members"].values()),
        "access_relaxed": relaxed,
        "problems": problems,
    }
    if a.out:
        Path(a.out).write_text(json.dumps(report, indent=2) + "\n")
    for p in problems:
        print(f"{p['kind']:16} {p.get('file', '')} {p['detail']}")
    print(f"{report['members']} members, {relaxed} with access relaxed; {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
