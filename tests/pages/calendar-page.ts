import { Page, Locator, expect } from '@playwright/test';

// Page Object: Modern calendar (appointments_calendar_fullcalendar.html + calendar/index.js)
// Selectors pulled from code:
// - Calendar mount: #appointmentCalendar
// - Filters: #doctorFilter, #titleFilter
// - Toolbar: #calendarPrev, #calendarToday, #calendarNext, #calendarNewAppointment
// - Cards: .calendar-appointment
// Dependencies: authenticated session (storageState), baseURL
export class CalendarPage {
  readonly appointmentCalendar: Locator;
  readonly doctorFilter: Locator;
  readonly titleFilter: Locator;
  readonly prevButton: Locator;
  readonly todayButton: Locator;
  readonly nextButton: Locator;
  readonly newAppointmentButton: Locator;
  readonly calendarRangeDebug: Locator;
  readonly appointmentCards: Locator;
  readonly appointmentCardTitle: Locator;
  readonly appointmentCardDoctor: Locator;
  readonly appointmentCardPatient: Locator;
  readonly appointmentCardTime: Locator;

  constructor(private readonly page: Page) {
    this.appointmentCalendar = page.locator(process.env.FAULT_SCENARIO === 'selector' ? '#appointmentCalendarBROKEN' : '#appointmentCalendar');
    this.doctorFilter = page.locator('#doctorFilter');
    this.titleFilter = page.locator('#titleFilter');
    this.prevButton = page.locator('#calendarPrev');
    this.todayButton = page.locator('#calendarToday');
    this.nextButton = page.locator('#calendarNext');
    this.newAppointmentButton = page.locator('#calendarNewAppointment');
    this.calendarRangeDebug = page.locator('#calendarRangeDebug');
    this.appointmentCards = page.locator('.calendar-appointment');
    this.appointmentCardTitle = this.appointmentCards.locator('.calendar-appointment__title');
    this.appointmentCardDoctor = this.appointmentCards.locator('.calendar-appointment__doctor');
    this.appointmentCardPatient = this.appointmentCards.locator('.calendar-appointment__patient');
    this.appointmentCardTime = this.appointmentCards.locator('.calendar-appointment__time');
  }

  async goto(baseURL: string) {
    await this.page.goto(`${baseURL}/praxi_backend/appointments/`);
    await this.page.waitForLoadState('domcontentloaded');
    if (this.page.url().includes('/login')) {
      return;
    }
    await expect(this.appointmentCalendar).toBeVisible();
    // Ensure toolbar is present for navigation actions
    await expect(this.todayButton).toBeVisible();
    // Calendar JS sets window.modernCalendar; waiting helps avoid early interactions
    await this.page.waitForFunction(() => Boolean((window as any).modernCalendar), null, {
      timeout: 10_000,
    });
  }

  async filterDoctorByIndex(index = 1) {
    await this.doctorFilter.selectOption({ index });
  }

  async filterTitleByText(title: string) {
    await this.titleFilter.selectOption({ label: title });
  }

  async openNewAppointment() {
    await this.newAppointmentButton.click();
  }

  async openFirstAppointment() {
    await expect(this.appointmentCards.first()).toBeVisible();
    await this.appointmentCards.first().dblclick();
  }

  appointmentCardByText(text: string) {
    return this.appointmentCards.filter({ hasText: text }).first();
  }

  appointmentCardById(id: string | number) {
    return this.page.locator(`.calendar-appointment[data-appointment-id="${id}"]`).first();
  }

  async openAppointmentByText(text: string) {
    const card = this.appointmentCardByText(text);
    await expect(card).toBeVisible();
    await card.dblclick();
  }

  async expectAppointmentPresent(text: string) {
    await expect(this.appointmentCardByText(text)).toBeVisible();
  }

  async expectAppointmentCardMeta(options: { containsText: string; doctor?: string; patient?: string }) {
    const card = this.appointmentCardByText(options.containsText);
    await expect(card).toBeVisible();

    if (options.doctor) {
      await expect(card.locator('.calendar-appointment__doctor')).toHaveText(options.doctor);
    }
    if (options.patient) {
      await expect(card.locator('.calendar-appointment__patient')).toHaveText(options.patient);
    }
  }
}
