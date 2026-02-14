import { test, expect } from '../fixtures/testdata.setup';
import { OperationsPage } from '../pages/operations-page';

test('operations dashboard loads without redirect and initializes charts', async ({ page, baseURL }) => {
  const operations = new OperationsPage(page);

  await page.goto(`${baseURL}/praxi_backend/operations/`);
  await page.waitForLoadState('domcontentloaded');

  if (page.url().includes('/admin/login')) {
    throw new Error('Operations page redirected to login; authentication/session missing');
  }

  // /praxi_backend/operations/ may redirect to /praxi_backend/dashboard/operations/
  await page.waitForURL(/\/praxi_backend\/(dashboard\/operations|operations)\/?/);

  await expect(operations.periodSelect).toBeVisible();

  // Server-rendered KPI card: should show a numeric value (0 is OK).
  const operationsTotal = page
    .locator('.prx-kpi', { hasText: /Operationen/i })
    .locator('.prx-kpi__value')
    .first();

  await expect(operationsTotal).toBeVisible();
  await expect
    .poll(async () => (await operationsTotal.textContent())?.trim() ?? '', {
      timeout: 10_000,
      message: 'Operations KPI should render a numeric value',
    })
    .toMatch(/^\d+/);

  // JS chart init status (set on window load) - verifies frontend chart setup runs.
  const debug = page.locator('#ops-chart-debug');
  await expect(debug).toBeVisible();
  await expect
    .poll(async () => (await debug.textContent())?.trim() ?? '', {
      timeout: 10_000,
      message: 'Operations charts should initialize (Chart.js loaded)',
    })
    .toContain('Chart.js: ok');
});
