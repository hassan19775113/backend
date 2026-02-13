#!/usr/bin/env node

// Role: Prepare structured Fix-Agent input from CI artifacts + Developer-Agent analysis.
// Guardrails: never edits code; best-effort network calls; always writes an input JSON.

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
  const outDir = argValue(args, '--out-dir', 'fix-agent');
  const outFile = argValue(args, '--out', path.join(outDir, 'input.json'));

  const runId = String(process.env.GITHUB_RUN_ID || process.env.RUN_ID || '').trim() || 'unknown';
  const runAttempt = Number(process.env.GITHUB_RUN_ATTEMPT || '1') || 1;
  const branch = String(process.env.GITHUB_REF_NAME || process.env.BRANCH || '');
  const commit = String(process.env.GITHUB_SHA || process.env.COMMIT || '');
  const status = String(process.env.E2E_STATUS || 'failed');
  const jobName = String(process.env.FIX_AGENT_JOB_NAME || 'e2e-tests');

  const playwrightLogPath =
    process.env.PLAYWRIGHT_LOG_PATH || path.join('artifacts', 'e2e', 'logs', 'playwright.log');
  const backendLogPath =
    process.env.BACKEND_LOG_PATH || path.join('artifacts', 'backend-logs', 'django', 'logs', 'system', 'ci.log');

  const playwrightLog = await readTextIfExists(playwrightLogPath);
  const backendLog = await readTextIfExists(backendLogPath);

  const specPaths = extractSpecPaths(playwrightLog);

  const payload = {
    playwright_log: playwrightLog,
    backend_log: backendLog,
    run_id: runId,
    run_attempt: runAttempt,
    job_name: jobName,
    timestamp: new Date().toISOString(),
    branch,
    commit,
    status,
  };

  const cloudAgentUrl = String(process.env.CLOUD_AGENT_URL || 'https://praxi-app.vercel.app/api/ci/logs');
  const agentToken = String(process.env.AGENT_TOKEN || '').trim();

  const out = {
    version: 1,
    prepared_at: new Date().toISOString(),
    run_id: runId,
    run_attempt: runAttempt,
    job_name: jobName,
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
      fix_agent_instructions: null,
      self_heal_plan: null,
    },
  };

  if (!agentToken) {
    out.developer_agent.error = 'missing_agent_token';
    // Guardrail: fix-agent input prep should not fail the workflow when secrets are missing.
    console.log('Fix-Agent input: AGENT_TOKEN missing; skipping Developer-Agent fetch.');
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
    out.analysis.fix_agent_instructions = effective?.fix_agent_instructions ?? null;
    out.analysis.self_heal_plan = effective?.self_heal_plan ?? null;

    if (!resp.ok) {
      out.developer_agent.error = 'cloud_agent_post_failed';
      console.log(`Fix-Agent input: Cloud-Agent POST failed (status=${resp.status}).`);
    } else {
      console.log('Fix-Agent input: Cloud-Agent POST ok; extracted classification/instructions when available.');
    }
  }

  await fs.mkdir(path.dirname(outFile), { recursive: true });
  await fs.writeFile(outFile, JSON.stringify(out, null, 2), 'utf8');
  console.log(`Wrote ${outFile} (run_id=${runId}, extracted_specs=${specPaths.length})`);
}

main().catch(async (err) => {
  // Guardrail: best-effort; still emit a minimal input file to keep downstream automation stable.
  try {
    const args = process.argv.slice(2);
    const outDir = argValue(args, '--out-dir', 'fix-agent');
    const outFile = argValue(args, '--out', path.join(outDir, 'input.json'));
    await fs.mkdir(path.dirname(outFile), { recursive: true });
    await fs.writeFile(
      outFile,
      JSON.stringify(
        {
          version: 1,
          prepared_at: new Date().toISOString(),
          run_id: String(process.env.GITHUB_RUN_ID || 'unknown'),
          error: String(err?.stack || err),
        },
        null,
        2,
      ),
      'utf8',
    );
    console.error(String(err?.stack || err));
    console.log(`Wrote ${outFile} (error fallback)`);
  } catch {
    console.error(String(err?.stack || err));
  }
  process.exit(0);
});
