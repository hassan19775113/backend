import { Page, Locator, expect } from '@playwright/test';
import { waitForResponseAfter } from '../utils/network-utils';
import {
  getFirstNonEmptyOptionLabel,
  waitForFirstNonEmptyOptionLabel,
  waitForOptionValue,
  waitForOptionValueMissing,
} from '../utils/select-utils';

// Page Object: Appointment modal (calendar/modal.js)
// Real selectors captured:
// - Container: #calendarModalBackdrop
// - Fields: #modalTitle, #modalDoctor, #modalPatient, #modalDate, #modalStartTime, #modalEndTime, #modalDescription
// - Actions: #calendarModalSave, #calendarModalDelete, #calendarModalCancel
// Dependencies: calendar page opens this modal; requires authenticated session
export class AppointmentModalPage {
  readonly backdrop: Locator;
  readonly closeButton: Locator;
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
    this.closeButton = page.locator('#calendarModalClose');
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

  async expectClosed() {
    await expect(this.backdrop).toBeHidden();
  }

  async waitForDropdownsLoaded(timeout = 10_000) {
    await this.titleSelect.waitFor({ state: 'visible' });
    await this.doctorSelect.waitFor({ state: 'visible' });
    await this.patientSelect.waitFor({ state: 'visible' });

    await waitForFirstNonEmptyOptionLabel(this.titleSelect, {
      timeout,
      message: 'Waiting for appointment type options to load',
    });
    await waitForFirstNonEmptyOptionLabel(this.doctorSelect, {
      timeout,
      message: 'Waiting for doctor options to load',
    });
    await waitForFirstNonEmptyOptionLabel(this.patientSelect, {
      timeout,
      message: 'Waiting for patient options to load',
    });
  }

  async getFirstSelectableLabels() {
    const titleLabel = await getFirstNonEmptyOptionLabel(this.titleSelect);
    const doctorLabel = await getFirstNonEmptyOptionLabel(this.doctorSelect);
    const patientLabel = await getFirstNonEmptyOptionLabel(this.patientSelect);

    if (!titleLabel || !doctorLabel || !patientLabel) {
      throw new Error('Modal dropdowns not populated (missing first non-empty option label)');
    }

    return { titleLabel, doctorLabel, patientLabel };
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
    await this.waitForDropdownsLoaded();
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

  async updateTimesAndWaitForAvailability(date: string, start: string, end: string) {
    // The modal triggers an availability check shortly after opening (setTimeout 500ms).
    // If we try to trigger another check during that in-flight request, the modal will
    // ignore it (isCheckingAvailability guard). Wait until it's idle first.
    await this.page.waitForFunction(
      () => {
        const modal = (window as any).modernCalendar?.modal;
        return !modal || !modal.isCheckingAvailability;
      },
      { timeout: 10_000 }
    );

    // The modal listens to *change* events (not input) on date/time fields.
    // Also, the modal triggers an availability check 500ms after opening with
    // default times; we must ensure we wait for the request caused by *our* inputs.
    const expected = await this.page.evaluate(
      ({ date, start, end }) => {
        const startISO = `${date}T${start}:00`;
        const endISO = `${date}T${end}:00`;
        return {
          startISO,
          endISO,
          startParam: encodeURIComponent(startISO),
          endParam: encodeURIComponent(endISO),
        };
      },
      { date, start, end }
    );

    const { response } = await waitForResponseAfter(
      this.page,
      async () => {
        // Set values and trigger a real in-page `change` event.
        // This avoids relying on Playwright's input event semantics for date/time inputs.
        await this.page.evaluate(
          ({ date, start, end }) => {
            const dateField = document.getElementById('modalDate');
            const startTimeField = document.getElementById('modalStartTime');
            const endTimeField = document.getElementById('modalEndTime');
            if (!dateField || !startTimeField || !endTimeField) return;
            (dateField as HTMLInputElement).value = date;
            (startTimeField as HTMLInputElement).value = start;
            (endTimeField as HTMLInputElement).value = end;
            endTimeField.dispatchEvent(new Event('change', { bubbles: true }));
          },
          { date, start, end }
        );
      },
      (r) => {
        if (r.request().method() !== 'GET') return false;
        const url = r.url();
        return (
          url.includes(process.env.FAULT_SCENARIO === 'availability' ? '/api/availabilityBROKEN/?' : '/api/availability/?') &&
          url.includes(`start=${expected.startParam}`) &&
          url.includes(`end=${expected.endParam}`)
        );
      },
      10_000
    );

    return response;
  }

  async save() {
    await this.saveButton.click();
  }

  async saveAndWaitForAppointmentsMutation(timeout = 10_000) {
    const { response } = await waitForResponseAfter(
      this.page,
      async () => {
        await this.saveButton.click();
      },
      (r) => {
        const url = r.url();
        const method = r.request().method();
        return url.includes('/api/appointments/') && (method === 'POST' || method === 'PATCH');
      },
      timeout
    );

    return response;
  }

  async delete() {
    await this.deleteButton.click();
  }

  async deleteAndConfirm(timeout = 10_000) {
    this.page.once('dialog', (d) => d.accept());

    await waitForResponseAfter(
      this.page,
      async () => {
        await this.deleteButton.click();
      },
      (r) => r.url().includes('/api/appointments/') && r.request().method() === 'DELETE',
      timeout
    );
  }

  async waitForOptionValue(value: string, timeout = 10_000) {
    await waitForOptionValue(this.doctorSelect, value, timeout);
  }

  async waitForDoctorOptionValueMissing(value: string, timeout = 10_000) {
    await waitForOptionValueMissing(this.doctorSelect, value, timeout);
  }

  async waitForPatientOptionValue(value: string, timeout = 10_000) {
    await waitForOptionValue(this.patientSelect, value, timeout);
  }

  async waitForPatientOptionValueMissing(value: string, timeout = 10_000) {
    await waitForOptionValueMissing(this.patientSelect, value, timeout);
  }
}
