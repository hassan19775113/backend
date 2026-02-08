import { request, chromium, type FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const STORAGE_PATH = path.join(__dirname, 'storageState.json');

async function globalSetup(config: FullConfig) {
  const baseURL = process.env.BASE_URL || 'http://localhost:8000';
  const username = process.env.E2E_USER;
  const password = process.env.E2E_PASSWORD;

  console.log("DEBUG ENV username:", username);
  console.log("DEBUG ENV password:", password ? "***" : undefined);
  console.log("DEBUG ENV BASE_URL:", baseURL);

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

  const tryLogin = async (payload: Record<string, string>) => {
    console.log("DEBUG Login payload:", payload);
    // Trailing slash matches Django route and avoids 301 on POST
    return api.post('/api/auth/login/', { data: payload });
  };

  let loginResponse = await tryLogin({ username, password });

  console.log('Login response status:', loginResponse.status());
  console.log('Login response body:', await loginResponse.text());

  if (!loginResponse.ok()) {
    loginResponse = await tryLogin({ username, password });
  }

  if (!loginResponse.ok()) {
    const body = await loginResponse.text();
    throw new Error(`Login failed: ${loginResponse.status()} - ${body}`);
  }

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ baseURL });

  const apiState = await api.storageState();
  if (apiState.cookies.length) {
    await page.context().addCookies(apiState.cookies);
  }

  await page.goto('/');

  await page.context().storageState({ path: STORAGE_PATH });

  await browser.close();
  await api.dispose();

  if (!fs.existsSync(STORAGE_PATH)) {
    throw new Error('storageState.json was not created');
  }
}

export default globalSetup;
