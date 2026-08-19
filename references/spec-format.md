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
| `width` / `height` | Real pixel size of the screenshots. The render is produced at exactly this size. |
| `defaults` | Inherited by every text entry. Anything in an entry overrides it. |
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
| `mask` | `false` | Draw a background plate behind the text. See below. |
| `maskColor` | from `mask` | Plate colour for this entry, e.g. the fill of the button it sits on. |
| `maskW` | — | Fixed plate width, to cover an original longer than the translation. |

## A grid entry

Same fields as a text entry, except `x`/`y` are replaced by `xs` and `ys`: the label is drawn at
every combination. Use it for repeated chrome — level badges on a row of item cards, a price under
every tile. The colour sampler probes the first cell only, which is what you want since they all
match.

## About `mask`

Off by default and it should usually stay off.

During calibration the source text is still in the image, and a plate hides exactly the
misalignment the calibration pass exists to catch. It also changes the look of the render, so what
the user approves is not what production will output.

The one legitimate use is a final deliverable made from screenshots that still have text in them —
when clean source images do not exist and never will. Then set `mask: true`, give `maskColor` the
colour of the surface under the label, and `maskW` the width of the original string so no tail of
it sticks out.
