You are a Senior Principal Engineer Agent. Generate a complete stabilization backlog for a Django/DRF monolith with a broken CI/CD pipeline, missing tests, fat serializers, missing service layer, hardcoded secrets, inconsistent API errors, and missing observability.

Your output must contain EXACTLY four artifacts:

============================================================
1) MARKDOWN: EPICS & CHILD ISSUES
============================================================
- Create 7 epics:
  1. Stabilize CI/CD Pipeline
  2. Refactor Scheduling Engine Into Service Layer
  3. Add Unit Test Coverage for Scheduling Engine
  4. Security Hardening & Secret Management
  5. Standardize API Error Handling
  6. Observability & Logging Improvements
  7. Documentation & Developer Experience

- For each epic, generate 3–5 child issues.
- Each issue must include:
  - Title
  - Problem summary
  - Acceptance criteria
  - Labels (P0/P1/P2, backend, ci, tests, security, api, docs, dx)
- Output as clean Markdown.

============================================================
2) JSON: issues.json (GitHub Bulk Import)
============================================================
- JSON array.
- Each object must contain:
  - "title"
  - "body"
  - "labels": [...]
  - "epic": <epic-id-number>
- Epics must have an "id" field.
- IDs must be sequential starting at 1.

============================================================
3) YAML: project-import.yml (GitHub Projects Beta)
============================================================
- YAML compatible with GitHub Projects (Beta).
- Structure:
    version: 1
    issues:
      - id: epic-ci
        title: ...
        labels: [...]
      - id: ci-1
        title: ...
        parent: epic-ci

- Epic IDs:
    epic-ci, epic-scheduling, epic-tests, epic-security,
    epic-errors, epic-observability, epic-docs

- Child IDs:
    ci-1, ci-2, sched-1, tests-1, sec-1, err-1, obs-1, docs-1

============================================================
4) WORKFLOW: agent-engine.yml (single orchestrator)
============================================================
Generate a fully working GitHub Actions workflow that:

- Uses workflow_dispatch
- Sets permissions:
      contents: read
      issues: write
      projects: write

- Loads automation/issues.json
- Creates issues if they do not exist
- Adds each issue to a GitHub Project (Beta) using GraphQL:
      addProjectV2ItemById

- Links child issues to epics using the Parent field:
      updateProjectV2ItemFieldValue

- Uses environment variables:
      PROJECT_ID
      PROJECT_NUMBER
      PARENT_FIELD_ID

- Includes debugging:
      ls -R .
      ls -R automation

- Is idempotent (no duplicates)
- Has full error visibility

============================================================
OUTPUT FORMAT
============================================================
Output the four artifacts in this exact order:

### 1. MARKDOWN
<markdown>

### 2. JSON
<json>

### 3. YAML
<yaml>

### 4. WORKFLOW
<workflow>

No explanations. No comments. Only the four artifacts.
