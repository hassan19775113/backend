import { Page, Locator, expect } from '@playwright/test';

// Page Object: Patients overview + detail
// Overview: /praxi_backend/patients/ (redirects to /praxi_backend/dashboard/patients/) with #patientsTable
// Detail: /praxi_backend/dashboard/patients/<id>/ where notes can be created
export class PatientsPage {
  readonly patientsTable: Locator;
  readonly patientRows: Locator;
  readonly firstPatientRow: Locator;
  readonly searchInput: Locator;
  readonly statusFilter: Locator;
  readonly riskFilter: Locator;
  readonly noteTextarea: Locator;
  readonly noteSubmitButton: Locator;
  readonly notesTimeline: Locator;

  constructor(private readonly page: Page) {
    this.patientsTable = page.locator('#patientsTable');
    this.patientRows = page.locator('#patientsTable tbody tr.prx-patient-row, #patientsTable tbody tr[data-detail-url]');
    this.firstPatientRow = this.patientRows.first();
    this.searchInput = page.locator('#patientSearchInput');
    this.statusFilter = page.locator('#statusFilter');
    this.riskFilter = page.locator('#riskFilter');
    this.noteTextarea = page.locator('form textarea[name="content"]');
    this.noteSubmitButton = page.locator('form button[type="submit"]');
    this.notesTimeline = page.locator('.timeline-item');
  }

  async goto(baseURL: string) {
    await this.page.goto(`${baseURL}/praxi_backend/patients/`);
    await this.page.waitForLoadState('domcontentloaded');
    await expect(this.patientsTable).toBeVisible();
  }

  async search(text: string) {
    if (await this.searchInput.count()) {
      await this.searchInput.fill(text);
    }
  }

  async filterStatus(value: string) {
    if (await this.statusFilter.count()) {
      await this.statusFilter.selectOption(value);
    }
  }

  async filterRisk(value: string) {
    if (await this.riskFilter.count()) {
      await this.riskFilter.selectOption(value);
    }
  }

  async openPatientRowByIndex(index: number) {
    const row = this.patientRows.nth(index);
    await expect(row).toBeVisible();
    await Promise.all([
      this.page.waitForURL(/\/praxi_backend\/dashboard\/patients\/\d+\//),
      row.click(),
    ]);
    await expect(this.noteTextarea).toBeVisible();
  }

  async chooseFirstPatient() {
    await expect(this.firstPatientRow).toBeVisible();
    await Promise.all([
      this.page.waitForURL(/\/praxi_backend\/dashboard\/patients\/\d+\//),
      this.firstPatientRow.click(),
    ]);
    await expect(this.noteTextarea).toBeVisible();
  }

  async addNote(text: string) {
    await this.noteTextarea.fill(text);
    await this.noteSubmitButton.click();
  }

  async addNoteAndExpectVisible(text: string) {
    await this.addNote(text);
    await this.expectNoteVisible(text);
  }

  async expectNoteVisible(text: string) {
    await expect(this.notesTimeline.filter({ hasText: text }).first()).toBeVisible();
  }
}
