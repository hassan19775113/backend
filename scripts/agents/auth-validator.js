#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { chromium, request } from 'playwright';

const STORAGE_PATH = process.env.STORAGE_PATH || path.join('tests', 'fixtures', 'storageState.json');
const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';
const E2E_USER = process.env.E2E_USER;
const E2E_PASSWORD = process.env.E2E_PASSWORD;

const OUTPUT_PATH =
  process.env.AUTH_VALIDATOR_OUTPUT_PATH ||
  path.join(process.env.AGENT_OUTPUT_DIR || 'agent-outputs', 'auth-validator.json');

const PROTECTED_PATH = '/praxi_backend/patients/';

function nowIso() {
  try {
    return new Date().toISOString();
  } catch {
    return String(Date.now());
  }
}

function safeJsonStringify(value) {
  try {
    return JSON.stringify(value, null, 2);
  } catch (e) {
    return JSON.stringify(
      {
        status: 'error',
        reason: 'json_stringify_failed',
        details: String(e?.message || e),
        timestamp: nowIso(),
      },
      null,
      2,
    );
  }
}

function safeWriteJson(filePath, data) {
  try {
    const dir = path.dirname(filePath);
    fs.mkdirSync(dir, { recursive: true });
    const tmp = `${filePath}.tmp.${process.pid}.${Date.now()}`;
    fs.writeFileSync(tmp, safeJsonStringify(data) + '\n', 'utf8');
    fs.renameSync(tmp, filePath);
  } catch {
    try {
      const fallback = safeJsonStringify(data) + '\n';
      const dir = path.dirname(filePath);
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(filePath, fallback, 'utf8');
    } catch {
      // never throw
    }
  }
}

function toErrorDetails(err) {
  if (!err) return null;
  if (typeof err === 'string') return err;
  return {
    name: err.name,
    message: err.message,
    stack: err.stack,
  };
}

const resources = {
  browser: null,
  context: null,
  page: null,
  api: null,
};

async function safeClosePlaywright() {
  const closers = [
    async () => {
      if (resources.page) await resources.page.close().catch(() => null);
      resources.page = null;
    },
    async () => {
      if (resources.context) await resources.context.close().catch(() => null);
      resources.context = null;
    },
    async () => {
      if (resources.browser) await resources.browser.close().catch(() => null);
      resources.browser = null;
    },
    async () => {
      if (resources.api) await resources.api.dispose().catch(() => null);
      resources.api = null;
    },
  ];

  for (const close of closers) {
    try {
      await close();
    } catch {
      // ignore
    }
  }
}

async function fail(reason, details) {
  const payload = {
    status: 'error',
    reason: String(reason || 'unknown_error'),
    details: details ?? null,
    timestamp: nowIso(),
  };

  try {
    console.error(`[auth-validator] ${payload.reason}`);
  } catch {
    // ignore
  }

  try {
    safeWriteJson(OUTPUT_PATH, payload);
  } catch {
    // ignore
  }

  try {
    console.log(safeJsonStringify(payload));
  } catch {
    // ignore
  }

  await safeClosePlaywright();
  process.exit(0);
}

function storageExists(storagePath) {
  try {
    return fs.existsSync(storagePath);
  } catch {
    return false;
  }
}

function shouldRetryChromiumLaunch(err) {
  const msg = String(err?.message || err || '').toLowerCase();
  return (
    msg.includes('target page, context or browser has been closed') ||
    msg.includes('browser has been closed') ||
    msg.includes('crash') ||
    msg.includes('closed')
  );
}

async function launchChromiumWithRetry() {
  let lastErr = null;
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    try {
      resources.browser = await chromium.launch({ headless: true });
      return resources.browser;
    } catch (e) {
      lastErr = e;
      await safeClosePlaywright();
      if (attempt === 1 && shouldRetryChromiumLaunch(e)) {
        continue;
      }
      break;
    }
  }
  await fail('chromium_launch_failed', toErrorDetails(lastErr));
  return null;
}

async function checkHealth(storageStatePath) {
  let browser = null;
  let context = null;
  let page = null;

  try {
    browser = await chromium.launch({ headless: true });
    context = await browser.newContext({ baseURL: BASE_URL, storageState: storageStatePath });
    page = await context.newPage();

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

    if (!resp) return false;
    if (redirectedToLogin || hasLoginForm) return false;
    if (!tokenCheck.ok) return false;
    return true;
  } catch {
    return false;
  } finally {
    try {
      if (page) await page.close().catch(() => null);
      if (context) await context.close().catch(() => null);
      if (browser) await browser.close().catch(() => null);
    } catch {
      // ignore
    }
  }
}

async function fetchJwtTokens() {
  if (!E2E_USER || !E2E_PASSWORD) {
    await fail('missing_env', { message: 'E2E_USER or E2E_PASSWORD missing' });
    return null;
  }

  try {
    resources.api = await request.newContext({ baseURL: BASE_URL });
    let resp = await resources.api.post('/api/auth/login/', {
      data: { username: E2E_USER, password: E2E_PASSWORD },
    });
    if (!resp.ok()) {
      resp = await resources.api.post('/api/auth/login/', {
        data: { email: E2E_USER, password: E2E_PASSWORD },
      });
    }

    if (!resp.ok()) {
      const body = await resp.text().catch(() => null);
      await fail('login_failed', { status: resp.status(), body });
      return null;
    }

    const json = await resp.json().catch(() => null);
    if (!json?.access || !json?.refresh) {
      await fail('login_invalid_response', { keys: Object.keys(json || {}) });
      return null;
    }

    return { access: json.access, refresh: json.refresh };
  } catch (e) {
    await fail('login_failed', toErrorDetails(e));
    return null;
  } finally {
    try {
      if (resources.api) await resources.api.dispose().catch(() => null);
    } catch {
      // ignore
    }
    resources.api = null;
  }
}

async function performAdminLogin(tokens) {
  if (!E2E_USER || !E2E_PASSWORD) {
    throw new Error('missing_env');
  }

  fs.mkdirSync(path.dirname(STORAGE_PATH), { recursive: true });

  await launchChromiumWithRetry();
  resources.context = await resources.browser.newContext({ baseURL: BASE_URL });
  resources.page = await resources.context.newPage();

  await resources.page.goto(`/admin/login/?next=${encodeURIComponent(PROTECTED_PATH)}`, {
    waitUntil: 'domcontentloaded',
  });

  await resources.page.locator('#id_username, input[name="username"]').fill(E2E_USER);
  await resources.page.locator('#id_password, input[name="password"]').fill(E2E_PASSWORD);

  const submit = resources.page.locator('input[type="submit"], button[type="submit"]').first();
  await Promise.all([
    resources.page.waitForNavigation({ waitUntil: 'domcontentloaded' }).catch(() => null),
    submit.click(),
  ]);

  // Retry-friendly check: sometimes waitForNavigation resolves early; give the redirect a moment.
  try {
    await resources.page.waitForURL((url) => !String(url).includes('/admin/login'), { timeout: 15_000 });
  } catch {
    // ignore; we check URL below
  }

  if (resources.page.url().includes('/admin/login')) {
    const errorText = await resources.page.locator('.errornote, .errorlist').first().textContent().catch(() => null);
    throw new Error(`admin_login_failed${errorText ? `: ${String(errorText).trim()}` : ''}`);
  }

  await resources.page.evaluate(({ access, refresh }) => {
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
  }, tokens);

  await resources.context.storageState({ path: STORAGE_PATH });
}

function shouldRetryLogin(err) {
  const msg = String(err?.message || err || '').toLowerCase();
  return (
    msg.includes('navigation') ||
    msg.includes('timeout') ||
    msg.includes('admin_login_failed') ||
    msg.includes('redirect')
  );
}

async function createBrowserStorageStateWithRetry(tokens) {
  let lastErr = null;
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    try {
      await performAdminLogin(tokens);
      return;
    } catch (e) {
      lastErr = e;
      await safeClosePlaywright();
      if (attempt === 1 && shouldRetryLogin(e)) {
        continue;
      }
      break;
    }
  }
  await fail('login_failed', toErrorDetails(lastErr));
}

async function success() {
  const payload = {
    status: 'success',
    storageState: STORAGE_PATH,
    timestamp: nowIso(),
  };

  safeWriteJson(OUTPUT_PATH, payload);
  console.log(safeJsonStringify(payload));
  await safeClosePlaywright();
  process.exit(0);
}

async function run() {
  try {
    process.on('unhandledRejection', (err) => {
      void fail('unhandled_rejection', toErrorDetails(err));
    });
    process.on('uncaughtException', (err) => {
      void fail('uncaught_exception', toErrorDetails(err));
    });

    // Ensure there's always at least *some* JSON output file, even if we fail very early.
    safeWriteJson(OUTPUT_PATH, {
      status: 'error',
      reason: 'started',
      details: { message: 'auth-validator started but did not complete' },
      timestamp: nowIso(),
    });

    if (storageExists(STORAGE_PATH)) {
      const healthy = await checkHealth(STORAGE_PATH);
      if (healthy) {
        await success();
        return;
      }
    }

    const tokens = await fetchJwtTokens();
    if (!tokens) return;

    await createBrowserStorageStateWithRetry(tokens);

    const healthy = await checkHealth(STORAGE_PATH);
    if (!healthy) {
      await fail('health_failed_after_login', { storageState: STORAGE_PATH });
      return;
    }

    await success();
  } catch (e) {
    await fail('fatal_error', toErrorDetails(e));
  } finally {
    await safeClosePlaywright();
    process.exit(0);
  }
}

await run();