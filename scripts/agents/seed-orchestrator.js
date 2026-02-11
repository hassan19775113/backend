#!/usr/bin/env node

import { spawnSync } from 'node:child_process';
import { request } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';
const SEED_COMMAND = process.env.SEED_COMMAND || '';

const ENDPOINTS = [
  { key: 'patients', path: '/api/patients/' },
  { key: 'appointments', path: '/api/appointments/' },
  { key: 'operations', path: '/api/operations/' },
];

function output(status, details = {}, exitCode = 0) {
  const payload = { status, ...details };
  try {
    const json = JSON.stringify(payload, null, 2);
    if (typeof json !== 'string') {
      throw new Error('invalid-json');
    }
    console.log(json);
  } catch (err) {
    const fallback = { status: 'error', reason: 'invalid-json', message: err.message };
    console.log(JSON.stringify(fallback));
    process.exit(1);
  }
  process.exit(exitCode);
}

function truncateLog(value, limit = 10000) {
  if (!value) return '';
  if (value.length <= limit) return value;
  return `${value.slice(0, limit)}\n...truncated...`;
}

async function loginAndGetToken() {
  const api = await request.newContext({ baseURL: BASE_URL });
  
  const E2E_USER = process.env.E2E_USER || 'e2e_ci';
  const E2E_PASSWORD = process.env.E2E_PASSWORD || 'e2e_ci_pw';
  
  let resp = await api.post('/api/auth/login/', { 
    data: { username: E2E_USER, password: E2E_PASSWORD } 
  });
  
  if (!resp.ok()) {
    resp = await api.post('/api/auth/login/', { 
      data: { email: E2E_USER, password: E2E_PASSWORD } 
    });
  }
  
  if (!resp.ok()) {
    const body = await resp.text();
    await api.dispose();
    output('error', { reason: 'login-failed', status: resp.status(), body }, 1);
  }
  
  const { access } = await resp.json();
  await api.dispose();
  return access;
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
  // Get fresh JWT token
  const accessToken = await loginAndGetToken();

  // Create context WITH JWT token in Authorization header
  let ctx = await request.newContext({ 
    baseURL: BASE_URL,
    extraHTTPHeaders: {
      'Authorization': `Bearer ${accessToken}`
    }
  });
  let seedLogs = '';

  const before = await fetchCounts(ctx);
  const emptyKeys = before.filter((r) => r.count === 0 || r.status >= 400 || r.status === 0).map((r) => r.key);

  if (emptyKeys.length && !SEED_COMMAND) {
    await ctx.dispose();
    output('error', { reason: 'missing-data', empty: emptyKeys, message: 'No SEED_COMMAND provided' }, 1);
  }

  if (emptyKeys.length && SEED_COMMAND) {
    const result = spawnSync(SEED_COMMAND, {
      shell: true,
      env: process.env,
      encoding: 'utf8',
      maxBuffer: 10 * 1024 * 1024,
    });

    const stdoutLog = truncateLog(result.stdout || '');
    const stderrLog = truncateLog(result.stderr || '');
    const combinedLog = [stdoutLog, stderrLog].filter(Boolean).join('\n');
    seedLogs = combinedLog;

    if (result.status !== 0) {
      await ctx.dispose();
      output(
        'error',
        {
          reason: 'seed-command-failed',
          empty: emptyKeys,
          message: result.error ? result.error.message : `exit code ${result.status}`,
          logs: combinedLog || undefined,
        },
        1
      );
    }

    // Refresh auth token after seeding (seed --flush invalidates the old token)
    await ctx.dispose();

    // Get fresh JWT token
    const newAccessToken = await loginAndGetToken();

    // Create new context with refreshed token
    ctx = await request.newContext({ 
      baseURL: BASE_URL,
      extraHTTPHeaders: {
        'Authorization': `Bearer ${newAccessToken}`
      }
    });
  }

  const after = await fetchCounts(ctx);
  await ctx.dispose();

  const stillEmpty = after.filter((r) => r.count === 0 || r.status >= 400 || r.status === 0).map((r) => r.key);
  if (stillEmpty.length) {
    output(
      'error',
      {
        reason: 'seed-incomplete',
        empty: stillEmpty,
        before,
        after,
        logs: seedLogs || undefined,
      },
      1
    );
  }

  output('ok', { before, after, logs: seedLogs || undefined }, 0);
}

main().catch((err) => {
  console.error(err);
  output('error', { reason: 'exception', message: err.message }, 1);
});