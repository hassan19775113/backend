#!/usr/bin/env ts-node

import './check-node-version.js';
import { Octokit } from '@octokit/rest';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import AdmZip from 'adm-zip';
import { execSync, spawnSync } from 'child_process';

const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
const OWNER = process.env.GH_OWNER;
const REPO = process.env.GH_REPO;
const WORKFLOW_FILE = process.env.GH_WORKFLOW_FILE || 'e2e-self-heal.yml';
const BRANCH_FIX = process.env.GH_BRANCH_FIX || 'ai-fix';
const BRANCH_MAIN = process.env.GH_BRANCH_MAIN || 'main';
const MAX_ITER = parseInt(process.env.MAX_ITER || '10', 10);

if (!GITHUB_TOKEN || !OWNER || !REPO) {
  console.error('Missing env: GITHUB_TOKEN, GH_OWNER, GH_REPO');
  process.exit(1);
}

const octokit = new Octokit({ auth: GITHUB_TOKEN });

async function dispatchWorkflow(): Promise<number> {
  const res = await octokit.actions.createWorkflowDispatch({
    owner: OWNER,
    repo: REPO,
    workflow_id: WORKFLOW_FILE,
    ref: BRANCH_FIX,
  });
  if (res.status !== 204) throw new Error('Failed to dispatch workflow');
  return await waitForNewRunId();
}

async function waitForNewRunId(): Promise<number> {
  for (let i = 0; i < 30; i++) {
    const runs = await octokit.actions.listWorkflowRuns({
      owner: OWNER,
      repo: REPO,
      workflow_id: WORKFLOW_FILE,
      branch: BRANCH_FIX,
      per_page: 1,
    });
    const run = runs.data.workflow_runs[0];
    if (run) return run.id;
    await delay(5000);
  }
  throw new Error('No workflow run found after dispatch');
}

async function waitForRun(runId: number): Promise<string> {
  while (true) {
    const run = await octokit.actions.getWorkflowRun({
      owner: OWNER,
      repo: REPO,
      run_id: runId,
    });
    const status = run.data.status || '';
    const conclusion = run.data.conclusion || '';
    if (status === 'completed') return conclusion;
    await delay(10000);
  }
}

async function downloadArtifacts(runId: number, outDir: string) {
  const { data } = await octokit.actions.listWorkflowRunArtifacts({
    owner: OWNER,
    repo: REPO,
    run_id: runId,
  });
  for (const artifact of data.artifacts) {
    const zipRes = await octokit.actions.downloadArtifact({
      owner: OWNER,
      repo: REPO,
      artifact_id: artifact.id,
      archive_format: 'zip',
    });
    const zipPath = path.join(outDir, `${artifact.name}.zip`);
    fs.writeFileSync(zipPath, Buffer.from(zipRes.data as ArrayBuffer));
    const zip = new AdmZip(zipPath);
    zip.extractAllTo(path.join(outDir, artifact.name), true);
  }
}

function runCmd(cmd: string, cwd = process.cwd()) {
  console.log(`> ${cmd}`);
  execSync(cmd, { stdio: 'inherit', cwd });
}

function tryRead(file: string): string | null {
  try {
    return fs.readFileSync(file, 'utf8');
  } catch {
    return null;
  }
}

function feedLogsToAgent(logDir: string) {
  const pwLog = tryRead(path.join(logDir, 'playwright-log', 'playwright.log'));
  const npmLog = tryRead(path.join(logDir, 'npm-error-log', 'npm-error.log'));
  const tscLog = tryRead(path.join(logDir, 'tsc-output-log', 'tsc-output.log'));

  const payload = [
    pwLog ? `Playwright log:\n${pwLog}` : '',
    npmLog ? `npm log:\n${npmLog}` : '',
    tscLog ? `tsc log:\n${tscLog}` : '',
  ]
    .filter(Boolean)
    .join('\n\n---\n\n');

  const tmpLog = path.join(logDir, 'combined.log');
  fs.writeFileSync(tmpLog, payload, 'utf8');

  const res = spawnSync('node', ['tools/ai-startup-fix-agent/startup-fix.js', '--log', tmpLog, '--verbose'], {
    stdio: 'inherit',
  });
  if (res.status !== 0) {
    throw new Error('AI Startup Fix Agent failed');
  }
}

function ensureAiFixBranch() {
  try {
    runCmd(`git rev-parse --verify ${BRANCH_FIX}`);
    runCmd(`git checkout ${BRANCH_FIX}`);
  } catch {
    runCmd(`git checkout -b ${BRANCH_FIX} origin/${BRANCH_FIX}`);
  }
}

function pushAiFix() {
  runCmd(`git push origin ${BRANCH_FIX}`);
}

async function ensurePullRequest() {
  const prs = await octokit.pulls.list({
    owner: OWNER,
    repo: REPO,
    head: `${OWNER}:${BRANCH_FIX}`,
    base: BRANCH_MAIN,
    state: 'open',
    per_page: 1,
  });
  if (prs.data.length === 0) {
    await octokit.pulls.create({
      owner: OWNER,
      repo: REPO,
      head: BRANCH_FIX,
      base: BRANCH_MAIN,
      title: 'AI self-heal: fix E2E pipeline',
      body: 'Automated fixes from AI Startup Fix Agent.',
    });
  }
}

async function main() {
  ensureAiFixBranch();
  for (let i = 1; i <= MAX_ITER; i++) {
    console.log(`\n=== Iteration ${i}/${MAX_ITER} ===`);
    const runId = await dispatchWorkflow();
    const conclusion = await waitForRun(runId);
    console.log(`Workflow concluded: ${conclusion}`);

    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'praxi-logs-'));
    await downloadArtifacts(runId, tempDir);

    feedLogsToAgent(tempDir);

    try {
      runCmd('git diff --quiet --cached || git commit -m "AI self-heal: apply fixes"');
    } catch {
      /* nothing to commit */
    }
    pushAiFix();
    await ensurePullRequest();

    if (conclusion === 'success') {
      console.log('CI is green. Exiting.');
      return;
    }
  }
  throw new Error('Max iterations reached without green CI');
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
