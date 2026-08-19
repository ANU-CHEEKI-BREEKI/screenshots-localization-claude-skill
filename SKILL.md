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

**Ask, do not assume,** about: which locales are needed, whether translations already exist, and
where the clean screenshots will come from. Ask these early — the answers change what you do.

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

1. **Read every screenshot** with the Read tool and inventory the visible text. Note what the app
   is, what each screen does, and which strings are UI chrome versus content — you need this for
   translation context.
2. **Measure coordinates.** The Read tool downscales images and reports the multiplier
   ("Multiply coordinates by 1.34"). Multiply every position you read off by that factor to get
   real pixels. See `references/measuring.md`.
3. **Identify the typeface.** Crop a title and a body line, enlarge them, and look at the
   letterforms. Do not guess from the thumbnail — `references/measuring.md` lists the tells.
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
own voice and beats anything you would write. Report which strings it could not find.

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
- **A screen with nothing to translate still belongs in the spec** with `"texts": []`. It is copied
  through unchanged, so the output folder stays a complete set.

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
| `templates/gallery.html` | The review page itself — restyle here, no Python involved |
| `examples/spec.example.json` | A filled-in spec to copy |
| `references/spec-format.md` | Every field of the spec |
| `references/measuring.md` | Measuring coordinates, identifying the typeface, cropping |
| `references/translating.md` | Translating from context when no localization exists |
