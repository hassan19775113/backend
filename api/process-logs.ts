import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';

type JsonResponse = {
  statusCode?: number;
  setHeader?: (name: string, value: string) => void;
  end?: (body?: string) => void;
};

type JsonRequest = {
  method?: string;
  headers?: Record<string, string | string[] | undefined>;
  body?: unknown;
  on?: (event: 'data' | 'end' | 'error', cb: (chunk?: any) => void) => void;
};

type ProcessLogsPayload = {
  playwright_log: string;
  backend_log: string;
  run_id: string | number;
  job_name: string;
  timestamp: string;
  branch: string;
  commit: string;
  status: string;
};

type Classification = {
  error_type:
    | 'frontend-selector'
    | 'frontend-timing'
    | 'backend-500'
    | 'backend-migration'
    | 'auth/session'
    | 'infra/network'
    | 'backend-exception'
    | 'unknown'
    | 'missing_logs';
  confidence: 'high' | 'medium' | 'low';
  failing_tests: string[];
  signals: string[];
  summary: string;
};

type SelfHealPlan = {
  what_to_inspect: string[];
  what_to_change: string[];
  tests_to_rerun: string[];
};

type FixAgentInstructions = {
  suspected_paths: string[];
  failing_tests: string[];
  suspected_root_cause: string;
  suggested_fix_direction: string;
  key_log_snippets: {
    playwright: string;
    backend: string;
  };
};

/**
 * Internal trigger interfaces (hooks)
 *
 * The self-heal and fix-agent modules are NOT implemented here.
 * This endpoint produces stable, structured payloads that those modules can consume.
 */
export type SelfHealModuleInput = {
  run_id: string;
  job_name: string;
  branch: string;
  commit: string;
  classification: Classification;
  self_heal_plan: SelfHealPlan;
  storage: {
    run_dir: string;
    playwright_log_path: string;
    backend_log_path: string;
    analysis_path: string;
  };
};

export type FixAgentModuleInput = {
  run_id: string;
  job_name: string;
  branch: string;
  commit: string;
  classification: Classification;
  fix_instructions: FixAgentInstructions;
  storage: {
    run_dir: string;
    playwright_log_path: string;
    backend_log_path: string;
    analysis_path: string;
  };
};

const REQUIRED_FIELDS: Array<keyof ProcessLogsPayload> = [
  'playwright_log',
  'backend_log',
  'run_id',
  'job_name',
  'timestamp',
  'branch',
  'commit',
  'status',
];

const MAX_LOG_BYTES = 512 * 1024;
const MAX_SNIPPET_CHARS = 6000;

function timingSafeEqualString(a: string, b: string): boolean {
  const aBuf = Buffer.from(a, 'utf8');
  const bBuf = Buffer.from(b, 'utf8');
  if (aBuf.length !== bBuf.length) return false;
  return crypto.timingSafeEqual(aBuf, bBuf);
}

function getBearerToken(headerValue: string | undefined): string | null {
  if (!headerValue) return null;
  const match = headerValue.match(/^Bearer\s+(.+)$/i);
  return match?.[1]?.trim() || null;
}

function sendJson(res: JsonResponse, statusCode: number, data: unknown) {
  const body = JSON.stringify(data);
  res.statusCode = statusCode;
  res.setHeader?.('Content-Type', 'application/json; charset=utf-8');
  res.end?.(body);
}

async function readJsonBody(req: JsonRequest): Promise<unknown> {
  if (req.body !== undefined) {
    if (typeof req.body === 'string') {
      if (!req.body.trim()) return undefined;
      return JSON.parse(req.body);
    }
    return req.body;
  }

  const chunks: Buffer[] = [];
  await new Promise<void>((resolve, reject) => {
    if (!req.on) return resolve();
    req.on('data', (chunk) => chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(String(chunk))));
    req.on('end', () => resolve());
    req.on('error', (err) => reject(err));
  });

  if (chunks.length === 0) return undefined;
  const raw = Buffer.concat(chunks).toString('utf8');
  if (!raw.trim()) return undefined;
  return JSON.parse(raw);
}

function isString(value: unknown): value is string {
  return typeof value === 'string';
}

function isStringOrNumber(value: unknown): value is string | number {
  return typeof value === 'string' || typeof value === 'number';
}

function missingFields(body: unknown): Array<keyof ProcessLogsPayload> {
  if (typeof body !== 'object' || body === null) return [...REQUIRED_FIELDS];
  const obj = body as Record<string, unknown>;
  const missing: Array<keyof ProcessLogsPayload> = [];

  for (const field of REQUIRED_FIELDS) {
    const value = obj[field as string];
    switch (field) {
      case 'run_id':
        if (!isStringOrNumber(value)) missing.push(field);
        break;
      case 'playwright_log':
      case 'backend_log':
      case 'job_name':
      case 'timestamp':
      case 'branch':
      case 'commit':
      case 'status':
        if (!isString(value)) missing.push(field);
        break;
      default:
        missing.push(field);
        break;
    }
  }

  return missing;
}

function normalizeRunId(runId: string | number): string {
  const s = String(runId);
  return s.replace(/[^a-zA-Z0-9._-]/g, '_').slice(0, 128) || 'unknown';
}

async function ensureDir(dir: string) {
  await fs.mkdir(dir, { recursive: true });
}

function safeUtf8Tail(input: string, maxBytes: number): string {
  const buf = Buffer.from(input ?? '', 'utf8');
  if (buf.length <= maxBytes) return input ?? '';

  let start = buf.length - maxBytes;
  while (start < buf.length && (buf[start] & 0b1100_0000) === 0b1000_0000) {
    start += 1;
  }

  return buf.toString('utf8', start);
}

function normalizeAndTrimLog(text: string): string {
  const normalized = (text ?? '').replace(/\r\n/g, '\n');
  return safeUtf8Tail(normalized, MAX_LOG_BYTES);
}

async function writeTextFile(filePath: string, content: string) {
  await ensureDir(path.dirname(filePath));
  await fs.writeFile(filePath, content ?? '', { encoding: 'utf8' });
}

function extractPlaywrightFailingTests(playwrightLog: string): string[] {
  const lines = (playwrightLog || '').split(/\n/);
  const tests: string[] = [];
  const seen = new Set<string>();

  for (const line of lines) {
    const m = line.match(/^\s*\d+\)\s+(.+)$/);
    if (m?.[1]) {
      const name = m[1].trim();
      if (!seen.has(name)) {
        seen.add(name);
        tests.push(name);
      }
    }
    if (tests.length >= 5) break;
  }

  return tests;
}

function extractFirstPlaywrightErrorSnippet(playwrightLog: string): string {
  const pl = playwrightLog || '';
  const idx = pl.search(/^\s*\d+\)\s+/m);
  const slice = idx >= 0 ? pl.slice(idx) : pl;

  const errorLine = slice.match(/\n\s*(Error:.*)$/m)?.[1]?.trim();
  if (errorLine) return errorLine.slice(0, 500);

  const timeoutLine = slice.match(/\n\s*(Test timeout of .*|Timeout \d+ms exceeded.*)$/mi)?.[1]?.trim();
  if (timeoutLine) return timeoutLine.slice(0, 500);

  const navLine = slice.match(/\n\s*(net::ERR_[^\s]+.*)$/m)?.[1]?.trim();
  if (navLine) return navLine.slice(0, 500);

  return '';
}

function extractBackendSnippet(backendLog: string): string {
  const bl = backendLog || '';

  const tbIdx = bl.search(/Traceback\s+\(most recent call last\):/);
  if (tbIdx >= 0) {
    return bl.slice(tbIdx, tbIdx + MAX_SNIPPET_CHARS);
  }

  const err5xx = bl.match(/\b500\b|Internal Server Error|Server Error \(500\)/i);
  if (err5xx) {
    const i = Math.max(0, (err5xx.index ?? 0) - 2000);
    return bl.slice(i, i + MAX_SNIPPET_CHARS);
  }

  const dbErr = bl.match(/psycopg|could not connect|relation\s+.*\s+does not exist|no such table|django\.db\.migrations/i);
  if (dbErr) {
    const i = Math.max(0, (dbErr.index ?? 0) - 2000);
    return bl.slice(i, i + MAX_SNIPPET_CHARS);
  }

  return bl.slice(-MAX_SNIPPET_CHARS);
}

function classifyFailure(playwrightLog: string, backendLog: string): Omit<Classification, 'failing_tests'> {
  const pl = playwrightLog || '';
  const bl = backendLog || '';
  const signals: string[] = [];

  if (!pl.trim() && !bl.trim()) {
    return {
      error_type: 'missing_logs',
      confidence: 'low',
      signals: ['no_log_content'],
      summary: 'No log content received.',
    };
  }

  const backendMigration = /django\.db\.migrations|Migration\s+.*\s+failed|relation\s+.*\s+does not exist|no such table/i;
  const backendTraceback = /Traceback\s+\(most recent call last\):/i;
  const backend500 = /\b500\b|Internal Server Error|Server Error \(500\)/i;
  const authSession = /\b401\b|\b403\b|CSRF|forbidden|unauthorized|invalid\s+credentials|login\s+failed/i;
  const network = /net::ERR_|ECONNREFUSED|ENOTFOUND|EAI_AGAIN|socket hang up|read ECONNRESET/i;
  const selector = /strict\s+mode\s+violation|waiting for selector|locator\(|toHaveCount\(|toBeVisible\(/i;
  const timing = /Test timeout of|Timeout \d+ms exceeded|expect\(.+\)\.to/i;

  if (backendMigration.test(bl)) {
    signals.push('backend:migration');
    return { error_type: 'backend-migration', confidence: 'high', signals, summary: 'Backend migration/DB schema error detected.' };
  }

  if (backendTraceback.test(bl)) {
    signals.push('backend:traceback');
    return { error_type: 'backend-exception', confidence: 'high', signals, summary: 'Backend Python traceback detected.' };
  }

  if (backend500.test(bl)) {
    signals.push('backend:5xx');
    return { error_type: 'backend-500', confidence: 'medium', signals, summary: 'Backend 5xx/server error detected in logs.' };
  }

  if (authSession.test(pl) || authSession.test(bl)) {
    signals.push('auth:session');
    return { error_type: 'auth/session', confidence: 'medium', signals, summary: 'Auth/session issue detected (401/403/CSRF/login failure).' };
  }

  if (network.test(pl) || network.test(bl)) {
    signals.push('infra:network');
    return { error_type: 'infra/network', confidence: 'medium', signals, summary: 'Network/infra error detected (net::ERR_ / ECONN* / DNS).' };
  }

  if (selector.test(pl)) {
    signals.push('frontend:selector');
    return { error_type: 'frontend-selector', confidence: 'medium', signals, summary: 'Frontend selector/locator issue detected.' };
  }

  if (timing.test(pl)) {
    signals.push('frontend:timing');
    return { error_type: 'frontend-timing', confidence: 'medium', signals, summary: 'Frontend timing/timeout issue detected.' };
  }

  return { error_type: 'unknown', confidence: 'low', signals: ['no_match'], summary: 'No known failure signature matched.' };
}

function buildSelfHealPlan(classification: Classification): SelfHealPlan {
  const base: SelfHealPlan = {
    what_to_inspect: [],
    what_to_change: [],
    tests_to_rerun: ['npx playwright test'],
  };

  switch (classification.error_type) {
    case 'backend-migration':
      base.what_to_inspect.push('CI migration step output and backend.log for schema errors.');
      base.what_to_change.push('Fix migrations/seed ordering; ensure all migrations run before tests.');
      base.tests_to_rerun.push('python django/manage.py migrate');
      break;
    case 'backend-exception':
      base.what_to_inspect.push('First traceback in backend.log and the request path that triggers it.');
      base.what_to_change.push('Fix failing backend code path; add regression coverage if possible.');
      break;
    case 'backend-500':
      base.what_to_inspect.push('Backend 5xx entries around failing test time.');
      base.what_to_change.push('Fix server error root cause; harden health checks and seed data.');
      break;
    case 'auth/session':
      base.what_to_inspect.push('E2E user creation, login flow, CSRF/JWT/session cookie behavior.');
      base.what_to_change.push('Align CI user credentials and storageState generation; stabilize auth in tests.');
      base.tests_to_rerun.push('node scripts/agents/auth-validator.js');
      break;
    case 'frontend-selector':
      base.what_to_inspect.push('Failing locator selectors in the first failing Playwright test.');
      base.what_to_change.push('Prefer role-based locators; avoid brittle CSS/XPath; stabilize strict-mode usage.');
      break;
    case 'frontend-timing':
      base.what_to_inspect.push('First failing test for timeout source (page load vs API vs UI assertions).');
      base.what_to_change.push('Replace fixed sleeps with deterministic waits and API readiness checks.');
      break;
    case 'infra/network':
      base.what_to_inspect.push('net::ERR_* / ECONN* errors and backend health endpoint readiness.');
      base.what_to_change.push('Add retries/backoff for readiness; ensure server binds and health endpoint is reachable.');
      break;
    default:
      base.what_to_inspect.push('First failing Playwright test block and surrounding errors.');
      base.what_to_change.push('Add logging/annotations for first failure; ensure artifacts include both logs.');
      break;
  }

  return base;
}

function buildFixAgentInstructions(classification: Classification, playwrightLog: string, backendLog: string): FixAgentInstructions {
  const suspectedPaths: string[] = [];
  const failing = classification.failing_tests;

  if (classification.error_type === 'frontend-selector' || classification.error_type === 'frontend-timing') {
    suspectedPaths.push('tests/e2e/');
    suspectedPaths.push('tests/pages/');
    suspectedPaths.push('dashboard/');
    suspectedPaths.push('playwright.config.ts');
  }

  if (
    classification.error_type === 'backend-500' ||
    classification.error_type === 'backend-exception' ||
    classification.error_type === 'backend-migration' ||
    classification.error_type === 'auth/session'
  ) {
    suspectedPaths.push('django/');
    suspectedPaths.push('django/apps/');
    suspectedPaths.push('backend/');
  }

  suspectedPaths.push('.github/workflows/backend-setup.yml');
  suspectedPaths.push('.github/workflows/agent-engine.yml');

  const pwSnippet = (extractFirstPlaywrightErrorSnippet(playwrightLog) || playwrightLog.slice(-MAX_SNIPPET_CHARS)).slice(
    0,
    MAX_SNIPPET_CHARS,
  );
  const beSnippet = extractBackendSnippet(backendLog).slice(0, MAX_SNIPPET_CHARS);

  let rootCause = classification.summary;
  if (pwSnippet) rootCause = `${rootCause} First Playwright signal: ${pwSnippet}`;

  let direction = 'Parse logs, map the first failure to code, then apply the smallest targeted fix.';
  switch (classification.error_type) {
    case 'frontend-selector':
      direction = 'Update failing locators/assertions to be resilient; prefer role-based locators and stable test ids.';
      break;
    case 'frontend-timing':
      direction = 'Replace flaky waits with deterministic waits; ensure backend readiness and stable navigation timing.';
      break;
    case 'auth/session':
      direction = 'Fix auth/session setup: ensure E2E user, role assignment, and storageState/session persistence.';
      break;
    case 'backend-migration':
      direction = 'Fix migrations/seed ordering and ensure DB schema matches expected models in CI.';
      break;
    case 'backend-exception':
    case 'backend-500':
      direction = 'Fix backend error path identified by traceback/5xx; add regression test if feasible.';
      break;
    case 'infra/network':
      direction = 'Harden server startup/readiness and retry transient network failures.';
      break;
    default:
      break;
  }

  return {
    suspected_paths: Array.from(new Set(suspectedPaths)),
    failing_tests: failing,
    suspected_root_cause: rootCause.slice(0, 2000),
    suggested_fix_direction: direction,
    key_log_snippets: {
      playwright: pwSnippet,
      backend: beSnippet,
    },
  };
}

async function dispatchSelfHeal(input: SelfHealModuleInput) {
  // Hook: replace this with a queue publish / webhook / workflow_dispatch call.
  // Persisting payload makes it easy to integrate with a downstream runner.
  await writeTextFile(path.join(input.storage.run_dir, 'self-heal.json'), JSON.stringify(input, null, 2));
}

async function dispatchFixAgent(input: FixAgentModuleInput) {
  // Hook: replace this with a queue publish / webhook / workflow_dispatch call.
  await writeTextFile(path.join(input.storage.run_dir, 'fix-agent.json'), JSON.stringify(input, null, 2));
}

export default async function handler(req: JsonRequest, res: JsonResponse) {
  if (req.method !== 'POST') {
    res.setHeader?.('Allow', 'POST');
    return sendJson(res, 405, { error: 'method_not_allowed' });
  }

  const expectedToken = process.env.DEVELOPER_AGENT_TOKEN;
  if (!expectedToken) {
    return sendJson(res, 500, { error: 'internal_error' });
  }

  const headers = req.headers || {};
  const authHeaderValue = Array.isArray(headers.authorization) ? headers.authorization[0] : headers.authorization;
  const presentedToken = getBearerToken(authHeaderValue);
  if (!presentedToken || !timingSafeEqualString(presentedToken, expectedToken)) {
    return sendJson(res, 401, { error: 'unauthorized' });
  }

  let body: unknown;
  try {
    body = await readJsonBody(req);
  } catch {
    body = undefined;
  }

  const missing = missingFields(body);
  if (missing.length > 0) {
    return sendJson(res, 400, { error: 'invalid_payload', missing: missing.map(String) });
  }

  const obj = body as Record<string, unknown>;
  const payload: ProcessLogsPayload = {
    playwright_log: obj.playwright_log as string,
    backend_log: obj.backend_log as string,
    run_id: obj.run_id as string | number,
    job_name: obj.job_name as string,
    timestamp: obj.timestamp as string,
    branch: obj.branch as string,
    commit: obj.commit as string,
    status: obj.status as string,
  };

  const runId = normalizeRunId(payload.run_id);

  const preferredLogsRoots = ['/logs', path.join(process.cwd(), 'logs'), path.join('/tmp', 'logs')];
  let logsRoot: string | null = null;
  for (const candidate of preferredLogsRoots) {
    try {
      await ensureDir(candidate);
      logsRoot = candidate;
      break;
    } catch {
      // try next
    }
  }

  if (!logsRoot) {
    return sendJson(res, 500, { error: 'internal_error' });
  }

  const runDir = path.join(logsRoot, runId);
  const playwrightLogPath = path.join(runDir, 'playwright.log');
  const backendLogPath = path.join(runDir, 'backend.log');
  const analysisPath = path.join(runDir, 'analysis.json');

  const playwrightLog = normalizeAndTrimLog(payload.playwright_log);
  const backendLog = normalizeAndTrimLog(payload.backend_log);

  try {
    await writeTextFile(playwrightLogPath, playwrightLog);
    await writeTextFile(backendLogPath, backendLog);

    const failingTests = extractPlaywrightFailingTests(playwrightLog);
    const baseClassification = classifyFailure(playwrightLog, backendLog);
    const classification: Classification = {
      ...baseClassification,
      failing_tests: failingTests,
    };

    const selfHealPlan = buildSelfHealPlan(classification);
    const fixInstructions = buildFixAgentInstructions(classification, playwrightLog, backendLog);

    const analysis = {
      processed_at: new Date().toISOString(),
      run_id: runId,
      job_name: payload.job_name,
      timestamp: payload.timestamp,
      branch: payload.branch,
      commit: payload.commit,
      status: payload.status,
      classification,
      self_heal_plan: selfHealPlan,
      fix_agent_instructions: fixInstructions,
      storage: {
        logs_root: logsRoot,
        run_dir: runDir,
        playwright_log_path: playwrightLogPath,
        backend_log_path: backendLogPath,
      },
    };

    await writeTextFile(analysisPath, JSON.stringify(analysis, null, 2));

    const shouldTrigger = String(payload.status).toLowerCase() === 'failed';
    const triggers = {
      self_heal: shouldTrigger,
      fix_agent: shouldTrigger,
    };

    if (shouldTrigger) {
      const storage = {
        run_dir: runDir,
        playwright_log_path: playwrightLogPath,
        backend_log_path: backendLogPath,
        analysis_path: analysisPath,
      };

      await dispatchSelfHeal({
        run_id: runId,
        job_name: payload.job_name,
        branch: payload.branch,
        commit: payload.commit,
        classification,
        self_heal_plan: selfHealPlan,
        storage,
      });

      await dispatchFixAgent({
        run_id: runId,
        job_name: payload.job_name,
        branch: payload.branch,
        commit: payload.commit,
        classification,
        fix_instructions: fixInstructions,
        storage,
      });

      await writeTextFile(path.join(runDir, 'triggers.json'), JSON.stringify({ triggered_at: new Date().toISOString(), triggers }, null, 2));
    }

    return sendJson(res, 200, {
      status: 'processed',
      run_id: runId,
      classification,
      self_heal_plan: selfHealPlan,
      fix_agent_instructions: fixInstructions,
      triggers,
    });
  } catch {
    return sendJson(res, 500, { error: 'internal_error' });
  }
}
