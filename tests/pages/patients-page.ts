import { Page, Locator, expect } from '@playwright/test';

// Page Object: Patients overview + detail
// Overview: /praxi_backend/patients/ (redirects to /praxi_backend/dashboard/patients/) with #patientsTable
// Detail: /praxi_backend/dashboard/patients/<id>/ where notes can be created
export class PatientsPage {
  readonly patientsTable: Locator;
  readonly firstPatientRow: Locator;
  readonly noteTextarea: Locator;
  readonly noteSubmitButton: Locator;
  readonly notesTimeline: Locator;

  constructor(private readonly page: Page) {
    this.patientsTable = page.locator('#patientsTable');
    this.firstPatientRow = page.locator('#patientsTable tbody tr.prx-patient-row').first();
    this.noteTextarea = page.locator('form textarea[name="content"]');
    this.noteSubmitButton = page.locator('form button[type="submit"]');
    this.notesTimeline = page.locator('.timeline-item');
  }

  async goto(baseURL: string) {
    await this.page.goto(`${baseURL}/praxi_backend/patients/`);
    await expect(this.patientsTable).toBeVisible();
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

  async expectNoteVisible(text: string) {
    await expect(this.notesTimeline.filter({ hasText: text }).first()).toBeVisible();
  }
}
