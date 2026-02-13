import { test, expect } from '../fixtures/testdata.setup';
import { ApiClient } from '../../api-client';
import { CalendarPage } from '../pages/calendar-page';
import { AppointmentModalPage } from '../pages/appointment-modal-page';

// Appointment editing: open first appointment, change time, save, and verify updated time text.
test('edit existing appointment time', async ({ page, baseURL, testData }) => {
  const calendar = new CalendarPage(page);
  const modal = new AppointmentModalPage(page);

  // Force testdata fixture execution to ensure an appointment exists.
  if (!testData.appointmentId || !testData.appointmentStartTime) {
    test.skip(true, 'Seed data incomplete for appointment modal edit test');
    return;
  }

  await calendar.goto(baseURL!);

  // Navigate calendar to the date of the seeded appointment (may be in the future depending on working hours).
  await page.evaluate((isoStart: string) => {
    const cal = (window as any).modernCalendar;
    if (!cal) return;
    cal.currentDate = new Date(isoStart);
    cal.renderView();
    cal.loadAppointments();
  }, testData.appointmentStartTime!);

  const seededCard = calendar.appointmentCardById(testData.appointmentId!);
  await seededCard.waitFor({ state: 'visible' });
  await seededCard.dblclick();
  await modal.expectOpen();

  const baseDate = new Date(testData.appointmentStartTime!);
  const yyyy = baseDate.getFullYear();
  const mm = String(baseDate.getMonth() + 1).padStart(2, '0');
  const dd = String(baseDate.getDate()).padStart(2, '0');
  const date = `${yyyy}-${mm}-${dd}`;

  // Pick an actually available slot for this doctor/type/day.
  const api = new ApiClient();
  await api.init();
  let nextStart = '10:00';
  let nextEnd = '10:30';
  try {
    const suggestRes = await api.suggestAppointment({
      doctor_id: testData.doctorId!,
      type_id: testData.appointmentTypeId,
      start_date: date,
      limit: 2,
    });
    if (suggestRes.ok()) {
      const suggest = await suggestRes.json();
      const primary = Array.isArray(suggest?.primary_suggestions) ? suggest.primary_suggestions : [];
      const slot = primary[0] || primary[1];
      if (slot?.start_time && slot?.end_time) {
        const startDt = new Date(String(slot.start_time));
        const endDt = new Date(String(slot.end_time));
        nextStart = `${String(startDt.getHours()).padStart(2, '0')}:${String(startDt.getMinutes()).padStart(2, '0')}`;
        nextEnd = `${String(endDt.getHours()).padStart(2, '0')}:${String(endDt.getMinutes()).padStart(2, '0')}`;
      }
    }
  } finally {
    await api.dispose();
  }

  await modal.updateTimes(date, nextStart, nextEnd);
  await modal.save();

  // Wait for modal to close to avoid flakiness
  await modal.backdrop.waitFor({ state: 'hidden' });

  // Verify an appointment card shows the updated time window.
  await calendar.expectAppointmentPresent(nextStart);
});
