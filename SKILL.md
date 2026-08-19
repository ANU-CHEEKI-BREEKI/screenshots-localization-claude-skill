---
name: screenshot-localization
description: Localize app store or in-app screenshots by overlaying translated text onto them with Playwright, then review the result on a generated web page. Use when someone wants screenshots translated into other languages, text on images replaced or re-rendered per locale, App Store / Google Play screenshots localized, or a review page to check that overlaid text lands correctly. Covers calibrating against screenshots that still have the original text baked in, pulling wording from existing localization files, translating from on-screen context when none exist, and producing final images for every locale from clean text-free screenshots.
---

# Screenshot localization

Overlay translated text onto screenshots, one rendered image per locale, driven by a single
coordinate spec that is measured once and reused for every language.

The whole thing rests on one idea: **the position of every label is language-independent.** Measure
where the text sits once, sample its colour once, and after that a new language is only a new list
of strings. Nothing is re-measured, nothing drifts.

## This is an interactive, iterative process — drive it that way

The user has screenshots and wants them in other languages. They do not know this skill, this
folder, or these scripts, and they should not have to. **You run the process and tell them what is
happening.** Assume they will not read any of the files here.

After every single step, tell them three things:

1. **What you just did** — in one or two lines.
2. **What you need from them, if anything** — a folder, a decision, a review.
3. **What happens next** — name the next step so they can see the shape of the whole thing.

End any turn that needs their input with a direct question. Never stop with a silent artifact link
and no instruction on what to look at.

**Start by orienting them.** On the first turn, before doing any work, lay out the three phases in a
few lines and say which one you are starting. Something like:

> Here is how this goes. First I overlay the translations onto your current screenshots and give you
> a web page to review — we loop on that until the placement is right. Then, when you have clean
> screenshots without text, I re-render all of them for every language using the same measurements.
> I am starting phase 1 now. Do you have the app's existing translations anywhere, or should I
> translate from what I see on screen?

### Ask these before doing any work

All four change what you do, and all four are cheap to ask and expensive to guess. Put them in the
**first** message, together, so the user answers once instead of being interrupted four times.

1. **Which languages?** Never assume one. Get the full list up front — the spec is built once and
   copied per locale, so knowing there are eight rather than one changes nothing about the work but
   everything about how you report progress.

2. **Do you already have translations?** A CSV, a `.strings` or `.arb` folder, an XLIFF export, a
   spreadsheet. If yes, ask for the path and pull the exact wording with `find-translation.py`. The
   product's own wording always beats anything you would write, and using it is the difference
   between a review pass that finds two problems and one that finds twenty.

3. **Do you have the fonts?** Ask explicitly, and ask for the files, not the name:

   > Do you have the font files the app uses — `.ttf`, `.otf` or `.woff2`? If you point me at the
   > folder I will render with the real thing. Otherwise I will identify the closest match on
   > Google Fonts from the screenshots and tell you which one I picked.

   A supplied font file is always right and a matched one never quite is, so this question is worth
   asking even when the match looks convincing. See "Fonts" below.

4. **Where will the clean screenshots come from?** Phase 2 needs the same screens with no baked-in
   text. Ask early whether they exist, are planned, or are not happening — if they are not, the
   whole job changes shape and plates become necessary (see `references/spec-format.md`).

Do not block on the answers. Start reading and measuring the screenshots while you wait — that work
is needed regardless of what they say.

**During the review loop, be concrete about what to check.** "Have a look" is useless. Say: drag the
wipe slider on each screenshot, look for labels in the wrong place, wrong size, wrong weight, wrong
shade — and tell me which screenshot and which label.

**Expect several rounds and say so.** The first pass is never right. Make it clear that iterating is
normal, not a failure, so the user keeps giving feedback instead of accepting something mediocre.

**When they report a problem, fix the spec and re-render — never patch the output image.** Then say
what you changed and republish. Keep the same artifact file path so the URL they have keeps working.

**Track where you are.** For a set of any size, keep a task list of the phases and the open feedback
items, so nothing they mentioned gets silently dropped.

## The three phases

Work through them in order. Do not skip phase 1 — the spec it produces is what every later phase
consumes.

### Phase 1 — Calibrate against screenshots that still have text

The user supplies screenshots with the original text baked in. The goal is a spec whose labels land
exactly on top of the originals: same place, same size, same weight, same colour.

1. **Read every screenshot** with the Read tool and inventory **every glyph on screen, numbers
   included**. Counters, stat values, ranks, prices, timers, badge counts — all of it. See
   "Numbers are text too" below; skipping them is the most expensive mistake in this workflow.
   Note what the app is, what each screen does, and which strings are UI chrome versus content —
   you need this for translation context.
2. **Measure coordinates.** The Read tool downscales images and reports the multiplier
   ("Multiply coordinates by 1.34"). Multiply every position you read off by that factor to get
   real pixels. See `references/measuring.md`.
3. **Set up the typeface.** If the user supplied font files, declare them in the spec's `fonts`
   array and use them. If not, crop a title and a body line, enlarge them, identify the closest
   Google Fonts match from the letterforms, and **tell the user which one you picked and why** —
   they may have the real file and not have thought to mention it.
   `references/measuring.md` lists the tells.
4. **Get the strings** — see phase 3 below. Do this before writing the spec, not after.
5. **Write `spec.<locale>.json`** with a position for every label. Schema in
   `references/spec-format.md`.
6. **Sample the colours.** Never eyeball them:
   ```bash
   node scripts/sample-colors.mjs spec.uk.json
   ```
   This reads the real pixel colour of every original label and writes it into the spec.
7. **Render:**
   ```bash
   node scripts/render.mjs spec.uk.json
   ```
8. **Look at the output yourself** with the Read tool before showing the user anything. Catch the
   obvious misses first; do not spend their review round on something you could see.
9. **Build the review page and publish it:**
   ```bash
   python3 scripts/build-gallery.py spec.uk.json --title "<app> <locale> screenshots"
   ```
   Then publish the generated `gallery-<locale>.html` with the Artifact tool. It gives a wipe slider
   per screenshot, which is the fastest way to spot a label that is a few pixels off.
10. **Iterate** until the user is satisfied. Edit the spec, re-render, republish the same path.

During this phase the translated text sits **on top of** the original text. That is expected — say so
plainly, so the overlap does not read as a bug. Do not add background plates to hide the original:
plates change the look of the render and hide the very misalignment this phase exists to catch.

### Phase 2 — Produce against clean screenshots

The user supplies a second folder with the same screenshots, text-free. Nothing is re-measured.

```bash
node scripts/render.mjs spec.uk.json --source ../clean-screenshots
node scripts/render.mjs --all --source ../clean-screenshots
```

`--all` renders every `spec.*.json` in the working directory, so all locales come out in one pass.
Output lands in `out/<locale>/` keeping the original file names, so the results are a drop-in
replacement for the source images.

File names must match between the two folders. If they do not, ask the user to rename rather than
guessing at a mapping.

Build a gallery for the clean render too, so they approve what actually ships:

```bash
python3 scripts/build-gallery.py spec.uk.json --source ../clean-screenshots
```

### Phase 3 — Where the strings come from

Two cases, and you must check for the first before doing the second.

**The user has translations already.** Ask for the folder, then:

```bash
python3 scripts/find-translation.py <folder> "Equip" "Base Damage" "Inventory"
```

It searches CSV, JSON, `.strings`, `.arb` and XLIFF files, matches on the source value, and prints
what every locale has for it. Two layouts are handled: one file per locale keyed by id, and one wide
file with a column per locale. Use what it finds verbatim — an existing translation is the product's
own voice and beats anything you would write.

Three things to get right here:

- **Search the whole folder, not one file.** UI labels, item names, mastery names and tooltips
  usually live in separate tables. Narrowing to the file that looks right is how two thirds of the
  strings come back "not found".
- **The same string often has more than one wording**, because a tooltip or a modifier table says it
  in a different grammatical form than the button does. The tool reports every candidate with its
  file rather than picking one. Take the wording from the file that holds the **UI strings** — a
  genitive lifted from a tooltip into a button is a mistake a native speaker spots instantly.
- **Report which strings it could not find**, and translate only those from context.

Expect the official wording to differ from yours, sometimes on words you were confident about. That
is the point of looking: a good translation that is not the product's own is still the wrong one.

**The user has no translations.** Translate from context, not word by word. The critical rule: look
at what the screenshot actually shows. A prompt over a character dragging a chest is "release", not
"open". Read `references/translating.md` before starting — it lists the traps and how to report your
choices back so wrong ones are easy to spot.

## Non-obvious things that will bite you

- **Never guess a colour.** UI palettes are full of near-identical pastels. Run the sampler. It has
  repeatedly found that a label a person would swear is white is actually orange or grey.
- **Text on a light plate is dark text.** Mark those entries `"dark": true` so the sampler takes the
  darkest pixels instead of the lightest. Buttons, chips and item badges are usually this case.
- **UI type is lighter than it looks.** Weight 500 is a better starting point than 600 or 700.
- **Flat panels carry no shadow.** Set `"shadow": "none"` for text printed onto a solid card or
  button. A drop shadow where the original has none is immediately visible.
- **Check the render, not the spec.** Read the output PNG back after every pass.
- **A screen with nothing at all to draw still belongs in the spec** with `"texts": []`. It is
  copied through unchanged, so the output folder stays a complete set. In practice almost every
  screen has something — see below.

## Fonts

**Prefer the user's own font files.** Ask for them; do not settle for a match without asking. Point
the spec at the files and they are embedded into the render as data URIs:

```json
"fonts": [
  { "family": "Titan UI", "src": "./fonts/TitanUI-Medium.woff2", "weight": 500 },
  { "family": "Titan UI", "src": "./fonts/TitanUI-Bold.woff2",   "weight": 700 }
],
"defaults": { "font": "Titan UI", "weight": 500 }
```

One entry per weight and style, all sharing a `family`. `woff2`, `woff`, `ttf` and `otf` all work,
and paths are relative to the spec. A family with no local file is fetched from Google Fonts
instead, so the two can be mixed — the app's own display face plus a Google body face, for example.

Two failure modes the renderer guards against, because both are silent otherwise:

- **A missing file is a hard error.** It stops rather than rendering with something else.
- **A family that does not resolve prints a warning.** A browser substitutes silently and the render
  then looks *almost* right, which is worse than an error. If you see
  `[WARN] 'X' did not resolve`, the output is wrong — fix it before showing anyone.

### One font per writing system is the normal case

A project rarely ships one font for every language. The display face is built for Latin, and each
other script gets its own file — a folder of them named `Greek/`, `Korean/`, `Thai/`, `Arab/` and so
on, plus one general fallback carrying Cyrillic. So **there is no single "the app's font"**: there
is a font per locale, and the spec for each locale names its own.

Never assume the Latin face covers the target language. Check it:

```bash
python3 scripts/check-font-coverage.py <font.ttf> --script cyrillic greek
python3 scripts/check-font-coverage.py <fonts-folder> --spec spec.uk.json
```

It reads the font's cmap table and lists what is missing. A real example: the Latin face of a game
covered 722 codepoints — every Latin script, Vietnamese and Turkish included — and **not one
Cyrillic or Greek letter**. Rendering Ukrainian with it would have substituted every single glyph,
silently, and the output would have looked fine at a glance.

When a font does not cover the language, look for the project's own fallback before proposing one:
the folder almost always contains it, and using their file keeps the render honest.

## Numbers are text too

Draw every number the screenshot shows: counters, stat values, ranks like `1/5`, currency amounts,
percentages, badge counts, timers. Two independent reasons, and either one alone is decisive.

**The clean screenshots will not have them.** Phase 2 renders onto images with the text removed, and
whoever produces those images removes *all* baked-in text, digits with it. Any number missing from
the spec is simply gone from the final image, and it is gone silently — nothing errors, the layout
just quietly loses its values.

**Digit shapes differ between fonts.** The face carrying the translation is often not the one the
original used — the game's face may have no Cyrillic or no Greek, so a substitute steps in. If the
words are drawn and the digits are left baked in, the screenshot ends up with two different sets of
numerals side by side. Lining figures next to old-style ones, a slashed zero next to a plain one,
different digit widths in a column. It reads as broken even to someone who cannot name why.

So a gameplay screen showing nothing but a HUD full of counters is **not** a screen with no text.
It is a screen whose every label is a number, and it gets a full set of entries.

Numbers are usually **centre-anchored** — a value column, a badge, a segmented bar — so reach for
`"align": "center"` before `left`. Keep the original's own formatting exactly: thousands separators,
decimal comma versus point, `77/100(+50)`, `57/57`. Only the words around a number get translated.

## Setup

```bash
npm install
npx playwright install chromium
```

Node 18+ and Python 3 (standard library only). `sips` handles crops and previews on macOS; on Linux
install ImageMagick and the scripts use `magick` instead.

## Files

| Path | What it is |
|---|---|
| `scripts/render.mjs` | Draws the spec onto the source images and screenshots each at full size |
| `scripts/sample-colors.mjs` | Reads the real colour of every label out of the originals |
| `scripts/build-gallery.py` | Builds the before/after review page from `templates/gallery.html` |
| `scripts/find-translation.py` | Finds existing translations for a source string in a folder |
| `scripts/check-font-coverage.py` | Checks a font actually contains the target script's characters |
| `templates/gallery.html` | The review page itself — restyle here, no Python involved |
| `fonts/` (yours) | Put supplied font files anywhere and point `fonts[].src` at them |
| `examples/spec.example.json` | A filled-in spec to copy |
| `references/spec-format.md` | Every field of the spec |
| `references/measuring.md` | Measuring coordinates, identifying the typeface, cropping |
| `references/translating.md` | Translating from context when no localization exists |
