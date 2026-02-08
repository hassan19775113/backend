#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { request } from 'playwright';

const STORAGE_PATH = process.env.STORAGE_PATH || path.join('tests', 'fixtures', 'storageState.json');
const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';
const E2E_USER = process.env.E2E_USER;
const E2E_PASSWORD = process.env.E2E_PASSWORD;

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
  const ctx = await request.newContext({ baseURL: BASE_URL, storageState: storageStatePath });
  try {
    const res = await ctx.get('/api/health/');
    const ok = res.ok();
    await ctx.dispose();
    return ok;
  } catch (_) {
    await ctx.dispose();
    return false;
  }
}

async function performLogin() {
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

  await api.storageState({ path: STORAGE_PATH });
  await api.dispose();
  return true;
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

  await performLogin();
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