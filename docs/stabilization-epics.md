## Epic 2: Refactor Scheduling Engine Into Service Layer
### Issue: Define Scheduling Domain Contracts
- Problem Summary: Scheduling rules live in serializers with no documented boundaries or invariants.
- Acceptance Criteria:
  - Create an ADR describing inputs, outputs, and invariants of the scheduling engine.
  - Map existing serializer logic to service operations.
  - Architecture owner approves the contract.
- Labels: P1, backend, docs

### Issue: Implement SchedulingService Interface
- Problem Summary: Lack of service abstraction prevents reuse and isolated testing.
- Acceptance Criteria:
  - Introduce a SchedulingService class with plan, commit, and rollback methods.
  - Serializer and view layers invoke the service instead of direct ORM logic.
  - Add type hints and docstrings for public methods.
- Labels: P0, backend, architecture

### Issue: Extract Validation Logic from Serializers
- Problem Summary: Fat serializers mix validation, orchestration, and persistence concerns.
- Acceptance Criteria:
  - Move business validations into a dedicated validators module used by the service.
  - Serializers focus on shape and basic field validation only.
  - API responses remain unchanged.
- Labels: P1, backend, api

### Issue: Introduce Scheduling Orchestration Module
- Problem Summary: Bulk scheduling logic is duplicated across tasks and cron jobs.
- Acceptance Criteria:
  - Create an orchestration helper handling batching, retries, and conflict resolution.
  - Expose hooks for async tasks and background workers.
  - Document usage in the developer guide.
- Labels: P2, backend

## Epic 3: Add Unit Test Coverage for Scheduling Engine
### Issue: Build Scheduling Engine Test Harness
- Problem Summary: No isolated harness exists to test scheduling flows without hitting the database.
- Acceptance Criteria:
  - Provide fixtures and mocks for service dependencies.
  - Support running tests via pytest and Django test runner.
  - Include harness in the CI matrix.
- Labels: P0, tests, backend

### Issue: Cover Conflict Resolution Rules
- Problem Summary: Overlap detection regressions slip through due to missing targeted tests.
- Acceptance Criteria:
  - Add unit tests for overlapping appointments, resources, and rooms.
  - Include positive and negative scenarios with assertions on error codes.
  - Report coverage deltas in CI output.
- Labels: P0, tests, backend

### Issue: Validate Capacity Planning Calculations
- Problem Summary: Capacity algorithms lack regression tests causing misallocation.
- Acceptance Criteria:
  - Add tests for capacity by practitioner, room, and daypart.
  - Simulate edge loads using fixtures without real DB access.
  - Tests must pass deterministically.
- Labels: P1, tests, backend

### Issue: Guard Timezone and DST Edge Cases
- Problem Summary: Scheduling fails during daylight-saving transitions across locales.
- Acceptance Criteria:
  - Add tests covering forward and backward DST shifts for supported time zones.
  - Verify serialization uses timezone-aware datetimes.
  - Document DST handling strategy.
- Labels: P1, tests, backend

## Epic 4: Security Hardening & Secret Management
### Issue: Integrate Centralized Secret Manager
- Problem Summary: Secrets are sourced from .env files without rotation or access control.
- Acceptance Criteria:
  - Integrate the app and CI with the chosen cloud secret manager via adapter.
  - Document local development fallback.
  - CI retrieves secrets via OIDC-backed credentials.
- Labels: P0, security, backend, ci

### Issue: Purge Hardcoded Secrets from Repository
- Problem Summary: Multiple modules contain plaintext API keys and credentials.
- Acceptance Criteria:
  - Replace secrets with environment lookups or secret manager references.
  - Add a pre-commit hook scanning for secrets.
  - Scrub git history where feasible and document exceptions.
- Labels: P0, security, backend

### Issue: Add Secret Scanning Gate to CI
- Problem Summary: No automated detection of leaked secrets in pull requests.
- Acceptance Criteria:
  - Add TruffleHog or Gitleaks step that fails on detections.
  - Upload scan reports as artifacts for triage.
  - Document false-positive handling in README.
- Labels: P1, security, ci

### Issue: Enforce Least-Privilege Database Roles
- Problem Summary: The application uses a superuser role across all environments.
- Acceptance Criteria:
  - Create a dedicated app role with restricted grants.
  - Update connection strings and migrations to use the new role.
  - Add a migration guard preventing accidental superuser usage.
- Labels: P1, security, database

## Epic 5: Standardize API Error Handling
### Issue: Define Global DRF Error Contract
- Problem Summary: APIs return inconsistent structures for errors, confusing clients.
- Acceptance Criteria:
  - Publish an error schema with code, message, and trace_id fields.
  - Update the DRF exception handler to emit the schema.
  - Backfill documentation in the OpenAPI spec.
- Labels: P0, api, backend

### Issue: Normalize Serializer Validation Errors
- Problem Summary: Field error responses vary by serializer causing front-end hacks.
- Acceptance Criteria:
  - Build a central utility to format validation errors consistently.
  - Update the top serializers to use the utility.
  - Add regression tests verifying the schema.
- Labels: P1, api, backend

### Issue: Attach Trace IDs to 5xx Responses
- Problem Summary: Operators cannot correlate API failures with logs.
- Acceptance Criteria:
  - Middleware injects a trace_id into error responses and logs.
  - Observability documentation updated with lookup steps.
  - Integration test ensures trace_id presence.
- Labels: P1, api, observability

### Issue: Add Contract Tests for Error Payloads
- Problem Summary: No automated guard ensures error payloads stay consistent.
- Acceptance Criteria:
  - Write pytest contract tests hitting representative endpoints.
  - Tests assert schema compliance and localization behavior.
  - Tests run in CI pipeline.
- Labels: P2, api, tests

## Epic 6: Observability & Logging Improvements
### Issue: Adopt Structured Logging with Context
- Problem Summary: Plaintext logs lack context for debugging production outages.
- Acceptance Criteria:
  - Configure a JSON/logfmt formatter including request_id, user_id, and feature flags.
  - Update log shipping configuration to accept structured payloads.
  - Verify logs in staging before rollout.
- Labels: P0, observability, backend

### Issue: Instrument Scheduling Service with APM Traces
- Problem Summary: No visibility into scheduling performance hotspots.
- Acceptance Criteria:
  - Add OpenTelemetry spans around scheduling service operations.
  - Export traces to the chosen APM backend.
  - Confirm overhead remains under 200 ms per request.
- Labels: P1, observability, backend

### Issue: Emit Scheduling Metrics to Monitoring Stack
- Problem Summary: Lack of metrics for queue depth or SLA adherence.
- Acceptance Criteria:
  - Publish metrics for latency, retries, and failures to StatsD/Prometheus.
  - Create dashboards and alerts with ops sign-off.
  - Document metric names and thresholds.
- Labels: P1, observability, backend, ops

### Issue: Define Log Retention and PII Scrubbing
- Problem Summary: Logs retain personally identifiable information indefinitely.
- Acceptance Criteria:
  - Implement log scrubbing middleware removing PII fields.
  - Configure retention and deletion automation per compliance needs.
  - Obtain compliance approval.
- Labels: P2, observability, security

## Epic 7: Documentation & Developer Experience
### Issue: Create Onboarding Runbook
- Problem Summary: New engineers spend weeks piecing together tribal knowledge.
- Acceptance Criteria:
  - Write a runbook covering environment setup, env vars, and CI overview.
  - Host in docs/ with a table of contents.
  - Reviewed by at least two recent hires.
- Labels: P1, docs, dx

### Issue: Document CI/CD Troubleshooting Guide
- Problem Summary: Repeated questions arise about pipeline failures and log locations.
- Acceptance Criteria:
  - Guide lists common failures, log locations, and escalation steps.
  - Linked from workflow summary outputs.
  - Updated whenever new failure mode is discovered.
- Labels: P1, docs, ci, dx

### Issue: Provide Dev Containers for Local Work
- Problem Summary: Local environments rarely match production, causing "works on my machine" bugs.
- Acceptance Criteria:
  - Add a devcontainer with Django, Postgres, and Playwright dependencies.
  - Support VS Code and GitHub Codespaces usage.
  - README includes setup instructions.
- Labels: P2, dx, backend

### Issue: Automate Changelog Generation
- Problem Summary: Manual changelog updates lag behind releases.
- Acceptance Criteria:
  - Add a release workflow generating changelog from conventional commits.
  - Publish artifact and PR comment on releases.
  - Document the new process in README.
- Labels: P2, docs, dx, ci
