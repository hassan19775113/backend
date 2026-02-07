import { test as base, expect, request } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';
const FIXTURES_DIR = path.join(__dirname, '..', 'fixtures');

const adminState = path.join(FIXTURES_DIR, 'storageState.admin.json');
const doctorState = path.join(FIXTURES_DIR, 'storageState.doctor.json');
const assistantState = path.join(FIXTURES_DIR, 'storageState.assistant.json');

async function loginAndSave(username: string, password: string, target: string) {
  const api = await request.newContext({ baseURL: BASE_URL });
  const tryLogin = async (payload: Record<string, string>) => api.post('/api/auth/login', { data: payload });

  let res = await tryLogin({ username, password });
  if (!res.ok()) {
    res = await tryLogin({ email: username, password });
  }
  if (!res.ok()) {
    const body = await res.text();
    throw new Error(`Login failed for ${username}: ${res.status()} ${res.statusText()} Body: ${body}`);
  }
  await api.storageState({ path: target });
  await api.dispose();
}

const hasAdmin = !!process.env.E2E_ADMIN_USER;
const hasDoctor = !!process.env.E2E_DOCTOR_USER;
const hasAssistant = !!process.env.E2E_ASSIST_USER;

base.beforeAll(async () => {
  if (hasAdmin) await loginAndSave(process.env.E2E_ADMIN_USER!, process.env.E2E_ADMIN_PASSWORD || 'admin', adminState);
  if (hasDoctor) await loginAndSave(process.env.E2E_DOCTOR_USER!, process.env.E2E_DOCTOR_PASSWORD || 'doctor', doctorState);
  if (hasAssistant) await loginAndSave(process.env.E2E_ASSIST_USER!, process.env.E2E_ASSIST_PASSWORD || 'assistant', assistantState);
});

base.describe('roles - admin', () => {
  base.skip(!hasAdmin, 'E2E_ADMIN_USER not set');
  base.use({ storageState: adminState });

  base('admin can access main sections', async ({ page }) => {
    const targets = [
      '/praxi_backend/',
      '/praxi_backend/appointments/',
      '/praxi_backend/patients/',
      '/praxi_backend/doctors/',
      '/praxi_backend/operations/',
      '/praxi_backend/resources/',
    ];
    for (const t of targets) {
      const res = await page.goto(`${BASE_URL}${t}`);
      expect([200, 302]).toContain(res?.status());
    }
  });
});

base.describe('roles - doctor', () => {
  base.skip(!hasDoctor, 'E2E_DOCTOR_USER not set');
  base.use({ storageState: doctorState });

  base('doctor can see appointments but not admin', async ({ page }) => {
    const resSched = await page.goto(`${BASE_URL}/praxi_backend/appointments/`);
    expect([200, 302]).toContain(resSched?.status());

    const resAdmin = await page.goto(`${BASE_URL}/admin/`);
    expect([302, 403]).toContain(resAdmin?.status());
  });
});

base.describe('roles - assistant', () => {
  base.skip(!hasAssistant, 'E2E_ASSIST_USER not set');
  base.use({ storageState: assistantState });

  base('assistant can open patients, limited admin', async ({ page }) => {
    const resPatients = await page.goto(`${BASE_URL}/praxi_backend/patients/`);
    expect([200, 302]).toContain(resPatients?.status());

    const resAdmin = await page.goto(`${BASE_URL}/admin/`);
    expect([302, 403]).toContain(resAdmin?.status());
  });
});
