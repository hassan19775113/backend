// tools/ai-startup-fix-agent/fixes/fixAuthSetup.js

import fs from "fs";
import path from "path";

export function applyFixAuthSetup(filePath) {
    const abs = path.resolve(process.cwd(), filePath);
    if (fs.existsSync(abs)) {
        console.log("ℹ️  auth.setup.ts exists – no changes needed.");
        return false;
    }

    fs.mkdirSync(path.dirname(abs), { recursive: true });
    const content = `import { request, chromium, type FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const STORAGE_PATH = path.resolve(process.cwd(), 'tests', 'fixtures', 'storageState.json');

async function globalSetup(_config: FullConfig) {
  const baseURL = process.env.BASE_URL || 'http://localhost:8000';
  const username = process.env.E2E_USER;
  const password = process.env.E2E_PASSWORD;

  if (!username || !password) {
    throw new Error('E2E_USER or E2E_PASSWORD missing in ENV');
  }

  const api = await request.newContext({ baseURL });
  const health = await api.get('/api/health/');
  if (!health.ok()) {
    throw new Error('Healthcheck failed before login');
  }

  const loginResponse = await api.post('/api/auth/login/', { data: { username, password } });
  if (!loginResponse.ok()) {
    const body = await loginResponse.text();
    throw new Error(
      'Login failed: ' + loginResponse.status() + ' - ' + body
    );
  }

  const json: any = await loginResponse.json();

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ baseURL });
  const page = await context.newPage();
  await page.goto(
    '/admin/login/?next=' + encodeURIComponent('/praxi_backend/dashboard/'),
    { waitUntil: 'domcontentloaded' }
  );
  await page.locator('#id_username, input[name="username"]').fill(username);
  await page.locator('#id_password, input[name="password"]').fill(password);
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }).catch(() => null),
    page.locator('input[type="submit"], button[type="submit"]').first().click(),
  ]);

  await page.evaluate(
    ({ access, refresh }) => {
      localStorage.setItem('access_token', access);
      localStorage.setItem('refresh_token', refresh);
    },
    { access: json.access, refresh: json.refresh }
  );

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
`;

    fs.writeFileSync(abs, content, "utf8");
    console.log("✅ auth.setup.ts created at tests/fixtures/auth.setup.ts");
    return true;
}
