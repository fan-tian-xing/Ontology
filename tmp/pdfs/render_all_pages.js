const { chromium } = require('C:/Users/尹仕程/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const { pathToFileURL } = require('url');
const fs = require('fs');

const source = 'D:/本体/汽轮机安调项目/项目初期demo/汽轮机本体安装及维护说明书 _ PDF.mhtml';
const outputDir = 'D:/obsidian笔记库/本体论一些知识/output/playwright/document-pages';
fs.mkdirSync(outputDir, { recursive: true });

const fontCss = Array.from({ length: 7 }, (_, index) => {
  const name = String(index).padStart(4, '0');
  const path = `D:/obsidian笔记库/本体论一些知识/tmp/pdfs/fonts/${name}.woff2`;
  const data = fs.readFileSync(path).toString('base64');
  const weight = index === 5 ? 'bold' : 'normal';
  return `@font-face { font-family: ff${index}; src: url(data:font/woff2;base64,${data}) format('woff2'); font-style: normal; font-weight: ${weight}; }`;
}).join('\n');

const overrideCss = `${fontCss}
html, body { margin: 0 !important; padding: 0 !important; overflow: hidden !important; background: white !important; }
#isolated-page { margin: 0 !important; padding: 0 !important; width: max-content; height: max-content; }
.newpage { transform: none !important; transform-origin: left top !important; display: block !important; margin: 0 !important; }
.ff0, .ff1, .ff2, .ff3, .ff4, .ff5, .ff6 { display: unset !important; }
.text_layer [style*="opacity: 0.50"],
.text_layer [style*="opacity:0.50"],
.text_layer [style*="opacity: 0.5"],
.text_layer [style*="opacity:0.5"] { display: none !important; }
`;

let browser;
(async () => {
  browser = await chromium.launch({
    headless: true,
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  });
  const context = await browser.newContext({
    viewport: { width: 902, height: 1276 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();
  await page.goto(pathToFileURL(source).href, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForSelector('#page1', { timeout: 30000 });

  const extracted = await page.evaluate(() => {
    const fragments = {};
    const dimensions = {};
    for (let number = 1; number <= 94; number += 1) {
      const element = document.getElementById(`page${number}`);
      if (!element) continue;
      fragments[number] = element.outerHTML;
      dimensions[number] = {
        width: parseInt(element.style.width, 10),
        height: parseInt(element.style.height, 10),
      };
    }
    window.__documentPageFragments = fragments;
    return { dimensions, count: Object.keys(fragments).length };
  });
  if (extracted.count !== 94) throw new Error(`Expected 94 pages, found ${extracted.count}`);

  const manifest = [];
  for (let number = 1; number <= 94; number += 1) {
    const dimensions = extracted.dimensions[number];
    await page.setViewportSize(dimensions);
    const metrics = await page.evaluate(async ({ pageNumber, css }) => {
      document.body.innerHTML = `<main id="isolated-page">${window.__documentPageFragments[pageNumber]}</main>`;
      let style = document.getElementById('reconstruction-overrides');
      if (!style) {
        style = document.createElement('style');
        style.id = 'reconstruction-overrides';
        document.head.appendChild(style);
      }
      style.textContent = css;
      const pageElement = document.getElementById(`page${pageNumber}`);
      await document.fonts.ready;
      await Promise.all([...pageElement.querySelectorAll('img')].map((image) => {
        if (image.complete) return Promise.resolve();
        return new Promise((resolve) => {
          image.addEventListener('load', resolve, { once: true });
          image.addEventListener('error', resolve, { once: true });
          setTimeout(resolve, 10000);
        });
      }));
      const images = [...pageElement.querySelectorAll('img')];
      const hiddenDuplicates = [...pageElement.querySelectorAll('.text_layer [style]')]
        .filter((element) => getComputedStyle(element).display === 'none').length;
      return {
        textLength: pageElement.innerText.trim().length,
        imageCount: images.length,
        failedImageCount: images.filter((image) => !image.complete || image.naturalWidth === 0).length,
        hiddenDuplicates,
      };
    }, { pageNumber: number, css: overrideCss });
    const filename = `page-${String(number).padStart(3, '0')}.png`;
    await page.screenshot({
      path: `${outputDir}/${filename}`,
      clip: { x: 0, y: 0, width: dimensions.width, height: dimensions.height },
    });
    manifest.push({ page: number, filename, ...dimensions, ...metrics });
    if (number === 1 || number % 10 === 0 || number === 94) {
      console.log(`rendered ${number}/94`);
    }
  }
  fs.writeFileSync(`${outputDir}/manifest.json`, JSON.stringify(manifest, null, 2), 'utf8');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
}).finally(async () => {
  if (browser) await browser.close();
});
