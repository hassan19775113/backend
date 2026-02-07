import { request, chromium, type FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const STORAGE_PATH = path.join(__dirname, 'storageState.json');

async function globalSetup(config: FullConfig) {
  const baseURL = process.env.BASE_URL || 'http://localhost:8000';
  const username = process.env.E2E_USER || 'admin';
  const password = process.env.E2E_PASSWORD || 'admin';

  const api = await request.newContext({ baseURL });

  const tryLogin = async (payload: Record<string, string>) =>
    api.post('/api/auth/login', { data: payload });

  let loginResponse = await tryLogin({ username, password });

  // DEBUG LOGS
  console.log('Login response status:', loginResponse.status());
  console.log('Login response body:', await loginResponse.text());

  if (!loginResponse.ok()) {
    loginResponse = await tryLogin({ email: username, password });
  }

  if (!loginResponse.ok()) {
    const body = await loginResponse.text();
    throw new Error(
      `Login failed ${loginResponse.status()} ${loginResponse.statusText()} - payload variants tried (username/password, email/password). Body: ${body}`,
    );
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
