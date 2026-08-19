# Measuring a screenshot

## Coordinates

The Read tool downscales images and states the factor:

```
[Image: original 2688x1242, displayed at 2000x924. Multiply coordinates by 1.34 to map to original image.]
```

Read positions off the displayed image, multiply by that factor, and write the result into the
spec. Take the **vertical middle** of the line, not its baseline or top — `y` is a centre.

For `align`:
- `left` for text in a left-hand column or after an icon — anchor on the first glyph.
- `center` for a label under a node, inside a button, or centred on a card.
- `right` for right-aligned numbers.

Getting `align` right matters more than getting `x` perfect: a centred label stays centred when the
translation changes length, while a left-anchored one grows to the right. Choose the anchor that
matches how the original behaves.

## Sizes

Estimate from cap height. For most sans faces cap height is about 0.70 of the font size, so a
capital letter 40 real pixels tall means roughly `size: 57`.

Check it in the render rather than trusting the arithmetic — one pass of compare-and-nudge is
faster than measuring precisely.

## Identifying the typeface

Never judge the face from the downscaled image. Crop a title and a body line at native resolution
and enlarge them:

```bash
# sips -c <height> <width> --cropOffset <y> <x>
sips -c 90 620 --cropOffset 45 250 --out /tmp/crop.png screenshot.png
sips -Z 1240 --out /tmp/crop-big.png /tmp/crop.png
```

Then read the crop and look for:

| Tell | What it narrows down |
|---|---|
| Single vs double storey `a` | Single storey means geometric: Poppins, Jost, Century Gothic, Futura |
| The digit `1` | A bare vertical stroke is geometric; a flag or a foot serif is humanist |
| Terminals | Rounded ends point at Nunito, Quicksand, Baloo |
| `t` | No bottom tail is geometric; a curved tail is humanist |
| `g` | Single storey with a hook, or a double-storey loop |
| Stroke contrast | UI faces are monolinear; any thick/thin means something else entirely |

Game and app UI is overwhelmingly one of: Poppins, Montserrat, Nunito, Rubik, Inter, SF Pro. All but
the last two are on Google Fonts and load directly.

## Weight

Whatever weight looks right in the thumbnail, go one step lighter. **500 is the right starting
point** for UI labels; 600 for titles and item names; 700 almost never. A render that is too bold is
the single most common complaint, and it is obvious the moment the two images are wiped against
each other.

## Shadows

Copy what the original does, which is usually less than you think:

- Text over gameplay or a photo: a soft shadow, `0 1px 3px rgba(0,0,0,0.45)`.
- Text on a flat card, panel or button: **none**. A shadow here reads as wrong immediately.
- Text over a busy background at small size: a tight dark halo rather than an offset shadow.

## Colours

Do not read colours off the image by eye — run `sample-colors.mjs`. It has repeatedly turned up
labels that look white and are not:

| Looked like | Actually was |
|---|---|
| white damage-type labels | orange `#e48e55`, matching the stat above them |
| the same labels in the row below | blue `#64b1d0` |
| light level badges on item cards | dark `#2a2325` type on a light plate |
| a black button label | red-brown `#993a07` |

When a sampled colour looks wrong, crop the exact box the sampler used and look at it. The usual
cause is the box catching an icon next to the label, or the label being dark on light and needing
`"dark": true`.
