import { request, chromium, type FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const STORAGE_PATH = path.resolve(process.cwd(), 'tests', 'fixtures', 'storageState.json');

async function globalSetup(config: FullConfig) {
  const baseURL = process.env.BASE_URL || 'http://localhost:8000';
  const username = process.env.E2E_USER;
  const password = process.env.E2E_PASSWORD;

  if (!username || !password) {
    throw new Error("E2E_USER or E2E_PASSWORD missing in ENV");
  }

  const api = await request.newContext({ baseURL });

  // Ensure backend is healthy before attempting login to reduce flaky 5xx/redirects
  const health = await api.get('/api/health/');
  if (!health.ok()) {
    const body = await health.text();
    throw new Error(`Healthcheck failed: ${health.status()} - ${body}`);
  }

  const loginResponse = await api.post('/api/auth/login/', { data: { username, password } });
  if (!loginResponse.ok()) {
    const body = await loginResponse.text();
    throw new Error(`Login failed: ${loginResponse.status()} - ${body}`);
  }

  const json = (await loginResponse.json()) as any;
  if (!json?.access || !json?.refresh) {
    throw new Error(`Login response missing tokens (keys: ${Object.keys(json || {}).join(',')})`);
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ baseURL });
  const page = await context.newPage();

  // Establish Django admin/session auth for server-rendered dashboard routes.
  await page.goto(`/admin/login/?next=${encodeURIComponent('/praxi_backend/dashboard/')}`, { waitUntil: 'domcontentloaded' });
  await page.locator('#id_username, input[name="username"]').fill(username);
  await page.locator('#id_password, input[name="password"]').fill(password);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }).catch(() => null),
    page.locator('input[type="submit"], button[type="submit"]').first().click(),
  ]);

  if (page.url().includes('/admin/login')) {
    throw new Error('Admin login failed during Playwright globalSetup');
  }

  // Persist JWT for frontend API calls (JS reads it from localStorage).
  await page.evaluate(({ access, refresh }) => {
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
  }, { access: json.access, refresh: json.refresh });

  await context.storageState({ path: STORAGE_PATH });

  await page.close();
  await context.close();
  await browser.close();
  await api.dispose();

  if (!fs.existsSync(STORAGE_PATH)) {
    throw new Error('storageState.json was not created');
  }
}

export default globalSetup;
