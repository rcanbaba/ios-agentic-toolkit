"""Resolve and check file:line evidence references, shared by the migration validators.

A reference is "path/File.swift:12" or "File.swift:12-30". The path is relative to the
source root, or any unique suffix of such a path (a bare file name when it is unique).
A bare ":21" after a reference reuses the previous file ("A.swift:30-43 and :21").
"""

import re

REF = re.compile(r"(?<![\w/.-])([\w./+-]+\.[A-Za-z0-9]+)?:(\d+)(?:-(\d+))?(?!\d)")


def line_counts(enums):
    """{path: number of lines} from enumerations.json's source_files."""
    return {c["path"]: c["lines"] for c in enums.get("source_files", {}).get("cases", [])}


def refs(text):
    """[(path, start, end)] in order; a missing path inherits the previous one."""
    out, last = [], None
    for m in REF.finditer(text):
        path = m.group(1) or last
        if path is None:
            continue
        start = int(m.group(2))
        out.append((path, start, int(m.group(3)) if m.group(3) else start))
        last = path
    return out


def resolve(path, counts):
    """(resolved path, None) or (None, reason)."""
    if path in counts:
        return path, None
    matches = [p for p in counts if p.endswith("/" + path)]
    if len(matches) == 1:
        return matches[0], None
    return None, ("ambiguous file name, matches " + ", ".join(matches[:3])) if matches else "no such source file"


def check(text, counts, where, errors, require=True):
    """Append an error per unresolvable reference; with require, text must hold at least one."""
    found = refs(text)
    if require and not found:
        errors.append(f"{where}: no file:line evidence in {text[:80]!r}")
    for path, start, end in found:
        real, why = resolve(path, counts)
        if real is None:
            errors.append(f"{where}: evidence {path}:{start}: {why}")
        elif not 1 <= start <= end <= counts[real]:
            errors.append(f"{where}: evidence {path}:{start}{'-' + str(end) if end != start else ''} is outside the file ({counts[real]} lines)")
