import { test } from '@playwright/test';
import { CalendarPage } from '../pages/calendar-page';
import { AppointmentModalPage } from '../pages/appointment-modal-page';

// Appointment editing: open first appointment, change time, save, and verify updated time text.
test('edit existing appointment time', async ({ page, baseURL }) => {
  const calendar = new CalendarPage(page);
  const modal = new AppointmentModalPage(page);

  await calendar.goto(baseURL!);
  // Ensure at least one appointment exists before trying to edit
  await calendar.appointmentCards.first().waitFor({ state: 'visible' });
  await calendar.openFirstAppointment();
  await modal.expectOpen();

  const today = new Date();
  const yyyy = today.getFullYear();
  const mm = String(today.getMonth() + 1).padStart(2, '0');
  const dd = String(today.getDate()).padStart(2, '0');
  const date = `${yyyy}-${mm}-${dd}`;

  await modal.updateTimes(date, '10:00', '10:30');
  await modal.save();

  // Wait for modal to close to avoid flakiness
  await modal.backdrop.waitFor({ state: 'hidden' });

  // Verify an appointment card shows the updated time window.
  await calendar.expectAppointmentPresent('10:00');
});
