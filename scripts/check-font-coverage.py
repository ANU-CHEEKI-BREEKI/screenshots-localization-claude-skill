#!/usr/bin/env python3
"""Checks whether a font file actually contains the characters a translation needs.

This is the failure that costs the most time when it is missed. A game's display face is usually
built for Latin only; point it at Cyrillic, Greek, Thai or CJK and the browser substitutes
per-glyph, silently. The render comes out looking plausible - some words in the right face, some in
a system fallback - and nobody notices until it ships.

    python3 check-font-coverage.py <font.ttf> --script cyrillic greek
    python3 check-font-coverage.py <font.ttf> --text "Життєздатність"
    python3 check-font-coverage.py <fonts-dir> --spec spec.uk.json    every string in a spec

Reads the cmap table directly, so it needs no dependencies and no rendering.
"""

import argparse
import glob
import json
import os
import struct
import sys

SCRIPTS = {
    "latin":      "ABCabc123",
    "latin-ext":  "ąćłńśźżčřůğşıİ",
    "cyrillic":   "АЯаяЁёІіЇїЄєҐґЪъЫы",
    "greek":      "ΑΩαωάέή",
    "hebrew":     "אבגדה",
    "arabic":     "ابتثج",
    "devanagari": "अआकखग",
    "bengali":    "অআকখগ",
    "thai":       "กขคง",
    "vietnamese": "ăâđêôơưạảấầ",
    "cjk":        "漢字日本語",
    "hangul":     "한국어",
    "kana":       "あいうアイウ",
}


def cmap_codepoints(path):
    """Every codepoint a TrueType/OpenType file maps, read straight out of its cmap table."""
    d = open(path, "rb").read()
    if d[:4] == b"ttcf":
        d = d[struct.unpack(">I", d[12:16])[0]:]

    num_tables = struct.unpack(">H", d[4:6])[0]
    cmap_off = None
    for i in range(num_tables):
        o = 12 + i * 16
        if d[o:o + 4] == b"cmap":
            cmap_off = struct.unpack(">I", d[o + 8:o + 12])[0]
    if cmap_off is None:
        return set()

    n = struct.unpack(">H", d[cmap_off + 2:cmap_off + 4])[0]
    best = None
    for i in range(n):
        o = cmap_off + 4 + i * 8
        pid, eid, off = struct.unpack(">HHI", d[o:o + 8])
        # unicode subtables, preferring the full-range format 12 one that comes later
        if (pid, eid) in ((3, 1), (3, 10), (0, 3), (0, 4)):
            best = cmap_off + off
    if best is None:
        return set()

    fmt = struct.unpack(">H", d[best:best + 2])[0]
    chars = set()

    if fmt == 4:
        seg_x2 = struct.unpack(">H", d[best + 6:best + 8])[0]
        seg = seg_x2 // 2
        ends = struct.unpack(f">{seg}H", d[best + 14:best + 14 + seg_x2])
        starts = struct.unpack(f">{seg}H", d[best + 16 + seg_x2:best + 16 + seg_x2 * 2])
        for s, e in zip(starts, ends):
            if s != 0xFFFF:
                chars.update(range(s, min(e, 0xFFFF) + 1))
    elif fmt == 12:
        groups = struct.unpack(">I", d[best + 12:best + 16])[0]
        for i in range(groups):
            o = best + 16 + i * 12
            s, e, _ = struct.unpack(">III", d[o:o + 12])
            chars.update(range(s, e + 1))

    return chars


def report(path, samples):
    chars = cmap_codepoints(path)
    print(f"\n{os.path.basename(path)}  ({len(chars)} codepoints)")
    ok = True
    for label, text in samples.items():
        missing = sorted({c for c in text if ord(c) not in chars})
        if missing:
            ok = False
            print(f"   {label:<22} MISSING  {''.join(missing)}")
        else:
            print(f"   {label:<22} ok")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="a font file, or a folder of them")
    ap.add_argument("--script", nargs="+", choices=sorted(SCRIPTS), help="named scripts to test")
    ap.add_argument("--text", nargs="+", help="literal strings to test")
    ap.add_argument("--spec", help="a spec.json; every string in it is tested")
    args = ap.parse_args()

    samples = {}
    for name in args.script or []:
        samples[name] = SCRIPTS[name]
    for i, text in enumerate(args.text or []):
        samples[f"text {i + 1}"] = text

    if args.spec:
        spec = json.load(open(args.spec))
        every = "".join(
            str(t["t"])
            for screen in spec["screens"]
            for t in list(screen.get("texts", [])) + list(screen.get("grids", []))
        )
        samples[f"spec {os.path.basename(args.spec)}"] = "".join(sorted(set(every)))

    if not samples:
        samples = dict(SCRIPTS)

    files = (
        sorted(glob.glob(os.path.join(args.target, "**", "*.ttf"), recursive=True) +
               glob.glob(os.path.join(args.target, "**", "*.otf"), recursive=True))
        if os.path.isdir(args.target) else [args.target]
    )
    if not files:
        sys.exit(f"[ERROR] no font files in {args.target}")

    all_ok = all([report(f, samples) for f in files])
    if not all_ok:
        print("\nA missing glyph is substituted silently at render time. Pick a font that covers "
              "the script, or ask which one the project uses for it.")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
