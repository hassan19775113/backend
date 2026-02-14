#!/usr/bin/env node

/**
 * Test script for risk assessment algorithm
 */

function normalizePath(p) {
  return String(p || '').replace(/\\/g, '/');
}

function computeRiskAssessment(metadata, changedFiles, stats, validationOk) {
  const assessment = {
    level: 'unknown',
    score: 0,
    factors: [],
    auto_merge_eligible: false,
  };

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

  let hasBackendChanges = false;
  let hasTestChanges = false;
  let hasInfraChanges = false;
  let hasConfigChanges = false;

  for (const file of changedFiles) {
    const n = normalizePath(file);
    if (n.startsWith('tests/')) hasTestChanges = true;
    else if (n.startsWith('django/') || n.startsWith('praxi_backend/')) hasBackendChanges = true;
    else if (n.startsWith('.github/')) hasInfraChanges = true;
    else if (n.includes('config') || n.includes('.json') || n.includes('.yml')) hasConfigChanges = true;
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

  if (validationOk === true) {
    assessment.score -= 2;
    assessment.factors.push('validation:passed(-2)');
  } else if (validationOk === false) {
    assessment.score += 3;
    assessment.factors.push('validation:failed(+3)');
  }

  if (assessment.score <= 2) assessment.level = 'low';
  else if (assessment.score <= 5) assessment.level = 'medium';
  else if (assessment.score <= 10) assessment.level = 'high';
  else assessment.level = 'critical';

  const isLowRisk = assessment.level === 'low';
  const isTestOnly = hasTestChanges && !hasBackendChanges && !hasInfraChanges && !hasConfigChanges;
  const isSmallDiff = stats.files_changed <= 3 && stats.lines_total <= 100;
  const validationAcceptable = validationOk === true || validationOk === null;
  assessment.auto_merge_eligible = isLowRisk && isTestOnly && isSmallDiff && validationAcceptable;

  return assessment;
}

const testCases = [
  {
    name: 'Low risk: Test-only selector fix',
    metadata: { error_type: 'frontend-selector' },
    changedFiles: ['tests/e2e/appointment.spec.ts'],
    stats: { files_changed: 1, lines_total: 10 },
    validationOk: true,
    expectedLevel: 'low',
    expectedAutoMerge: true,
  },
  {
    name: 'Medium risk: Test timing fix',
    metadata: { error_type: 'frontend-timing' },
    changedFiles: ['tests/e2e/a.spec.ts', 'tests/e2e/b.spec.ts'],
    stats: { files_changed: 2, lines_total: 40 },
    validationOk: null,
    expectedLevel: 'medium',
    expectedAutoMerge: false,
  },
  {
    name: 'High risk: Backend changes',
    metadata: { error_type: 'frontend-selector' },
    changedFiles: ['tests/e2e/test.spec.ts', 'django/appointments/views.py'],
    stats: { files_changed: 2, lines_total: 50 },
    validationOk: true,
    expectedLevel: 'medium',
    expectedAutoMerge: false,
  },
  {
    name: 'Critical: Infrastructure',
    metadata: { error_type: 'unknown' },
    changedFiles: ['.github/workflows/ci.yml'],
    stats: { files_changed: 1, lines_total: 100 },
    validationOk: false,
    expectedLevel: 'critical',
    expectedAutoMerge: false,
  },
];

console.log('=== Risk Assessment Tests ===\n');
let passed = 0;

for (const tc of testCases) {
  const result = computeRiskAssessment(tc.metadata, tc.changedFiles, tc.stats, tc.validationOk);
  const ok = result.level === tc.expectedLevel && result.auto_merge_eligible === tc.expectedAutoMerge;
  if (ok) {
    passed++;
    console.log(`✅ ${tc.name}`);
  } else {
    console.log(`❌ ${tc.name}`);
    console.log(`   Expected: ${tc.expectedLevel}, auto=${tc.expectedAutoMerge}`);
    console.log(`   Got: ${result.level}, auto=${result.auto_merge_eligible}, score=${result.score}`);
  }
}

console.log(`\n${passed}/${testCases.length} passed`);
process.exit(passed === testCases.length ? 0 : 1);
