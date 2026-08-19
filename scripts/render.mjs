// Draws a localization spec onto the source screenshots and saves one full-size PNG per screen.
//
// Every text entry becomes an absolutely positioned div over the image inside a headless Chromium,
// which then screenshots the stage at the exact original resolution. Going through a browser rather
// than an image library is what makes the type match: real font rendering, real shadows, real
// subpixel positioning, and a spec you can reason about in CSS terms.
//
//   node render.mjs                          renders spec.<first found>.json
//   node render.mjs spec.uk.json             renders one locale
//   node render.mjs --all                    renders every spec.*.json in the working directory
//   node render.mjs spec.uk.json --source ../clean-screenshots   overrides the spec's source folder
//   node render.mjs --all --out ./final      overrides the output folder

import { chromium } from 'playwright';
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync } from 'fs';
import { dirname, resolve, join, basename } from 'path';
import { fileURLToPath } from 'url';

const here = process.cwd();
const scriptDir = dirname(fileURLToPath(import.meta.url));

const args = process.argv.slice(2);
const flag = (name) => {
  const i = args.indexOf(name);
  return i === -1 ? null : args[i + 1];
};

const sourceOverride = flag('--source');
const outOverride = flag('--out');
const renderAll = args.includes('--all');

const positional = args.filter((a, i) => !a.startsWith('--') && !args[i - 1]?.startsWith('--'));

/** every spec.*.json in the working directory, so --all covers all locales in one pass */
function findSpecs() {
  return readdirSync(here)
    .filter((f) => /^spec\..+\.json$/.test(f))
    .sort()
    .map((f) => join(here, f));
}

const specPaths = renderAll
  ? findSpecs()
  : positional.length
    ? positional.map((p) => resolve(here, p))
    : findSpecs().slice(0, 1);

if (specPaths.length === 0) {
  console.error('[ERROR] no spec found. Expected a spec.<locale>.json in the working directory.');
  process.exit(1);
}

const escapeHtml = (s) =>
  String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/**
 * one text box. x/y is the anchor: y is always the vertical middle of the line, x is the left,
 * middle or right edge depending on align, which is how positions get measured off a screenshot
 */
function renderText(spec, text) {
  const t = { ...spec.defaults, ...text };

  const translate = {
    left: 'translate(0, -50%)',
    center: 'translate(-50%, -50%)',
    right: 'translate(-100%, -50%)',
  }[t.align] ?? 'translate(0, -50%)';

  // a plate is off by default: during calibration it would hide the very misalignment being checked
  const plate = t.mask && spec.mask
    ? `background:${t.maskColor ?? spec.mask.color};` +
      `padding:${spec.mask.padY}px ${spec.mask.padX}px;` +
      `margin:-${spec.mask.padY}px -${spec.mask.padX}px;` +
      `border-radius:${spec.mask.radius}px;` +
      (spec.mask.blur ? `backdrop-filter:blur(${spec.mask.blur}px);` : '')
    : '';

  // a translation shorter than the original leaves a tail of it sticking out from under a plate;
  // maskW widens the patch to the width it has to cover while the anchor stays put
  const plateWidth = t.mask && t.maskW
    ? `width:${t.maskW}px;text-align:${t.align};box-sizing:border-box;`
    : '';

  const style = [
    'position:absolute',
    `left:${t.x}px`,
    `top:${t.y}px`,
    `transform:${translate}`,
    `font-family:'${t.font}',system-ui,sans-serif`,
    `font-size:${t.size}px`,
    `font-weight:${t.weight}`,
    `color:${t.color}`,
    `text-shadow:${t.shadow}`,
    t.letterSpacing ? `letter-spacing:${t.letterSpacing}px` : '',
    t.transform ? `text-transform:${t.transform}` : '',
    t.opacity != null ? `opacity:${t.opacity}` : '',
    'white-space:pre',
    'line-height:1',
    plate,
    plateWidth,
  ].filter(Boolean).join(';');

  return `<div style="${style}">${escapeHtml(t.t)}</div>`;
}

/** a grid repeats one label over a set of x/y positions, for things like a row of item cards */
function expandGrids(screen) {
  const fromGrids = (screen.grids ?? []).flatMap((grid) =>
    grid.ys.flatMap((y) => grid.xs.map((x) => ({ ...grid, x, y, xs: undefined, ys: undefined })))
  );

  return [...(screen.texts ?? []), ...fromGrids];
}

function buildHtml(spec, imagePath, texts) {
  const families = [...new Set(texts.map((t) => (t.font ?? spec.defaults.font)))];
  const fontLink = families
    .map((f) => `family=${encodeURIComponent(f)}:wght@300;400;500;600;700;800`)
    .join('&');

  return `<!doctype html>
<html><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?${fontLink}&display=swap" rel="stylesheet">
<style>
  html,body{margin:0;padding:0;background:#000}
  #stage{position:relative;width:${spec.width}px;height:${spec.height}px;overflow:hidden}
  #stage img{display:block;width:${spec.width}px;height:${spec.height}px}
</style></head>
<body><div id="stage">
<img src="file://${imagePath}">
${texts.map((t) => renderText(spec, t)).join('\n')}
</div></body></html>`;
}

const browser = await chromium.launch();

for (const specPath of specPaths) {
  const spec = JSON.parse(readFileSync(specPath, 'utf8'));
  const specDir = dirname(specPath);

  const sourceDir = resolve(specDir, sourceOverride ?? spec.source);
  const outDir = resolve(specDir, outOverride ?? spec.out ?? 'out', spec.locale);
  const tmpDir = join(specDir, '.render-tmp');

  if (!existsSync(sourceDir)) {
    console.error(`[ERROR] source folder not found: ${sourceDir}`);
    continue;
  }

  mkdirSync(outDir, { recursive: true });
  mkdirSync(tmpDir, { recursive: true });

  console.log(`\n${basename(specPath)}  (${spec.locale})`);
  console.log(`   source: ${sourceDir}`);

  const page = await browser.newPage({
    viewport: { width: spec.width, height: spec.height },
    deviceScaleFactor: 1,
  });

  let localized = 0;
  let passthrough = 0;

  for (const screen of spec.screens) {
    const source = join(sourceDir, screen.file);
    if (!existsSync(source)) {
      console.log(`   [WARN] ${screen.file} not in source folder, skipped.`);
      continue;
    }

    const texts = expandGrids(screen);
    const htmlPath = join(tmpDir, `${spec.locale}-${screen.file}.html`);

    writeFileSync(htmlPath, buildHtml(spec, source, texts));
    await page.goto(`file://${htmlPath}`);
    await page.evaluate(() => document.fonts.ready);

    await page.locator('#stage').screenshot({ path: join(outDir, screen.file) });

    if (texts.length === 0) passthrough++; else localized++;
    console.log(`   ${screen.file.padEnd(24)} ${String(texts.length).padStart(3)} labels`);
  }

  await page.close();
  console.log(`   -> ${localized} localized, ${passthrough} passed through, written to ${outDir}`);
}

await browser.close();
