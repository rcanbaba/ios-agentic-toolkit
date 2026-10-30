#!/usr/bin/env python3
"""Minimal Swift lexer shared by the divergence scripts.

segments(text) splits Swift source into (kind, text) pieces, kind = "code", "comment" or "string",
so that "".join(text for _, text in segments(src)) == src. It knows line and nested block comments,
"..." / multi-line \"\"\"...\"\"\" strings, raw strings (#"..."#) and string interpolation \\( ... ),
whose contents are code again. It is not a parser: it exists so renames and checks never touch the
inside of string literals, which hold wire names, keys and user-visible text.
"""
import re

_OPEN = re.compile(r'(#*)("""|")')


def segments(text):
    out = []
    i, n = 0, len(text)
    buf, kind = [], "code"
    stack = []  # open strings: [delimiter, hashes, paren depth inside the current interpolation]

    def flush(new_kind):
        nonlocal buf, kind
        if buf:
            out.append((kind, "".join(buf)))
        buf, kind = [], new_kind

    while i < n:
        c = text[i]
        if kind == "code":
            if text.startswith("//", i):
                j = text.find("\n", i)
                j = n if j < 0 else j
                flush("code"); out.append(("comment", text[i:j])); i = j
                continue
            if text.startswith("/*", i):
                depth, j = 1, i + 2
                while j < n and depth:
                    if text.startswith("/*", j):
                        depth += 1; j += 2
                    elif text.startswith("*/", j):
                        depth -= 1; j += 2
                    else:
                        j += 1
                flush("code"); out.append(("comment", text[i:j])); i = j
                continue
            m = _OPEN.match(text, i)
            if m:
                hashes, delim = len(m.group(1)), m.group(2)
                buf.append(m.group(0)); i += len(m.group(0))
                flush("string")
                stack.append([delim, hashes, 0])
                continue
            if stack:  # code inside an interpolation
                if c == "(":
                    stack[-1][2] += 1
                elif c == ")":
                    if stack[-1][2] == 0:
                        flush("string"); buf.append(c); i += 1
                        continue
                    stack[-1][2] -= 1
            buf.append(c); i += 1
        else:
            delim, hashes, _ = stack[-1]
            close = delim + "#" * hashes
            if text.startswith(close, i):
                flush("code"); buf.append(close); i += len(close); stack.pop()
                continue
            esc = "\\" + "#" * hashes
            if text.startswith(esc + "(", i):
                buf.append(esc + "("); i += len(esc) + 1
                flush("code")
                stack[-1][2] = 0
                continue
            if text.startswith(esc, i) and i + len(esc) < n:
                buf.append(text[i:i + len(esc) + 1]); i += len(esc) + 1
                continue
            buf.append(c); i += 1
    flush(kind)
    return out


def blank(t):
    """Same length and line breaks, no content."""
    return re.sub(r"[^\n]", " ", t)


def mask(text, keep=("code",)):
    """The source with every segment whose kind is not in `keep` blanked (offsets and lines preserved)."""
    return "".join(t if k in keep else blank(t) for k, t in segments(text))


def string_literals(text):
    return [t for k, t in segments(text) if k == "string"]
