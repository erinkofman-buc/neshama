const { test, expect } = require('@playwright/test');
const { FrictionLogger, generateMarkdownReport } = require('../helpers/report');

test.describe('Journey: Caterer Directory', () => {
  let logger;

  test('Caterer evaluates directory listing and vendor detail pages', async ({ page }) => {
    logger = new FrictionLogger('caterer-directory', page);

    // Step 1: Navigate to directory
    await logger.step('directory', async () => {
      await page.goto('/directory');
      await page.waitForSelector('#vendorGrid', { state: 'visible', timeout: 15000 });

      // Filter bar should be visible
      const filterBar = page.locator('.filter-bar, .filter-controls');
      await expect(filterBar.first()).toBeVisible();

      // Vendor cards should be present
      const cards = page.locator('.vendor-card');
      expect(await cards.count()).toBeGreaterThan(0);
    });

    // Step 2: Count initial vendors
    let initialCount;
    await logger.step('all-vendors', async () => {
      const resultCountEl = page.locator('#resultCount');
      const countText = await resultCountEl.textContent();
      initialCount = parseInt(countText.match(/\d+/)?.[0] || '0');

      const cards = page.locator('.vendor-card');
      const cardCount = await cards.count();

      // Counts should match (or be close — result text vs DOM)
      if (initialCount > 0 && Math.abs(initialCount - cardCount) > 1) {
        logger.logFriction('medium', `Result count text (${initialCount}) doesn't match card count (${cardCount})`, 'Ensure #resultCount stays in sync with visible cards');
      }

      expect(cardCount).toBeGreaterThan(0);
    });

    // Step 3: Filter by delivery zone — Toronto
    await logger.step('filter-toronto', async () => {
      const zoneFilter = page.locator('#deliveryZoneFilter');
      await expect(zoneFilter).toBeVisible();

      await zoneFilter.selectOption({ label: 'Toronto' });

      // Wait for filter to take effect
      await page.waitForTimeout(500);

      const filteredCards = page.locator('.vendor-card:visible');
      const filteredCount = await filteredCards.count();

      // Should have results but potentially fewer
      if (filteredCount === 0) {
        logger.logFriction('high', 'Toronto delivery zone filter returned zero results', 'Check delivery zone data for Toronto vendors');
      }
    });

    // Step 4: Filter by delivery zone — Thornhill/Vaughan
    await logger.step('filter-thornhill', async () => {
      const zoneFilter = page.locator('#deliveryZoneFilter');

      // Try different label patterns
      const options = await zoneFilter.locator('option').allTextContents();
      const thornhillOption = options.find(o => /thornhill|vaughan/i.test(o));

      if (thornhillOption) {
        await zoneFilter.selectOption({ label: thornhillOption });
        await page.waitForTimeout(500);

        const filteredCards = page.locator('.vendor-card:visible');
        const filteredCount = await filteredCards.count();

        if (filteredCount === 0) {
          logger.logFriction('medium', 'Thornhill/Vaughan filter returned zero results', 'Check delivery zone data');
        }
      } else {
        logger.logFriction('low', 'No Thornhill/Vaughan option found in delivery zone filter', 'May not be a current delivery zone option');
      }
    });

    // Step 5: Reset delivery filter, toggle COR Kosher
    await logger.step('kosher-filter', async () => {
      // Reset delivery zone
      const zoneFilter = page.locator('#deliveryZoneFilter');
      await zoneFilter.selectOption({ index: 0 });
      await page.waitForTimeout(300);

      // Toggle kosher filter
      const kosherToggle = page.locator('#kosherToggle');
      await expect(kosherToggle).toBeVisible();
      await kosherToggle.click();

      await page.waitForTimeout(500);

      // Verify toggle is active
      const classes = await kosherToggle.getAttribute('class');
      const ariaPressed = await kosherToggle.getAttribute('aria-pressed');

      if (!classes?.includes('active') && ariaPressed !== 'true') {
        logger.logFriction('medium', 'Kosher toggle click did not activate the filter visually', 'Add .active class or aria-pressed on toggle');
      }

      const filteredCards = page.locator('.vendor-card:visible');
      const kosherCount = await filteredCards.count();

      // Should have some kosher vendors
      if (kosherCount === 0) {
        logger.logFriction('high', 'COR Kosher filter returned zero results', 'Check kosher certification data');
      }
    });

    // Step 6: Toggle Delivers (combined with kosher)
    await logger.step('combined-filters', async () => {
      const deliveryToggle = page.locator('#deliveryToggle');
      await expect(deliveryToggle).toBeVisible();
      await deliveryToggle.click();

      await page.waitForTimeout(500);

      const filteredCards = page.locator('.vendor-card:visible');
      const combinedCount = await filteredCards.count();

      // Combined filter may have fewer results
      if (combinedCount === 0) {
        logger.logFriction('medium', 'Combined kosher + delivery filter returned zero results', 'May be too restrictive or data gap');
      }

      // Reset both toggles
      const kosherToggle = page.locator('#kosherToggle');
      const kosherActive = (await kosherToggle.getAttribute('class'))?.includes('active') || (await kosherToggle.getAttribute('aria-pressed')) === 'true';
      if (kosherActive) await kosherToggle.click();

      const deliveryActive = (await deliveryToggle.getAttribute('class'))?.includes('active') || (await deliveryToggle.getAttribute('aria-pressed')) === 'true';
      if (deliveryActive) await deliveryToggle.click();

      await page.waitForTimeout(300);
    });

    // Step 7: Test search
    await logger.step('search', async () => {
      const searchInput = page.locator('#searchInput');
      await expect(searchInput).toBeVisible();

      // Get a vendor name to search for
      const firstCard = page.locator('.vendor-card').first();
      const vendorName = await firstCard.locator('h3').first().textContent();
      const searchTerm = vendorName.split(' ')[0]; // First word of name

      await searchInput.fill(searchTerm);
      await page.waitForTimeout(500);

      const filteredCards = page.locator('.vendor-card:visible');
      const searchCount = await filteredCards.count();

      if (searchCount === 0) {
        logger.logFriction('high', `Search for "${searchTerm}" returned zero results despite being a vendor name`, 'Check search filtering logic');
      }

      // Clear search
      await searchInput.fill('');
      await page.waitForTimeout(300);
    });

    // Step 8: Test neighborhood filter
    await logger.step('neighborhood', async () => {
      const neighborhoodFilter = page.locator('#neighborhoodFilter');
      await expect(neighborhoodFilter).toBeVisible();

      const options = await neighborhoodFilter.locator('option').allTextContents();

      // Select first non-default option
      if (options.length > 1) {
        await neighborhoodFilter.selectOption({ index: 1 });
        await page.waitForTimeout(500);

        const filteredCards = page.locator('.vendor-card:visible');
        const nhCount = await filteredCards.count();

        if (nhCount === 0) {
          logger.logFriction('medium', `Neighborhood filter "${options[1]}" returned zero results`, 'Check neighborhood data mapping');
        }

        // Reset
        await neighborhoodFilter.selectOption({ index: 0 });
        await page.waitForTimeout(300);
      } else {
        logger.logFriction('medium', 'Neighborhood filter has no options beyond default', 'Populate neighborhood filter with vendor areas');
      }
    });

    // Step 9: Click into vendor detail page
    let vendorDetailUrl;
    await logger.step('vendor-detail', async () => {
      const firstCard = page.locator('.vendor-card').first();
      const cardLink = firstCard.locator('a').first();

      // If the card itself is a link, click it; otherwise find the link inside
      const href = await firstCard.evaluate(el => {
        if (el.tagName === 'A') return el.href;
        const link = el.querySelector('a');
        return link ? link.href : el.dataset.href || '';
      });

      await firstCard.click();
      await page.waitForURL(/\/directory\//, { timeout: 15000 });
      vendorDetailUrl = page.url();

      await page.waitForSelector('#mainContent', { state: 'visible', timeout: 15000 });
    });

    // Step 10: Verify vendor detail content
    await logger.step('detail-content', async () => {
      // Vendor name
      const vendorName = page.locator('#vendorName');
      await expect(vendorName).toBeVisible();

      // Category
      const category = page.locator('#vendorCategory');
      await expect(category).toBeVisible();

      // Description
      const desc = page.locator('#vendorDesc');
      if (await desc.isVisible()) {
        const text = await desc.textContent();
        if (!text.trim()) {
          logger.logFriction('low', 'Vendor description is empty', 'Encourage vendors to add descriptions');
        }
      }

      // Info rows (contact details)
      const infoRows = page.locator('.info-row');
      expect(await infoRows.count()).toBeGreaterThan(0);

      await logger.checkAccessibility('#mainContent');
    });

    // Step 11: Check website click tracking
    await logger.step('click-tracking', async () => {
      const websiteLink = page.locator('a[href*="/api/track-click"], a[href*="track-click"]');
      const hasTrackingLink = (await websiteLink.count()) > 0;

      if (hasTrackingLink) {
        const href = await websiteLink.first().getAttribute('href');
        expect(href).toContain('/api/track-click');
        expect(href).toContain('vendor=');
      } else {
        // Check for direct website links as fallback
        const directLink = page.locator('.info-row a[href^="http"]');
        if (await directLink.count() > 0) {
          logger.logFriction('medium', 'Vendor website link is a direct link, not routed through click tracking', 'Route website links through /api/track-click for analytics');
        } else {
          logger.logFriction('low', 'No website link found on vendor detail page', 'Data-dependent — this vendor may not have a website');
        }
      }
    });

    // Step 12: Intercept click tracking redirect
    await logger.step('redirect-verified', async () => {
      const websiteLink = page.locator('a[href*="/api/track-click"]');
      const hasTrackingLink = (await websiteLink.count()) > 0;

      if (hasTrackingLink) {
        const href = await websiteLink.first().getAttribute('href');
        const fullUrl = new URL(href, page.url()).toString();

        // Set up route interception to catch the redirect without following it
        let interceptedUrl = null;
        await page.route('**/api/track-click**', async (route) => {
          interceptedUrl = route.request().url();
          // Fetch the redirect response without following it
          const response = await route.fetch({ maxRedirects: 0 }).catch(() => null);
          if (response) {
            const status = response.status();
            const location = response.headers()['location'];

            if (status >= 300 && status < 400 && location) {
              // Verified: tracking endpoint returns redirect
              expect(location).toBeTruthy();
            }
          }
          // Abort the navigation to stay on the page
          await route.abort();
        });

        // Click the link
        await websiteLink.first().click().catch(() => {});

        // Wait a moment for the route to be intercepted
        await page.waitForTimeout(1000);

        // Unroute to clean up
        await page.unroute('**/api/track-click**');

        if (!interceptedUrl) {
          logger.logFriction('low', 'Click tracking redirect could not be verified via interception', 'May need manual verification of tracking endpoint');
        }
      } else {
        logger.logFriction('low', 'No click tracking link to verify redirect', 'Skipping redirect verification');
      }
    });

    // Step 13: Check card-level website links on directory
    await logger.step('card-links', async () => {
      await page.goto('/directory');
      await page.waitForSelector('#vendorGrid', { state: 'visible', timeout: 15000 });
      await page.waitForTimeout(1000);

      // Check if vendor cards have website links using track-click
      const cardLinks = page.locator('.vendor-card a[href*="/api/track-click"]');
      const trackingCount = await cardLinks.count();

      const directLinks = page.locator('.vendor-card a[href^="http"]');
      const directCount = await directLinks.count();

      if (trackingCount > 0) {
        // Good — cards use tracking links
        expect(trackingCount).toBeGreaterThan(0);
      } else if (directCount > 0) {
        logger.logFriction('medium', `Found ${directCount} direct website links on directory cards not routed through click tracking`, 'Update card website links to use /api/track-click');
      } else {
        // No website links on cards — may be by design
        logger.logFriction('low', 'No website links found on directory vendor cards', 'Cards may intentionally omit website links');
      }

      await logger.checkLinks('#vendorGrid');
    });

    // Generate report
    const result = logger.generateReport();

    const fs = require('fs');
    const path = require('path');
    const resultsDir = path.join(__dirname, '..', 'test-results');
    const jsonFiles = fs.readdirSync(resultsDir).filter(f => f.endsWith('.json'));
    if (jsonFiles.length >= 3) {
      generateMarkdownReport();
    }
  });
});
