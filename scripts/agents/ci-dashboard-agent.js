#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';

const OUTPUT_DIR = process.env.AGENT_OUTPUT_DIR || 'agent-outputs';
const ARTIFACT_PATH = path.join('artifacts', 'dashboard.html');

const FILES = {
  auth: 'auth-validator.json',
  seed: 'seed-orchestrator.json',
  smoke: 'page-smoke.json',
  flaky: 'flaky-classifier.json',
  selector: 'selector-auditor.json',
  supervisor: 'fix-agent-supervisor.json',
};

function readJson(file) {
  const p = path.join(OUTPUT_DIR, file);
  if (!fs.existsSync(p)) return null;
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8') || '{}');
  } catch (err) {
    return { status: 'error', reason: 'parse', message: err.message };
  }
}

function statusColor(status) {
  if (!status) return 'gray';
  if (status === 'ok' || status === 'refactored' || status === 'generated' || status === 'dashboard-generated') return 'green';
  if (status === 'noop' || status === 'skipped') return 'yellow';
  return 'red';
}

function escapeHtml(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function renderRow(name, data) {
  const st = data?.status || 'missing';
  const color = statusColor(st);
  const reason = escapeHtml(data?.reason || data?.message || '');
  return `<tr><td>${escapeHtml(name)}</td><td><span class="dot ${color}"></span>${escapeHtml(st)}</td><td>${reason}</td></tr>`;
}

function main() {
  const auth = readJson(FILES.auth);
  const seed = readJson(FILES.seed);
  const smoke = readJson(FILES.smoke);
  const flaky = readJson(FILES.flaky);
  const selector = readJson(FILES.selector);
  const supervisor = readJson(FILES.supervisor);

  const tableRows = [
    renderRow('Auth Validator', auth),
    renderRow('Seed Orchestrator', seed),
    renderRow('Page Smoke', smoke),
    renderRow('Flaky Classifier', flaky),
    renderRow('Selector Auditor', selector),
    renderRow('Fix-Agent Supervisor', supervisor),
  ].join('\n');

  const decision = escapeHtml(supervisor?.decision || '');
  const decisionReason = escapeHtml(supervisor?.reason || '');
  const recs = (supervisor?.recommendations || []).map(escapeHtml).join('<br>');

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>CI Agent Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; }
    h1 { margin-bottom: 0; }
    table { border-collapse: collapse; width: 100%; margin-top: 10px; }
    th, td { border: 1px solid #ddd; padding: 8px; }
    th { background: #f5f5f5; text-align: left; }
    .dot { height: 12px; width: 12px; border-radius: 50%; display: inline-block; margin-right: 6px; }
    .green { background: #2ecc71; }
    .yellow { background: #f1c40f; }
    .red { background: #e74c3c; }
    .gray { background: #bdc3c7; }
    .section { margin-top: 20px; }
    .box { border: 1px solid #ddd; padding: 10px; border-radius: 4px; background: #fafafa; }
  </style>
</head>
<body>
  <h1>CI Agent Dashboard</h1>
  <p>Aggregated status from agent outputs.</p>

  <div class="section">
    <h2>Agent Status</h2>
    <table>
      <thead><tr><th>Agent</th><th>Status</th><th>Reason</th></tr></thead>
      <tbody>
        ${tableRows}
      </tbody>
    </table>
  </div>

  <div class="section box">
    <h3>Self-Heal Decision</h3>
    <p><strong>Decision:</strong> ${decision}</p>
    <p><strong>Reason:</strong> ${decisionReason}</p>
    <p><strong>Recommendations:</strong><br>${recs || 'None'}</p>
  </div>

  <div class="section">
    <h3>Artifacts</h3>
    <ul>
      <li>Playwright report: <code>playwright-report</code></li>
      <li>Test results: <code>test-results</code></li>
      <li>Logs: <code>logs/playwright.log</code></li>
      <li>Storage state: <code>tests/fixtures/storageState.json</code></li>
    </ul>
  </div>
</body>
</html>`;

  fs.mkdirSync(path.dirname(ARTIFACT_PATH), { recursive: true });
  fs.writeFileSync(ARTIFACT_PATH, html, 'utf8');

  console.log(JSON.stringify({ status: 'dashboard-generated', file: ARTIFACT_PATH }, null, 2));
}

main();