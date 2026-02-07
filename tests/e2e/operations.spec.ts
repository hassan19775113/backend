import { test } from '@playwright/test';
import { OperationsPage } from '../pages/operations-page';

// Operations dashboard: change period and ensure charts exist.
test('operations charts visible after period change', async ({ page, baseURL }) => {
  const ops = new OperationsPage(page);
  await ops.goto(baseURL!);

  await ops.changePeriodTo('7');
  await ops.expectChartsVisible();
});
