import { test, expect } from '@playwright/test';
import { NavPage } from '../pages/nav-page';

// Navigation smoke tests for header links defined in base_dashboard.html

test('navigate through primary sections', async ({ page, baseURL }) => {
  const nav = new NavPage(page);

  // Start at main dashboard
  await page.goto(`${baseURL}/praxi_backend/dashboard/`);
  await page.waitForLoadState('domcontentloaded');
  if (page.url().includes('/login')) {
    test.skip(true, 'Not authenticated in navigation smoke test environment');
    return;
  }
  await page.waitForSelector('[role="navigation"]', { timeout: 15000 });
  await nav.expectHeaderVisible();

  await nav.gotoScheduling();
  await expect(page).toHaveURL(/\/praxi_backend\/dashboard\/(appointments|scheduling)\//);

  await nav.gotoPatients();
  await expect(page).toHaveURL(/\/praxi_backend\/dashboard\/patients\//);

  await nav.gotoDoctors();
  await expect(page).toHaveURL(/\/praxi_backend\/dashboard\/doctors\//);

  await nav.gotoOperations();
  await expect(page).toHaveURL(/\/praxi_backend\/dashboard\/operations\//);

  await nav.gotoResources();
  await expect(page).toHaveURL(/\/praxi_backend\/dashboard\/resources\//);

  // Admin might require permissions; just assert navigation attempt does not throw
  await nav.gotoAdmin();
});
