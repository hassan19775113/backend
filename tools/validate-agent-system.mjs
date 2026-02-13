#!/usr/bin/env node

// Dry-run validation for the agent-driven system wiring.
// Intentionally text-based (no YAML deps) to keep the repo lightweight.

import fs from 'node:fs/promises';
import path from 'node:path';

async function readText(p) {
  const raw = await fs.readFile(p, 'utf8');
  return raw.replace(/\r\n/g, '\n');
}

function assert(condition, message, failures) {
  if (!condition) failures.push(message);
}

function includesAll(haystack, needles) {
  return needles.every((n) => haystack.includes(n));
}

function indexJobs(text) {
  const jobs = [];
  const re = /^  ([a-zA-Z0-9_-]+):\s*$/gm;
  let m;
  while ((m = re.exec(text)) !== null) {
    jobs.push({ id: m[1], index: m.index });
  }
  return jobs;
}

function findJobBlock(text, jobId) {
  const jobs = indexJobs(text);
  const idx = jobs.findIndex((j) => j.id === jobId);
  if (idx < 0) return null;
  const start = jobs[idx].index;
  const end = idx + 1 < jobs.length ? jobs[idx + 1].index : text.length;
  return text.slice(start, end);
}

async function main() {
  const root = process.cwd();
  const workflowPath = path.join(root, '.github', 'workflows', 'agent-engine.yml');
  const backendSetupPath = path.join(root, '.github', 'workflows', 'backend-setup.yml');
  const cloudAgentPath = path.join(root, 'api', 'ci', 'logs.ts');
  const devAgentPath = path.join(root, 'api', 'process-logs.ts');
  const vercelPath = path.join(root, 'vercel.json');
  const archPath = path.join(root, 'ARCHITECTURE-AGENTS.md');

  const failures = [];

  const [workflow, backendSetup, cloudAgent, devAgent, vercel, arch] = await Promise.all([
    readText(workflowPath),
    readText(backendSetupPath),
    readText(cloudAgentPath),
    readText(devAgentPath),
    readText(vercelPath),
    readText(archPath),
  ]);

  // 1) Workflow DAG presence
  const requiredJobs = [
    'auth-validator',
    'seed-orchestrator',
    'page-smoke',
    'e2e-tests',
    'startup-fix-agent',
    'self-heal-supervisor',
    'self-heal-runner',
    'fix-agent-prep',
    'fix-agent-runner',
    'ci-dashboard-agent',
    'publish-dashboard',
    'send-ci-logs',
  ];

  for (const job of requiredJobs) {
    assert(workflow.includes(`  ${job}:`), `Missing job '${job}' in agent-engine.yml`, failures);
  }

  assert(workflow.includes('run-name:'), 'Missing run-name (Actions UI readability)', failures);

  // 2) Artifact/log flow expectations
  const workflowAndBackendSetup = `${workflow}\n${backendSetup}`;
  const artifactNames = [
    'test-results',
    'backend-logs-e2e-tests',
    'storage-state',
    'self-heal-context',
    'self-heal-bundle',
    'self-heal-report',
    'fix-agent-input',
    'fix-agent-output',
    'dashboard',
  ];
  for (const name of artifactNames) {
    assert(
      workflowAndBackendSetup.includes(name),
      `Expected artifact name missing from workflow/back-end setup text: ${name}`,
      failures,
    );
  }

  // 3) Self-heal triggers/guardrails
  const startup = findJobBlock(workflow, 'startup-fix-agent') || '';
  assert(
    includesAll(startup, ["needs: e2e-tests", "github.event_name == 'workflow_dispatch'", "needs.e2e-tests.result == 'failure'"]),
    'startup-fix-agent trigger guardrail missing (workflow_dispatch + e2e failure)',
    failures,
  );

  const supervisor = findJobBlock(workflow, 'self-heal-supervisor') || '';
  assert(
    includesAll(supervisor, ["github.event_name == 'workflow_dispatch'", 'needs: startup-fix-agent']),
    'self-heal-supervisor trigger wiring missing',
    failures,
  );

  const runner = findJobBlock(workflow, 'self-heal-runner') || '';
  assert(
    includesAll(runner, ["needs.self-heal-supervisor.outputs.should_self_heal == 'true'", 'uses: ./.github/workflows/backend-setup.yml']),
    'self-heal-runner gating missing (should_self_heal output) or not using backend-setup.yml',
    failures,
  );

  // 4) Fix-agent triggers + best-effort
  const fixPrep = findJobBlock(workflow, 'fix-agent-prep') || '';
  assert(
    includesAll(fixPrep, ["needs.e2e-tests.result == 'failure'", 'continue-on-error: true']),
    'fix-agent-prep should be best-effort and conditioned on e2e failure',
    failures,
  );

  const fixRunner = findJobBlock(workflow, 'fix-agent-runner') || '';
  assert(
    includesAll(fixRunner, ['uses: ./.github/workflows/backend-setup.yml', 'best_effort: true', 'apply-and-validate.mjs']),
    'fix-agent-runner should call backend-setup with best_effort and run apply-and-validate.mjs',
    failures,
  );
  assert(!fixRunner.includes('continue-on-error:'), 'fix-agent-runner must not use job-level continue-on-error (invalid for reusable workflows)', failures);

  // 5) Dashboard publishing chain exists
  const publish = findJobBlock(workflow, 'publish-dashboard') || '';
  assert(publish.includes('actions/deploy-pages@'), 'publish-dashboard should deploy pages when enabled', failures);

  // 6) Cloud-Agent integration and endpoints
  assert(cloudAgent.includes('DEVELOPER_AGENT_URL'), 'Cloud-Agent missing DEVELOPER_AGENT_URL usage', failures);
  assert(cloudAgent.includes('DEVELOPER_AGENT_TOKEN'), 'Cloud-Agent missing DEVELOPER_AGENT_TOKEN usage', failures);
  assert(cloudAgent.includes('AGENT_TOKEN'), 'Cloud-Agent missing AGENT_TOKEN auth', failures);

  assert(devAgent.includes('DEVELOPER_AGENT_TOKEN'), 'Developer-Agent missing DEVELOPER_AGENT_TOKEN auth', failures);
  assert(devAgent.includes('classification'), 'Developer-Agent should output classification', failures);
  assert(devAgent.includes('self_heal_plan'), 'Developer-Agent should output self_heal_plan', failures);
  assert(devAgent.includes('fix_agent_instructions'), 'Developer-Agent should output fix_agent_instructions', failures);

  assert(vercel.includes('"src": "/process-logs"') && vercel.includes('"dest": "api/process-logs.ts"'), 'vercel.json missing /process-logs route', failures);

  // 7) Backend-setup reusable workflow wiring
  assert(backendSetup.includes('best_effort:'), 'backend-setup.yml missing best_effort input', failures);
  assert(backendSetup.includes('continue-on-error: ${{ inputs.best_effort }}'), 'backend-setup.yml should apply best_effort continue-on-error to critical steps', failures);

  // 8) Architecture doc present and references key endpoints/jobs
  assert(arch.includes('POST /api/ci/logs'), 'ARCHITECTURE-AGENTS.md should document Cloud-Agent endpoint', failures);
  assert(arch.includes('POST /process-logs'), 'ARCHITECTURE-AGENTS.md should document Developer-Agent endpoint', failures);
  assert(arch.includes('fix-agent-runner'), 'ARCHITECTURE-AGENTS.md should mention fix-agent-runner', failures);
  assert(arch.includes('self-heal-runner'), 'ARCHITECTURE-AGENTS.md should mention self-heal-runner', failures);

  // Report
  if (failures.length > 0) {
    console.error('DRY-RUN VALIDATION: FAILED');
    for (const f of failures) console.error(`- ${f}`);
    process.exit(1);
  }

  console.log('DRY-RUN VALIDATION: PASSED');
  console.log(`- Workflow DAG: ok (${requiredJobs.length} jobs found)`);
  console.log('- Artifact/log flow: ok (expected names present)');
  console.log('- Self-heal triggers: ok (workflow_dispatch gating + should_self_heal output)');
  console.log('- Fix-agent triggers: ok (e2e failure gating + best_effort reusable call)');
  console.log('- Dashboard generation/publish: ok (deploy-pages referenced)');
  console.log('- Cloud/Developer agent integration: ok (env vars + endpoints referenced)');
}

main().catch((err) => {
  console.error(String(err?.stack || err));
  process.exit(1);
});
