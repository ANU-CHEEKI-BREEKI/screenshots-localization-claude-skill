# Translating screenshot text

## Always look for existing translations first

The product almost certainly has a localization file already, and its wording is the voice users
know. Ask before writing a single string:

> Do you have the app's translations anywhere — a CSV, a `.strings`/`.arb` folder, an XLIFF export?
> If so, point me at the folder and I will pull the exact wording instead of inventing it.

Then:

```bash
python3 scripts/find-translation.py <folder> "Equip" "Inventory" "Base Damage"
```

Use what it returns verbatim, even where you would have phrased it differently. Consistency with
the app beats elegance. Report which strings it could not find, and translate only those.

## Translating from context

When there is no localization, the image is the brief. Work in this order.

**1. Read the whole set first.** What the app is decides the vocabulary. "Cast" is one thing in a
fishing game and another in a spellcasting one. Never translate a screen in isolation.

**2. Look at what is actually happening on screen.** The most common failure is translating a word
by its dictionary sense while the picture says something else:

| String | On screen | Wrong | Right |
|---|---|---|---|
| Release | character is dragging a chest | "open" | "let go" |
| Lock | inventory item | "padlock" | "keep / protect from selling" |
| Equip | a spear is selected | "put on" | "equip / gear up" |
| All | a filter tab above items | "everything" | "all items" |
| Carry Weight | a 15/25/35 threshold bar | "the cargo" | "carrying capacity" |

If the picture and the word disagree, the picture wins.

**3. Keep one term per concept.** If `Defense` is a mastery tree, a stat and a node label, all three
get the same word. Build the glossary as you go and apply it across every screen.

**4. Match the register.** Buttons are short imperatives. Stat labels are nouns. Section titles are
nouns. Tooltips are sentences. Do not turn a one-word button into a phrase.

**5. Respect the space.** Most languages run 20–40% longer than English, and a screenshot has no
reflow. Between two correct options take the shorter one, then check the render for collisions with
neighbouring labels. If a string genuinely does not fit, say so and propose the abbreviation rather
than silently truncating.

**6. Keep numbers, units and format strings untouched.** `77/100(+50)`, `3,5`, `57/57` stay exactly
as they are — only the words around them change.

**7. Abbreviate the way the original does.** `Max.` → `Макс.`, `Avg.` → `Сер.`, `Lv.` → `Рв.`.
If the source abbreviates, the translation abbreviates too, and consistently.

## Report your choices

When handing the render back, list the strings you translated yourself, grouped by screen, source
next to translation. The user knows their product and will catch a wrong sense in seconds — but only
if they can see the pairs without opening the spec.

Flag anything you were unsure about explicitly rather than burying it.
