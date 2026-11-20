// Renders an HTML file to a single-page 12in x 8in PDF (same page size as the original FUSE quotes).
// Usage: node render.js input.html output.pdf
const path = require('path');
const { chromium } = require('playwright');

const [, , htmlPath, pdfPath] = process.argv;
if (!htmlPath || !pdfPath) {
  console.error('usage: node render.js input.html output.pdf');
  process.exit(1);
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + path.resolve(htmlPath), { waitUntil: 'networkidle' });
  await page.pdf({
    path: pdfPath,
    width: '12in',
    height: '8in',
    printBackground: true,
    margin: { top: 0, right: 0, bottom: 0, left: 0 },
  });
  await browser.close();
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
