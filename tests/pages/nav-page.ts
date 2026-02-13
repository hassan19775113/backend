import { Page, expect } from '@playwright/test';

// Page Object: Header navigation (base_dashboard.html)
// Uses getByRole('link', { name }) for real labels: Dashboards, Terminplanung, Patienten,
// Ärzte, Operationen, Ressourcen, Admin
// Dependency: rendered dashboard header (authenticated session)
export class NavPage {
  constructor(private readonly page: Page) {}

  private async clickHeaderLinkByHref(partialHref: string) {
    await this.page.locator(`.prx-header__nav a[href*="${partialHref}"]`).first().click();
  }

  async gotoDashboards() {
    await Promise.all([
      this.page.waitForURL(/\/praxi_backend\/dashboard\/?/),
      this.clickHeaderLinkByHref('/praxi_backend/Dashboardadministration/'),
    ]);
  }

  async gotoScheduling() {
    await Promise.all([
      this.page.waitForURL(/\/praxi_backend\/dashboard\/(appointments|scheduling)\/?/),
      this.clickHeaderLinkByHref('/praxi_backend/dashboard/appointments/'),
    ]);
  }

  async gotoPatients() {
    await Promise.all([
      this.page.waitForURL(/\/praxi_backend\/dashboard\/patients\/?/),
      this.clickHeaderLinkByHref('/praxi_backend/dashboard/patients/'),
    ]);
  }

  async gotoDoctors() {
    await Promise.all([
      this.page.waitForURL(/\/praxi_backend\/dashboard\/doctors\/?/),
      this.clickHeaderLinkByHref('/praxi_backend/dashboard/doctors/'),
    ]);
  }

  async gotoOperations() {
    await Promise.all([
      this.page.waitForURL(/\/praxi_backend\/dashboard\/operations\/?/),
      this.clickHeaderLinkByHref('/praxi_backend/dashboard/operations/'),
    ]);
  }

  async gotoResources() {
    await Promise.all([
      this.page.waitForURL(/\/praxi_backend\/dashboard\/resources\/?/),
      this.clickHeaderLinkByHref('/praxi_backend/dashboard/resources/'),
    ]);
  }

  async gotoAdmin() {
    await this.page.locator('.prx-header__nav a[href*="/admin/"]').first().click();
  }

  async expectHeaderVisible() {
    await this.page.waitForLoadState('domcontentloaded');
    await this.page.waitForSelector('[role="navigation"]', { timeout: 15000 });
    await expect(this.page.locator('.prx-header__nav')).toBeVisible();
    await expect(this.page.getByRole('navigation')).toBeVisible();
  }
}
