import crypto from 'node:crypto';

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

type CiLogsPayload = {
  playwright_log: string;
  backend_log: string;
  run_id: string | number;
  job_name: string;
  timestamp: string;
  branch: string;
  commit: string;
  status: string;
};

type ValidationResult =
  | { ok: true; value: CiLogsPayload }
  | { ok: false; errors: string[] };

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

function validatePayload(body: unknown): ValidationResult {
  const errors: string[] = [];
  if (typeof body !== 'object' || body === null) {
    return { ok: false, errors: ['Body must be a JSON object'] };
  }

  const obj = body as Record<string, unknown>;

  const expectString = (key: keyof CiLogsPayload) => {
    if (typeof obj[key as string] !== 'string') errors.push(`${String(key)} must be a string`);
  };

  expectString('playwright_log');
  expectString('backend_log');

  if (!(typeof obj.run_id === 'string' || typeof obj.run_id === 'number')) {
    errors.push('run_id must be a string or number');
  }

  expectString('job_name');
  expectString('timestamp');
  expectString('branch');
  expectString('commit');
  expectString('status');

  if (errors.length > 0) return { ok: false, errors };

  return {
    ok: true,
    value: {
      playwright_log: obj.playwright_log as string,
      backend_log: obj.backend_log as string,
      run_id: obj.run_id as string | number,
      job_name: obj.job_name as string,
      timestamp: obj.timestamp as string,
      branch: obj.branch as string,
      commit: obj.commit as string,
      status: obj.status as string,
    },
  };
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

export default async function handler(req: JsonRequest, res: JsonResponse) {
  if (req.method !== 'POST') {
    res.setHeader?.('Allow', 'POST');
    return sendJson(res, 405, { error: 'Method Not Allowed' });
  }

  const expectedToken = process.env.AGENT_TOKEN;
  if (!expectedToken) {
    return sendJson(res, 500, { error: 'Server misconfigured: AGENT_TOKEN missing' });
  }

  const headers = req.headers || {};
  const authHeaderValue = Array.isArray(headers.authorization) ? headers.authorization[0] : headers.authorization;
  const presentedToken = getBearerToken(authHeaderValue);
  if (!presentedToken || !timingSafeEqualString(presentedToken, expectedToken)) {
    return sendJson(res, 401, { error: 'Unauthorized' });
  }

  let body: unknown;
  try {
    body = await readJsonBody(req);
  } catch (e) {
    return sendJson(res, 400, { error: 'Invalid JSON body', details: [String(e)] });
  }

  const validated = validatePayload(body);
  if (validated.ok === false) {
    return sendJson(res, 400, { error: 'Invalid payload', details: validated.errors });
  }

  const developerAgentUrl = process.env.DEVELOPER_AGENT_URL;
  const developerAgentToken = process.env.DEVELOPER_AGENT_TOKEN;

  if (!developerAgentUrl) {
    return sendJson(res, 500, { error: 'Server misconfigured: DEVELOPER_AGENT_URL missing' });
  }
  if (!developerAgentToken) {
    return sendJson(res, 500, { error: 'Server misconfigured: DEVELOPER_AGENT_TOKEN missing' });
  }

  const endpoint = developerAgentUrl.endsWith('/process-logs')
    ? developerAgentUrl
    : `${developerAgentUrl.replace(/\/$/, '')}/process-logs`;

  const forwardBody = {
    playwright_log: validated.value.playwright_log,
    backend_log: validated.value.backend_log,
    run_id: validated.value.run_id,
    job_name: validated.value.job_name,
    timestamp: validated.value.timestamp,
    branch: validated.value.branch,
    commit: validated.value.commit,
    status: validated.value.status,
  };

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15_000);

  try {
    const resp = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${developerAgentToken}`,
      },
      body: JSON.stringify(forwardBody),
      signal: controller.signal,
    });

    const text = await resp.text().catch(() => '');

    if (!resp.ok) {
      return sendJson(res, 502, {
        error: 'Forwarding failed',
        upstream_status: resp.status,
        upstream_body: text,
      });
    }

    let upstreamJson: unknown = null;
    try {
      upstreamJson = text ? JSON.parse(text) : null;
    } catch {
      upstreamJson = null;
    }

    // NOTE: Returning upstream details enables downstream CI (self-heal) to consume
    // classification + plans without needing access to Developer-Agent storage.
    return sendJson(res, 200, { status: 'received', upstream: upstreamJson });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return sendJson(res, 502, { error: 'Forwarding failed', message });
  } finally {
    clearTimeout(timeout);
  }
}
