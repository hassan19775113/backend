# CI/CD Troubleshooting Guide

This repo’s CI is driven by GitHub Actions workflows under `.github/workflows/`.

## Where to look first

1) Open the failing GitHub Actions run
- Repo → **Actions** → open the failed workflow run.

2) Identify the failing job + step
- A run can have multiple jobs (e.g. `page-smoke`, `e2e-tests`, `flaky-classifier`).
- Click the red job → expand the first red step.

3) Download artifacts (most useful debugging signal)
Common artifacts in this repo:
- Backend logs: `backend-logs-*` (Django server log + CI log)
- Playwright output: `test-results` / `playwright.log` (varies by job)
- Agent reports: `*-output` artifacts (JSON)

## Common failure modes

### 1) Playwright install / browser download issues
**Symptoms**
- Install step fails during `npx playwright ... install`.

**Where to look**
- Job step “Install base dependencies” output.

**What to try**
- Confirm Playwright version is pinned in the workflow.
- Confirm the workflow installs only needed browsers (Chromium).

### 2) Cache drift / flaky installs
**Symptoms**
- `npm ci` or `pip install` behaves differently across runs.
- Cache restores but dependencies mismatch.

**Where to look**
- Cache restore logs for pip/npm/Playwright.

**What to try**
- Ensure cache keys include version components (Node/Python/pip/Playwright).
- Ensure lockfiles are present (`package-lock.json`, `requirements.txt`).

### 3) Django server not ready / health check failures
**Symptoms**
- Health check step fails (`/api/health/`), timeouts.

**Where to look**
- Artifact `backend-logs-*`:
  - `django/logs/django/server.log`
  - `django/logs/system/ci.log`

**What to try**
- Check migrations output.
- Check for port conflicts, DB readiness, or exceptions during startup.

### 4) E2E login / auth setup failures
**Symptoms**
- Global setup fails (missing user/password or login errors).

**Where to look**
- Playwright global setup output + backend logs.

**What to try**
- Confirm E2E user is created in CI (workflow step “Create E2E user”).
- Confirm base URL and credentials env vars are set.

### 5) Workflow scripting errors (jq/bash quoting)
**Symptoms**
- `jq: parse error ...`
- `bash` exits early due to quoting or `set -e`.

**Where to look**
- The exact failed step log.

**What to try**
- Avoid interpolating JSON into shell strings.
- Use `while IFS= read -r ...` when reading JSON lines.

## Log locations (repo paths)

When the workflow uploads backend logs, these paths are typically included:
- `django/logs/django/server.log`
- `django/logs/system/ci.log`
- (Optional) `django/logs/agent/*` for agent scripts

## Escalation checklist

When filing or updating an issue/PR, include:
- Link to the failing Actions run
- Failing job + step name
- Relevant artifact names downloaded
- The smallest error snippet that explains the failure
- Whether the failure is deterministic or flaky (re-run outcome)

## Keeping this doc current

If you discover a new failure mode:
- Add a new section under “Common failure modes”
- Link to the run/PR that introduced or fixed it
