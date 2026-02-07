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

  constructor(private readonly page: Page) {
    this.appointmentCalendar = page.locator('#appointmentCalendar');
    this.doctorFilter = page.locator('#doctorFilter');
    this.titleFilter = page.locator('#titleFilter');
    this.prevButton = page.locator('#calendarPrev');
    this.todayButton = page.locator('#calendarToday');
    this.nextButton = page.locator('#calendarNext');
    this.newAppointmentButton = page.locator('#calendarNewAppointment');
    this.calendarRangeDebug = page.locator('#calendarRangeDebug');
    this.appointmentCards = page.locator('.calendar-appointment');
  }

  async goto(baseURL: string) {
    await this.page.goto(`${baseURL}/praxi_backend/appointments/`);
    await expect(this.appointmentCalendar).toBeVisible();
    // Ensure toolbar is present for navigation actions
    await expect(this.todayButton).toBeVisible();
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

  async expectAppointmentPresent(text: string) {
    await expect(this.appointmentCards.filter({ hasText: text }).first()).toBeVisible();
  }
}
