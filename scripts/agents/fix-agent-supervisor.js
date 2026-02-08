#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const OUTPUT_DIR = process.env.AGENT_OUTPUT_DIR || 'agent-outputs';

const FILES = {
  auth: 'auth-validator.json',
  seed: 'seed-orchestrator.json',
  smoke: 'page-smoke.json',
  flaky: 'flaky-classifier.json',
  selector: 'selector-auditor.json',
};

function output(status, details = {}, exitCode = 0) {
  const payload = { status, ...details };
  console.log(JSON.stringify(payload, null, 2));
  process.exit(exitCode);
}

function readJson(name) {
  const p = path.join(OUTPUT_DIR, name);
  if (!fs.existsSync(p)) return null;
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8') || '{}');
  } catch (err) {
    return { status: 'error', reason: 'parse', message: err.message };
  }
}

function decide() {
  const auth = readJson(FILES.auth);
  const seed = readJson(FILES.seed);
  const smoke = readJson(FILES.smoke);
  const flaky = readJson(FILES.flaky);
  const selector = readJson(FILES.selector);

  const blockers = [];
  if (!auth || auth.status !== 'ok') blockers.push('auth');
  if (!seed || seed.status !== 'ok') blockers.push('seed');
  if (!smoke || smoke.status !== 'ok') blockers.push('page-smoke');

  const deterministic = (flaky?.deterministic || []).length;
  const flakyCount = (flaky?.flaky || []).length;

  const decision = {
    allowSelfHeal: blockers.length === 0 && deterministic > 0,
    reason: blockers.length ? `blocked by ${blockers.join(', ')}` : deterministic > 0 ? 'deterministic failures present' : 'no deterministic failures',
    recommendations: [],
  };

  if (blockers.length) {
    decision.recommendations.push('Fix auth/seed/smoke blockers before self-heal.');
  }
  if (flakyCount) {
    decision.recommendations.push('Stabilize flaky tests before patching.');
  }
  if (selector && selector.status !== 'ok') {
    decision.recommendations.push('Inspect selector auditor results for refactors.');
  }

  return { auth, seed, smoke, flaky, selector, decision, blockers };
}

function main() {
  const agg = decide();
  if (agg.blockers.length) {
    output('error', agg, 1);
  }
  output('ok', agg, 0);
}

main();