# GitHub Support Ticket Draft — Actions workflow name shows path

## Subject
GitHub Actions workflow `name:` ignored; UI/API shows workflow path as name

## Repo
- Owner: hassan19775113
- Repository: PraxiApp
- Branch: main

## Summary
Two workflows in this repository display incorrectly in the GitHub Actions UI sidebar and via the Actions REST API: the workflow **name shown is the file path** (fallback) instead of the YAML `name:` field.

Other workflows in the same repository display correctly.

## Affected workflows
### 1) import-stabilization-backlog.yml
- Path: `.github/workflows/import-stabilization-backlog.yml`
- Expected name (YAML): `Import Stabilization Backlog`
- Actions API currently reports:
  - `id`: `232750425`
  - `name`: `.github/workflows/import-stabilization-backlog.yml`
  - `path`: `.github/workflows/import-stabilization-backlog.yml`
  - `state`: `active`

### 2) import-stabilization-backlog-v2.yml
- Path: `.github/workflows/import-stabilization-backlog-v2.yml`
- Expected name (YAML): `Import Stabilization Backlog v2`
- Actions API currently reports:
  - `id`: `232955184`
  - `name`: `.github/workflows/import-stabilization-backlog-v2.yml`
  - `path`: `.github/workflows/import-stabilization-backlog-v2.yml`
  - `state`: `active`

## Evidence (commands)
List all workflows:

```powershell
gh api repos/hassan19775113/PraxiApp/actions/workflows
```

Fetch workflow metadata by path:

```powershell
gh api repos/hassan19775113/PraxiApp/actions/workflows/import-stabilization-backlog.yml

gh api repos/hassan19775113/PraxiApp/actions/workflows/import-stabilization-backlog-v2.yml
```

## Controls (workflows in same repo that display correctly)
- `.github/workflows/agent-engine.yml` → `Agent Engine`
- `.github/workflows/backend-setup.yml` → `Backend Setup`
- `.github/workflows/cleanup-workflow-runs.yml` → `Cleanup Workflow Runs`

> Note (2026-02): The referenced workflows were removed as part of consolidating CI into a single orchestrator.
> Use `.github/workflows/agent-engine.yml` + `.github/workflows/backend-setup.yml` going forward.

## What we already tried
- Renamed the workflow file (new path) → still shows path as name.
- Hard remove + re-add as two separate commits (forced re-index) → still shows path as name.
- Created a brand-new v2 workflow with different file path **and** different YAML `name:` → still shows path as name.
- Verified no UTF‑8 BOM and first line starts with `name: ...` using GitHub Contents API.

## Expected behavior
GitHub Actions should parse and display the YAML `name:` value in both UI and REST API.

## Request
Please investigate why these workflows are stuck in fallback mode and repair/re-index the workflow metadata for workflow IDs:
- `232750425`
- `232955184`
