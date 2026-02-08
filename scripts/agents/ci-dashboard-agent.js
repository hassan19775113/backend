#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';

const OUTPUT_DIR = process.env.AGENT_OUTPUT_DIR || 'agent-outputs';
const ARTIFACT_PATH = path.join('artifacts', 'dashboard', 'dashboard.html');
const BADGE_PATH = path.join('artifacts', 'badge.svg');
const DASHBOARD_BADGE_PATH = path.join('artifacts', 'dashboard', 'badge.svg');

const FILES = {
  auth: 'auth-validator.json',
  seed: 'seed-orchestrator.json',
  smoke: 'page-smoke.json',
  flaky: 'flaky-classifier.json',
  selector: 'selector-auditor.json',
  supervisor: 'fix-agent-supervisor.json',
};

function readSupervisor() {
  const data = readJson(FILES.supervisor);
  if (!data) return null;
  return data;
}

function badgeColor(decision) {
  if (!decision) return { color: '#f44336', label: 'STATUS: UNKNOWN' };
  if (decision === 'run-self-heal') return { color: '#f44336', label: 'STATUS: RUN SELF-HEAL' };
  if (decision === 'needs-selector-refactor') return { color: '#ff9800', label: 'STATUS: SELECTOR REFACTOR' };
  if (decision === 'abort') return { color: '#f44336', label: 'STATUS: ABORT' };
  if (decision === 'ok') return { color: '#4caf50', label: 'STATUS: OK' };
  return { color: '#f44336', label: `STATUS: ${decision.toUpperCase?.() || 'UNKNOWN'}` };
}

function writeBadge(decision) {
  const { color, label } = badgeColor(decision);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="200" height="24">
  <rect width="200" height="24" fill="${color}"/>
  <text x="100" y="16" fill="#fff" font-size="12" font-family="Arial, sans-serif" text-anchor="middle">
    ${label}
  </text>
</svg>`;

  fs.mkdirSync(path.dirname(BADGE_PATH), { recursive: true });
  fs.writeFileSync(BADGE_PATH, svg, 'utf8');

  fs.mkdirSync(path.dirname(DASHBOARD_BADGE_PATH), { recursive: true });
  fs.writeFileSync(DASHBOARD_BADGE_PATH, svg, 'utf8');

  return { badgePath: BADGE_PATH, dashboardBadgePath: DASHBOARD_BADGE_PATH };
}

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
  const supervisorDecision = supervisor?.decision;
  const badgeInfo = writeBadge(supervisorDecision);

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
      body { font-family: Arial, sans-serif; margin: 20px; position: relative; background: #ffffff; color: #000000; }
      @media (prefers-color-scheme: dark) {
        body { background: #121212; color: #e0e0e0; }
        .card { background: #1e1e1e; border: 1px solid #333; }
        .badge img { filter: invert(1); }
      }
      .card { padding: 16px; margin: 12px 0; border-radius: 8px; background: #f5f5f5; }
    .badge { position: absolute; top: 20px; right: 20px; }
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
    .theme-toggle { position: absolute; top: 20px; left: 20px; padding: 6px 10px; border-radius: 6px; border: 1px solid #ccc; background: #f5f5f5; cursor: pointer; }
    body.dark { background: #121212; color: #e0e0e0; }
    body.dark .card { background: #1e1e1e; border: 1px solid #333; }
    body.dark .badge img { filter: invert(1); }
    body.dark table th { background: #1e1e1e; }
    body.dark table th, body.dark table td { border-color: #333; }
  </style>
</head>
<body>
  <h1>CI Agent Dashboard</h1>
  <div class="badge"><img src="badge.svg" alt="Status badge" /></div>
  <button class="theme-toggle" id="themeToggle">Toggle Theme</button>
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

  <div class="section card">
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
  <script>
    (function() {
      const btn = document.getElementById('themeToggle');
      const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      if (prefersDark) document.body.classList.add('dark');
      btn.addEventListener('click', () => {
        document.body.classList.toggle('dark');
      });
    })();
  </script>
</body>
</html>`;

  fs.mkdirSync(path.dirname(ARTIFACT_PATH), { recursive: true });
  fs.writeFileSync(ARTIFACT_PATH, html, 'utf8');

  // Also place a copy at artifacts/dashboard.html for convenience
  const flatPath = path.join('artifacts', 'dashboard.html');
  fs.mkdirSync(path.dirname(flatPath), { recursive: true });
  fs.writeFileSync(flatPath, html, 'utf8');

  console.log(JSON.stringify({ status: 'dashboard-generated', file: ARTIFACT_PATH, flatFile: flatPath, badge: badgeInfo }, null, 2));
}

main();