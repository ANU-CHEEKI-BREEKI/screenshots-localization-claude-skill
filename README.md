# screenshot-localization

A Claude Code skill for localizing app store and in-app screenshots: translated text is drawn back
onto the images with Playwright, one rendered set per language.

One coordinate spec is measured against the original screenshots and reused for every locale, so
adding a language is only a new list of strings — nothing is re-measured and nothing drifts.

Read [`SKILL.md`](SKILL.md) for the process. It is written for the agent, but it is also the fastest
way for a person to see what the workflow is.

## The short version

1. **Calibrate.** Hand over screenshots that still have the original text. The agent measures every
   label, samples its real colour out of the pixels, renders the translations on top, and publishes
   a review page with a wipe slider. You point at what is wrong; it fixes the spec and re-renders.
   Repeat until it looks right.
2. **Produce.** Hand over the same screenshots without text. The same spec renders final images for
   every language in one pass.
3. **Strings.** If you already have translations — CSV, `.strings`, `.arb`, XLIFF — point at the
   folder and the exact wording is pulled from it. If not, the agent translates from what the
   screenshots actually show.
4. **Fonts.** If you have the app's font files, point at them and they are used directly. If not,
   the closest Google Fonts match is identified from the letterforms and named for you.

You will be asked about languages, existing translations, fonts and clean screenshots up front —
answer what you can, the rest can follow later.

## Setup

```bash
npm install          # installs playwright and its chromium
```

Node 18+, Python 3 (standard library only). macOS uses `sips` for crops and previews; on Linux
install ImageMagick.

## Usage

```bash
node scripts/sample-colors.mjs spec.uk.json           # real colours out of the originals
node scripts/render.mjs spec.uk.json                  # render one locale
node scripts/render.mjs --all --source ../clean       # every locale, clean screenshots
python3 scripts/build-gallery.py spec.uk.json         # the review page
python3 scripts/find-translation.py ./l10n "Equip"    # existing wording, if any
```

## Layout

```
SKILL.md                     the process, for the agent
templates/gallery.html       the review page - restyle here
scripts/                     render, sample, gallery, translation lookup
references/                  spec schema, measuring, translating
examples/spec.example.json   a filled-in spec to copy
```
