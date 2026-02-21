const { test, expect } = require('@playwright/test');
const { FrictionLogger, generateMarkdownReport } = require('../helpers/report');

test.describe('Journey: Shiva Organizer', () => {
  let logger;

  test('Organizer sets up shiva support page through wizard', async ({ page }) => {
    logger = new FrictionLogger('shiva-organizer', page);

    // Step 1: Navigate to organize wizard
    await logger.step('wizard-start', async () => {
      await page.goto('/shiva/organize');
      await page.waitForSelector('#step1', { state: 'visible', timeout: 15000 });

      await expect(page.locator('#organizerName')).toBeVisible();
      await expect(page.locator('#organizerEmail')).toBeVisible();
      await expect(page.locator('#organizerPhone')).toBeVisible();
      await expect(page.locator('#organizerRelationship')).toBeVisible();
    });

    // Step 2: Fill step 1 — organizer info
    await logger.step('step1-filled', async () => {
      await page.locator('#organizerName').fill('Sarah Cohen');
      await page.locator('#organizerEmail').fill('sarah.cohen@example.com');
      await page.locator('#organizerPhone').fill('416-555-0123');

      // Select relationship
      const relationship = page.locator('#organizerRelationship');
      if ((await relationship.evaluate(el => el.tagName)) === 'SELECT') {
        await relationship.selectOption({ index: 1 });
      } else {
        await relationship.fill('Family Friend');
      }

      // Check privacy consent if present on step 1
      const consent = page.locator('#privacyConsent1');
      if (await consent.isVisible()) {
        await consent.check();
      }
    });

    // Step 3: Advance to step 2
    await logger.step('step2', async () => {
      // Find and click the next/continue button for step 1
      const nextBtn = page.locator('#step1 button:has-text("Next"), #step1 button:has-text("Continue"), button.btn-primary:visible').first();
      await nextBtn.click();

      await expect(page.locator('#step2')).toBeVisible({ timeout: 5000 });
    });

    // Step 4: Fill step 2 — family/shiva info
    await logger.step('step2-filled', async () => {
      await page.locator('#familyName').fill('The Goldstein Family');

      await page.locator('#shivaAddress').fill('123 Bathurst Street');

      const cityField = page.locator('#shivaCity');
      if ((await cityField.evaluate(el => el.tagName)) === 'SELECT') {
        await cityField.selectOption({ index: 1 });
      } else {
        await cityField.fill('Toronto');
      }

      // Fill date fields
      const startDate = page.locator('#shivaStartDate');
      const endDate = page.locator('#shivaEndDate');

      if (await startDate.isVisible()) {
        // Set dates to tomorrow through 5 days from now
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        const endDay = new Date();
        endDay.setDate(endDay.getDate() + 5);

        await startDate.fill(tomorrow.toISOString().split('T')[0]);
        await endDate.fill(endDay.toISOString().split('T')[0]);
      }

      // Fill dietary notes if present
      const dietary = page.locator('#dietaryNotes');
      if (await dietary.isVisible()) {
        await dietary.fill('Strictly kosher. No nuts due to allergies.');
      }

      // Fill special instructions if present
      const instructions = page.locator('#specialInstructions');
      if (await instructions.isVisible()) {
        await instructions.fill('Please use side entrance. Ring buzzer #3.');
      }
    });

    // Step 5: Advance to step 3 (review)
    await logger.step('step3-review', async () => {
      const nextBtn = page.locator('#step2 button:has-text("Next"), #step2 button:has-text("Review"), #step2 button.btn-primary:visible').first();
      await nextBtn.click();

      await expect(page.locator('#step3')).toBeVisible({ timeout: 5000 });

      // Verify review summary shows entered data
      const reviewSummary = page.locator('#reviewSummary');
      if (await reviewSummary.isVisible()) {
        const text = await reviewSummary.textContent();
        // Check that at least some of our entered data appears
        const hasOrganizerName = text.includes('Sarah Cohen');
        const hasFamilyName = text.includes('Goldstein');

        if (!hasOrganizerName && !hasFamilyName) {
          logger.logFriction('high', 'Review summary does not display entered data', 'Ensure review step reflects all form inputs');
        }
      }
    });

    // Step 6: Verify submit button exists but DO NOT click
    await logger.step('ready-to-submit', async () => {
      const submitBtn = page.locator('#submitBtn, #step3 button:has-text("Submit"), #step3 button:has-text("Create"), #step3 button.btn-primary').first();
      await expect(submitBtn).toBeVisible();

      // Verify it looks enabled (not disabled)
      const isDisabled = await submitBtn.isDisabled();
      if (isDisabled) {
        logger.logFriction('high', 'Submit button is disabled on review step even after filling all fields', 'Check form validation logic');
      }
    });

    // Step 7: Navigate back to step 1
    await logger.step('back-nav', async () => {
      // Click back from step 3 to step 2
      const backBtn3 = page.locator('#step3 button:has-text("Back"), #step3 button.btn-secondary').first();
      if (await backBtn3.isVisible()) {
        await backBtn3.click();
        await expect(page.locator('#step2')).toBeVisible({ timeout: 5000 });
      }

      // Click back from step 2 to step 1
      const backBtn2 = page.locator('#step2 button:has-text("Back"), #step2 button.btn-secondary').first();
      if (await backBtn2.isVisible()) {
        await backBtn2.click();
        await expect(page.locator('#step1')).toBeVisible({ timeout: 5000 });
      }

      // Verify data persists after navigation
      const nameValue = await page.locator('#organizerName').inputValue();
      if (nameValue !== 'Sarah Cohen') {
        logger.logFriction('high', 'Form data lost when navigating back through wizard steps', 'Preserve form state across step navigation');
      }
    });

    // Step 8: Test standalone flow (fresh)
    await logger.step('standalone-start', async () => {
      await page.goto('/shiva/organize');
      await page.waitForSelector('#step1', { state: 'visible', timeout: 15000 });

      // Verify no ?obit= param
      const url = page.url();
      expect(url).not.toContain('obit=');
    });

    // Step 9: Verify standalone mode works
    await logger.step('standalone-filled', async () => {
      await page.locator('#organizerName').fill('David Levy');
      await page.locator('#organizerEmail').fill('david.levy@example.com');
      await page.locator('#organizerPhone').fill('514-555-0456');

      // Should be able to proceed without an obituary selected
      const nameValue = await page.locator('#organizerName').inputValue();
      expect(nameValue).toBe('David Levy');
    });

    // Step 10: Check validation
    await logger.step('validation', async () => {
      // Start fresh to test validation
      await page.goto('/shiva/organize');
      await page.waitForSelector('#step1', { state: 'visible', timeout: 15000 });

      // Try advancing with empty required fields
      const nextBtn = page.locator('#step1 button:has-text("Next"), #step1 button:has-text("Continue"), button.btn-primary:visible').first();
      await nextBtn.click();

      // Check for error messages
      const errorMsg = page.locator('.form-error, #step1Error, .error-message, [class*="error"]');
      const errorVisible = await errorMsg.first().isVisible().catch(() => false);

      // Also check if step 2 became visible (meaning validation was skipped)
      const step2Visible = await page.locator('#step2').isVisible().catch(() => false);

      if (step2Visible && !errorVisible) {
        logger.logFriction('high', 'Wizard advanced to step 2 without filling required fields — no validation', 'Add client-side validation for required fields before advancing');
      } else if (!errorVisible && !step2Visible) {
        logger.logFriction('medium', 'Validation prevented advancement but no visible error message shown', 'Show clear error messages for required fields');
      }
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
