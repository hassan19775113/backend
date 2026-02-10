#!/usr/bin/env node

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const REPORT_PATH = path.join('logs', 'flaky-report.json');

function output(status, details = {}, exitCode = 0) {
  const payload = { status, ...details };
  console.log(JSON.stringify(payload, null, 2));
  process.exit(exitCode);
}

function ensureDirs() {
  fs.mkdirSync(path.dirname(REPORT_PATH), { recursive: true });
}

function runRerun() {
  try {
    const result = execSync(`npx playwright test --last-failed --repeat-each=2 --reporter=json`, {
      encoding: 'utf8',
      env: process.env,
    });
    fs.writeFileSync(REPORT_PATH, result, 'utf8');
  } catch (err) {
    // Allow failures; write stderr if available
    if (err.stdout) fs.writeFileSync(REPORT_PATH, err.stdout, 'utf8');
  }
}

function classify() {
  if (!fs.existsSync(REPORT_PATH)) {
    output('error', { reason: 'missing-report', reportPath: REPORT_PATH }, 1);
  }
  const data = JSON.parse(fs.readFileSync(REPORT_PATH, 'utf8') || '{}');
  const suites = data.suites || [];
  const results = [];

  const collect = (suite) => {
    (suite.specs || []).forEach((spec) => {
      (spec.tests || []).forEach((test) => {
        const outcomes = (test.results || []).map((r) => r.status);
        const hasPass = outcomes.includes('passed');
        const hasFail = outcomes.includes('failed');
        let classification = 'unknown';
        if (hasPass && hasFail) classification = 'flaky';
        else if (hasFail && !hasPass) classification = 'deterministic-fail';
        else if (hasPass && !hasFail) classification = 'pass';
        results.push({ title: test.title, classification, outcomes });
      });
    });
    (suite.suites || []).forEach(collect);
  };
  suites.forEach(collect);
  return results;
}

function main() {
  ensureDirs();
  runRerun();
  const results = classify();
  const flaky = results.filter((r) => r.classification === 'flaky');
  const deterministic = results.filter((r) => r.classification === 'deterministic-fail');

  if (flaky.length || deterministic.length) {
    output('ok', { flaky, deterministic, results }, 0);
  } else {
    output('ok', { message: 'No tests classified (maybe no last-failed context)', results }, 0);
  }
}

main();