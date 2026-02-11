import { test, expect } from '@playwright/test';

import { ApiClient } from '../../api-client';
import { NavPage } from '../pages/nav-page';

type Resource = {
  id: number;
  name: string;
  type: 'room' | 'device' | string;
  color?: string;
  active?: boolean;
};

function jsonContains(body: any, needle: string) {
  const raw = typeof body === 'string' ? body : JSON.stringify(body || {});
  return raw.toLowerCase().includes(needle.toLowerCase());
}

test.describe('Resources CRUD (API + dashboard list)', () => {
  test('Create/Read/Update/Delete resource', async ({ page, baseURL }) => {
    const api = new ApiClient();
    await api.init();

    const suffix = `${Date.now()}`;
    const name = `E2E Resource ${suffix}`;
    let resourceId: number | null = null;

    try {
      // Create
      const createRes = await api.post('/api/resources/', {
        name,
        type: 'room',
        active: true,
      });

      if (createRes.status() === 403) {
        test.skip(true, 'Current test user cannot create resources (RBAC)');
        return;
      }

      expect(createRes.ok()).toBeTruthy();
      const created = (await createRes.json()) as Resource;
      expect(created.id).toBeTruthy();
      resourceId = Number(created.id);

      // Read/list (API)
      const detailRes = await api.get(`/api/resources/${resourceId}/`);
      expect(detailRes.ok()).toBeTruthy();
      const detail = (await detailRes.json()) as Resource;
      expect(detail.name).toBe(name);

      // Read/list (UI dashboard)
      await page.goto(`${baseURL}/praxi_backend/dashboard/`);
      const nav = new NavPage(page);
      await nav.expectHeaderVisible();
      await nav.gotoResources();
      await expect(page.getByText(name).first()).toBeVisible();

      // Update
      const updatedName = `${name} Updated`;
      const updateRes = await api.put(`/api/resources/${resourceId}/`, {
        name: updatedName,
        type: 'room',
        active: true,
      });
      expect(updateRes.ok()).toBeTruthy();

      const detailRes2 = await api.get(`/api/resources/${resourceId}/`);
      expect(detailRes2.ok()).toBeTruthy();
      const detail2 = (await detailRes2.json()) as Resource;
      expect(detail2.name).toBe(updatedName);

      // Delete
      const delRes = await api.del(`/api/resources/${resourceId}/`);
      expect(delRes.ok()).toBeTruthy();
      resourceId = null;
    } finally {
      if (resourceId) {
        try {
          await api.del(`/api/resources/${resourceId}/`);
        } catch {
          // ignore
        }
      }
      await api.dispose();
    }
  });

  test('Dependency rule: prevent deleting resource assigned to appointments', async ({}) => {
    const api = new ApiClient();
    await api.init();

    const suffix = `${Date.now()}`;
    const name = `E2E Resource Dep ${suffix}`;
    const createdAppointmentIds: Array<number | string> = [];
    let resourceId: number | null = null;

    try {
      const createRes = await api.post('/api/resources/', {
        name,
        type: 'room',
        active: true,
      });
      if (createRes.status() === 403) {
        test.skip(true, 'Current test user cannot create resources (RBAC)');
        return;
      }
      expect(createRes.ok()).toBeTruthy();
      const created = (await createRes.json()) as Resource;
      resourceId = Number(created.id);

      // Create doctor, patient, type for appointment
      const doctorsRes = await api.listDoctors();
      expect(doctorsRes.ok()).toBeTruthy();
      const doctors = await doctorsRes.json();
      const doctorId = Number((Array.isArray(doctors) ? doctors[0] : doctors?.results?.[0])?.id);
      test.skip(!doctorId, 'No doctor available');

      const patientRes = await api.createPatient({ first_name: 'E2E', last_name: `ResDepPatient ${suffix}` });
      if (!patientRes.ok()) {
        const txt = await patientRes.text();
        test.skip(true, `Could not create patient: ${patientRes.status()} ${txt}`);
        return;
      }
      const p = await patientRes.json();
      const patientId = Number(p.id || p.pk);
      test.skip(!patientId, 'Missing patient id');

      const typesRes = await api.listAppointmentTypes();
      expect(typesRes.ok()).toBeTruthy();
      const types = await typesRes.json();
      const typeId = Number((Array.isArray(types) ? types[0] : types?.results?.[0])?.id);
      test.skip(!typeId, 'No appointment type available');

      const start = new Date(Date.now() + 3 * 60 * 60 * 1000);
      const end = new Date(start.getTime() + 30 * 60 * 1000);
      const apptRes = await api.createAppointment({
        patient_id: patientId,
        doctor: doctorId,
        type: typeId,
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        notes: 'E2E resource delete dependency',
        resource_ids: [resourceId],
      });

      if (!apptRes.ok()) {
        const txt = await apptRes.text();
        test.skip(true, `Could not create resource appointment: ${apptRes.status()} ${txt}`);
        return;
      }
      const appt = await apptRes.json();
      const apptId = appt.id || appt.pk;
      createdAppointmentIds.push(apptId);

      // Attempt delete (should be blocked)
      const delRes = await api.del(`/api/resources/${resourceId}/`);
      expect(delRes.ok()).toBeFalsy();
      expect([400, 409]).toContain(delRes.status());
      const body = await delRes.text();
      expect(jsonContains(body, 'assigned') || jsonContains(body, 'appointment') || jsonContains(body, 'resource')).toBeTruthy();

      // Cleanup: delete appointment then delete resource should succeed
      for (const id of createdAppointmentIds) {
        await api.deleteAppointment(id);
      }
      createdAppointmentIds.length = 0;

      const delRes2 = await api.del(`/api/resources/${resourceId}/`);
      expect(delRes2.ok()).toBeTruthy();
      resourceId = null;
    } finally {
      for (const id of createdAppointmentIds) {
        await api.deleteAppointment(id);
      }
      if (resourceId) {
        try {
          await api.del(`/api/resources/${resourceId}/`);
        } catch {
          // ignore
        }
      }
      await api.dispose();
    }
  });

  test('Negative validation: missing fields / invalid formats', async () => {
    const api = new ApiClient();
    await api.init();
    try {
      const r1 = await api.post('/api/resources/', { type: 'room', active: true });
      if (r1.status() === 403) {
        test.skip(true, 'Current test user cannot create resources (RBAC)');
        return;
      }
      expect(r1.ok()).toBeFalsy();
      expect([400, 422]).toContain(r1.status());

      const r2 = await api.post('/api/resources/', {
        name: `BadType ${Date.now()}`,
        type: 'not-a-type',
        active: true,
      });
      expect(r2.ok()).toBeFalsy();
      expect([400, 422]).toContain(r2.status());
    } finally {
      await api.dispose();
    }
  });
});
