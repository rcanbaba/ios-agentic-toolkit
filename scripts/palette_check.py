#!/usr/bin/env python3
"""Find screenshot colors that the design-system palette cannot explain.

Deterministic evidence for the visual-review workflow. Input: the contract and the output of
sample_colors.swift for one or more screenshots. A sampled cluster is explained when it is
within --tolerance (CIE76 delta E) of
  - a color token (its light or dark value, by --appearance), or
  - a blend of two tokens: antialiased edges, text glyphs and translucent overlays
    (an overlay over a surface lands on the segment between the two colors).
Clusters below --min-coverage are ignored. What is left is reported with its coverage and the
nearest token: a legacy color, a system color, or content (photos, avatars, video), which the
reviewer has to tell apart by looking at the screenshot. --ignore skips colors that are not the
app's, such as the Dynamic Island's #000000 in a full-screen capture.

Usage: palette_check.py <design-system.json> <samples.json> [--appearance light|dark]
                        [--tolerance 6] [--min-coverage 0.01] [--ignore HEX]... [--out report.json]
Exit code 0 = every cluster explained, 1 = unexplained clusters, 2 = usage/IO error.
"""

import argparse
import json
import sys
from pathlib import Path


def hex_rgb(value):
    v = value.lstrip("#")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def lab(rgb):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e(a, b):
    return sum((p - q) ** 2 for p, q in zip(lab(a), lab(b))) ** 0.5


def blend_distance(c, a, b, steps=20):
    """Smallest delta E between c and a sRGB mix of a and b (the way alpha compositing mixes)."""
    best = None
    for i in range(1, steps):
        t = i / steps
        mix = tuple(round(a[k] * (1 - t) + b[k] * t) for k in range(3))
        d = delta_e(c, mix)
        best = d if best is None or d < best else best
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("contract")
    ap.add_argument("samples")
    ap.add_argument("--appearance", choices=["light", "dark"], default="light")
    ap.add_argument("--tolerance", type=float, default=6.0)
    ap.add_argument("--min-coverage", type=float, default=0.01)
    ap.add_argument("--ignore", action="append", default=[], metavar="HEX")
    ap.add_argument("--out")
    args = ap.parse_args()

    try:
        doc = json.loads(Path(args.contract).read_text())
        samples = json.loads(Path(args.samples).read_text())
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    palette = []
    for c in doc["colors"]:
        value = c[args.appearance]
        if len(value.lstrip("#")) == 8 and value.lstrip("#")[6:].upper() != "FF":
            continue  # translucent tokens show up as blends with what is under them
        palette.append((c["name"], hex_rgb(value)))

    images = []
    unexplained_total = 0
    for image in samples:
        rows = []
        for cluster in image["colors"]:
            if cluster["coverage"] < args.min_coverage:
                continue
            if any(delta_e(hex_rgb(cluster["hex"]), hex_rgb(h)) <= args.tolerance for h in args.ignore):
                continue
            rgb = hex_rgb(cluster["hex"])
            nearest, distance = min(((n, delta_e(rgb, v)) for n, v in palette), key=lambda x: x[1])
            if distance <= args.tolerance:
                rows.append({"hex": cluster["hex"], "coverage": cluster["coverage"], "explained_by": nearest,
                             "delta_e": round(distance, 1)})
                continue
            pair, pair_distance = None, None
            for i, (na, va) in enumerate(palette):
                for nb, vb in palette[i + 1:]:
                    d = blend_distance(rgb, va, vb)
                    if pair_distance is None or d < pair_distance:
                        pair, pair_distance = f"{na} + {nb}", d
            if pair_distance is not None and pair_distance <= args.tolerance:
                rows.append({"hex": cluster["hex"], "coverage": cluster["coverage"], "explained_by": f"blend {pair}",
                             "delta_e": round(pair_distance, 1)})
            else:
                rows.append({"hex": cluster["hex"], "coverage": cluster["coverage"], "explained_by": None,
                             "nearest": nearest, "delta_e": round(distance, 1)})
                unexplained_total += 1
        images.append({"file": image["file"], "clusters": rows})

    report = {
        "contract": Path(args.contract).as_posix(),
        "appearance": args.appearance,
        "tolerance": args.tolerance,
        "min_coverage": args.min_coverage,
        "unexplained": unexplained_total,
        "images": images,
    }
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    for image in images:
        bad = [r for r in image["clusters"] if r["explained_by"] is None]
        print(f"{image['file']}: {len(image['clusters'])} cluster(s), {len(bad)} unexplained")
        for r in bad:
            print(f"  {r['hex']} {r['coverage'] * 100:.1f}% (nearest {r['nearest']}, delta E {r['delta_e']})")
    return 1 if unexplained_total else 0


if __name__ == "__main__":
    sys.exit(main())
