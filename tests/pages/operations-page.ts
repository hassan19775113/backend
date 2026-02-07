import { Page, Locator, expect } from '@playwright/test';

// Page Object: Operations dashboard (operations.html)
// Selectors: #periodSelect, #hourlyChart, #dailyTrendChart
// Dependency: authenticated session; ops data available for charts
export class OperationsPage {
  readonly periodSelect: Locator;
  readonly hourlyChart: Locator;
  readonly dailyTrendChart: Locator;

  constructor(private readonly page: Page) {
    this.periodSelect = page.locator('#periodSelect');
    this.hourlyChart = page.locator('#hourlyChart');
    this.dailyTrendChart = page.locator('#dailyTrendChart');
  }

  async goto(baseURL: string) {
    await this.page.goto(`${baseURL}/praxi_backend/operations/`);
    await expect(this.periodSelect).toBeVisible();
  }

  async changePeriodTo(value: string) {
    await this.periodSelect.selectOption(value);
  }

  async expectChartsVisible() {
    await expect(this.hourlyChart).toBeVisible();
    await expect(this.dailyTrendChart).toBeVisible();
  }
}
