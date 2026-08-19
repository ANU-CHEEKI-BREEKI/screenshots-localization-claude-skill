#!/usr/bin/env python3
"""Finds existing translations for a source string inside a localization folder.

An existing translation is the product's own voice. It beats anything invented here, so this runs
before any translating is done - always ask the user whether such a folder exists.

Two layouts are recognized, which between them cover most projects:

  wide      one file, one column per locale
            Key,English (United States)(en-US),Ukrainian(uk),German(de-DE)
            equip_button,Equip,Спорядити,Ausrüsten

  per-file  one file per locale, keyed by id
            en.csv / uk.csv / de.json / uk.strings / uk.arb / uk.xliff
            the id is found by its english value, then looked up in every other file

    python3 find-translation.py <folder> "Equip" "Inventory" "Base Damage"
    python3 find-translation.py <folder> --file strings.csv "Equip"
    python3 find-translation.py <folder> --json "Equip"        machine-readable output

Matching is case-insensitive and ignores surrounding whitespace. Every hit is printed with the file
it came from, so a wrong guess is easy to spot.
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict

TEXT_EXT = {".csv", ".tsv", ".json", ".strings", ".arb", ".xliff", ".xlf", ".xml"}

# 'Ukrainian(uk)', 'German (Germany)(de-DE)', 'uk', 'pt-BR', 'zh-Hans'
LOCALE_IN_PARENS = re.compile(r"\(([A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?)\)\s*$")
BARE_LOCALE = re.compile(r"^[a-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})?$")


def locale_of(text):
    """Reads a locale code out of a column header or a file name, or returns None."""
    m = LOCALE_IN_PARENS.search(text.strip())
    if m:
        return m.group(1)
    stem = text.strip()
    return stem if BARE_LOCALE.match(stem) else None


def walk(folder):
    for root, _dirs, files in os.walk(folder):
        for f in sorted(files):
            if os.path.splitext(f)[1].lower() in TEXT_EXT:
                yield os.path.join(root, f)


def read_table(path):
    """Any delimited file as (headers, rows-of-lists), or None."""
    delim = "\t" if path.lower().endswith(".tsv") else ","
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh, delimiter=delim))
    except (UnicodeDecodeError, csv.Error):
        return None
    return (rows[0], rows[1:]) if len(rows) >= 2 else None


def read_pairs(path):
    """A flat id -> value mapping out of json, .strings, .arb or xliff, or None."""
    ext = os.path.splitext(path)[1].lower()
    try:
        raw = open(path, encoding="utf-8").read()
    except UnicodeDecodeError:
        return None

    if ext in (".json", ".arb"):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        out = {}

        def flatten(node, prefix=""):
            if isinstance(node, dict):
                for k, v in node.items():
                    flatten(v, f"{prefix}{k}.")
            elif isinstance(node, str):
                out[prefix.rstrip(".")] = node

        flatten(data)
        return out

    if ext == ".strings":
        return dict(re.findall(r'"((?:[^"\\]|\\.)*)"\s*=\s*"((?:[^"\\]|\\.)*)"\s*;', raw))

    if ext in (".xliff", ".xlf", ".xml"):
        units = re.findall(
            r'<trans-unit[^>]*\bid="([^"]+)"[^>]*>.*?<target[^>]*>(.*?)</target>',
            raw, re.S,
        )
        if units:
            return {i: re.sub(r"<[^>]+>", "", t).strip() for i, t in units}
        strings = re.findall(r'<string[^>]*\bname="([^"]+)"[^>]*>(.*?)</string>', raw, re.S)
        return {i: re.sub(r"<[^>]+>", "", t).strip() for i, t in strings} or None

    return None


def search(folder, needles, only_file=None):
    wanted = {n.strip().lower(): n for n in needles}
    results = defaultdict(dict)   # needle -> locale -> (value, source)

    paths = [p for p in walk(folder) if not only_file or os.path.basename(p) == only_file]

    # --- wide tables: one row holds every locale ---
    for path in paths:
        table = read_table(path)
        if not table:
            continue
        headers, rows = table
        cols = {i: locale_of(h) for i, h in enumerate(headers)}
        if sum(1 for v in cols.values() if v) < 2:
            continue
        for row in rows:
            for i, cell in enumerate(row):
                key = cell.strip().lower()
                if key in wanted and cols.get(i):
                    for j, other in enumerate(row):
                        if cols.get(j) and j != i and other.strip():
                            results[wanted[key]][cols[j]] = (other.strip(), os.path.basename(path))

    # --- one file per locale: find the id by its english value, then look it up everywhere ---
    per_file = {}
    for path in paths:
        pairs = read_pairs(path)
        if pairs is None:
            table = read_table(path)
            if table and len(table[0]) == 2:
                pairs = {r[0]: r[1] for r in table[1] if len(r) == 2}
        if pairs:
            loc = locale_of(os.path.splitext(os.path.basename(path))[0])
            if loc:
                per_file[(loc, path)] = pairs

    ids = {}
    for (loc, path), pairs in per_file.items():
        for key, value in pairs.items():
            low = value.strip().lower()
            if low in wanted:
                ids.setdefault(wanted[low], set()).add(key)

    for needle, keys in ids.items():
        for (loc, path), pairs in per_file.items():
            for key in keys:
                if key in pairs and pairs[key].strip():
                    results[needle][loc] = (pairs[key].strip(), os.path.basename(path))

    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("needles", nargs="+", help="source strings to look up, as they appear on screen")
    ap.add_argument("--file", help="only search this file name")
    ap.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = ap.parse_args()

    if not os.path.isdir(args.folder):
        sys.exit(f"[ERROR] {args.folder} is not a folder.")

    results = search(args.folder, args.needles, args.file)

    if args.json:
        print(json.dumps(
            {n: {loc: v for loc, (v, _src) in locs.items()} for n, locs in results.items()},
            ensure_ascii=False, indent=2,
        ))
        return

    for needle in args.needles:
        found = results.get(needle)
        print(f"\n{needle!r}")
        if not found:
            print("   not found - translate it from context instead")
            continue
        for loc in sorted(found):
            value, src = found[loc]
            print(f"   {loc:<10} {value:<40} {src}")

    missing = [n for n in args.needles if n not in results]
    if missing:
        print(f"\n{len(missing)} of {len(args.needles)} strings need translating from context.")


if __name__ == "__main__":
    main()
