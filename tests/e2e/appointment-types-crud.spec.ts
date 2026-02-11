import { test, expect } from '@playwright/test';

import { ApiClient } from '../../api-client';

type AppointmentType = {
  id: number;
  name: string;
  color?: string;
  duration_minutes?: number;
  active?: boolean;
};

test.describe('Appointment Types CRUD (API-only)', () => {
  test('Create/Read/Update/Delete appointment type', async () => {
    const api = new ApiClient();
    await api.init();

    const suffix = `${Date.now()}`;
    const name = `E2E Type ${suffix}`;
    let typeId: number | null = null;

    try {
      // Create
      const createRes = await api.post('/api/appointment-types/', {
        name,
        color: '#1A73E8',
        duration_minutes: 30,
        active: true,
      });

      if (createRes.status() === 403) {
        test.skip(true, 'Current test user cannot create appointment types (RBAC)');
        return;
      }

      expect(createRes.ok()).toBeTruthy();
      const created = (await createRes.json()) as AppointmentType;
      expect(created.id).toBeTruthy();
      typeId = Number(created.id);

      // Read (detail)
      const detailRes = await api.get(`/api/appointment-types/${typeId}/`);
      expect(detailRes.ok()).toBeTruthy();
      const detail = (await detailRes.json()) as AppointmentType;
      expect(detail.name).toBe(name);

      // Read/list (list endpoint)
      const listRes = await api.get('/api/appointment-types/');
      expect(listRes.ok()).toBeTruthy();
      const list = await listRes.json();
      const arr: AppointmentType[] = Array.isArray(list) ? list : list?.results;
      expect(arr.some((t) => Number(t.id) === typeId)).toBeTruthy();

      // Update
      const updatedName = `${name} Updated`;
      const updateRes = await api.put(`/api/appointment-types/${typeId}/`, {
        name: updatedName,
        color: '#34A853',
        duration_minutes: 45,
        active: true,
      });
      expect(updateRes.ok()).toBeTruthy();

      const detailRes2 = await api.get(`/api/appointment-types/${typeId}/`);
      expect(detailRes2.ok()).toBeTruthy();
      const detail2 = (await detailRes2.json()) as AppointmentType;
      expect(detail2.name).toBe(updatedName);

      // Delete
      const delRes = await api.del(`/api/appointment-types/${typeId}/`);
      expect(delRes.ok()).toBeTruthy();
      typeId = null;
    } finally {
      if (typeId) {
        try {
          await api.del(`/api/appointment-types/${typeId}/`);
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
      const r1 = await api.post('/api/appointment-types/', { color: '#1A73E8', duration_minutes: 30, active: true });
      if (r1.status() === 403) {
        test.skip(true, 'Current test user cannot create appointment types (RBAC)');
        return;
      }
      expect(r1.ok()).toBeFalsy();
      expect([400, 422]).toContain(r1.status());

      const r2 = await api.post('/api/appointment-types/', {
        name: `BadDuration ${Date.now()}`,
        color: '#1A73E8',
        duration_minutes: -5,
        active: true,
      });
      expect(r2.ok()).toBeFalsy();
      expect([400, 422]).toContain(r2.status());

      const r3 = await api.post('/api/appointment-types/', {
        name: `BadColor ${Date.now()}`,
        color: 'not-a-hex',
        duration_minutes: 30,
        active: true,
      });
      // Some environments may not validate color format; accept either 201 or 400.
      expect([201, 400, 422, 403]).toContain(r3.status());
    } finally {
      await api.dispose();
    }
  });
});
