import { test, expect } from '@playwright/test';

type EndpointCheck = {
  name: string;
  path: string;
};

const endpointChecks: EndpointCheck[] = [
  { name: 'appointment-types', path: '/api/appointment-types/' },
  { name: 'doctors', path: '/api/appointments/doctors/' },
  { name: 'patients-search', path: '/api/patients/search/' },
  { name: 'resources', path: '/api/resources/' },
  { name: 'appointments-list', path: '/api/appointments/' },
];

function isTargetResponse(urlString: string, check: EndpointCheck): boolean {
  try {
    const url = new URL(urlString);
    if (check.path === '/api/appointments/') {
      return url.pathname === '/api/appointments/' &&
        (url.searchParams.has('start_date') || url.searchParams.has('date'));
    }
    return url.pathname === check.path;
  } catch {
    return false;
  }
}

test('dashboard appointments loads via session auth when localStorage token is unavailable', async ({ page, baseURL }) => {
  const apiResponses = new Map<string, number>();

  const waiters = endpointChecks.map((check) =>
    page.waitForResponse(
      (response) => isTargetResponse(response.url(), check),
      { timeout: 20_000 }
    )
  );

  await page.addInitScript(() => {
    try {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    } catch {
      // ignore storage errors (e.g. tracking prevention)
    }
  });

  await page.goto(`${baseURL}/praxi_backend/dashboard/appointments/`, { waitUntil: 'domcontentloaded' });

  if (page.url().includes('/admin/login')) {
    throw new Error('Expected session-authenticated dashboard page, but got redirected to admin login.');
  }

  const responses = await Promise.all(waiters);
  responses.forEach((response, index) => {
    apiResponses.set(endpointChecks[index].name, response.status());
  });

  for (const check of endpointChecks) {
    const status = apiResponses.get(check.name);
    expect(status, `${check.name} should return a response`).toBeDefined();
    expect(status, `${check.name} must not return 401`).not.toBe(401);
  }

  await expect(page.locator('#appointmentCalendar')).toBeVisible();

  await page.locator('#calendarNewAppointment').click();
  await expect(page.locator('#calendarModalBackdrop')).toBeVisible();

  await expect(page.locator('#modalTitle option', { hasText: 'Fehler beim Laden' })).toHaveCount(0);
  await expect(page.locator('#modalDoctor option', { hasText: 'Fehler beim Laden' })).toHaveCount(0);
  await expect(page.locator('#modalPatient option', { hasText: 'Fehler beim Laden' })).toHaveCount(0);
});
