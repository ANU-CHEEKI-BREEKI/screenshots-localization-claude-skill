#!/usr/bin/env python3
"""Turns one calibrated spec into one spec per App Store locale.

The calibrated spec (spec.uk.json) carries the layout: where every label sits, what colour it is and
how much room it has. That part is language independent and measured once. This script keeps it and
swaps only the strings, picking the font file that actually covers the target script.

Two things it fixes on the way through:

* a number and the label after it become one entry with runs, because the digits are a different
  width in every font and two separately anchored entries collide as soon as that width changes;
* every label without an explicit maxW gets one, measured to its neighbour on the same row, so a
  long translation shrinks instead of running across the value next to it.

    python3 build-specs.py                 writes spec.<locale>.json for every locale
    python3 build-specs.py --only de-DE ja
"""

import argparse
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
LAYOUT = os.path.join(HERE, 'layout.json')
STRINGS = os.path.join(HERE, 'strings.json')

# the game ships one font per writing system; latin is the default face the screenshots were made in
LATIN = '../fonts/Alata-Regular.ttf'
FONTS = {
    'uk': '../fonts/OpenSans-SemiBold.ttf',
    'ru': '../fonts/OpenSans-SemiBold.ttf',
    'el': '../fonts/Greek/GFSNeohellenic-Regular.ttf',
    'ar-SA': '../fonts/Arab/NotoSansArabic-VariableFont_wdth,wght.ttf',
    'he': '../fonts/Herbrew/NotoSansHebrew-Regular.ttf',
    'hi': '../fonts/Hinde/Akshar Unicode.ttf',
    'bn-BD': '../fonts/Bangle/FN Shaymol Bangla Unicodee.ttf',
    'zh-Hans': '../fonts/Chinese/MaShanZheng-Regular.ttf',
    'ja': '../fonts/Japanesse/NotoSansJP-Regular.ttf',
    'ko': '../fonts/Korean/NanumGothic-Regular.ttf',
    'th': '../fonts/Thai/NotoSansThai-VariableFont_wdth,wght.ttf',
    # scripts the game itself never shipped: free OFL faces, downloaded into ./fonts
    'zh-Hant': './fonts/LXGWWenKaiTC-Medium.ttf',
    'gu-IN': './fonts/NotoSansGujarati-Regular.ttf',
    'kn-IN': './fonts/NotoSansKannada-Regular.ttf',
    'ml-IN': './fonts/NotoSansMalayalam-Regular.ttf',
    'or-IN': './fonts/NotoSansOriya-Regular.ttf',
    'pa-IN': './fonts/NotoSansGurmukhi-Regular.ttf',
    'ta-IN': './fonts/NotoSansTamil-Regular.ttf',
    'te-IN': './fonts/NotoSansTelugu-Regular.ttf',
}
# noto sans arabic has no ascii punctuation at all, so "(", "/" and "|" come from the latin face
ASCII_RANGE = 'U+0000-00FF'
NEEDS_LATIN_PUNCTUATION = {'ar-SA', 'he'}

# a run of digits, slashes and percent signs is the same in every language and never translated
NUMERIC = re.compile(r'^[\d\s/%.,:()+\-]*$')

# where the readable area of a panel ends on each screen, so the last label in a row has a limit too
PANEL_RIGHT = {'01_2.png': 2560, '07_8.png': 2545}
GAP = 12
ROW = 20


def group_rows(texts):
    """labels that sit on the same baseline, so 'what is to my right' can be answered"""
    rows = []
    for t in sorted(texts, key=lambda t: (t['y'], t['x'])):
        for row in rows:
            if abs(row[0]['y'] - t['y']) <= ROW:
                row.append(t)
                break
        else:
            rows.append([t])
    return rows


def est_width(t, defaults):
    """a rough width is enough here: it only decides where a neighbour starts, not how text is drawn"""
    size = t.get('size', defaults['size'])
    text = ''.join(r['t'] for r in t['runs']) if t.get('runs') else t['t']
    return len(text) * size * 0.58


def left_edge(t, defaults):
    align = t.get('align', defaults.get('align', 'left'))
    w = est_width(t, defaults)
    return t['x'] - w / 2 if align == 'center' else t['x'] - w if align == 'right' else t['x']


def add_budgets(screen, spec):
    """give every label the width it is actually allowed, measured to the next thing on its row"""
    defaults = spec['defaults']
    limit = PANEL_RIGHT.get(screen['file'], spec['width'] - 20)

    for row in group_rows(screen['texts']):
        for t in row:
            if t.get('maxW') or (NUMERIC.match(t['t']) and not t.get('runs')):
                continue
            # neighbours are decided by x, not by position in the row list: two panels can sit at
            # nearly the same y in different columns, and taking the leftmost of those as "the next
            # thing along" hands the label a negative budget and silently skips it
            right = min([left_edge(n, defaults) for n in row if n['x'] > t['x']], default=limit)
            align = t.get('align', defaults.get('align', 'left'))
            if align == 'center':
                left = max([n['x'] + est_width(n, defaults) / 2 for n in row if n['x'] < t['x']],
                           default=0)
                room = 2 * min(t['x'] - left, right - t['x']) - GAP
            else:
                room = right - t['x'] - GAP
            if room > 40:
                t['maxW'] = int(room)
                t['nowrap'] = True
                t['fit'] = True
                t.setdefault('minSize', max(16, int(t.get('size', defaults['size']) * 0.55)))


def merge_runs(spec):
    """fold "<number> <label>" pairs into one entry so the browser, not the spec, does the spacing"""
    plan = {
        '01_2.png': [[('Level', 258, 284), (' ',), ('2',), ('/10',)]],
        '07_8.png': [
            [('13',), (' ',), ('(6)',), (' ',), ('Stamina Use', 1976, 679)],
            [('110',), (' ',), ('Pierce Damage', 1976, 751)],
            [('60',), (' ',), ('Slash Damage', 1976, 804)],
            [('37%',), (' ',), ('Damage Reduction', 1976, 922)],
            [('10',), (' ',), ('Stamina Use', 1976, 974)],
        ],
    }
    if any(t.get('runs') for s in spec['screens'] for t in s['texts']):
        return  # already folded, e.g. when the layout file was written by an earlier pass

    for screen in spec['screens']:
        for group in plan.get(screen['file'], []):
            keys = [g[0] for g in group if g[0] != ' ']
            anchor = next(g for g in group if len(g) == 3)
            picked, rest = [], list(screen['texts'])
            for key in keys:
                match = next(t for t in rest
                             if (t.get('src') or t['t']) == key
                             and abs(t['y'] - anchor[2]) <= ROW)
                rest.remove(match)
                picked.append(match)
            head = min(picked, key=lambda t: t['x'])
            runs = []
            it = iter(picked)
            for g in group:
                if g[0] == ' ':
                    runs.append({'t': ' '})
                    continue
                t = next(it)
                run = {'t': t['t'], 'color': t['color']}
                if 'src' in t and not NUMERIC.match(t['src']):
                    run['src'] = t['src']
                if t.get('size') and t['size'] != head.get('size'):
                    run['size'] = t['size']
                runs.append(run)
            merged = {k: v for k, v in head.items() if k not in ('t', 'src', 'maxW', 'fit', 'nowrap', 'minSize')}
            merged.update(x=head['x'], runs=runs, t=''.join(r['t'] for r in runs))
            screen['texts'] = [m for m in rest if m is not None]
            screen['texts'].append(merged)
            screen['texts'].sort(key=lambda t: (t['y'], t['x']))


def translate(spec, table):
    for screen in spec['screens']:
        for t in screen['texts'] + screen.get('grids', []):
            for run in t.get('runs', []):
                if run.get('src') in table:
                    run['t'] = table[run['src']]
            if t.get('runs'):
                t['t'] = ''.join(r['t'] for r in t['runs'])
            elif t.get('src') in table:
                t['t'] = table[t['src']]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', nargs='+')
    args = ap.parse_args()

    strings = json.load(open(STRINGS, encoding='utf-8'))
    base = json.load(open(LAYOUT, encoding='utf-8'))

    # the layout is calibrated in ukrainian; english is what the spec keys off
    for screen in base['screens']:
        for t in screen['texts']:
            if 'src' in t:
                t['t'] = t['src']
    merge_runs(base)
    for screen in base['screens']:
        add_budgets(screen, base)

    locales = args.only or sorted(strings)
    for locale in locales:
        spec = json.loads(json.dumps(base))
        spec['locale'] = locale
        spec['source'] = '../final-ios-store-images-horizontal-NO-TEXT'
        font = FONTS.get(locale, LATIN)
        spec['fonts'] = [{'family': 'Game UI', 'src': font, 'weight': '100 900'}]
        if locale in NEEDS_LATIN_PUNCTUATION:
            spec['fonts'].append({'family': 'Game UI', 'src': LATIN,
                                  'weight': '100 900', 'unicodeRange': ASCII_RANGE})
        translate(spec, strings[locale])
        out = os.path.join(HERE, f'spec.{locale}.json')
        json.dump(spec, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'   {locale:9} {os.path.basename(font)}')

    print(f'-> {len(locales)} specs')


if __name__ == '__main__':
    main()
