const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './journeys',
  outputDir: './test-results',
  timeout: 120000,
  expect: {
    timeout: 10000,
  },
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.BASE_URL || 'https://neshama.ca',
    viewport: { width: 375, height: 812 },
    screenshot: 'off',
    trace: 'off',
    navigationTimeout: 60000,
    actionTimeout: 10000,
  },
  projects: [
    {
      name: 'chromium-mobile',
      use: {
        browserName: 'chromium',
        viewport: { width: 375, height: 812 },
        userAgent: devices['iPhone SE'].userAgent,
        deviceScaleFactor: 2,
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
});
