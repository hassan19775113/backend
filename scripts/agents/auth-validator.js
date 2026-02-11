#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { chromium, request } from 'playwright';

const STORAGE_PATH = process.env.STORAGE_PATH || path.join('tests', 'fixtures', 'storageState.json');
const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';
const E2E_USER = process.env.E2E_USER;
const E2E_PASSWORD = process.env.E2E_PASSWORD;

const PROTECTED_PATH = '/praxi_backend/patients/';

function output(status, details = {}, exitCode = 0) {
  const payload = { status, ...details };
  console.log(JSON.stringify(payload, null, 2));
  process.exit(exitCode);
}

function storageExists() {
  try {
    return fs.existsSync(STORAGE_PATH);
  } catch (_) {
    return false;
  }
}

async function checkHealth(storageStatePath) {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ baseURL: BASE_URL, storageState: storageStatePath });
  const page = await context.newPage();
  try {
    const resp = await page.goto(PROTECTED_PATH, { waitUntil: 'domcontentloaded' });
    const finalUrl = page.url();
    const redirectedToLogin = finalUrl.includes('/admin/login');
    const hasLoginForm = (await page.locator('#id_username, input[name="username"]').count()) > 0;

    const tokenCheck = await page.evaluate(async () => {
      const access = localStorage.getItem('access_token');
      if (!access) return { ok: false, reason: 'missing-access-token' };
      const r = await fetch('/api/auth/me/', {
        headers: {
          Authorization: `Bearer ${access}`,
        },
      });
      return { ok: r.ok, status: r.status };
    });

    await page.close();
    await context.close();
    await browser.close();

    if (!resp) return false;
    if (redirectedToLogin || hasLoginForm) return false;
    if (!tokenCheck.ok) return false;
    return true;
  } catch (_) {
    try {
      await page.close();
      await context.close();
      await browser.close();
    } catch (_) {
      // ignore
    }
    return false;
  }
}

async function fetchJwtTokens() {
  if (!E2E_USER || !E2E_PASSWORD) {
    output('error', { reason: 'missing-env', message: 'E2E_USER or E2E_PASSWORD missing' }, 1);
  }

  const api = await request.newContext({ baseURL: BASE_URL });
  let resp = await api.post('/api/auth/login/', { data: { username: E2E_USER, password: E2E_PASSWORD } });
  if (!resp.ok()) {
    resp = await api.post('/api/auth/login/', { data: { email: E2E_USER, password: E2E_PASSWORD } });
  }
  if (!resp.ok()) {
    const body = await resp.text();
    await api.dispose();
    output('error', { reason: 'login-failed', status: resp.status(), body }, 1);
  }

  const json = await resp.json();
  await api.dispose();

  if (!json?.access || !json?.refresh) {
    output('error', { reason: 'login-invalid-response', keys: Object.keys(json || {}) }, 1);
  }

  return { access: json.access, refresh: json.refresh };
}

async function createBrowserStorageState(tokens) {
  fs.mkdirSync(path.dirname(STORAGE_PATH), { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ baseURL: BASE_URL });
  const page = await context.newPage();

  // Establish Django admin/session auth for server-rendered dashboard routes.
  await page.goto(`/admin/login/?next=${encodeURIComponent(PROTECTED_PATH)}`, { waitUntil: 'domcontentloaded' });
  await page.locator('#id_username, input[name="username"]').fill(E2E_USER);
  await page.locator('#id_password, input[name="password"]').fill(E2E_PASSWORD);

  const submit = page.locator('input[type="submit"], button[type="submit"]').first();
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }).catch(() => null),
    submit.click(),
  ]);

  if (page.url().includes('/admin/login')) {
    const errorText = await page.locator('.errornote, .errorlist').first().textContent().catch(() => null);
    throw new Error(`admin-login-failed${errorText ? `: ${errorText.trim()}` : ''}`);
  }

  // Persist JWT for frontend API calls (JS reads it from localStorage).
  await page.evaluate(({ access, refresh }) => {
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
  }, tokens);

  await context.storageState({ path: STORAGE_PATH });

  await page.close();
  await context.close();
  await browser.close();
}

async function main() {
  let refreshed = false;
  const exists = storageExists();

  if (exists) {
    const healthy = await checkHealth(STORAGE_PATH);
    if (healthy) {
      output('ok', { refreshed: false, storagePath: STORAGE_PATH, baseURL: BASE_URL }, 0);
    }
  }

  const tokens = await fetchJwtTokens();
  await createBrowserStorageState(tokens);
  refreshed = true;

  const healthy = await checkHealth(STORAGE_PATH);
  if (!healthy) {
    output('error', { reason: 'health-failed-after-login' }, 1);
  }

  output('ok', { refreshed, storagePath: STORAGE_PATH, baseURL: BASE_URL }, 0);
}

main().catch((err) => {
  console.error(err);
  output('error', { reason: 'exception', message: err.message }, 1);
});