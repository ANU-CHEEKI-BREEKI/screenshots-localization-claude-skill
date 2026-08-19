# The spec format

One `spec.<locale>.json` per language. Positions, sizes and colours are identical across locales —
only `locale` and the `t` strings change — so a new language starts as a copy of a finished spec.

```json
{
  "locale": "uk",
  "source": "../screenshots/en-US",
  "out": "out",
  "width": 2688,
  "height": 1242,

  "sourceLabel": "EN",
  "eyebrow": "Titan Souls · 1.5.0 · iPhone 6.5″",
  "headline": "Ukrainian screenshots, first pass",

  "defaults": {
    "font": "Poppins",
    "weight": 500,
    "color": "#ffffff",
    "align": "left",
    "size": 36,
    "shadow": "0 1px 3px rgba(0,0,0,0.45)"
  },

  "mask": { "padX": 10, "padY": 4, "radius": 8, "color": "rgba(20,16,28,0.72)", "blur": 6 },

  "screens": [
    {
      "file": "01_home.png",
      "note": "Equipment screen",
      "texts": [
        { "t": "Спорядження", "x": 276, "y": 83, "size": 58, "weight": 600 },
        { "t": "Живучість", "x": 235, "y": 552, "color": "#45c7aa" },
        { "t": "Одягнути", "x": 2460, "y": 1156, "align": "center", "dark": true, "shadow": "none" }
      ],
      "grids": [
        { "t": "Рв. 1", "size": 30, "align": "center", "dark": true, "shadow": "none",
          "xs": [446, 642, 840], "ys": [407, 660, 915] }
      ]
    }
  ]
}
```

## Top level

| Field | Meaning |
|---|---|
| `locale` | Locale code. Names the output folder (`out/<locale>/`) and the gallery file. |
| `source` | Folder of source screenshots, relative to the spec. Overridable with `--source`. |
| `out` | Output root, relative to the spec. Default `out`. Overridable with `--out`. |
| `variant` | Screenshot size this spec covers, e.g. `APP_IPHONE_65`. Appended to the output path and the gallery name, so a phone spec and a tablet spec do not overwrite each other. Optional but expected whenever a locale has more than one size. |
| `width` / `height` | Real pixel size of the screenshots. The render is produced at exactly this size. |
| `defaults` | Inherited by every text entry. Anything in an entry overrides it. |
| `fonts` | The project's own font files, embedded into the render. See below. Optional. |
| `mask` | Shape of the optional background plate. Only applies to entries with `"mask": true`. |
| `screens` | The list below. |
| `sourceLabel`, `eyebrow`, `headline`, `intro`, `footer` | Copy for the review gallery. All optional. |

## A screen

| Field | Meaning |
|---|---|
| `file` | File name, identical in the source folder and the output folder. |
| `note` | One line shown in the gallery. Say what the screen is. |
| `texts` | The labels — **including every number on screen**. A screen with genuinely nothing to draw keeps `"texts": []` and is copied through. |
| `grids` | A label repeated over a set of positions. |

## A text entry

| Field | Default | Meaning |
|---|---|---|
| `t` | — | The string to draw. |
| `x`, `y` | — | Anchor in real pixels. `y` is always the **vertical middle** of the line. |
| `align` | `left` | What `x` points at: `left`, `center` or `right` edge of the text. |
| `size` | from defaults | Font size in pixels. |
| `font` | from defaults | Google Fonts family name. |
| `weight` | from defaults | 300–800. UI type is usually 500; only titles and item names go to 600+. |
| `color` | from defaults | Written by `sample-colors.mjs`. Do not hand-write it. |
| `shadow` | from defaults | Any CSS `text-shadow`. Use `"none"` on flat panels and buttons. |
| `dark` | `false` | The label is dark type on a light plate. Flips how the sampler picks pixels. |
| `letterSpacing` | — | Pixels. Rarely needed. |
| `transform` | — | CSS `text-transform`, e.g. `uppercase`. |
| `opacity` | — | For disabled or dimmed labels. |
| `src` | — | The original string this replaces. Recommended: it documents the pair for review, and the colour sampler sizes its box from it rather than from a translation of a different length. |
| `sampleW` | — | Explicit sampling box width in pixels. Use when a translation runs past the original into an icon or a bar and the sampler reports that colour instead. |
| `maxW` | — | The width the label is allowed. It wraps inside that box. |
| `maxH` | — | Height budget, used together with `fit` when the text wraps. |
| `nowrap` | `false` | Keep the label on one line inside `maxW`, so `fit` shrinks it instead of wrapping. |
| `lineHeight` | `1` / `1.12` | Line height. Defaults to 1.12 when wrapping. |
| `fit` | `false` | Step the font size down until the label fits `maxW`/`maxH`. |
| `minSize` | 60% of `size` | Floor for `fit`. |
| `mask` | `false` | Draw a background plate behind the text. See below. |
| `maskColor` | from `mask` | Plate colour for this entry, e.g. the fill of the button it sits on. |
| `maskW` | — | Fixed plate width, to cover an original longer than the translation. |

## A grid entry

Same fields as a text entry, except `x`/`y` are replaced by `xs` and `ys`: the label is drawn at
every combination. Use it for repeated chrome — level badges on a row of item cards, a price under
every tile. The colour sampler probes the first cell only, which is what you want since they all
match.

## Fitting a translation into the space it has

A translation is routinely 20–40% longer than the original and a screenshot cannot reflow around it.
Two tools, and which one is right is a layout question, not a preference:

```json
{ "t": "Переглянути всі майстерності", "src": "See All Masteries", "x": 637, "y": 1153,
  "align": "center", "maxW": 300, "maxH": 76, "lineHeight": 1.05, "fit": true, "minSize": 18 }

{ "t": "Переносима вага", "src": "Carry Weight", "x": 2032, "y": 216,
  "maxW": 215, "nowrap": true, "fit": true, "minSize": 22 }
```

- **Wrap** when there is vertical room: a button, a card, a standalone caption. The anchor still
  refers to the middle of the whole block, so the label stays centred as it grows.
- **Shrink** when there is not: a dense stat column where two lines would collide with the rows above
  and below. `nowrap` plus `fit` keeps one line and reduces the size until it fits.

`render.mjs` prints every label it shrank and by how much, so a size that dropped further than you
expected is visible rather than silent.

## `fonts`

```json
"fonts": [
  { "family": "Titan UI", "src": "./fonts/TitanUI-Medium.woff2", "weight": 500 },
  { "family": "Titan UI", "src": "./fonts/TitanUI-Bold.woff2",   "weight": 700, "style": "normal" }
]
```

| Field | Default | Meaning |
|---|---|---|
| `family` | — | The name entries refer to in `font`. Several files share one family. |
| `src` | — | Path to the file, relative to the spec. `woff2`, `woff`, `ttf`, `otf`. |
| `weight` | `400` | The weight this file provides. |
| `style` | `normal` | `normal` or `italic`. |

Files are inlined as data URIs rather than linked, because the render page lives on `file://` and a
font fetched from there is refused.

Any family **not** listed here is requested from Google Fonts, so the two mix freely. A missing file
is a hard error; a family that fails to resolve prints a warning rather than silently substituting.

## About `mask`

Off by default and it should usually stay off.

During calibration the source text is still in the image, and a plate hides exactly the
misalignment the calibration pass exists to catch. It also changes the look of the render, so what
the user approves is not what production will output.

The one legitimate use is a final deliverable made from screenshots that still have text in them —
when clean source images do not exist and never will. Then set `mask: true`, give `maskColor` the
colour of the surface under the label, and `maskW` the width of the original string so no tail of
it sticks out.

## `runs` — one line, several colours

A text entry may carry `runs` instead of relying on `t` alone. Each run is drawn inline, in order,
inside the same box, so the browser does the spacing:

| Field | Meaning |
| --- | --- |
| `t` | the run's text |
| `color` | overrides the entry's colour for this run |
| `size` | overrides the entry's font size for this run |
| `weight` | overrides the entry's weight for this run |
| `src` | the source string, so a generator can translate just this run |

`t` on the entry stays as the joined text, which is what `fit` measures and what the log prints.

## `unicodeRange` on a font entry

Restricts a `@font-face` to a set of codepoints. Declaring two files under the same `family`, one of
them ranged, makes the browser fall back per glyph — the way to give a script font the ASCII
punctuation it does not have.
