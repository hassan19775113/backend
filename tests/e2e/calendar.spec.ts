import { test, expect } from '@playwright/test';
import { CalendarPage } from '../pages/calendar-page';
import { AppointmentModalPage } from '../pages/appointment-modal-page';

// Calendar E2E: dynamically choose available doctor/type/patient from live options, create appointment, assert card.
test('create appointment via calendar modal with live options', async ({ page, baseURL }) => {
  const calendar = new CalendarPage(page);
  const modal = new AppointmentModalPage(page);

  await calendar.goto(baseURL!);

  // Select first available doctor (skip empty value)
  const doctorLabel = await calendar.doctorFilter.evaluate((select) => {
    const opts = Array.from(select.querySelectorAll('option'));
    const first = opts.find((o) => o.value && o.value.trim().length > 0);
    return first?.textContent?.trim() || null;
  });
  if (doctorLabel) {
    await calendar.doctorFilter.selectOption({ label: doctorLabel });
  }

  // Pick a title filter if available
  const titleLabel = await calendar.titleFilter.evaluate((select) => {
    const opts = Array.from(select.querySelectorAll('option'));
    const first = opts.find((o) => o.value && o.value.trim().length > 0);
    return first?.textContent?.trim() || null;
  });
  if (titleLabel) {
    await calendar.titleFilter.selectOption({ label: titleLabel });
  }

  // Open creation modal.
  await calendar.openNewAppointment();
  await modal.expectOpen();

  await modal.waitForDropdownsLoaded();
  const { titleLabel: modalTitleLabel, doctorLabel: modalDoctorLabel, patientLabel: modalPatientLabel } =
    await modal.getFirstSelectableLabels();

  const today = new Date();
  const yyyy = today.getFullYear();
  const mm = String(today.getMonth() + 1).padStart(2, '0');
  const dd = String(today.getDate()).padStart(2, '0');
  const date = `${yyyy}-${mm}-${dd}`;

  await modal.fillNewAppointment({
    titleLabel: String(modalTitleLabel),
    doctorLabel: String(modalDoctorLabel),
    patientLabel: String(modalPatientLabel),
    date,
    start: '09:00',
    end: '09:30',
    description: 'E2E Termin via Playwright',
  });

  await modal.save();

  // Expect an appointment card containing the description
  await calendar.expectAppointmentPresent('E2E Termin');
});
