#!/usr/bin/env python3
"""Builds the before/after review page from a spec and its rendered output.

The page is the review instrument for phase 1: a wipe slider per screenshot, with the original on
one side and the render on the other, both scaled identically. Dragging the slider is the fastest
way to catch a label that is a few pixels off, the wrong weight, or the wrong shade - things that
are invisible when the two images are merely next to each other.

Everything visual lives in templates/gallery.html. This script only measures, downscales and fills
in the placeholders, so the page can be restyled without touching any Python.

    python3 build-gallery.py spec.uk.json
    python3 build-gallery.py spec.uk.json --source ../with-text --title "Titan Souls UA"

The result is gallery-<locale>.html next to the spec. Publish it with the Artifact tool; republish
the same path on later passes so the URL stays stable for the user.
"""

import argparse
import base64
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile

# artifacts cap out at 16MB and base64 adds a third, so previews are downscaled well below that
PREVIEW_WIDTH = 1100
PREVIEW_QUALITY = 68


def downscale(src, dst, width=PREVIEW_WIDTH):
    """macOS ships sips; elsewhere ImageMagick stands in. Falls back to the original file."""
    if shutil.which("sips"):
        subprocess.run(
            ["sips", "-Z", str(width), "-s", "format", "jpeg",
             "-s", "formatOptions", str(PREVIEW_QUALITY), "--out", dst, src],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
    elif shutil.which("magick"):
        subprocess.run(
            ["magick", src, "-resize", f"{width}x", "-quality", str(PREVIEW_QUALITY), dst],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
    return dst if os.path.exists(dst) else src


def b64(path):
    with open(path, "rb") as fh:
        return base64.b64encode(fh.read()).decode()


def label_count(screen):
    n = len(screen.get("texts", []))
    for grid in screen.get("grids", []):
        n += len(grid["xs"]) * len(grid["ys"])
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--source", help="folder of the originals; defaults to the spec's source")
    ap.add_argument("--out", help="folder of the renders; defaults to the spec's out/<locale>")
    ap.add_argument("--title", help="page title; defaults to '<locale> screenshots'")
    ap.add_argument("--template", help="path to gallery.html; defaults to ../templates/gallery.html")
    args = ap.parse_args()

    spec_path = os.path.abspath(args.spec)
    spec_dir = os.path.dirname(spec_path)
    with open(spec_path) as fh:
        spec = json.load(fh)

    locale = spec["locale"]
    source_dir = os.path.abspath(os.path.join(spec_dir, args.source or spec["source"]))
    out_dir = os.path.abspath(
        args.out or os.path.join(spec_dir, spec.get("out", "out"), locale)
    )

    here = os.path.dirname(os.path.abspath(__file__))
    template_path = args.template or os.path.join(here, "..", "templates", "gallery.html")
    with open(template_path) as fh:
        template = fh.read()

    if not os.path.isdir(out_dir):
        sys.exit(f"[ERROR] no renders in {out_dir}. Run render.mjs first.")

    tmp = tempfile.mkdtemp(prefix="gallery-")
    cards = []
    total = 0
    localized = 0

    for i, screen in enumerate(spec["screens"], 1):
        name = screen["file"]
        original = os.path.join(source_dir, name)
        render = os.path.join(out_dir, name)
        if not (os.path.exists(original) and os.path.exists(render)):
            print(f"   [WARN] {name} missing on one side, skipped.")
            continue

        stem = os.path.splitext(name)[0]
        n = label_count(screen)
        total += n
        localized += 1 if n else 0

        a = b64(downscale(original, os.path.join(tmp, f"a-{stem}.jpg")))
        b = b64(downscale(render, os.path.join(tmp, f"b-{stem}.jpg")))

        badge = (
            f'<span class="chip chip--on"><span class="chip__n">{n}</span> labels</span>'
            if n else '<span class="chip chip--off">no text</span>'
        )
        safe = html.escape(name)

        cards.append(f'''
      <article class="card">
        <header class="card__head">
          <span class="card__idx">{i}</span>
          <div class="card__id">
            <h2 class="card__file">{safe}</h2>
            <p class="card__note">{html.escape(screen.get("note", ""))}</p>
          </div>
          {badge}
        </header>
        <div class="viewer" tabindex="0" role="slider"
             aria-label="Reveal the {locale} version of {safe}"
             aria-valuemin="0" aria-valuemax="100" aria-valuenow="50" style="--wipe:50%">
          <img class="viewer__img viewer__img--a" src="data:image/jpeg;base64,{a}" alt="Original {safe}">
          <img class="viewer__img viewer__img--b" src="data:image/jpeg;base64,{b}" alt="{locale} render of {safe}">
          <span class="tag tag--a">{spec.get("sourceLabel", "SOURCE").upper()}</span>
          <span class="tag tag--b">{locale.upper()}</span>
          <div class="handle" aria-hidden="true"><span class="handle__grip"></span></div>
        </div>
      </article>''')

    shutil.rmtree(tmp, ignore_errors=True)

    if not cards:
        sys.exit("[ERROR] nothing to show.")

    def stat(n, label):
        return f'      <div class="stat"><div class="stat__n">{n}</div><div class="stat__l">{label}</div></div>'

    stats = "\n".join([
        stat(len(cards), "screenshots"),
        stat(localized, "localized"),
        stat(total, "labels drawn"),
        stat(f'{spec["width"]}&times;{spec["height"]}', "output size"),
    ])

    title = args.title or f"{locale} screenshots"
    page = (template
        .replace("__TITLE__", html.escape(title))
        .replace("__EYEBROW__", html.escape(spec.get("eyebrow", f"locale {locale}")))
        .replace("__HEADLINE__", html.escape(spec.get("headline", title)))
        .replace("__INTRO__", spec.get("intro",
            "Every label is drawn on top of the source screenshot at coordinates measured from it, "
            "in the typeface and colour sampled from the original. The source text underneath stays "
            "visible on purpose: this pass answers one question only &mdash; does the type land in the "
            "right place, at the right size, weight and colour?"))
        .replace("__STATS__", stats)
        .replace("__LABEL_B__", html.escape(locale.upper()))
        .replace("__CARDS__", "\n".join(cards))
        .replace("__FOOTER__", spec.get("footer",
            "Rendered by <code>render.mjs</code> from <code>" + html.escape(os.path.basename(spec_path)) +
            "</code>. Move a label by editing its <code>x</code> / <code>y</code> in the spec and "
            "running the script again. Full-size output lives in <code>" +
            html.escape(os.path.relpath(out_dir, spec_dir)) + "/</code>."))
    )

    dest = os.path.join(spec_dir, f"gallery-{locale}.html")
    with open(dest, "w") as fh:
        fh.write(page)

    print(f"{dest}  {os.path.getsize(dest) // 1024} KB  ({len(cards)} screenshots, {total} labels)")


if __name__ == "__main__":
    main()
