import { test, expect, Page } from '@playwright/test';

import { ApiClient } from '../../api-client';
import { adminLoginIfNeeded } from '../helpers/admin-login';
import { NavPage } from '../pages/nav-page';

const ADMIN_BASE_PATH = '/praxi_backend/Dashboardadministration';

async function selectRoleDoctor(page: Page) {
  const roleSelect = page.locator('#id_role');
  await expect(roleSelect).toBeVisible();

  // The select displays Role.__str__ which is the label (e.g. "Arzt").
  // Prefer exact label; fallback to any option containing "Arzt".
  const tryExact = await roleSelect.selectOption({ label: 'Arzt' }).catch(() => null);
  if (tryExact) return;

  const options = roleSelect.locator('option');
  const count = await options.count();
  for (let i = 0; i < count; i++) {
    const label = (await options.nth(i).textContent()) || '';
    if (label.toLowerCase().includes('arzt')) {
      const value = await options.nth(i).getAttribute('value');
      if (value) {
        await roleSelect.selectOption(value);
        return;
      }
    }
  }
  throw new Error('Could not find doctor role option (expected label contains "Arzt")');
}

async function createDoctorViaAdmin(page: Page, opts: { username: string; email: string; firstName: string; lastName: string; password: string }) {
  await page.goto(`${ADMIN_BASE_PATH}/core/user/add/`);
  await page.waitForLoadState('domcontentloaded');
  await adminLoginIfNeeded(page, process.env.E2E_USER, process.env.E2E_PASSWORD);

  await page.locator('#id_username').fill(opts.username);
  await page.locator('#id_password1').fill(opts.password);
  await page.locator('#id_password2').fill(opts.password);
  await page.locator('#id_email').fill(opts.email);
  await selectRoleDoctor(page);
  await page.locator('#id_first_name').fill(opts.firstName);
  await page.locator('#id_last_name').fill(opts.lastName);

  await Promise.all([
    page.waitForLoadState('domcontentloaded'),
    page.getByRole('button', { name: /save/i }).click(),
  ]);

  // URL after save is typically .../core/user/<id>/change/
  const url = page.url();
  const match = url.match(/\/core\/user\/(\d+)\//);
  if (!match) throw new Error(`Could not parse created doctor id from URL: ${url}`);
  return Number(match[1]);
}

async function deleteUserViaAdmin(page: Page, userId: number) {
  await page.goto(`${ADMIN_BASE_PATH}/core/user/${userId}/delete/`);
  await page.waitForLoadState('domcontentloaded');
  await adminLoginIfNeeded(page, process.env.E2E_USER, process.env.E2E_PASSWORD);

  // If there are protected related objects, Django shows a "Cannot delete" page.
  if (await page.getByText(/cannot delete/i).count()) {
    return { deleted: false, reason: 'protected' as const };
  }

  await Promise.all([
    page.waitForLoadState('domcontentloaded'),
    page.locator('input[type="submit"], button[type="submit"]').first().click(),
  ]);
  return { deleted: true, reason: 'deleted' as const };
}

test.describe('Doctors CRUD (Admin UI)', () => {
  test('Create/Read/Update/Delete doctor user via admin UI', async ({ page, baseURL }) => {
    // Use dashboard header to ensure the authenticated browser session is alive.
    await page.goto(`${baseURL}/praxi_backend/dashboard/`);
    const nav = new NavPage(page);
    await nav.expectHeaderVisible();
    await nav.gotoAdmin();

    // We might land on admin index (or login). Ensure login if needed.
    await page.waitForLoadState('domcontentloaded');
    await adminLoginIfNeeded(page, process.env.E2E_USER, process.env.E2E_PASSWORD);

    const suffix = `${Date.now()}`;
    const username = `e2e_doctor_${suffix}`;
    const password = `Pw!${suffix}`;
    const email = `e2e.doctor.${suffix}@example.com`;
    const firstName = 'E2E';
    const lastName = `Doctor ${suffix}`;

    const userId = await createDoctorViaAdmin(page, { username, email, firstName, lastName, password });

    // Read/list: changelist filtered by username
    await page.goto(`${ADMIN_BASE_PATH}/core/user/?q=${encodeURIComponent(username)}`);
    await page.waitForLoadState('domcontentloaded');
    await adminLoginIfNeeded(page, process.env.E2E_USER, process.env.E2E_PASSWORD);
    await expect(page.getByRole('link', { name: username })).toBeVisible();

    // Update: change last name
    await page.goto(`${ADMIN_BASE_PATH}/core/user/${userId}/change/`);
    await page.waitForLoadState('domcontentloaded');
    await adminLoginIfNeeded(page, process.env.E2E_USER, process.env.E2E_PASSWORD);
    await page.locator('#id_last_name').fill(`${lastName} Updated`);
    await Promise.all([
      page.waitForLoadState('domcontentloaded'),
      page.getByRole('button', { name: /save/i }).click(),
    ]);
    await expect(page.locator('.messagelist')).toContainText(/changed successfully|success/i);

    // Delete
    const del = await deleteUserViaAdmin(page, userId);
    expect(del.deleted).toBeTruthy();
  });

  test('Dependency rule: prevent deleting doctor with appointments', async ({ page, baseURL }) => {
    const api = new ApiClient();
    await api.init();

    const createdAppointmentIds: Array<number | string> = [];
    let userId: number | null = null;

    try {
      await page.goto(`${baseURL}/praxi_backend/dashboard/`);
      const nav = new NavPage(page);
      await nav.expectHeaderVisible();
      await nav.gotoAdmin();
      await page.waitForLoadState('domcontentloaded');
      await adminLoginIfNeeded(page, process.env.E2E_USER, process.env.E2E_PASSWORD);

      const suffix = `${Date.now()}`;
      const username = `e2e_doctor_dep_${suffix}`;
      const password = `Pw!${suffix}`;
      const email = `e2e.doctor.dep.${suffix}@example.com`;
      userId = await createDoctorViaAdmin(page, {
        username,
        email,
        firstName: 'E2E',
        lastName: `DoctorDep ${suffix}`,
        password,
      });

      // Create a patient (API)
      const patientRes = await api.createPatient({ first_name: 'E2E', last_name: `DoctorDepPatient ${suffix}` });
      if (!patientRes.ok()) {
        const txt = await patientRes.text();
        test.skip(true, `Could not create patient: ${patientRes.status()} ${txt}`);
        return;
      }
      const p = await patientRes.json();
      const patientId = Number(p.id || p.pk);
      test.skip(!patientId, 'Missing patient id');

      // Get a type
      const typesRes = await api.listAppointmentTypes();
      expect(typesRes.ok()).toBeTruthy();
      const types = await typesRes.json();
      const typeId = Number((Array.isArray(types) ? types[0] : types?.results?.[0])?.id);
      test.skip(!typeId, 'No appointment type available');

      // Create appointment referencing this doctor
      const start = new Date(Date.now() + 2 * 60 * 60 * 1000);
      const end = new Date(start.getTime() + 30 * 60 * 1000);
      const apptRes = await api.createAppointment({
        patient_id: patientId,
        doctor: userId,
        type: typeId,
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        notes: 'E2E doctor delete dependency',
      });

      if (!apptRes.ok()) {
        const txt = await apptRes.text();
        test.skip(true, `Could not create appointment for dependency: ${apptRes.status()} ${txt}`);
        return;
      }
      const appt = await apptRes.json();
      const apptId = appt.id || appt.pk;
      expect(apptId).toBeTruthy();
      createdAppointmentIds.push(apptId);

      // Attempt to delete doctor in admin: should be protected due to Appointment.doctor on_delete=PROTECT
      const delAttempt = await deleteUserViaAdmin(page, userId);
      expect(delAttempt.deleted).toBeFalsy();
      await expect(page.getByText(/cannot delete/i)).toBeVisible();

      // Cleanup: remove appointment and then delete user
      for (const id of createdAppointmentIds) {
        await api.deleteAppointment(id);
      }
      createdAppointmentIds.length = 0;

      const delAfter = await deleteUserViaAdmin(page, userId);
      expect(delAfter.deleted).toBeTruthy();
      userId = null;
    } finally {
      for (const id of createdAppointmentIds) {
        await api.deleteAppointment(id);
      }
      if (userId) {
        try {
          await deleteUserViaAdmin(page, userId);
        } catch {
          // ignore
        }
      }
      await api.dispose();
    }
  });

  test('Negative validation: missing required fields', async ({ page }) => {
    await page.goto(`${ADMIN_BASE_PATH}/core/user/add/`);
    await page.waitForLoadState('domcontentloaded');
    await adminLoginIfNeeded(page, process.env.E2E_USER, process.env.E2E_PASSWORD);

    // Submit with missing fields
    await Promise.all([
      page.waitForLoadState('domcontentloaded'),
      page.getByRole('button', { name: /save/i }).click(),
    ]);
    await expect(page.locator('.errorlist')).toBeVisible();
  });
});
