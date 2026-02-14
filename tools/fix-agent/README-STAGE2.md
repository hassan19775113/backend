# Stage 2 - Conditional Autonomy

This directory contains the implementation of Stage 2 features for the Fix-Agent system.

## Overview

Stage 2 introduces **Conditional Autonomy** - the ability for the Fix-Agent to automatically create pull requests for low-risk fixes with proper guardrails and risk assessment.

## Components

### 1. Risk Assessment (`apply-and-validate.mjs`)

The risk assessment algorithm evaluates patches based on multiple factors:

**Scoring Factors:**
- **Error Type**: 
  - `frontend-selector`: +1 (low risk)
  - `frontend-timing`: +2 (medium risk)
  - Other/unknown: +5 (high risk base)
  
- **File Scope**:
  - Test-only changes: +0 (safe)
  - Backend changes: +3 (requires review)
  - Infrastructure/config: +10 (critical)
  
- **Diff Size**:
  - Empty: +0
  - Small (≤2 files, ≤50 lines): +1
  - Medium (≤4 files, ≤150 lines): +2
  - Large (>150 lines or >4 files): +5
  
  Note: Patches are rejected if they exceed hard limits (4 files or 180 lines), but risk scoring uses 150 lines as the threshold for "medium" vs "large" classification.
  
- **Validation**:
  - Passed: -2 (reduces risk)
  - Failed: +3 (increases risk)
  - Not attempted: +0

**Risk Levels:**
- **Low** (score ≤ 2): Auto-merge eligible
- **Medium** (score 3-5): Requires approval
- **High** (score 6-10): Careful review needed
- **Critical** (score > 10): Manual intervention required

**Auto-merge Eligibility:**
A patch is eligible for auto-merge when ALL conditions are met:
- Risk level: Low (score ≤ 2)
- Scope: Test-only changes
- Size: ≤3 files and ≤100 lines
- Validation: Passed or not attempted

### 2. PR Creation (`create-pr.mjs`)

Creates pull requests automatically for eligible patches:
- Reads metadata and patch files
- Checks auto-merge eligibility
- Creates branch with naming convention: `fix-agent/run-{RUN_ID}-{ERROR_TYPE}`
- Applies patch and commits changes
- Outputs metadata for workflow consumption

### 3. Workflow Job (`create-fix-pr`)

GitHub Actions job that orchestrates PR creation:
- Downloads fix-agent output artifacts
- Extracts risk assessment metadata
- Skips if manual review is required
- Creates and pushes fix branch
- Opens PR with risk-based labels
- Adds descriptive PR body with risk information

### 4. CODEOWNERS (`.github/CODEOWNERS`)

Defines approval requirements:
- Test files: Lower approval threshold
- Backend code: Requires explicit approval
- Infrastructure/CI: Critical, requires owner review
- Security files (`.env`, dependencies): Always manual review

## Usage

### Running Tests

```bash
# Test risk assessment algorithm
node tests/tools/test-risk-assessment.mjs
```

### Triggering Workflow

The PR creation workflow runs automatically when:
1. E2E tests fail
2. Fix-agent generates a patch
3. Patch metadata indicates it's safe to create PR

### Manual Testing

```bash
# Dry run PR creation
node tools/fix-agent/create-pr.mjs \
  --metadata fix-agent/metadata-123.json \
  --patch fix-agent/patch-123.diff \
  --dry-run
```

## Guardrails

### Path Allowlist
Only files in these directories can be modified:
- `tests/` - Test files and specs
- `django/` - Django backend (with restrictions)

### Size Limits
- Maximum files: 4 (configurable via `FIX_AGENT_MAX_FILES`)
- Maximum lines: 180 (configurable via `FIX_AGENT_MAX_LINES`)

### Review Requirements
Patches are skipped for automatic PR creation when:
- `needs_manual_review` flag is set
- No classification/instructions from Developer-Agent
- Diff exceeds size limits
- Risk assessment indicates manual intervention needed

## Future Enhancements (Stage 3)

- Actual auto-merge automation (requires GitHub App)
- Rate limiting on PR creation
- CI rerun validation on created PRs
- Deterministic reproduction checks
- Progressive rollout policies
- Automated rollback on regression detection

## Example Metadata

```json
{
  "version": 1,
  "run_id": "12345",
  "error_type": "frontend-selector",
  "risk_assessment": {
    "level": "low",
    "score": 0,
    "factors": [
      "error_type:frontend-selector(+1)",
      "scope:test-only(+0)",
      "size:small(+1)",
      "validation:passed(-2)",
      "auto_merge:eligible"
    ],
    "auto_merge_eligible": true
  },
  "needs_manual_review": false,
  "change_summary": {
    "changed_files": ["tests/e2e/appointment.spec.ts"],
    "diff_stats": {
      "files_changed": 1,
      "lines_total": 10
    }
  }
}
```

## Security Considerations

- PRs are created by `github-actions[bot]`
- Branch protection rules still apply
- CODEOWNERS approval required for sensitive files
- All patches are validated before PR creation
- Audit trail maintained through CI logs and artifacts
