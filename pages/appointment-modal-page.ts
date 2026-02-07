import { Page, Locator, expect } from '@playwright/test';

// Page Object: Appointment modal (calendar/modal.js)
// Real selectors captured:
// - Container: #calendarModalBackdrop
// - Fields: #modalTitle, #modalDoctor, #modalPatient, #modalDate, #modalStartTime, #modalEndTime, #modalDescription
// - Actions: #calendarModalSave, #calendarModalDelete, #calendarModalCancel
// Dependencies: calendar page opens this modal; requires authenticated session
export class AppointmentModalPage {
  readonly backdrop: Locator;
  readonly titleSelect: Locator;
  readonly doctorSelect: Locator;
  readonly patientSelect: Locator;
  readonly dateInput: Locator;
  readonly startTimeInput: Locator;
  readonly endTimeInput: Locator;
  readonly descriptionInput: Locator;
  readonly saveButton: Locator;
  readonly deleteButton: Locator;
  readonly cancelButton: Locator;

  constructor(private readonly page: Page) {
    this.backdrop = page.locator('#calendarModalBackdrop');
    this.titleSelect = page.locator('#modalTitle');
    this.doctorSelect = page.locator('#modalDoctor');
    this.patientSelect = page.locator('#modalPatient');
    this.dateInput = page.locator('#modalDate');
    this.startTimeInput = page.locator('#modalStartTime');
    this.endTimeInput = page.locator('#modalEndTime');
    this.descriptionInput = page.locator('#modalDescription');
    this.saveButton = page.locator('#calendarModalSave');
    this.deleteButton = page.locator('#calendarModalDelete');
    this.cancelButton = page.locator('#calendarModalCancel');
  }

  async expectOpen() {
    await expect(this.backdrop).toBeVisible();
  }

  async fillNewAppointment(options: {
    titleLabel: string;
    doctorLabel: string;
    patientLabel: string;
    date: string; // YYYY-MM-DD
    start: string; // HH:MM
    end: string; // HH:MM
    description?: string;
  }) {
    // Ensure options are loaded
    await this.titleSelect.waitFor({ state: 'visible' });
    await this.doctorSelect.waitFor({ state: 'visible' });
    await this.patientSelect.waitFor({ state: 'visible' });
    await this.titleSelect.selectOption({ label: options.titleLabel });
    await this.doctorSelect.selectOption({ label: options.doctorLabel });
    await this.patientSelect.selectOption({ label: options.patientLabel });
    await this.dateInput.fill(options.date);
    await this.startTimeInput.fill(options.start);
    await this.endTimeInput.fill(options.end);
    if (options.description) {
      await this.descriptionInput.fill(options.description);
    }
  }

  async updateTimes(date: string, start: string, end: string) {
    await this.dateInput.fill(date);
    await this.startTimeInput.fill(start);
    await this.endTimeInput.fill(end);
  }

  async save() {
    await this.saveButton.click();
  }

  async delete() {
    await this.deleteButton.click();
  }
}
