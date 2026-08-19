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
import { dirname, resolve, join, basename, extname } from 'path';
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

const MIME = { woff2: 'font/woff2', woff: 'font/woff', ttf: 'font/ttf', otf: 'font/otf' };
const FORMAT = { woff2: 'woff2', woff: 'woff', ttf: 'truetype', otf: 'opentype' };

/**
 * The project's own font files, inlined as data URIs.
 *
 * A local file has to be embedded rather than linked: the render page lives on file://, and a
 * font fetched from there is refused. Embedding also removes the failure mode that matters most
 * here - a missing font does not throw, the browser quietly falls back to something else and the
 * render looks almost right, which is far worse than an error.
 */
function fontFaces(spec, specDir) {
  return (spec.fonts ?? []).map((f) => {
    const file = resolve(specDir, f.src);
    if (!existsSync(file)) {
      console.error(`[ERROR] font file not found: ${file}`);
      process.exit(1);
    }

    const ext = extname(file).slice(1).toLowerCase();
    if (!FORMAT[ext]) {
      console.error(`[ERROR] unsupported font format '${ext}' (${file}). Use woff2, woff, ttf or otf.`);
      process.exit(1);
    }

    const data = readFileSync(file).toString('base64');

    return `@font-face{font-family:'${f.family}';` +
      `font-weight:${f.weight ?? 400};font-style:${f.style ?? 'normal'};` +
      `src:url(data:${MIME[ext]};base64,${data}) format('${FORMAT[ext]}');font-display:block}`;
  }).join('\n');
}

function buildHtml(spec, specDir, imagePath, texts) {
  const local = new Set((spec.fonts ?? []).map((f) => f.family));
  const families = [...new Set(texts.map((t) => (t.font ?? spec.defaults.font)))];

  // only families without a local file are asked of google fonts
  const remote = families.filter((f) => !local.has(f));
  const fontLink = remote
    .map((f) => `family=${encodeURIComponent(f)}:wght@300;400;500;600;700;800`)
    .join('&');

  const googleFonts = remote.length
    ? `<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?${fontLink}&display=swap" rel="stylesheet">`
    : '';

  return `<!doctype html>
<html><head><meta charset="utf-8">
${googleFonts}
<style>
${fontFaces(spec, specDir)}
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

    writeFileSync(htmlPath, buildHtml(spec, specDir, source, texts));
    await page.goto(`file://${htmlPath}`);
    await page.evaluate(() => document.fonts.ready);

    // a font that failed to load does not throw, it silently substitutes, and the render then
    // looks almost right - which is worse than an error. document.fonts.check() is no use here:
    // it answers true for a family that was never defined. Measuring is the only honest test:
    // if "X", monospace renders exactly as wide as monospace alone, X never resolved
    const families = [...new Set(texts.map((t) => t.font ?? spec.defaults.font))];
    const missing = await page.evaluate((families) => {
      const canvas = document.createElement('canvas').getContext('2d');
      const probe = 'MMMWWWiiillo0123456789';

      const width = (font) => {
        canvas.font = `500 72px ${font}`;
        return canvas.measureText(probe).width;
      };

      return families.filter((f) =>
        ['monospace', 'serif'].every((fb) => width(`"${f}", ${fb}`) === width(fb))
      );
    }, families);

    for (const family of missing) {
      console.log(`   [WARN] '${family}' did not resolve - the render fell back to another face.`);
    }

    await page.locator('#stage').screenshot({ path: join(outDir, screen.file) });

    if (texts.length === 0) passthrough++; else localized++;
    console.log(`   ${screen.file.padEnd(24)} ${String(texts.length).padStart(3)} labels`);
  }

  await page.close();
  console.log(`   -> ${localized} localized, ${passthrough} passed through, written to ${outDir}`);
}

await browser.close();
