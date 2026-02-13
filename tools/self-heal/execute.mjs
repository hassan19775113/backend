#!/usr/bin/env node

// Role: Execute safe self-heal actions (no code edits) and write a report artifact.

import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';

function argValue(args, name, fallback = null) {
  const idx = args.indexOf(name);
  if (idx === -1) return fallback;
  return args[idx + 1] ?? fallback;
}

async function readJson(filePath) {
  const raw = await fs.readFile(filePath, 'utf8');
  return JSON.parse(raw);
}

async function ensureDir(dir) {
  await fs.mkdir(dir, { recursive: true });
}

function runCmd(cmd, args, opts = {}) {
  return new Promise((resolve) => {
    const child = spawn(cmd, args, { stdio: ['ignore', 'pipe', 'pipe'], ...opts });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (d) => (stdout += d.toString('utf8')));
    child.stderr.on('data', (d) => (stderr += d.toString('utf8')));
    child.on('close', (code) => resolve({ code: code ?? 1, stdout, stderr }));
  });
}

async function writeText(filePath, content) {
  await ensureDir(path.dirname(filePath));
  await fs.writeFile(filePath, content ?? '', 'utf8');
}

async function main() {
  const args = process.argv.slice(2);
  const decisionPath = argValue(args, '--decision', path.join('self-heal', 'decision.json'));
  const contextPath = argValue(args, '--context', path.join('self-heal', 'context.json'));

  const decision = await readJson(decisionPath);
  const context = await readJson(contextPath);

  const runId = String(decision?.run_id || context?.run_id || process.env.GITHUB_RUN_ID || 'unknown');
  const maxAttempts = Number(decision?.rerun?.max_attempts || process.env.SELF_HEAL_MAX_ATTEMPTS || '1') || 1;
  const runAttempt = Number(process.env.GITHUB_RUN_ATTEMPT || '1') || 1;

  console.log(
    `Self-heal execute: run_id=${runId} run_attempt=${runAttempt} max_attempts=${maxAttempts} error_type=${decision?.error_type || 'unknown'}`,
  );

  // Guardrail: don't repeatedly self-heal the same run_id across workflow reruns.
  if (runAttempt > maxAttempts) {
    const reportPath = path.join('self-heal', `report-${runId}.json`);
    const report = {
      version: 1,
      run_id: runId,
      executed_at: new Date().toISOString(),
      status: 'skipped',
      reason: 'run_attempt_exceeded',
      run_attempt: runAttempt,
      max_attempts: maxAttempts,
      decision,
      context_summary: {
        error_type: decision?.error_type,
        allowed: decision?.allowed,
        transient_likelihood: decision?.transient_likelihood,
      },
      actions: [],
      recommendations_for_fix_agent: decision?.recommendations_for_fix_agent || [],
    };
    await writeText(reportPath, JSON.stringify(report, null, 2));
    console.log(`Wrote ${reportPath}`);
    return;
  }

  const stateDir = 'self-heal';
  const statePath = path.join(stateDir, 'attempt-state.json');

  let attemptState = { run_id: runId, attempts: 0 };
  try {
    attemptState = await readJson(statePath);
  } catch {
    // first attempt
  }

  if (String(attemptState?.run_id || '') !== runId) {
    attemptState = { run_id: runId, attempts: 0 };
  }

  if ((attemptState.attempts || 0) >= maxAttempts) {
    const reportPath = path.join(stateDir, `report-${runId}.json`);
    const report = {
      version: 1,
      run_id: runId,
      executed_at: new Date().toISOString(),
      status: 'skipped',
      reason: 'max_attempts_reached',
      max_attempts: maxAttempts,
      attempts: attemptState.attempts || 0,
      decision,
      context_summary: {
        error_type: decision?.error_type,
        allowed: decision?.allowed,
        transient_likelihood: decision?.transient_likelihood,
      },
      actions: [],
      recommendations_for_fix_agent: decision?.recommendations_for_fix_agent || [],
    };
    await writeText(reportPath, JSON.stringify(report, null, 2));
    console.log(`Wrote ${reportPath}`);
    return;
  }

  attemptState.attempts = (attemptState.attempts || 0) + 1;
  await writeText(statePath, JSON.stringify(attemptState, null, 2));

  const report = {
    version: 1,
    run_id: runId,
    executed_at: new Date().toISOString(),
    status: 'unknown',
    attempt: attemptState.attempts,
    max_attempts: maxAttempts,
    decision,
    context_summary: {
      error_type: decision?.error_type,
      allowed: decision?.allowed,
      transient_likelihood: decision?.transient_likelihood,
    },
    actions: [],
    recommendations_for_fix_agent: decision?.recommendations_for_fix_agent || [],
  };

  if (!decision?.allowed) {
    report.status = 'skipped';
    report.reason = 'not_allowed_by_policy';
    const reportPath = path.join(stateDir, `report-${runId}.json`);
    await writeText(reportPath, JSON.stringify(report, null, 2));
    console.log(`Wrote ${reportPath}`);
    return;
  }

  // Integration point: safe, reversible operations only (no code edits).
  for (const action of decision?.actions || []) {
    if (!action?.type) continue;

    if (action.type === 'reseed_db') {
      console.log('Self-heal: reseed DB (safe baseline).');
      const r = await runCmd('python', ['django/manage.py', 'seed'], { env: process.env });
      console.log(`Self-heal: reseed_db exit_code=${r.code}`);
      report.actions.push({ type: 'reseed_db', ok: r.code === 0, exit_code: r.code });
      await writeText(path.join(stateDir, 'reseed.log'), `${r.stdout}\n${r.stderr}`);
      continue;
    }

    if (action.type === 'regenerate_storage_state') {
      console.log('Self-heal: regenerate storage state (auth-validator).');
      const r = await runCmd('node', ['scripts/agents/auth-validator.js'], { env: process.env });
      console.log(`Self-heal: regenerate_storage_state exit_code=${r.code}`);
      report.actions.push({ type: 'regenerate_storage_state', ok: r.code === 0, exit_code: r.code });
      await writeText(path.join(stateDir, 'auth-validator.log'), `${r.stdout}\n${r.stderr}`);
      continue;
    }

    if (action.type === 'rerun_e2e_subset') {
      console.log('Self-heal: rerun E2E (targeted, max 1 attempt).');
      const cmd = String(decision?.rerun?.command || 'npx playwright test');
      console.log(`Self-heal: rerun command: ${cmd}`);
      const r = await runCmd('bash', ['-lc', `${cmd} 2>&1 | tee ${stateDir}/playwright-rerun.log`], { env: process.env });
      console.log(`Self-heal: rerun exit_code=${r.code}`);
      report.actions.push({ type: 'rerun_e2e_subset', ok: r.code === 0, exit_code: r.code, command: cmd });
      continue;
    }

    report.actions.push({ type: action.type, ok: false, skipped: true, reason: 'unknown_action' });
  }

  const rerun = report.actions.find((a) => a.type === 'rerun_e2e_subset');
  report.status = rerun?.ok ? 'rerun_passed' : 'rerun_failed';

  const reportPath = path.join(stateDir, `report-${runId}.json`);
  await writeText(reportPath, JSON.stringify(report, null, 2));

  console.log(`Wrote ${reportPath}`);
}

main().catch((err) => {
  console.error(String(err?.stack || err));
  process.exit(1);
});
