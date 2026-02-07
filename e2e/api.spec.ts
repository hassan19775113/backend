import { test, expect } from '@playwright/test';
import { withApiClient } from '../utils/api-client';

// Basic API reachability checks using authenticated context

test('appointments API returns list', async () => {
  await withApiClient(async (api) => {
    const res = await api.listAppointments({ limit: '5' });
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data).toBeTruthy();
  });
});

test('availability API responds', async () => {
  await withApiClient(async (api) => {
    const start = new Date();
    const end = new Date(start.getTime() + 30 * 60 * 1000);
    const res = await api.checkAvailability(start.toISOString(), end.toISOString());
    expect(res.ok()).toBeTruthy();
  });
});

test('doctors API returns entries', async () => {
  await withApiClient(async (api) => {
    const res = await api.listDoctors();
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data).toBeTruthy();
  });
});

test('appointment types API returns entries', async () => {
  await withApiClient(async (api) => {
    const res = await api.listAppointmentTypes();
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data).toBeTruthy();
  });
});
