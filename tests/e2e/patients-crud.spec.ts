import { test, expect, Page } from '@playwright/test';

import { ApiClient } from '../../api-client';
import { adminLoginIfNeeded } from '../helpers/admin-login';
import { NavPage } from '../pages/nav-page';
import { PatientsPage } from '../pages/patients-page';

type Patient = {
  id: number;
  first_name?: string;
  last_name?: string;
  email?: string | null;
  phone?: string | null;
};

const ADMIN_BASE_PATH = '/praxi_backend/Dashboardadministration';

async function createPatientFlexible(api: ApiClient, payload: Record<string, any>): Promise<Patient> {
  const res = await api.post('/api/patients/', payload);
  if (res.ok()) return (await res.json()) as Patient;

  // Some environments require legacy PK `id` on create; retry with a safe 32-bit-ish ID.
  const bodyText = await res.text();
  const needsId = res.status() === 400 && bodyText.toLowerCase().includes('id');
  if (!needsId) {
    throw new Error(`create patient failed: ${res.status()} ${bodyText}`);
  }

  const safeId = Math.floor(Date.now() / 1000) + Math.floor(Math.random() * 1000);
  const retry = await api.post('/api/patients/', { id: safeId, ...payload });
  if (!retry.ok()) {
    const retryBody = await retry.text();
    throw new Error(`create patient retry failed: ${retry.status()} ${retryBody}`);
  }
  return (await retry.json()) as Patient;
}

async function updatePatientFlexible(api: ApiClient, id: number, payload: Record<string, any>) {
  // Most environments accept PATCH without `id`, but some require it.
  const res = await api.put(`/api/patients/${id}/`, payload);
  if (res.ok()) return;

  const bodyText = await res.text();
  const needsId = res.status() === 400 && bodyText.toLowerCase().includes('id');
  if (!needsId) {
    throw new Error(`update patient failed: ${res.status()} ${bodyText}`);
  }

  const retry = await api.put(`/api/patients/${id}/`, { id, ...payload });
  if (!retry.ok()) {
    const retryBody = await retry.text();
    throw new Error(`update patient retry failed: ${retry.status()} ${retryBody}`);
  }
}

async function deletePatient(api: ApiClient, id: number): Promise<'api' | 'not-supported'> {
  const res = await api.del(`/api/patients/${id}/`);
  if (res.status() === 405) return 'not-supported';
  if (!res.ok()) {
    const body = await res.text();
    throw new Error(`delete patient failed: ${res.status()} ${body}`);
  }
  return 'api';
}

async function deletePatientViaAdmin(page: Page, patientId: number) {
  await page.goto(`${ADMIN_BASE_PATH}/patients/patient/${patientId}/delete/`);
  await page.waitForLoadState('domcontentloaded');
  await adminLoginIfNeeded(page, process.env.E2E_USER, process.env.E2E_PASSWORD);

  // Django admin delete confirm page
  const confirm = page.locator('input[type="submit"], button[type="submit"]').filter({ hasText: /delete|löschen/i });
  if (await confirm.count()) {
    await Promise.all([page.waitForLoadState('domcontentloaded'), confirm.first().click()]);
    return;
  }

  // Fallback: sometimes the confirm input has value "Yes, I\'m sure" without text.
  await Promise.all([
    page.waitForLoadState('domcontentloaded'),
    page.locator('input[type="submit"]').first().click(),
  ]);
}

test.describe('Patients CRUD', () => {
  test('Create/Read/Update/Delete patient (API + UI list)', async ({ page, baseURL }) => {
    const api = new ApiClient();
    await api.init();

    const suffix = `${Date.now()}`;
    const lastName = `CRUD Patient ${suffix}`;
    let patientId: number | null = null;

    try {
      // Create
      const created = await createPatientFlexible(api, {
        first_name: 'E2E',
        last_name: lastName,
      });
      expect(created.id).toBeTruthy();
      patientId = Number(created.id);

      // Read (API detail)
      const detailRes = await api.get(`/api/patients/${patientId}/`);
      expect(detailRes.ok()).toBeTruthy();
      const detail = (await detailRes.json()) as Patient;
      expect(detail.id).toBe(patientId);
      expect(String(detail.last_name || '')).toContain('CRUD Patient');

      // Read/list (UI dashboard)
      const nav = new NavPage(page);
      await page.goto(`${baseURL}/praxi_backend/dashboard/`);
      await nav.expectHeaderVisible();
      await nav.gotoPatients();

      const patientsPage = new PatientsPage(page);
      await expect(patientsPage.patientsTable).toBeVisible();
      await patientsPage.search(lastName);
      await expect(patientsPage.patientsTable).toContainText(lastName);

      // Update
      await updatePatientFlexible(api, patientId, {
        first_name: 'E2E',
        last_name: `${lastName} Updated`,
        email: `e2e.${suffix}@example.com`,
        phone: '+49123456789',
      });

      const updatedRes = await api.get(`/api/patients/${patientId}/`);
      expect(updatedRes.ok()).toBeTruthy();
      const updated = (await updatedRes.json()) as Patient;
      expect(updated.email || '').toContain('@example.com');
      expect(updated.last_name || '').toContain('Updated');

      // Delete (API if supported; fallback to admin UI)
      const deletedVia = await deletePatient(api, patientId);
      if (deletedVia === 'not-supported') {
        await deletePatientViaAdmin(page, patientId);
      }
      patientId = null;
    } finally {
      if (patientId) {
        // Best-effort cleanup
        try {
          const deletedVia = await deletePatient(api, patientId);
          if (deletedVia === 'not-supported') {
            await deletePatientViaAdmin(page, patientId);
          }
        } catch {
          // ignore cleanup errors
        }
      }
      await api.dispose();
    }
  });

  test('Dependency rule: prevent deleting patient with appointments', async ({ page }) => {
    const api = new ApiClient();
    await api.init();

    const suffix = `${Date.now()}`;
    const lastName = `CRUD Patient With Appt ${suffix}`;
    const createdAppointmentIds: Array<number | string> = [];
    let patientId: number | null = null;

    try {
      // Create patient
      const created = await createPatientFlexible(api, {
        first_name: 'E2E',
        last_name: lastName,
      });
      patientId = Number(created.id);

      // Pick any doctor and type, then create an appointment for this patient
      const doctorsRes = await api.listDoctors();
      expect(doctorsRes.ok()).toBeTruthy();
      const doctors = await doctorsRes.json();
      const doctorId = Number((Array.isArray(doctors) ? doctors[0] : doctors?.results?.[0])?.id);
      test.skip(!doctorId, 'No doctor available to create dependency appointment');

      const typesRes = await api.listAppointmentTypes();
      expect(typesRes.ok()).toBeTruthy();
      const types = await typesRes.json();
      const typeId = Number((Array.isArray(types) ? types[0] : types?.results?.[0])?.id);
      test.skip(!typeId, 'No appointment type available to create dependency appointment');

      const start = new Date(Date.now() + 60 * 60 * 1000);
      const end = new Date(start.getTime() + 30 * 60 * 1000);
      const apptRes = await api.createAppointment({
        patient_id: patientId,
        doctor: doctorId,
        type: typeId,
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        notes: 'E2E patient delete dependency',
      });

      if (!apptRes.ok()) {
        const bodyText = await apptRes.text();
        test.skip(true, `Could not create dependency appointment: ${apptRes.status()} ${bodyText}`);
        return;
      }

      const appt = await apptRes.json();
      const apptId = appt.id || appt.pk;
      expect(apptId).toBeTruthy();
      createdAppointmentIds.push(apptId);

      // Attempt delete: require API delete support for a deterministic rule check.
      const delRes = await api.del(`/api/patients/${patientId}/`);
      test.skip(delRes.status() === 405, 'Patient DELETE endpoint not available; cannot enforce dependency rule via API');

      expect(delRes.ok()).toBeFalsy();
      expect([400, 409]).toContain(delRes.status());
      const delBody = await delRes.text();
      expect(delBody.toLowerCase()).toContain('appointment');

      // Cleanup: remove appointment then delete should succeed
      for (const id of createdAppointmentIds) {
        await api.deleteAppointment(id);
      }
      createdAppointmentIds.length = 0;

      const delRes2 = await api.del(`/api/patients/${patientId}/`);
      expect(delRes2.ok()).toBeTruthy();
      patientId = null;
    } finally {
      for (const id of createdAppointmentIds) {
        await api.deleteAppointment(id);
      }
      if (patientId) {
        try {
          const deletedVia = await deletePatient(api, patientId);
          if (deletedVia === 'not-supported') {
            await deletePatientViaAdmin(page, patientId);
          }
        } catch {
          // ignore
        }
      }
      await api.dispose();
    }
  });

  test('Negative validation: missing required fields / invalid formats', async () => {
    const api = new ApiClient();
    await api.init();
    try {
      // Missing last_name should be rejected in stricter environments.
      const r1 = await api.post('/api/patients/', { first_name: 'E2E' });
      expect(r1.ok()).toBeFalsy();
      expect([400, 422]).toContain(r1.status());

      // Invalid email
      const r2 = await api.post('/api/patients/', {
        first_name: 'E2E',
        last_name: `InvalidEmail ${Date.now()}`,
        email: 'not-an-email',
      });
      expect(r2.ok()).toBeFalsy();
      expect([400, 422]).toContain(r2.status());
    } finally {
      await api.dispose();
    }
  });
});
