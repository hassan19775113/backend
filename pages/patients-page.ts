import { Page, Locator, expect } from '@playwright/test';

// Page Object: Patients dashboard (patients.html)
// Selectors: #patientSelect, form textarea[name="content"], form button[type="submit"], .timeline-item
// Dependency: authenticated session; patient data and note creation permitted
export class PatientsPage {
  readonly patientSelect: Locator;
  readonly noteTextarea: Locator;
  readonly noteSubmitButton: Locator;
  readonly notesTimeline: Locator;

  constructor(private readonly page: Page) {
    this.patientSelect = page.locator('#patientSelect');
    this.noteTextarea = page.locator('form textarea[name="content"]');
    this.noteSubmitButton = page.locator('form button[type="submit"]');
    this.notesTimeline = page.locator('.timeline-item');
  }

  async goto(baseURL: string) {
    await this.page.goto(`${baseURL}/praxi_backend/patients/`);
    await expect(this.patientSelect).toBeVisible();
  }

  async chooseFirstPatient() {
    await this.patientSelect.selectOption({ index: 1 });
  }

  async addNote(text: string) {
    await this.noteTextarea.fill(text);
    await this.noteSubmitButton.click();
  }

  async expectNoteVisible(text: string) {
    await expect(this.notesTimeline.filter({ hasText: text }).first()).toBeVisible();
  }
}
