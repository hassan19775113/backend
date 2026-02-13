#!/usr/bin/env node

// Role: Prepare context for self-heal (logs + Developer-Agent classification/plan) without making code changes.

import fs from 'node:fs/promises';
import path from 'node:path';

function argValue(args, name, fallback = null) {
  const idx = args.indexOf(name);
  if (idx === -1) return fallback;
  return args[idx + 1] ?? fallback;
}

function safeJsonParse(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function readTextIfExists(filePath) {
  try {
    return await fs.readFile(filePath, 'utf8');
  } catch {
    return '';
  }
}

function extractSpecPaths(playwrightLog) {
  const text = String(playwrightLog || '');
  const re = /(tests\/e2e\/[\w./-]+\.spec\.(?:ts|js))/g;
  const paths = new Set();
  let m;
  while ((m = re.exec(text)) !== null) {
    paths.add(m[1]);
    if (paths.size >= 3) break;
  }
  return Array.from(paths);
}

async function readEventTimestamp() {
  const eventPath = process.env.GITHUB_EVENT_PATH;
  if (!eventPath) return '';

  const raw = await readTextIfExists(eventPath);
  const evt = raw ? safeJsonParse(raw) : null;
  if (!evt || typeof evt !== 'object') return '';

  const ts =
    evt?.head_commit?.timestamp ||
    evt?.pull_request?.updated_at ||
    evt?.pull_request?.created_at ||
    evt?.repository?.pushed_at ||
    '';

  return typeof ts === 'string' ? ts : '';
}

async function postJson(url, token, payload) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  const text = await resp.text().catch(() => '');
  const json = text ? safeJsonParse(text) : null;

  return {
    ok: resp.ok,
    status: resp.status,
    text,
    json,
  };
}

async function main() {
  const args = process.argv.slice(2);
  const outDir = argValue(args, '--out-dir', 'self-heal');

  const runId = String(process.env.GITHUB_RUN_ID || process.env.RUN_ID || '').trim() || 'unknown';
  const runAttempt = Number(process.env.GITHUB_RUN_ATTEMPT || '1') || 1;
  const jobName = String(process.env.SELF_HEAL_JOB_NAME || 'e2e-tests');
  const branch = String(process.env.GITHUB_REF_NAME || process.env.BRANCH || '');
  const commit = String(process.env.GITHUB_SHA || process.env.COMMIT || '');
  const status = String(process.env.E2E_STATUS || 'failed');
  const timestamp = (await readEventTimestamp()) || new Date().toISOString();

  const playwrightLogPath =
    process.env.PLAYWRIGHT_LOG_PATH ||
    path.join('artifacts', 'e2e', 'logs', 'playwright.log');

  const backendLogPath =
    process.env.BACKEND_LOG_PATH ||
    path.join('artifacts', 'backend-logs', 'django', 'logs', 'system', 'ci.log');

  const playwrightLog = await readTextIfExists(playwrightLogPath);
  const backendLog = await readTextIfExists(backendLogPath);

  const payload = {
    playwright_log: playwrightLog,
    backend_log: backendLog,
    run_id: runId,
    run_attempt: runAttempt,
    job_name: jobName,
    timestamp,
    branch,
    commit,
    status,
  };

  const cloudAgentUrl = String(process.env.CLOUD_AGENT_URL || 'https://praxi-app.vercel.app/api/ci/logs');
  const agentToken = String(process.env.AGENT_TOKEN || '').trim();

  const specPaths = extractSpecPaths(playwrightLog);

  const out = {
    version: 1,
    prepared_at: new Date().toISOString(),
    run_id: runId,
    job_name: jobName,
    timestamp,
    branch,
    commit,
    status,
    logs: {
      playwright_log_path: playwrightLogPath,
      backend_log_path: backendLogPath,
      playwright_log_bytes: Buffer.from(playwrightLog || '', 'utf8').length,
      backend_log_bytes: Buffer.from(backendLog || '', 'utf8').length,
      extracted_spec_paths: specPaths,
    },
    developer_agent: {
      source: 'none',
      cloud_agent_url: cloudAgentUrl,
      response: null,
      error: null,
    },
    analysis: {
      classification: null,
      self_heal_plan: null,
      fix_agent_instructions: null,
    },
  };

  if (!agentToken) {
    out.developer_agent.error = 'missing_agent_token';
    console.log('Self-heal context: AGENT_TOKEN missing; skipping Developer-Agent fetch.');
  } else {
    const resp = await postJson(cloudAgentUrl, agentToken, payload);
    out.developer_agent.source = 'cloud-agent';
    out.developer_agent.response = {
      ok: resp.ok,
      status: resp.status,
      json: resp.json,
    };

    const upstream = resp?.json?.upstream ?? null;
    const effective = upstream && typeof upstream === 'object' ? upstream : resp.json;

    out.analysis.classification = effective?.classification ?? null;
    out.analysis.self_heal_plan = effective?.self_heal_plan ?? null;
    out.analysis.fix_agent_instructions = effective?.fix_agent_instructions ?? null;

    if (!resp.ok) {
      out.developer_agent.error = 'cloud_agent_post_failed';
      console.log(`Self-heal context: Cloud-Agent POST failed (status=${resp.status}).`);
    } else {
      console.log('Self-heal context: Cloud-Agent POST ok; extracted classification/plan when available.');
    }
  }

  await fs.mkdir(outDir, { recursive: true });
  await fs.writeFile(path.join(outDir, 'context.json'), JSON.stringify(out, null, 2), 'utf8');

  // Integration point: stable location for downstream self-heal coordinator.
  console.log(
    `Wrote ${path.join(outDir, 'context.json')} (run_id=${runId}, run_attempt=${runAttempt}, extracted_specs=${specPaths.length})`,
  );
}

main().catch((err) => {
  console.error(String(err?.stack || err));
  process.exit(1);
});
