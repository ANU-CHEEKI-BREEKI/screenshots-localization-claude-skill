#!/usr/bin/env python3
"""Builds one review page covering every locale, with a language switcher.

The single-locale page (build-gallery.py) is the calibration instrument: one language, wiped against
the original, checked pixel by pixel. This one is the acceptance instrument for phase 2 - all the
locales in one page, so a font that silently fell back or a translation that ran out of its button
is one arrow key away instead of one file open away.

    python3 build-gallery-multi.py --specs 'spec.*.json' --renders ../Screenshots \
        --base ../Screenshots/en-US/APP_IPHONE_65 --title "Titan Souls"

Renders are read from <renders>/<locale>/<variant>. Everything is embedded, so the previews are
downscaled hard: an artifact caps out at 16MB and base64 costs another third on top.
"""

import argparse
import base64
import glob
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile

CAP = 13_000_000          # bytes of jpeg before base64, leaving room under the 16MB artifact cap
LADDER = [(900, 48), (820, 44), (760, 40), (680, 36)]

# which writing system each locale is drawn in, so the rail explains why the font changes
SCRIPTS = {
    'ar-SA': 'Arabic', 'he': 'Hebrew', 'el': 'Greek', 'hi': 'Devanagari', 'bn-BD': 'Bengali',
    'th': 'Thai', 'ja': 'Japanese', 'ko': 'Korean', 'zh-Hans': 'Chinese', 'zh-Hant': 'Chinese',
    'uk': 'Cyrillic', 'ru': 'Cyrillic', 'bg': 'Cyrillic', 'sr': 'Cyrillic',
}
NAMES = {
    'ar-SA': 'Arabic', 'bn-BD': 'Bengali', 'ca': 'Catalan', 'cs': 'Czech', 'da': 'Danish',
    'de-DE': 'German', 'el': 'Greek', 'en-US': 'English (US)', 'es-ES': 'Spanish (Spain)',
    'es-MX': 'Spanish (Mexico)', 'fi': 'Finnish', 'fr-CA': 'French (Canada)', 'fr-FR': 'French',
    'he': 'Hebrew', 'hi': 'Hindi', 'hr': 'Croatian', 'hu': 'Hungarian', 'id': 'Indonesian',
    'it': 'Italian', 'ja': 'Japanese', 'ko': 'Korean', 'ms': 'Malay', 'nl-NL': 'Dutch',
    'no': 'Norwegian', 'pl': 'Polish', 'pt-BR': 'Portuguese (Brazil)', 'pt-PT': 'Portuguese',
    'ro': 'Romanian', 'ru': 'Russian', 'sk': 'Slovak', 'sl-SI': 'Slovenian', 'sv': 'Swedish',
    'th': 'Thai', 'tr': 'Turkish', 'uk': 'Ukrainian', 'vi': 'Vietnamese',
    'zh-Hans': 'Chinese (Simplified)', 'zh-Hant': 'Chinese (Traditional)',
}


def downscale(src, dst, width, quality):
    if shutil.which('sips'):
        subprocess.run(['sips', '-Z', str(width), '-s', 'format', 'jpeg',
                        '-s', 'formatOptions', str(quality), '--out', dst, src],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    elif shutil.which('magick'):
        subprocess.run(['magick', src, '-resize', f'{width}x', '-quality', str(quality), dst],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return dst if os.path.exists(dst) else src


def label_count(screen):
    n = len(screen.get('texts', []))
    for grid in screen.get('grids', []):
        n += len(grid['xs']) * len(grid['ys'])
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--specs', default='spec.*.json')
    ap.add_argument('--renders', required=True, help='folder holding <locale>/<variant>/')
    ap.add_argument('--base', required=True, help='folder of the originals to wipe against')
    ap.add_argument('--out', default='gallery-all.html')
    ap.add_argument('--title', default='Localized screenshots')
    ap.add_argument('--default', help='locale selected on load')
    ap.add_argument('--template')
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    template_path = args.template or os.path.join(here, '..', 'templates', 'gallery-multi.html')
    template = open(template_path).read()

    specs = {}
    for path in sorted(glob.glob(args.specs)):
        spec = json.load(open(path, encoding='utf-8'))
        specs[spec['locale']] = (path, spec)
    if not specs:
        sys.exit(f'[ERROR] no specs matched {args.specs}')

    any_spec = next(iter(specs.values()))[1]
    screens = any_spec['screens']
    variant = any_spec.get('variant', '')

    # find a size that fits the artifact cap instead of guessing one
    tmp = tempfile.mkdtemp(prefix='gallery-multi-')
    for width, quality in LADDER:
        total, files = 0, {}
        for locale, (_, spec) in specs.items():
            for screen in screens:
                src = os.path.join(args.renders, locale, variant, screen['file'])
                if not os.path.exists(src):
                    continue
                dst = os.path.join(tmp, f'{locale}-{screen["file"]}.jpg')
                total += os.path.getsize(downscale(src, dst, width, quality))
                files[(locale, screen['file'])] = dst
        bases = {}
        for screen in screens:
            src = os.path.join(args.base, screen['file'])
            if os.path.exists(src):
                dst = os.path.join(tmp, f'base-{screen["file"]}.jpg')
                total += os.path.getsize(downscale(src, dst, width, quality))
                bases[screen['file']] = dst
        print(f'   {width}px q{quality}: {total // 1024 // 1024} MB of jpeg')
        if total <= CAP:
            break

    def b64(path):
        with open(path, 'rb') as fh:
            return base64.b64encode(fh.read()).decode()

    locales = sorted(specs, key=lambda l: (NAMES.get(l, l)))
    default = args.default if args.default in specs else locales[0]

    # the rail groups by writing system: that is the thing that decides the font
    groups = {}
    for locale in locales:
        groups.setdefault(SCRIPTS.get(locale, 'Latin'), []).append(locale)
    order = ['Latin', 'Cyrillic', 'Greek'] + sorted(set(groups) - {'Latin', 'Cyrillic', 'Greek'})
    rail = []
    for script in order:
        if script not in groups:
            continue
        chips = ''.join(
            f'<button class="chip" type="button" data-loc="{l}" aria-pressed="false">'
            f'{html.escape(NAMES.get(l, l))}<code>{l}</code></button>'
            for l in groups[script])
        rail.append(f'<div class="group"><span class="group__l">{script}</span>'
                    f'<div class="group__c">{chips}</div></div>')

    meta = {}
    for locale, (path, spec) in specs.items():
        font = os.path.basename(spec.get('fonts', [{}])[0].get('src', '')) or 'system'
        meta[locale] = {'name': NAMES.get(locale, locale), 'font': font,
                        'source': os.path.basename(path)}

    cards = []
    for i, screen in enumerate(screens, 1):
        name = screen['file']
        if name not in bases:
            continue
        imgs = ''.join(
            f'<img class="shot" data-loc="{l}" hidden src="data:image/jpeg;base64,{b64(files[(l, name)])}" '
            f'alt="{html.escape(NAMES.get(l, l))} version of {html.escape(name)}">'
            for l in locales if (l, name) in files)
        cards.append(f'''
  <article class="card">
    <header class="card__head">
      <span class="card__idx">{i:02d}</span>
      <p class="card__note">{html.escape(screen.get('note', name))}</p>
      <span class="card__n">{label_count(screen)} labels</span>
    </header>
    <div class="viewer" data-mode="off" style="--wipe:0%">
      <img class="base" src="data:image/jpeg;base64,{b64(bases[name])}" alt="Original {html.escape(name)}">
      {imgs}
      <span class="tag tag--a">EN-US</span>
      <span class="tag tag--b"></span>
    </div>
    <p class="hint">{html.escape(name)} &middot; drag across to wipe the English original back in, double-click to stop</p>
  </article>''')

    shutil.rmtree(tmp, ignore_errors=True)

    def stat(n, label):
        return f'<li><div class="stat__n">{n}</div><div class="stat__l">{label}</div></li>'

    total_labels = sum(label_count(s) for s in screens)
    stats = ''.join([
        stat(len(locales), 'languages'),
        stat(len(cards), 'screenshots'),
        stat(len(locales) * len(cards), 'images'),
        stat(total_labels, 'labels per language'),
        stat(f'{any_spec["width"]}&times;{any_spec["height"]}', 'output size'),
    ])

    page = (template
            .replace('__TITLE__', html.escape(args.title))
            .replace('__EYEBROW__', html.escape(variant or 'localized screenshots'))
            .replace('__HEADLINE__', html.escape(args.title))
            .replace('__INTRO__', 'Every label is drawn onto the text-free plate at coordinates measured '
                                  'once from the English build, in the colour sampled from it and the font '
                                  'file that actually covers the script. Pick a language above; drag across '
                                  'a screenshot to wipe the English original back in.')
            .replace('__STATS__', stats)
            .replace('__RAIL__', ''.join(rail))
            .replace('__CARDS__', ''.join(cards))
            .replace('__META__', json.dumps(meta, ensure_ascii=False))
            .replace('__DEFAULT__', default)
            .replace('__FOOTER__', 'Rendered by <code>render.mjs</code> from one spec per locale. '
                                   'Full-size PNGs live in <code>' + html.escape(args.renders) +
                                   '/&lt;locale&gt;/' + html.escape(variant) + '/</code>.'))

    with open(args.out, 'w') as fh:
        fh.write(page)
    print(f'{args.out}  {os.path.getsize(args.out) // 1024 // 1024} MB  '
          f'({len(locales)} languages, {len(cards)} screenshots)')


if __name__ == '__main__':
    main()
