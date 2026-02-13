import { Page, Locator, expect } from '@playwright/test';

// Page Object: Scheduling KPIs (scheduling.html + scheduling_charts.js)
// Selectors: #trendChart, #leadTimeChart, #weekdayChart, #hourlyChart, #funnelContainer
// Dependency: authenticated session; data presence for charts
export class SchedulingKpisPage {
  readonly trendChart: Locator;
  readonly leadTimeChart: Locator;
  readonly weekdayChart: Locator;
  readonly hourlyChart: Locator;
  readonly funnelContainer: Locator;

  constructor(private readonly page: Page) {
    this.trendChart = page.locator('#trendChart');
    this.leadTimeChart = page.locator('#leadTimeChart');
    this.weekdayChart = page.locator('#weekdayChart');
    this.hourlyChart = page.locator('#hourlyChart');
    this.funnelContainer = page.locator('#funnelContainer');
  }

  async goto(baseURL: string) {
    await this.page.goto(`${baseURL}/praxi_backend/dashboard/scheduling/`);
    await this.page.waitForLoadState('domcontentloaded');
    await this.page.waitForSelector('#scheduling-charts-json', { timeout: 15000 });
    await this.page.waitForSelector('#trendChart', { timeout: 15000 });

    await this.page
      .waitForResponse(
        (resp) =>
          resp.status() === 200 &&
          (resp.url().includes('/dashboard/scheduling/api/') ||
            resp.url().toLowerCase().includes('kpi')),
        { timeout: 5000 }
      )
      .catch(() => {});
  }

  async expectChartsVisible() {
    await this.trendChart.waitFor({ state: 'visible', timeout: 15000 });
    await this.leadTimeChart.waitFor({ state: 'visible', timeout: 15000 });
    await this.weekdayChart.waitFor({ state: 'visible', timeout: 15000 });
    await this.hourlyChart.waitFor({ state: 'visible', timeout: 15000 });
    await this.funnelContainer.waitFor({ state: 'visible', timeout: 15000 });

    await expect(this.trendChart).toBeVisible();
    await expect(this.leadTimeChart).toBeVisible();
    await expect(this.weekdayChart).toBeVisible();
    await expect(this.hourlyChart).toBeVisible();
    await expect(this.funnelContainer).toBeVisible();
  }
}
