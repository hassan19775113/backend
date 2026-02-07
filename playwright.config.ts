import { defineConfig, devices } from '@playwright/test';
import path from 'path';

// Playwright config tuned for PraxiApp dashboards & APIs.
// Key points:
// - BASE_URL env overrides default http://localhost:8000.
// - storageState comes from fixtures/auth.setup.ts (login via API).
// - HTML reporter plus artifacts (trace/video/screenshot) on failure for debugging.
export default defineConfig({
  // All specs live under tests/e2e
  testDir: path.join(__dirname, 'e2e'),

  // Generous timeouts for heavier pages (charts, calendar)
  timeout: 90_000,
  expect: { timeout: 10_000 },

  // HTML reporter for local review; adjust to 'list' for CI logs only
  reporter: [['list'], ['html']],

  use: {
    // Target base URL; override with BASE_URL env when running against other hosts
    baseURL: process.env.BASE_URL || 'http://localhost:8000',

    headless: true,

    // Capture artifacts on failure for investigation
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',

    // Reuse authenticated session from global setup
    storageState: path.join(__dirname, 'fixtures', 'storageState.json'),
  },

  // Global login via API before tests
  globalSetup: path.join(__dirname, 'fixtures', 'auth.setup.ts'),

  // Browser matrix (extend if needed)
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
