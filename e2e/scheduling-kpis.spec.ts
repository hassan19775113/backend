import { test } from '@playwright/test';
import { SchedulingKpisPage } from '../pages/scheduling-kpis-page';

// Validate KPI charts render (presence of canvases/funnel container).
test('scheduling KPIs show charts', async ({ page, baseURL }) => {
  const scheduling = new SchedulingKpisPage(page);
  await scheduling.goto(baseURL!);
  await scheduling.expectChartsVisible();
});
