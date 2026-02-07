import { request, chromium, type FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';

// Global auth setup
// - Logs in via backend API (/api/auth/login) using env credentials.
// - Saves storageState to tests/fixtures/storageState.json for reuse.
// Env vars: E2E_USER, E2E_PASSWORD, BASE_URL (optional, defaults to http://localhost:8000).
// If the login payload differs, adjust the data object below.
const STORAGE_PATH = path.join(__dirname, 'storageState.json');

async function globalSetup(config: FullConfig) {
  const baseURL = process.env.BASE_URL || 'http://localhost:8000';
  const username = process.env.E2E_USER || 'admin';
  const password = process.env.E2E_PASSWORD || 'admin';

  const api = await request.newContext({ baseURL });

  // Perform credential login; try username/password first, fallback to email/password.
  const tryLogin = async (payload: Record<string, string>) =>
    api.post('/api/auth/login', { data: payload });

  let loginResponse = await tryLogin({ username, password });
  if (!loginResponse.ok()) {
    loginResponse = await tryLogin({ email: username, password });
  }

  if (!loginResponse.ok()) {
    const body = await loginResponse.text();
    throw new Error(
      `Login failed ${loginResponse.status()} ${loginResponse.statusText()} - payload variants tried (username/password, email/password). Body: ${body}`,
    );
  }

  // Capture cookies/session into storageState using a real browser context for consistency with UI requests.
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ baseURL });

  // Apply cookies from API context if any
  const apiState = await api.storageState();
  if (apiState.cookies.length) {
    await page.context().addCookies(apiState.cookies);
  }

  // Touch the base page to ensure context is initialized
  await page.goto('/');

  // Persist storage state for all tests.
  await page.context().storageState({ path: STORAGE_PATH });

  await browser.close();
  await api.dispose();

  // Ensure file exists for Playwright use hook.
  if (!fs.existsSync(STORAGE_PATH)) {
    throw new Error('storageState.json was not created');
  }
}

export default globalSetup;
