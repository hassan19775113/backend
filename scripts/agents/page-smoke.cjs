#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const STORAGE_PATH = process.env.STORAGE_PATH || path.join('tests', 'fixtures', 'storageState.json');
const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';

const PAGES = [
  { key: 'calendar', path: '/praxi_backend/appointments/', anchor: '#appointmentCalendar' },
  { key: 'patients', path: '/praxi_backend/patients/', anchor: '#patientSelect' },
  { key: 'operations', path: '/praxi_backend/operations/', anchor: '#periodSelect' },
  { key: 'scheduling', path: '/praxi_backend/scheduling/', anchor: '#trendChart' },
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

async function run() {
  ensureStorage();
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ baseURL: BASE_URL, storageState: STORAGE_PATH });
  const results = [];

  for (const pageDef of PAGES) {
    const page = await context.newPage();
    let status = 'ok';
    let reason = '';
    let httpStatus = 0;
    try {
      const resp = await page.goto(pageDef.path);
      httpStatus = resp ? resp.status() : 0;
      await page.waitForLoadState('networkidle');
      const count = await page.locator(pageDef.anchor).count();
      if (count === 0) {
        status = 'missing-anchor';
        reason = 'anchor-not-found';
      }
    } catch (err) {
      status = 'error';
      reason = err.message;
    }
    results.push({ key: pageDef.key, status, reason, httpStatus, anchor: pageDef.anchor, path: pageDef.path });
    await page.close();
  }

  await context.close();
  await browser.close();

  const failed = results.filter((r) => r.status !== 'ok');
  if (failed.length) {
    output('error', { results }, 1);
  }

  output('ok', { results }, 0);
}

run().catch((err) => {
  console.error(err);
  output('error', { reason: 'exception', message: err.message }, 1);
});