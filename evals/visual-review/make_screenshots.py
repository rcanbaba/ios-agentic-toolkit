#!/usr/bin/env python3
"""Draw the fixture's synthetic "screenshots": flat color blocks standing in for screens.

They exist so palette_check.py has pixels to measure: paper-lantern colors, an antialiased
blend, and on the wallet screen a system blue (#007AFF) that is not in the palette.
Usage: make_screenshots.py <out-dir>
"""
import struct
import sys
import zlib
from pathlib import Path

W, H = 393, 852


def png(path, bands):
    rows = []
    y = 0
    for height, color in bands:
        rgb = bytes(int(color[i:i + 2], 16) for i in (1, 3, 5))
        for _ in range(height):
            if y < H:
                rows.append(b"\x00" + rgb * W)
                y += 1
    while y < H:
        rows.append(b"\x00" + bytes.fromhex("F6F1E7") * W)
        y += 1

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b"")
    Path(path).write_bytes(data)


out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
# paper, card rows separated by hairlines, ink text stand-ins, an ink/paper antialias blend
leaderboard = [(120, "#F6F1E7"), (90, "#FFFCF5"), (2, "#DDD3C2"), (90, "#FFFCF5"), (2, "#DDD3C2"),
               (90, "#FFFCF5"), (30, "#1F1B16"), (20, "#8B857C"), (60, "#F6F1E7"), (56, "#C2410C")]
png(out / "leaderboard-light.png", leaderboard)
png(out / "leaderboard-large-type.png", leaderboard[:4] + [(200, "#FFFCF5"), (40, "#1F1B16")])
# the wallet card: a system blue balance band and two vermilion buttons
png(out / "wallet-light.png", [(120, "#F6F1E7"), (180, "#FFFCF5"), (60, "#007AFF"), (40, "#F6F1E7"),
                               (56, "#C2410C"), (20, "#F6F1E7"), (56, "#C2410C")])
