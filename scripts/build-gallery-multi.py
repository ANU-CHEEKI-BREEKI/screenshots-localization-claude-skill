#!/usr/bin/env python3
"""Builds one review page covering every locale, with a language switcher.

The single-locale page (build-gallery.py) is the calibration instrument: one language, wiped against
the original, checked pixel by pixel. This one is the acceptance instrument for phase 2 - all the
locales in one page, so a font that silently fell back or a translation that ran out of its button
is one arrow key away instead of one file open away.

    python3 build-gallery-multi.py --specs 'spec.*.json' --renders ../Screenshots \
        --base ../Screenshots/en-US/APP_IPHONE_65 --title "Titan Souls"

Every locale also gets a strings table read straight out of its own spec, because "did the right
translation reach the right images" is not a question a screenshot answers on its own - especially
in a script the reviewer cannot read. Source string, rendered string, locale code, font file and
spec file, all in one block that changes with the picker.

Renders are read from <renders>/<locale>/<variant>. Everything is embedded, so the previews are
downscaled hard: an artifact caps out at 16MB and base64 costs another third on top.
"""

import argparse
import base64
import glob
import html
import io
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile

PAGE_CAP = 15_200_000     # bytes of finished html, leaving headroom under the 16MB artifact cap
SLACK = 400_000           # template, markup and the meta json around the payloads
LADDER = [(900, 48), (820, 44), (760, 40), (680, 36), (600, 32)]

# the strings the verification table shows. they exist in every spec, they are short, and between
# them they cover a title, a stat, a tab and three buttons - enough to tell a mis-wired locale apart
VERIFY_KEYS = ['Equipment', 'Inventory', 'Masteries', 'Vitality', 'Strength',
               'Defense', 'All', 'Details', 'Lock', 'Equip']

# which writing system each locale is drawn in, so the picker explains why the font changes
SCRIPTS = {
    'ar-SA': 'Arabic', 'he': 'Hebrew', 'el': 'Greek', 'hi': 'Devanagari', 'bn-BD': 'Bengali',
    'th': 'Thai', 'ja': 'Japanese', 'ko': 'Korean', 'zh-Hans': 'Chinese', 'zh-Hant': 'Chinese',
    'uk': 'Cyrillic', 'ru': 'Cyrillic', 'bg': 'Cyrillic', 'sr': 'Cyrillic',
    'gu-IN': 'Gujarati', 'kn-IN': 'Kannada', 'ml-IN': 'Malayalam', 'or-IN': 'Odia',
    'pa-IN': 'Gurmukhi', 'ta-IN': 'Tamil', 'te-IN': 'Telugu',
}
NAMES = {
    'ar-SA': 'Arabic', 'bn-BD': 'Bengali', 'ca': 'Catalan', 'cs': 'Czech', 'da': 'Danish',
    'de-DE': 'German', 'el': 'Greek', 'en-US': 'English (US)', 'es-ES': 'Spanish (Spain)',
    'es-MX': 'Spanish (Mexico)', 'fi': 'Finnish', 'fr-CA': 'French (Canada)', 'fr-FR': 'French',
    'gu-IN': 'Gujarati', 'he': 'Hebrew', 'hi': 'Hindi', 'hr': 'Croatian', 'hu': 'Hungarian',
    'id': 'Indonesian', 'it': 'Italian', 'ja': 'Japanese', 'kn-IN': 'Kannada', 'ko': 'Korean',
    'ml-IN': 'Malayalam', 'ms': 'Malay', 'nl-NL': 'Dutch', 'no': 'Norwegian', 'or-IN': 'Odia',
    'pa-IN': 'Punjabi', 'pl': 'Polish', 'pt-BR': 'Portuguese (Brazil)', 'pt-PT': 'Portuguese',
    'ro': 'Romanian', 'ru': 'Russian', 'sk': 'Slovak', 'sl-SI': 'Slovenian', 'sv': 'Swedish',
    'ta-IN': 'Tamil', 'te-IN': 'Telugu', 'th': 'Thai', 'tr': 'Turkish', 'uk': 'Ukrainian',
    'vi': 'Vietnamese', 'zh-Hans': 'Chinese (Simplified)', 'zh-Hant': 'Chinese (Traditional)',
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


def spec_strings(spec):
    """what the renderer actually drew, keyed by its english source.

    Reading it back out of the spec rather than out of the translation table is the whole point: it
    is the same object render.mjs consumed, so the table cannot agree with a locale the images
    disagree with. A run-folded entry carries the words on its runs, not on itself.
    """
    out = {}
    for screen in spec['screens']:
        for entry in list(screen.get('texts', [])) + list(screen.get('grids', [])):
            for run in entry.get('runs', []):
                if run.get('src'):
                    out.setdefault(run['src'], run['t'])
            if entry.get('src') and not entry.get('runs'):
                out.setdefault(entry['src'], entry['t'])
    return out


def subset_font(path, text):
    """cut a font down to the glyphs one locale's verification strings need.

    The render fonts total ~34MB - Ma Shan Zheng and LXGW WenKai alone are 21MB - so embedding them
    whole is not on the table. Subset to the ~60 characters the table shows and each one lands
    around 10KB, which buys the thing that matters: the table renders in the same file the
    screenshot did, so a script the font does not cover tofus here instead of being silently
    rescued by a system fallback.
    """
    from fontTools import subset

    options = subset.Options(layout_features=['*'], notdef_outline=True, drop_tables=['DSIG'])
    options.ignore_missing_unicodes = True
    font = subset.load_font(path, options)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(text=text)
    subsetter.subset(font)
    buf = io.BytesIO()
    subset.save_font(font, buf, options)
    font.close()
    return buf.getvalue()


def font_faces(specs, strings, spec_dir_of):
    """one @font-face per locale, named V-<locale>, deduped by (file, glyphs actually needed)"""
    try:
        import fontTools  # noqa: F401
    except ImportError:
        # no subsetter, so no honest preview font. the table falls back to the page's own face,
        # which means a missing glyph will NOT show as tofu - check the screenshots for that instead
        print('   [WARN] fontTools not installed; the strings table falls back to the page font')
        return '', {}

    logging.getLogger('fontTools').setLevel(logging.ERROR)
    faces, cache, total = [], {}, 0
    for locale, (path, spec) in specs.items():
        sources = spec.get('fonts') or []
        if not sources:
            continue
        file = os.path.join(spec_dir_of(path), sources[0]['src'])
        if not os.path.exists(file):
            continue
        text = ''.join(en + target for en, target in strings.get(locale, []))
        key = (os.path.realpath(file), ''.join(sorted(set(text))))
        if key not in cache:
            try:
                cache[key] = subset_font(file, text)
            except Exception as err:                      # a broken face must not fail the page
                print(f'   [WARN] could not subset {os.path.basename(file)}: {err}')
                continue
            total += len(cache[key])
        data = base64.b64encode(cache[key]).decode()
        faces.append(f"  @font-face{{font-family:'V-{locale}';font-display:swap;"
                     f"src:url(data:font/ttf;base64,{data}) format('truetype')}}")
    print(f'   preview fonts: {total // 1024} KB across {len(cache)} subsets')
    return '\n'.join(faces), cache


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

    locales = sorted(specs, key=lambda l: (NAMES.get(l, l)))
    default = args.default if args.default in specs else locales[0]

    strings = {}
    for locale, (_, spec) in specs.items():
        drawn = spec_strings(spec)
        strings[locale] = [[key, drawn[key]] for key in VERIFY_KEYS if key in drawn]

    # the fonts are sized first because they come out of the same budget the previews do
    faces, _ = font_faces(specs, strings, os.path.dirname)
    budget = (PAGE_CAP - len(faces) - SLACK) * 3 // 4
    print(f'   preview budget: {budget // 1024 // 1024} MB of jpeg')

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
        if total <= budget:
            break

    def b64(path):
        with open(path, 'rb') as fh:
            return base64.b64encode(fh.read()).decode()

    # a native select is the right control for 44 options: it scrolls on every platform and costs
    # one bar of height, where a chip per locale cost half the viewport. optgroups keep the "which
    # writing system" grouping, which is the thing that decides the font
    groups = {}
    for locale in locales:
        groups.setdefault(SCRIPTS.get(locale, 'Latin'), []).append(locale)
    order = ['Latin', 'Cyrillic', 'Greek'] + sorted(set(groups) - {'Latin', 'Cyrillic', 'Greek'})
    rail = []
    for script in order:
        if script not in groups:
            continue
        options = ''.join(
            f'<option value="{l}">{html.escape(NAMES.get(l, l))} &middot; {l}</option>'
            for l in groups[script])
        rail.append(f'<optgroup label="{html.escape(script)}">{options}</optgroup>')

    meta = {}
    for locale, (path, spec) in specs.items():
        font = os.path.basename(spec.get('fonts', [{}])[0].get('src', '')) or 'system'
        meta[locale] = {'name': NAMES.get(locale, locale), 'font': font,
                        'source': os.path.basename(path), 'strings': strings[locale]}

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
                                  'file that actually covers the script. Pick a language below; the table '
                                  'shows what that language actually says, and dragging across a screenshot '
                                  'wipes the English original back in.')
            .replace('__STATS__', stats)
            .replace('__FONTFACES__', faces)
            .replace('__RAIL__', ''.join(rail))
            .replace('__CARDS__', ''.join(cards))
            # the page is wrapped in someone else's <head>, so it cannot declare a charset of its
            # own. \uXXXX escapes keep every translated string readable whatever encoding is
            # assumed, and "</" must never survive raw inside a <script>
            .replace('__META__', json.dumps(meta).replace('</', '<\\/'))
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
