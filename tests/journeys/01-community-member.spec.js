const { test, expect } = require('@playwright/test');
const { FrictionLogger, generateMarkdownReport } = require('../helpers/report');

test.describe('Journey: Grieving Community Member', () => {
  let logger;

  test('Community member browses obituaries and explores shiva support', async ({ page }) => {
    logger = new FrictionLogger('community-member', page);

    // Dismiss email popup before navigating to prevent interference
    await page.addInitScript(() => {
      localStorage.setItem('neshama_popup_dismissed', Date.now().toString());
    });

    // Step 1: Land on home page
    await logger.step('home-page', async () => {
      await page.goto('/');
      await expect(page).toHaveTitle(/Neshama/i);
      await expect(page.locator('.top-nav, .nav')).toBeVisible();

      // Check for a CTA to view obituaries
      const feedLink = page.locator('a:has-text("View Obituaries"), a:has-text("Feed"), a.nav-link[href*="feed"]');
      await expect(feedLink.first()).toBeVisible();
    });

    // Step 2: Navigate to feed
    await logger.step('navigate-to-feed', async () => {
      const feedLink = page.locator('a:has-text("View Obituaries"), a:has-text("Feed"), a.nav-link[href*="feed"]');
      await feedLink.first().click();
      await page.waitForURL(/\/(feed|index)/);
      await expect(page.locator('#feed')).toBeVisible();
    });

    // Step 3: Wait for obituary cards to load
    await logger.step('cards-loaded', async () => {
      // "Today" filter may show no results — expand to "Month" if needed
      let cards = page.locator('.obituary-card');
      let count = await cards.count();

      if (count === 0) {
        const monthTab = page.locator('.tab[data-tab="month"], .tab:has-text("Month")').first();
        if (await monthTab.isVisible()) {
          await monthTab.click();
          await page.waitForTimeout(1000);
        }
      }

      await page.waitForSelector('.obituary-card', { timeout: 15000 });
      cards = page.locator('.obituary-card');
      count = await cards.count();
      expect(count).toBeGreaterThan(0);

      // Check if cards have visible class (animated in)
      const firstCard = cards.first();
      const classes = await firstCard.getAttribute('class');
      if (!classes.includes('visible')) {
        logger.logFriction('low', 'Obituary cards may not have .visible class applied', 'Check card animation/visibility logic');
      }
    });

    // Step 4: Check feed filters
    await logger.step('filters', async () => {
      await expect(page.locator('#searchBox')).toBeVisible();

      const cityButtons = page.locator('.city-btn');
      expect(await cityButtons.count()).toBeGreaterThan(0);

      const tabs = page.locator('.tab');
      expect(await tabs.count()).toBeGreaterThan(0);

      // Verify filters are interactive
      const searchBox = page.locator('#searchBox');
      await expect(searchBox).toBeEnabled();
    });

    // Step 5: Click first obituary card
    let memorialUrl;
    await logger.step('click-obituary', async () => {
      const firstCard = page.locator('.obituary-card').first();
      const link = firstCard.locator('a').first();

      // Get the href before clicking
      const href = await link.getAttribute('href');
      await firstCard.click();

      await page.waitForURL(/\/memorial\//, { timeout: 15000 });
      memorialUrl = page.url();
    });

    // Step 6: Check memorial content
    await logger.step('memorial-content', async () => {
      // Wait for content to load
      await page.waitForSelector('#memorialContent', { state: 'visible', timeout: 15000 }).catch(() => {
        // Some pages use different container
      });

      // Deceased name should be visible
      const nameEl = page.locator('#heroName, #deceasedName, .hero-name');
      await expect(nameEl.first()).toBeVisible();

      // Check for photo or placeholder
      const photo = page.locator('#heroPhotoArea, .hero-photo-wrapper, .hero-initials');
      await expect(photo.first()).toBeVisible();
    });

    // Step 7: Check shiva/service info section
    let hasServices = false;
    await logger.step('shiva-info', async () => {
      const servicesSection = page.locator('#servicesSection');
      const supportSection = page.locator('#supportSection');

      hasServices = await servicesSection.isVisible().catch(() => false);
      const hasSupport = await supportSection.isVisible().catch(() => false);

      if (!hasServices && !hasSupport) {
        logger.logFriction('low', 'No services or support section visible on this memorial', 'May be data-dependent — not all obituaries have shiva info');
      }
    });

    // Step 8: Check "Support the Family" section
    let hasShivaSupport = false;
    let shivaId = null;
    await logger.step('support-section', async () => {
      const supportCard = page.locator('#supportCard');
      const isVisible = await supportCard.isVisible().catch(() => false);

      if (isVisible) {
        const content = await supportCard.textContent();

        // Check for shiva support link
        const shivaLink = page.locator('#supportCard a[href*="/shiva/"]');
        hasShivaSupport = (await shivaLink.count()) > 0;

        if (hasShivaSupport) {
          const href = await shivaLink.first().getAttribute('href');
          shivaId = href.match(/\/shiva\/(\d+)/)?.[1];
        }

        // Check for organize CTA
        const organizeCta = page.locator('#supportCard a[href*="/shiva/organize"]');
        const hasOrganizeCta = (await organizeCta.count()) > 0;

        if (!hasShivaSupport && !hasOrganizeCta) {
          logger.logFriction('medium', 'Support card visible but has no shiva link or organize CTA', 'Ensure support section always has a clear call to action');
        }
      } else {
        logger.logFriction('low', 'Support section not visible on this memorial page', 'Data-dependent — this obituary may not have support set up');
      }
    });

    // Step 9: Navigate to shiva page (if available)
    if (hasShivaSupport && shivaId) {
      await logger.step('shiva-page', async () => {
        await page.goto(`/shiva/${shivaId}`);
        await page.waitForSelector('#mainContent', { state: 'visible', timeout: 15000 });
        await expect(page.locator('#calendarSection, #mealCalendar')).toBeVisible();
      });

      // Step 10: Check meal signup modal
      await logger.step('signup-modal', async () => {
        const availableSlot = page.locator('.meal-slot.available').first();
        const hasSlot = (await availableSlot.count()) > 0;

        if (hasSlot) {
          await availableSlot.click();
          await expect(page.locator('#signupModal')).toBeVisible();
          await expect(page.locator('#volName')).toBeVisible();
          await expect(page.locator('#volEmail')).toBeVisible();
          await expect(page.locator('#volConsent')).toBeVisible();
        } else {
          logger.logFriction('low', 'No available meal slots found on shiva page', 'All slots may be taken — data-dependent');
        }
      });

      // Step 11: Fill form but DO NOT submit
      await logger.step('form-filled', async () => {
        const modal = page.locator('#signupModal');
        if (await modal.isVisible()) {
          await page.locator('#volName').fill('Test Community Member');
          await page.locator('#volEmail').fill('test@example.com');
          await page.locator('#volConsent').check();

          // Verify submit button is enabled
          const submitBtn = page.locator('#signupSubmitBtn');
          await expect(submitBtn).toBeVisible();

          // Close modal without submitting
          const cancelBtn = page.locator('#signupCancelBtn');
          if (await cancelBtn.isVisible()) {
            await cancelBtn.click();
          } else {
            await page.keyboard.press('Escape');
          }
        }
      });
    } else {
      // Fallback: test organize CTA
      await logger.step('shiva-page-fallback', async () => {
        logger.logFriction('low', 'No shiva support page found — testing organize CTA instead', 'This is data-dependent, not a bug');

        const organizeCta = page.locator('a[href*="/shiva/organize"]').first();
        if (await organizeCta.isVisible()) {
          const href = await organizeCta.getAttribute('href');
          expect(href).toContain('/shiva/organize');
        }
      });

      await logger.step('signup-modal-fallback', async () => {
        // Skip — no shiva page to test
      });

      await logger.step('form-filled-fallback', async () => {
        // Skip — no shiva page to test
      });
    }

    // Step 12: Check page footer links
    await logger.step('footer', async () => {
      // Navigate back to feed for footer check
      await page.goto('/feed');
      await page.waitForSelector('.site-footer', { timeout: 10000 });

      await logger.checkLinks('.site-footer');
      await logger.checkAccessibility('.site-footer');
    });

    // Generate report
    const result = logger.generateReport();

    // If this is the last journey, generate the full markdown report
    const fs = require('fs');
    const path = require('path');
    const resultsDir = path.join(__dirname, '..', 'test-results');
    const jsonFiles = fs.readdirSync(resultsDir).filter(f => f.endsWith('.json'));
    if (jsonFiles.length >= 3) {
      generateMarkdownReport();
    }
  });
});
