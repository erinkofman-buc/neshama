#!/usr/bin/env node
/**
 * Render frontend/the-shiva-guide.html → frontend/the-shiva-guide.pdf
 *
 * Uses Playwright (chromium) from tests/node_modules. The rendered PDF is
 * the asset that gets emailed to lead-magnet subscribers via SendGrid.
 *
 * Usage:  node tools/render_shiva_guide_pdf.js
 *
 * Re-run any time the page content changes. Commit the PDF to git so it
 * ships with deploys (Render serves it as a static asset).
 */
const { chromium } = require('../tests/node_modules/playwright');
const path = require('path');
const fs = require('fs');

async function main() {
    const repoRoot = path.resolve(__dirname, '..');
    const htmlPath = path.join(repoRoot, 'frontend', 'the-shiva-guide.html');
    const pdfPath  = path.join(repoRoot, 'frontend', 'the-shiva-guide.pdf');

    if (!fs.existsSync(htmlPath)) {
        console.error(`ERROR: ${htmlPath} not found`);
        process.exit(1);
    }

    console.log(`Rendering ${path.basename(htmlPath)} → PDF...`);

    const browser = await chromium.launch();
    const page = await browser.newPage();
    await page.goto(`file://${htmlPath}`, { waitUntil: 'networkidle' });
    await page.emulateMedia({ media: 'print' });
    await page.pdf({
        path: pdfPath,
        format: 'Letter',
        printBackground: true,
        margin: { top: '0.5in', bottom: '0.5in', left: '0.5in', right: '0.5in' }
    });
    await browser.close();

    const sizeKb = (fs.statSync(pdfPath).size / 1024).toFixed(1);
    console.log(`✓ ${path.basename(pdfPath)} (${sizeKb} KB)`);
}

main().catch(err => {
    console.error('PDF render failed:', err);
    process.exit(1);
});
