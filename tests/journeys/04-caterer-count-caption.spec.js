const { test, expect } = require('@playwright/test');
const http = require('http');
const fs = require('fs');
const path = require('path');

// Regression guard for the "18 caterers listed / 14 shown" drift.
//
// The stats banner on /shiva/caterers must report the count of the caterer
// list it is ACTUALLY showing, not a number from a separate source
// (/api/directory-stats used to win and could disagree with /api/caterers).
//
// This test is self-contained: it serves the real shiva-caterers.html over a
// throwaway local server and mocks the API responses so the two sources
// deliberately DISAGREE (API returns 14 caterers, directory-stats says 18).
// A correct page shows 14 (the rendered count); the old bug showed 18.

const PAGE_HTML = fs.readFileSync(
  path.join(__dirname, '..', '..', 'frontend', 'shiva-caterers.html'),
  'utf8'
);

const CATERER_COUNT = 14;
const STALE_STAT_COUNT = 18; // what /api/directory-stats would wrongly report

function makeCaterers(n) {
  return Array.from({ length: n }, (_, i) => ({
    business_name: 'Test Caterer ' + (i + 1),
    delivery_area: 'Toronto',
    shiva_menu_description: 'Shiva meal trays and platters.',
    kosher_level: i % 2 === 0 ? 'kosher' : '',
    has_delivery: true,
    has_online_ordering: false,
    slug: 'test-caterer-' + (i + 1),
    phone: '(416) 555-0' + String(100 + i),
  }));
}

let server;
let baseURL;

test.beforeAll(async () => {
  server = http.createServer((req, res) => {
    // Serve the page itself for any non-API GET; API calls are mocked in-page.
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(PAGE_HTML);
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address();
  baseURL = `http://127.0.0.1:${port}`;
});

test.afterAll(async () => {
  if (server) await new Promise((resolve) => server.close(resolve));
});

test.describe('Caterer count caption', () => {
  test('banner number equals the rendered caterer card count', async ({ page }) => {
    // Mock the two endpoints so they DISAGREE on purpose.
    await page.route('**/api/caterers**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', data: makeCaterers(CATERER_COUNT) }),
      });
    });
    await page.route('**/api/directory-stats**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', data: { caterer_count: STALE_STAT_COUNT } }),
      });
    });

    await page.goto(`${baseURL}/shiva/caterers`);

    // Wait for the cards to render.
    await page.waitForSelector('.caterer-card', { state: 'attached', timeout: 15000 });

    const cardCount = await page.locator('.caterer-card').count();
    const bannerText = (await page.locator('#statCaterers').textContent()).trim();
    const bannerNum = parseInt(bannerText, 10);

    // Sanity: the mock actually drove the list.
    expect(cardCount).toBe(CATERER_COUNT);

    // The contract: banner == rendered cards, and it did NOT pick up the
    // stale directory-stats number.
    expect(bannerNum).toBe(cardCount);
    expect(bannerNum).not.toBe(STALE_STAT_COUNT);
  });

  test('banner stays in sync after a filter narrows the list', async ({ page }) => {
    let firstCall = true;
    await page.route('**/api/caterers**', async (route) => {
      // First (unfiltered) load returns 14; any filtered load returns 6.
      const n = firstCall ? CATERER_COUNT : 6;
      firstCall = false;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', data: makeCaterers(n) }),
      });
    });
    await page.route('**/api/directory-stats**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'success', data: { caterer_count: STALE_STAT_COUNT } }),
      });
    });

    await page.goto(`${baseURL}/shiva/caterers`);
    await page.waitForSelector('.caterer-card', { state: 'attached', timeout: 15000 });
    expect(await page.locator('.caterer-card').count()).toBe(CATERER_COUNT);

    // Apply the Kosher filter -> triggers a new /api/caterers load (now 6).
    await page.locator('[data-filter="kosher"]').click();
    await expect(page.locator('.caterer-card')).toHaveCount(6);

    const bannerNum = parseInt((await page.locator('#statCaterers').textContent()).trim(), 10);
    expect(bannerNum).toBe(6);
  });
});
