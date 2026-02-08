#!/usr/bin/env node

const fs = require('fs');
const { execSync } = require('child_process');
const path = require('path');
const { request } = require('playwright');

const STORAGE_PATH = process.env.STORAGE_PATH || path.join('tests', 'fixtures', 'storageState.json');
const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';
const SEED_COMMAND = process.env.SEED_COMMAND || '';

const ENDPOINTS = [
  { key: 'patients', path: '/api/patients/' },
  { key: 'appointments', path: '/api/appointments/' },
  { key: 'kpis', path: '/api/kpis/' },
  { key: 'operations', path: '/api/operations/' },
];

function output(status, details = {}, exitCode = 0) {
  const payload = { status, ...details };
  console.log(JSON.stringify(payload, null, 2));
  process.exit(exitCode);
}

function ensureStorage() {
  if (!fs.existsSync(STORAGE_PATH)) {
    output('error', { reason: 'missing-storage', storagePath: STORAGE_PATH }, 1);
  }
}

function extractCount(json) {
  if (Array.isArray(json)) return json.length;
  if (json && Array.isArray(json.results)) return json.results.length;
  if (json && typeof json.count === 'number') return json.count;
  return 0;
}

async function fetchCounts(ctx) {
  const results = [];
  for (const ep of ENDPOINTS) {
    try {
      const res = await ctx.get(ep.path);
      if (!res.ok()) {
        results.push({ key: ep.key, status: res.status(), count: 0 });
        continue;
      }
      const data = await res.json();
      results.push({ key: ep.key, status: res.status(), count: extractCount(data) });
    } catch (err) {
      results.push({ key: ep.key, status: 0, count: 0, error: err.message });
    }
  }
  return results;
}

async function main() {
  ensureStorage();
  const ctx = await request.newContext({ baseURL: BASE_URL, storageState: STORAGE_PATH });

  const before = await fetchCounts(ctx);
  const emptyKeys = before.filter((r) => r.count === 0 || r.status >= 400 || r.status === 0).map((r) => r.key);

  if (emptyKeys.length && !SEED_COMMAND) {
    await ctx.dispose();
    output('error', { reason: 'missing-data', empty: emptyKeys, message: 'No SEED_COMMAND provided' }, 1);
  }

  if (emptyKeys.length && SEED_COMMAND) {
    try {
      execSync(SEED_COMMAND, { stdio: 'inherit', env: process.env });
    } catch (err) {
      await ctx.dispose();
      output('error', { reason: 'seed-command-failed', empty: emptyKeys, message: err.message }, 1);
    }
  }

  const after = await fetchCounts(ctx);
  await ctx.dispose();

  const stillEmpty = after.filter((r) => r.count === 0 || r.status >= 400 || r.status === 0).map((r) => r.key);
  if (stillEmpty.length) {
    output('error', { reason: 'seed-incomplete', empty: stillEmpty, before, after }, 1);
  }

  output('ok', { before, after }, 0);
}

main().catch((err) => {
  console.error(err);
  output('error', { reason: 'exception', message: err.message }, 1);
});