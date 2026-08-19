// Reads the real colour of every label straight out of the source screenshots.
//
// Eyeballing colours off a screenshot is guesswork: UI palettes are full of near-identical pastels
// that all read as "light blue" or "off white" by eye, and a label that looks white very often is
// not. So this samples the pixels the original label occupies instead.
//
// The sampling box is deliberately tight - one cap-height band, a few characters wide - because
// anything looser catches an icon, a star or a button next to the label and reports that colour.
// Within the band the glyphs are simply the lightest pixels, or on a light plate the darkest ones,
// which is what "dark": true on a text entry switches.
//
// Run it against the screenshots that still have the original text. Colours are language
// independent, so the result is reused by every locale afterwards.
//
//   node sample-colors.mjs spec.uk.json
//   node sample-colors.mjs spec.uk.json --source ../with-text   overrides the spec's source folder
//   node sample-colors.mjs spec.uk.json --dry                   prints without writing

import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { dirname, resolve, join, basename } from 'path';

const args = process.argv.slice(2);
const flag = (name) => {
  const i = args.indexOf(name);
  return i === -1 ? null : args[i + 1];
};

const specPath = resolve(process.cwd(), args.find((a) => !a.startsWith('--')) ?? 'spec.json');
const spec = JSON.parse(readFileSync(specPath, 'utf8'));
const sourceDir = resolve(dirname(specPath), flag('--source') ?? spec.source);
const dry = args.includes('--dry');

// canvas readback of a file:// image is only allowed when chromium trusts local files
const browser = await chromium.launch({ args: ['--allow-file-access-from-files'] });
const page = await browser.newPage({ viewport: { width: 400, height: 300 } });

let changed = 0;

for (const screen of spec.screens) {
  const texts = screen.texts ?? [];
  const grids = screen.grids ?? [];
  if (texts.length === 0 && grids.length === 0) continue;

  const imagePath = join(sourceDir, screen.file);
  if (!existsSync(imagePath)) {
    console.log(`   [WARN] ${screen.file} not in ${sourceDir}, skipped.`);
    continue;
  }

  // the page itself has to live on file:// too, otherwise the image taints the canvas
  await page.goto(`file://${imagePath}`);
  await page.evaluate(async (src) => {
    const img = new Image();
    img.src = src;
    await img.decode();

    const canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    canvas.getContext('2d').drawImage(img, 0, 0);
    window.__ctx = canvas.getContext('2d');
  }, `file://${imagePath}`);

  const boxes = [];
  const collect = (t) => {
    const size = t.size ?? spec.defaults.size;
    const align = t.align ?? spec.defaults.align;

    // the box is scaled to the string it has to cover. a fixed width would reach past a short
    // label like "4" or "1/5" into the background and average that in, which turns a saturated
    // stat colour into mud
    // the width follows the ORIGINAL string, which is what the box has to sit on. "src" records
    // it; without one the translation stands in, and "sampleW" overrides both when a translation
    // runs long enough to reach past the original into an icon or a bar next to it
    const covers = String(t.src ?? t.t).length;
    const w = t.sampleW ?? Math.min(320, Math.max(size, Math.round(covers * size * 0.62)));
    const h = Math.max(8, Math.round(size * 0.78));
    const left = align === 'center' ? t.x - w / 2 : align === 'right' ? t.x - w : t.x;

    boxes.push({ x: Math.round(left), y: Math.round(t.y - h / 2), w, h, dark: !!t.dark });
  };

  texts.forEach(collect);
  grids.forEach((g) => collect({ ...g, x: g.xs[0], y: g.ys[0] }));

  const colors = await page.evaluate((boxes) => {
    const lum = (p) => 0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2];

    return boxes.map((b) => {
      const d = window.__ctx.getImageData(b.x, b.y, b.w, b.h).data;

      const px = [];
      for (let i = 0; i < d.length; i += 4) px.push([d[i], d[i + 1], d[i + 2]]);

      // light text on a dark ground is the top of the luminance range, dark text on a plate the bottom
      px.sort((a, b2) => (b.dark ? lum(a) - lum(b2) : lum(b2) - lum(a)));

      // the core of the strokes, past the antialiased edge that blends into the background
      const core = px.slice(0, Math.max(4, Math.floor(px.length * 0.06)));
      const avg = [0, 1, 2].map((c) => Math.round(core.reduce((s, x) => s + x[c], 0) / core.length));

      return '#' + avg.map((v) => v.toString(16).padStart(2, '0')).join('');
    });
  }, boxes);

  let i = 0;
  for (const t of [...texts, ...grids]) {
    const was = (t.color ?? spec.defaults.color).toLowerCase();
    const now = colors[i++];
    if (was !== now) {
      console.log(`   ${screen.file.padEnd(18)} ${String(t.t).slice(0, 28).padEnd(30)} ${was} -> ${now}`);
      changed++;
    }
    t.color = now;
  }
}

await browser.close();

if (dry) {
  console.log(`\n${changed} colours would change. Nothing written (--dry).`);
} else {
  writeFileSync(specPath, JSON.stringify(spec, null, 2) + '\n');
  console.log(`\n${changed} colours updated in ${basename(specPath)}.`);
}
