import { test, expect } from '@playwright/test';
import { NavPage } from '../pages/nav-page';

// Navigation smoke tests for header links defined in base_dashboard.html

test('navigate through primary sections', async ({ page, baseURL }) => {
  const nav = new NavPage(page);

  // Start at main dashboard
  await page.goto(`${baseURL}/praxi_backend/`);
  await nav.expectHeaderVisible();

  await nav.gotoScheduling();
  await expect(page).toHaveURL(/\/praxi_backend\/appointments/);

  await nav.gotoPatients();
  await expect(page).toHaveURL(/\/praxi_backend\/patients/);

  await nav.gotoDoctors();
  await expect(page).toHaveURL(/\/praxi_backend\/doctors/);

  await nav.gotoOperations();
  await expect(page).toHaveURL(/\/praxi_backend\/operations/);

  await nav.gotoResources();
  await expect(page).toHaveURL(/\/praxi_backend\/resources/);

  // Admin might require permissions; just assert navigation attempt does not throw
  await nav.gotoAdmin();
});
