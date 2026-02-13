import { test, expect } from '../fixtures/testdata.setup';
import { CalendarPage } from '../pages/calendar-page';

// Prüft, ob ein vorhandener Termin auf der Appointments-Seite sichtbar ist.
// URL-Anforderung vom Nutzer: /praxi_backend/dashboard/appointments/
test('appointments are visible on dashboard appointments page', async ({ page, baseURL, testData }) => {
  if (!testData.appointmentId || !testData.appointmentStartTime) {
    test.skip(true, 'Seed appointment missing; cannot verify visibility');
    return;
  }

  const calendar = new CalendarPage(page);

  await page.goto(`${baseURL}/praxi_backend/dashboard/appointments/`);
  await page.waitForLoadState('domcontentloaded');

  if (page.url().includes('/admin/login')) {
    throw new Error('Dashboard appointments URL redirected to admin login; auth/session is missing');
  }

  await expect(calendar.appointmentCalendar).toBeVisible();
  await page.waitForFunction(() => Boolean((window as any).modernCalendar), null, {
    timeout: 10_000,
  });

  // Zum Termin-Tag springen, damit der erzeugte Termin sicher im sichtbaren Bereich geladen wird.
  await page.evaluate((isoStart: string) => {
    const cal = (window as any).modernCalendar;
    if (!cal) return;
    cal.currentDate = new Date(isoStart);
    cal.renderView();
    cal.loadAppointments();
  }, testData.appointmentStartTime);

  const targetCard = calendar.appointmentCardById(testData.appointmentId);
  await expect(targetCard).toBeVisible({ timeout: 15_000 });
});
