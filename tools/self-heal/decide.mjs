#!/usr/bin/env node

// Role: Decide whether self-heal is appropriate and which safe actions to run.

import fs from 'node:fs/promises';
import path from 'node:path';

function argValue(args, name, fallback = null) {
  const idx = args.indexOf(name);
  if (idx === -1) return fallback;
  return args[idx + 1] ?? fallback;
}

async function readJson(filePath) {
  const raw = await fs.readFile(filePath, 'utf8');
  return JSON.parse(raw);
}

function toErrorType(classification) {
  const t = classification?.error_type;
  return typeof t === 'string' ? t : 'unknown';
}

function inferTransientLikelihood(errorType) {
  switch (errorType) {
    case 'infra/network':
    case 'frontend-timing':
      return 'high';
    case 'auth/session':
      return 'medium';
    default:
      return 'low';
  }
}

function allowedForSelfHeal(errorType) {
  // Guardrail: only attempt self-heal for cases that are plausibly transient and safe to rerun.
  return errorType === 'infra/network' || errorType === 'frontend-timing' || errorType === 'auth/session';
}

function buildActions(errorType) {
  const actions = [];

  // Guardrail: no destructive schema changes; only safe, reversible operations.
  if (errorType === 'auth/session') {
    actions.push({ type: 'regenerate_storage_state', why: 'Auth/session failures often recover after regenerating storageState.' });
  }

  // Safe in CI: reseeding DB restores known baseline data; no schema mutation.
  if (errorType === 'infra/network' || errorType === 'frontend-timing' || errorType === 'auth/session') {
    actions.push({ type: 'reseed_db', why: 'Ensure baseline data is present for a clean rerun.' });
  }

  actions.push({ type: 'rerun_e2e_subset', why: 'Validate whether the failure is transient without changing code.' });

  return actions;
}

function buildRerunPlan(context) {
  const specPaths = context?.logs?.extracted_spec_paths;
  const paths = Array.isArray(specPaths) ? specPaths.filter((p) => typeof p === 'string') : [];

  // Guardrail: one rerun max per workflow run.
  const maxAttempts = Number(process.env.SELF_HEAL_MAX_ATTEMPTS || '1') || 1;

  const cmd = paths.length > 0 ? `npx playwright test ${paths.join(' ')}` : 'npx playwright test';

  return {
    max_attempts: Math.max(1, Math.min(2, maxAttempts)),
    mode: paths.length > 0 ? 'subset' : 'full',
    spec_paths: paths,
    command: cmd,
  };
}

async function main() {
  const args = process.argv.slice(2);
  const contextPath = argValue(args, '--context', path.join('self-heal', 'context.json'));
  const outPath = argValue(args, '--out', path.join('self-heal', 'decision.json'));

  const context = await readJson(contextPath);
  const classification = context?.analysis?.classification ?? null;
  const selfHealPlan = context?.analysis?.self_heal_plan ?? null;
  const errorType = toErrorType(classification);

  const allowed = allowedForSelfHeal(errorType);
  const transient = inferTransientLikelihood(errorType);

  const decision = {
    version: 1,
    decided_at: new Date().toISOString(),
    run_id: String(context?.run_id || 'unknown'),
    job_name: String(context?.job_name || 'e2e-tests'),
    branch: String(context?.branch || ''),
    commit: String(context?.commit || ''),
    error_type: errorType,
    allowed,
    transient_likelihood: transient,
    reason:
      allowed
        ? 'Eligible error type for safe self-heal (rerun-only + environment reset).'
        : 'Not eligible for self-heal (likely structural or requires code change).',
    inputs: {
      has_developer_agent_classification: !!classification,
      has_developer_agent_self_heal_plan: !!selfHealPlan,
    },
    actions: allowed ? buildActions(errorType) : [],
    rerun: allowed ? buildRerunPlan(context) : null,
    recommendations_for_fix_agent: allowed
      ? ['If rerun still fails, treat as structural and escalate to Fix-Agent with captured context.']
      : ['Use Fix-Agent for code changes; self-heal skipped by policy.'],
  };

  await fs.mkdir(path.dirname(outPath), { recursive: true });
  await fs.writeFile(outPath, JSON.stringify(decision, null, 2), 'utf8');

  // Integration point: stable decision file for self-heal execution runner.
  console.log(`Wrote ${outPath}`);
  console.log(
    `Self-heal decision: run_id=${decision.run_id} error_type=${decision.error_type} allowed=${decision.allowed} transient=${decision.transient_likelihood}`,
  );
  if (decision.allowed) {
    console.log(`Self-heal planned actions: ${decision.actions.map((a) => a.type).join(', ')}`);
    console.log(`Self-heal rerun command: ${decision.rerun?.command || ''}`);
  }
}

main().catch((err) => {
  console.error(String(err?.stack || err));
  process.exit(1);
});
