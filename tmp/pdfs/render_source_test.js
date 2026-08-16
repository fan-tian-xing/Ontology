const { chromium } = require('C:/Users/尹仕程/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const { pathToFileURL } = require('url');
const fs = require('fs');

const source = 'D:/本体/汽轮机安调项目/项目初期demo/汽轮机本体安装及维护说明书 _ PDF.mhtml';
const outputDir = 'D:/obsidian笔记库/本体论一些知识/output/playwright/source-test';
fs.mkdirSync(outputDir, { recursive: true });

const fontCss = Array.from({ length: 7 }, (_, index) => {
  const name = String(index).padStart(4, '0');
  const data = fs.readFileSync(`D:/obsidian笔记库/本体论一些知识/tmp/pdfs/fonts/${name}.woff2`).toString('base64');
  return `@font-face { font-family: ff${index}; src: url(data:font/woff2;base64,${data}) format('woff2'); font-style: normal; font-weight: ${index === 5 ? 'bold' : 'normal'}; }`;
}).join('\n');

let browser;
(async () => {
  browser = await chromium.launch({
    headless: true,
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    args: ['--allow-file-access-from-files', '--disable-web-security'],
  });
  const context = await browser.newContext({
    viewport: { width: 1200, height: 1500 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();
  page.on('console', (message) => {
    if (message.type() === 'error') console.log('browser-console-error', message.text());
  });
  page.on('pageerror', (error) => console.log('browser-page-error', error.message));
  await page.goto(pathToFileURL(source).href, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForSelector('#outer_page_1', { timeout: 30000 });
  await page.evaluate(() => {
    window.__documentPageFragments = {};
    for (let number = 1; number <= 94; number += 1) {
      const element = document.getElementById(`page${number}`);
      if (element) window.__documentPageFragments[number] = element.outerHTML;
    }
  });

  for (const pageNumber of [1, 2, 10, 25, 50, 75, 92, 93, 94]) {
    const dimensions = await page.evaluate((number) => {
      const holder = document.createElement('div');
      holder.innerHTML = window.__documentPageFragments[number];
      const element = holder.firstElementChild;
      return {
        width: parseInt(element.style.width, 10),
        height: parseInt(element.style.height, 10),
      };
    }, pageNumber);
    await page.setViewportSize(dimensions);
    await page.evaluate(async ({ number, css }) => {
      document.body.innerHTML = `<main id="isolated-page">${window.__documentPageFragments[number]}</main>`;
      let style = document.getElementById('reconstruction-overrides');
      if (!style) {
        style = document.createElement('style');
        style.id = 'reconstruction-overrides';
        document.head.appendChild(style);
      }
      style.textContent = `${css}\nhtml, body { margin: 0 !important; padding: 0 !important; overflow: hidden !important; background: white !important; }\n#isolated-page { margin: 0 !important; padding: 0 !important; width: max-content; height: max-content; }\n.newpage { transform: none !important; transform-origin: left top !important; display: block !important; margin: 0 !important; }\n.ff0, .ff1, .ff2, .ff3, .ff4, .ff5, .ff6 { display: unset !important; }\n.text_layer [style*="opacity: 0.50"], .text_layer [style*="opacity:0.50"], .text_layer [style*="opacity: 0.5"], .text_layer [style*="opacity:0.5"] { display: none !important; }`;
      const pageElement = document.getElementById(`page${number}`);
      pageElement.style.transform = 'none';
      pageElement.style.transformOrigin = 'left top';
      pageElement.style.display = 'block';
      for (const image of pageElement.querySelectorAll('img.absimg')) {
        const original = image.getAttribute('orig');
        if (original && !image.src) image.src = original.replace('http://html.scribd.com/', 'https://html.scribdassets.com/');
      }
      await document.fonts.ready;
      await Promise.all([...pageElement.querySelectorAll('img')].map((image) => {
        if (image.complete) return Promise.resolve();
        return new Promise((resolve) => {
          image.addEventListener('load', resolve, { once: true });
          image.addEventListener('error', resolve, { once: true });
          setTimeout(resolve, 10000);
        });
      }));
    }, { number: pageNumber, css: fontCss });
    const target = page.locator(`#page${pageNumber}`);
    const info = await target.evaluate((element) => ({
      width: element.offsetWidth,
      height: element.offsetHeight,
      textLength: element.innerText.length,
      images: element.querySelectorAll('img').length,
    }));
    console.log('page', pageNumber, info);
    await page.screenshot({
      path: `${outputDir}/isolated-page-${pageNumber}.png`,
      clip: { x: 0, y: 0, width: dimensions.width, height: dimensions.height },
    });
  }
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
}).finally(async () => {
  if (browser) await browser.close();
});
