#!/usr/bin/env node

// Role: Apply small, scoped fixes (tests/selectors/local backend) based on Developer-Agent hints.
// Output: patch + metadata artifacts, PR-ready (no pushing, no PR creation).
// Guardrails:
// - Limit touched paths (tests + small backend) and disallow large diffs.
// - Always write patch + metadata, even if validation fails.
// - Never fail CI hard: exit 0 after producing artifacts.

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

async function writeJson(filePath, data) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, JSON.stringify(data, null, 2), 'utf8');
}

async function writeText(filePath, content) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, content ?? '', 'utf8');
}

async function fileExists(p) {
  try {
    await fs.stat(p);
    return true;
  } catch {
    return false;
  }
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

function normalizePath(p) {
  return String(p || '').replace(/\\/g, '/');
}

function isAllowedPath(p) {
  const n = normalizePath(p);
  // Scope limitation: tests, selectors, and small localized backend fixes only.
  if (n.startsWith('tests/')) return true;
  if (n.startsWith('django/')) return true;
  return false;
}

function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n));
}

function toErrorType(classification) {
  const t = classification?.error_type;
  return typeof t === 'string' ? t : 'unknown';
}

function extractSpecPathsFromInput(input) {
  const arr = input?.logs?.extracted_spec_paths;
  return Array.isArray(arr) ? arr.filter((p) => typeof p === 'string') : [];
}

function extractStrictModeSelectors(playwrightLogText) {
  const text = String(playwrightLogText || '');
  // Common Playwright message includes: "strict mode violation: locator('...') resolved to ..."
  const re = /strict mode violation[\s\S]{0,800}?locator\((['"`])([^'"`]{1,200})\1\)/gi;
  const selectors = [];
  let m;
  while ((m = re.exec(text)) !== null) {
    selectors.push(m[2]);
    if (selectors.length >= 3) break;
  }
  return selectors;
}

function hasPlaywrightImportTest(source) {
  const s = String(source);
  return /from\s+['"]@playwright\/test['"]/m.test(s);
}

function addFileLevelTimeoutIfMissing(source, timeoutMs) {
  const s = String(source);
  if (!hasPlaywrightImportTest(s)) return { changed: false, source: s };
  if (/\btest\.setTimeout\(/m.test(s)) return { changed: false, source: s };

  // Guardrail: minimal, file-local change near imports.
  const lines = s.split(/\n/);
  let insertAt = 0;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (/^\s*import\b/.test(line) || /^\s*\/\//.test(line) || /^\s*$/.test(line)) {
      insertAt = i + 1;
      continue;
    }
    break;
  }

  lines.splice(insertAt, 0, `test.setTimeout(${timeoutMs});`);
  return { changed: true, source: lines.join('\n') };
}

function addFirstForStrictLocator(source, selector) {
  const s = String(source);
  if (!selector) return { changed: false, source: s };

  // Guardrail: only patch exact string matches and avoid duplicate .first().
  const needle = `page.locator('${selector}')`;
  const needleDq = `page.locator(\"${selector}\")`;

  let out = s;
  let changed = false;

  if (out.includes(needle) && !out.includes(`${needle}.first()`)) {
    out = out.replaceAll(needle, `${needle}.first()`);
    changed = true;
  }

  // Best-effort for double quotes; keep conservative string-based replace.
  if (out.includes(needleDq) && !out.includes(`${needleDq}.first()`)) {
    out = out.replaceAll(needleDq, `${needleDq}.first()`);
    changed = true;
  }

  return { changed, source: out };
}

async function computeDiffStats() {
  const numstat = await runCmd('git', ['diff', '--numstat']);
  const lines = String(numstat.stdout || '').trim().split(/\n/).filter(Boolean);

  let filesChanged = 0;
  let added = 0;
  let deleted = 0;

  for (const line of lines) {
    const parts = line.split(/\t/);
    if (parts.length < 3) continue;
    const a = parts[0];
    const d = parts[1];
    filesChanged += 1;
    if (a !== '-' && Number.isFinite(Number(a))) added += Number(a);
    if (d !== '-' && Number.isFinite(Number(d))) deleted += Number(d);
  }

  return {
    files_changed: filesChanged,
    lines_added: added,
    lines_deleted: deleted,
    lines_total: added + deleted,
  };
}

/**
 * Compute risk assessment for the patch based on:
 * - Error type
 * - Changed file paths (tests vs backend vs infrastructure)
 * - Diff size
 * - Validation results
 * 
 * Risk levels: low, medium, high, critical
 * Auto-merge eligible only for low-risk changes
 * 
 * @param {Object} metadata - Patch metadata containing error_type
 * @param {Array<string>} changedFiles - Array of file paths that were changed
 * @param {Object} stats - Diff statistics with files_changed, lines_total, etc.
 * @param {boolean|null} validationOk - Validation result (true=passed, false=failed, null=not attempted)
 * @returns {Object} Risk assessment with level, score, factors, and auto_merge_eligible
 */
function computeRiskAssessment(metadata, changedFiles, stats, validationOk) {
  const assessment = {
    level: 'unknown',
    score: 0,
    factors: [],
    auto_merge_eligible: false,
  };

  // Base risk by error type
  const errorType = metadata.error_type;
  if (errorType === 'frontend-selector') {
    assessment.score += 1;
    assessment.factors.push('error_type:frontend-selector(+1)');
  } else if (errorType === 'frontend-timing') {
    assessment.score += 2;
    assessment.factors.push('error_type:frontend-timing(+2)');
  } else {
    assessment.score += 5;
    assessment.factors.push(`error_type:${errorType}(+5)`);
  }

  // Assess changed paths
  let hasBackendChanges = false;
  let hasTestChanges = false;
  let hasInfraChanges = false;
  let hasConfigChanges = false;

  for (const file of changedFiles) {
    const n = normalizePath(file);
    
    if (n.startsWith('tests/')) {
      hasTestChanges = true;
    } else if (n.startsWith('django/') || n.startsWith('praxi_backend/')) {
      hasBackendChanges = true;
    } else if (n.startsWith('.github/')) {
      hasInfraChanges = true;
    } else if (n.includes('config') || n.includes('.json') || n.includes('.yml')) {
      hasConfigChanges = true;
    }
  }

  if (hasTestChanges && !hasBackendChanges && !hasInfraChanges && !hasConfigChanges) {
    assessment.score += 0;
    assessment.factors.push('scope:test-only(+0)');
  } else if (hasBackendChanges && !hasInfraChanges) {
    assessment.score += 3;
    assessment.factors.push('scope:backend(+3)');
  } else if (hasInfraChanges || hasConfigChanges) {
    assessment.score += 10;
    assessment.factors.push('scope:infrastructure(+10)');
  }

  // Assess diff size
  if (stats.files_changed === 0) {
    assessment.score += 0;
    assessment.factors.push('size:empty(+0)');
  } else if (stats.files_changed <= 2 && stats.lines_total <= 50) {
    assessment.score += 1;
    assessment.factors.push('size:small(+1)');
  } else if (stats.files_changed <= 4 && stats.lines_total <= 150) {
    assessment.score += 2;
    assessment.factors.push('size:medium(+2)');
  } else {
    assessment.score += 5;
    assessment.factors.push('size:large(+5)');
  }

  // Validation impact
  if (validationOk === true) {
    assessment.score -= 2;
    assessment.factors.push('validation:passed(-2)');
  } else if (validationOk === false) {
    assessment.score += 3;
    assessment.factors.push('validation:failed(+3)');
  }

  // Determine risk level from score
  if (assessment.score <= 2) {
    assessment.level = 'low';
  } else if (assessment.score <= 5) {
    assessment.level = 'medium';
  } else if (assessment.score <= 10) {
    assessment.level = 'high';
  } else {
    assessment.level = 'critical';
  }

  // Auto-merge eligibility:
  // - Low risk (score <= 2)
  // - Test-only changes
  // - Small diff
  // - Validation passed OR not attempted (for selector fixes)
  const isLowRisk = assessment.level === 'low';
  const isTestOnly = hasTestChanges && !hasBackendChanges && !hasInfraChanges && !hasConfigChanges;
  const isSmallDiff = stats.files_changed <= 3 && stats.lines_total <= 100;
  const validationAcceptable = validationOk === true || validationOk === null;

  assessment.auto_merge_eligible = isLowRisk && isTestOnly && isSmallDiff && validationAcceptable;

  if (assessment.auto_merge_eligible) {
    assessment.factors.push('auto_merge:eligible');
  } else {
    const reasons = [];
    if (!isLowRisk) reasons.push('!low_risk');
    if (!isTestOnly) reasons.push('!test_only');
    if (!isSmallDiff) reasons.push('!small_diff');
    if (!validationAcceptable) reasons.push('!validation_ok');
    assessment.factors.push(`auto_merge:blocked(${reasons.join(',')})`);
  }

  return assessment;
}


async function main() {
  const args = process.argv.slice(2);
  const inputPath = argValue(args, '--input', path.join('fix-agent', 'input.json'));
  const outDir = argValue(args, '--out-dir', 'fix-agent');

  const now = new Date().toISOString();

  const input = await readJson(inputPath);
  const runId = String(input?.run_id || process.env.GITHUB_RUN_ID || 'unknown');
  const errorType = toErrorType(input?.analysis?.classification);

  const patchPath = path.join(outDir, `patch-${runId}.diff`);
  const metadataPath = path.join(outDir, `metadata-${runId}.json`);

  const maxFiles = clamp(Number(process.env.FIX_AGENT_MAX_FILES || '4') || 4, 1, 8);
  const maxLines = clamp(Number(process.env.FIX_AGENT_MAX_LINES || '180') || 180, 20, 500);

  const metadata = {
    version: 1,
    generated_at: now,
    run_id: runId,
    error_type: errorType,
    allowed: true,
    guardrails: {
      max_files: maxFiles,
      max_lines: maxLines,
      allowed_roots: ['tests/', 'django/'],
    },
    suggestions: {
      branch_name: `fix-agent/run-${runId}-${errorType}`.slice(0, 80),
      commit_message: `Fix(${errorType}): stabilize failing CI run ${runId}`,
      pr_title: `Fix(${errorType}): stabilize CI failures`,
      pr_body:
        `Automated Fix-Agent patch for run_id=${runId}.\n\n` +
        `- Guardrails: scoped changes only; capped file/line changes\n` +
        `- Validation: minimal subset when possible\n\n` +
        `Please review carefully before merging.`,
    },
    inputs: {
      has_classification: !!input?.analysis?.classification,
      has_fix_instructions: !!input?.analysis?.fix_agent_instructions,
    },
    change_summary: {
      attempted_files: [],
      changed_files: [],
      diff_stats: null,
    },
    validation: {
      attempted: false,
      command: null,
      exit_code: null,
      ok: null,
      notes: null,
    },
    needs_manual_review: false,
    errors: [],
    risk_assessment: {
      level: 'unknown',
      score: 0,
      factors: [],
      auto_merge_eligible: false,
    },
  };

  // Guardrail: if we have no structured analysis, avoid blind edits.
  if (!input?.analysis?.classification || !input?.analysis?.fix_agent_instructions) {
    metadata.allowed = false;
    metadata.needs_manual_review = true;
    metadata.validation.notes = 'Missing classification/instructions; patch intentionally empty.';
    metadata.risk_assessment = {
      level: 'critical',
      score: 999,
      factors: ['no_analysis'],
      auto_merge_eligible: false,
    };

    await writeText(patchPath, '');
    await writeJson(metadataPath, metadata);
    console.log(`Wrote ${patchPath}`);
    console.log(`Wrote ${metadataPath}`);
    return;
  }

  const fixInstr = input.analysis.fix_agent_instructions;
  const suspectedPathsRaw = Array.isArray(fixInstr?.suspected_paths) ? fixInstr.suspected_paths : [];
  const suspectedPaths = suspectedPathsRaw.filter((p) => typeof p === 'string').map(normalizePath);

  const specPaths = extractSpecPathsFromInput(input).map(normalizePath);

  const candidatePaths = [];
  for (const p of [...specPaths, ...suspectedPaths]) {
    if (!p) continue;
    if (!isAllowedPath(p)) continue;
    if (!candidatePaths.includes(p)) candidatePaths.push(p);
    if (candidatePaths.length >= maxFiles) break;
  }

  metadata.change_summary.attempted_files = candidatePaths;

  // Load a lightweight log snippet to drive safe, string-based transforms.
  const playwrightSnippet = String(fixInstr?.key_log_snippets?.playwright || '');
  const strictSelectors = extractStrictModeSelectors(playwrightSnippet);

  const touched = [];
  for (const relPath of candidatePaths) {
    const filePath = relPath;
    if (!(await fileExists(filePath))) continue;

    const before = await fs.readFile(filePath, 'utf8');
    let current = before;
    let changed = false;

    if (errorType === 'frontend-timing') {
      const r = addFileLevelTimeoutIfMissing(current, 60_000);
      current = r.source;
      changed = changed || r.changed;
    }

    // Guardrail: selector auto-fixes limited to strict-mode violations (low risk: choose first match).
    if (errorType === 'frontend-selector') {
      for (const sel of strictSelectors) {
        const r = addFirstForStrictLocator(current, sel);
        current = r.source;
        changed = changed || r.changed;
        if (changed) break;
      }
    }

    // Guardrail: do not attempt backend changes without explicit, localized targets.

    if (changed && current !== before) {
      await fs.writeFile(filePath, current, 'utf8');
      touched.push(relPath);
    }
  }

  metadata.change_summary.changed_files = touched;
  const stats = await computeDiffStats();
  metadata.change_summary.diff_stats = stats;

  // Change size guardrails: if too large, revert changes and produce empty patch with manual-review flag.
  if (stats.files_changed > maxFiles || stats.lines_total > maxLines) {
    metadata.needs_manual_review = true;
    metadata.errors.push(
      `Guardrail triggered: diff too large (files=${stats.files_changed}/${maxFiles}, lines=${stats.lines_total}/${maxLines}).`,
    );

    if (touched.length > 0) {
      await runCmd('git', ['checkout', '--', ...touched]);
    }

    await writeText(patchPath, '');
    metadata.risk_assessment = {
      level: 'critical',
      score: 999,
      factors: ['diff_too_large'],
      auto_merge_eligible: false,
    };
    await writeJson(metadataPath, metadata);
    console.log(`Wrote ${patchPath}`);
    console.log(`Wrote ${metadataPath}`);
    return;
  }

  // Minimal validation: attempt subset rerun when we have concrete spec paths.
  // Guardrail: keep it fast and deterministic (single worker, max-failures).
  let validationCmd = null;
  if (touched.length > 0 && specPaths.length > 0 && (errorType === 'frontend-timing' || errorType === 'frontend-selector')) {
    const specs = specPaths.slice(0, 2);
    validationCmd = `npx playwright test ${specs.join(' ')} --max-failures=1 --workers=1`;
    metadata.validation.attempted = true;
    metadata.validation.command = validationCmd;

    const r = await runCmd('bash', ['-lc', validationCmd], { env: process.env });
    metadata.validation.exit_code = r.code;
    metadata.validation.ok = r.code === 0;

    if (r.code !== 0) {
      metadata.needs_manual_review = true;
      metadata.validation.notes = 'Validation failed; patch still produced for manual review.';
    }
  } else {
    metadata.validation.notes = 'Validation skipped (no safe subset available or no changes).';
    metadata.needs_manual_review = metadata.needs_manual_review || touched.length === 0;
  }

  // Patch proposal output: git diff against current HEAD.
  const diff = await runCmd('git', ['diff']);
  await writeText(patchPath, diff.stdout || '');

  // Compute risk assessment for Stage 2 auto-merge decisions
  metadata.risk_assessment = computeRiskAssessment(
    metadata,
    touched,
    stats,
    metadata.validation.ok
  );

  await writeJson(metadataPath, metadata);

  console.log(`Wrote ${patchPath}`);
  console.log(`Wrote ${metadataPath}`);
  console.log(`Risk Assessment: ${metadata.risk_assessment.level} (score: ${metadata.risk_assessment.score}, auto-merge: ${metadata.risk_assessment.auto_merge_eligible})`);
}

main().catch(async (err) => {
  // Guardrail: always emit artifacts; never hard-fail the workflow.
  try {
    const args = process.argv.slice(2);
    const inputPath = argValue(args, '--input', path.join('fix-agent', 'input.json'));
    const outDir = argValue(args, '--out-dir', 'fix-agent');

    let runId = String(process.env.GITHUB_RUN_ID || 'unknown');
    try {
      const input = await readJson(inputPath);
      runId = String(input?.run_id || runId);
    } catch {
      // ignore
    }

    const patchPath = path.join(outDir, `patch-${runId}.diff`);
    const metadataPath = path.join(outDir, `metadata-${runId}.json`);

    await writeText(patchPath, '');
    await writeJson(metadataPath, {
      version: 1,
      generated_at: new Date().toISOString(),
      run_id: runId,
      status: 'error',
      error: String(err?.stack || err),
      needs_manual_review: true,
    });

    console.error(String(err?.stack || err));
    console.log(`Wrote ${patchPath}`);
    console.log(`Wrote ${metadataPath}`);
  } catch {
    console.error(String(err?.stack || err));
  }
  process.exit(0);
});
