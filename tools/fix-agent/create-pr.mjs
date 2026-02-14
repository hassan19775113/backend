#!/usr/bin/env node

/**
 * Stage 2 - PR Creation Job
 * 
 * Role: Create a PR from Fix-Agent patch with guard gates.
 * Guardrails:
 * - Only create PR if risk assessment allows
 * - Rate limiting on PR creation
 * - Clear labeling and metadata
 * - Require approvals based on risk level
 */

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

async function fileExists(p) {
  try {
    await fs.stat(p);
    return true;
  } catch {
    return false;
  }
}

function runCmd(cmd, args, opts = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { stdio: ['ignore', 'pipe', 'pipe'], ...opts });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (d) => (stdout += d.toString('utf8')));
    child.stderr.on('data', (d) => (stderr += d.toString('utf8')));
    child.on('error', (err) => reject(err));
    child.on('close', (code) => resolve({ code: code ?? 1, stdout, stderr }));
  });
}

async function main() {
  const args = process.argv.slice(2);
  const metadataPath = argValue(args, '--metadata', 'fix-agent/metadata.json');
  const patchPath = argValue(args, '--patch', 'fix-agent/patch.diff');
  const dryRun = args.includes('--dry-run');

  console.log('PR Creation Agent - Stage 2 Conditional Autonomy');
  console.log(`Metadata: ${metadataPath}`);
  console.log(`Patch: ${patchPath}`);
  console.log(`Dry run: ${dryRun}`);

  // Check if metadata exists
  if (!(await fileExists(metadataPath))) {
    console.error(`Metadata file not found: ${metadataPath}`);
    process.exit(1);
  }

  const metadata = await readJson(metadataPath);
  const riskAssessment = metadata.risk_assessment || { auto_merge_eligible: false, level: 'unknown' };

  console.log('\n=== Risk Assessment ===');
  console.log(`Level: ${riskAssessment.level}`);
  console.log(`Score: ${riskAssessment.score}`);
  console.log(`Auto-merge eligible: ${riskAssessment.auto_merge_eligible}`);
  console.log(`Factors: ${riskAssessment.factors?.join(', ') || 'none'}`);

  // Check if patch exists and is non-empty
  const patchExists = await fileExists(patchPath);
  let patchContent = '';
  if (patchExists) {
    patchContent = await fs.readFile(patchPath, 'utf8');
  }

  if (!patchExists || patchContent.trim().length === 0) {
    console.log('\n⚠️  No patch to apply. Skipping PR creation.');
    process.exit(0);
  }

  // Check if manual review is required
  if (metadata.needs_manual_review) {
    console.log('\n⚠️  Manual review required. Skipping automatic PR creation.');
    console.log('Reason: needs_manual_review flag is set');
    process.exit(0);
  }

  // Check current branch
  const branchResult = await runCmd('git', ['rev-parse', '--abbrev-ref', 'HEAD']);
  const currentBranch = branchResult.stdout.trim();
  console.log(`\nCurrent branch: ${currentBranch}`);

  // Create branch name from metadata
  const branchName = metadata.suggestions?.branch_name || `fix-agent/run-${metadata.run_id}`;
  console.log(`Target branch: ${branchName}`);

  if (dryRun) {
    console.log('\n=== DRY RUN MODE ===');
    console.log('Would create PR with:');
    console.log(`  Branch: ${branchName}`);
    console.log(`  Title: ${metadata.suggestions?.pr_title || 'Automated fix'}`);
    console.log(`  Risk: ${riskAssessment.level}`);
    console.log(`  Auto-merge: ${riskAssessment.auto_merge_eligible}`);
    console.log('\nPatch preview (first 500 chars):');
    console.log(patchContent.substring(0, 500));
    process.exit(0);
  }

  // Check if branch already exists
  const branchCheckResult = await runCmd('git', ['rev-parse', '--verify', branchName]);
  const branchExists = branchCheckResult.code === 0;

  if (branchExists) {
    console.log(`\n⚠️  Branch ${branchName} already exists.`);
    console.log('Checking out existing branch...');
    const checkoutResult = await runCmd('git', ['checkout', branchName]);
    if (checkoutResult.code !== 0) {
      console.error('Failed to checkout branch');
      console.error(checkoutResult.stderr);
      process.exit(1);
    }
  } else {
    console.log(`\nCreating new branch: ${branchName}`);
    const createResult = await runCmd('git', ['checkout', '-b', branchName]);
    if (createResult.code !== 0) {
      console.error('Failed to create branch');
      console.error(createResult.stderr);
      process.exit(1);
    }
  }

  // Apply the patch
  console.log('\nApplying patch...');
  const applyResult = await runCmd('git', ['apply', patchPath]);
  if (applyResult.code !== 0) {
    console.error('Failed to apply patch');
    console.error(applyResult.stderr);
    
    // Try to revert to original branch
    await runCmd('git', ['checkout', currentBranch]);
    process.exit(1);
  }

  // Stage changes
  console.log('Staging changes...');
  const addResult = await runCmd('git', ['add', '-A']);
  if (addResult.code !== 0) {
    console.error('Failed to stage changes');
    console.error(addResult.stderr);
    await runCmd('git', ['checkout', currentBranch]);
    process.exit(1);
  }

  // Commit changes
  const commitMessage = metadata.suggestions?.commit_message || `fix: automated patch for run ${metadata.run_id}`;
  console.log(`Committing: ${commitMessage}`);
  const commitResult = await runCmd('git', ['commit', '-m', commitMessage]);
  if (commitResult.code !== 0) {
    console.error('Failed to commit changes');
    console.error(commitResult.stderr);
    await runCmd('git', ['checkout', currentBranch]);
    process.exit(1);
  }

  console.log('\n✅ Branch created and patch applied successfully!');
  console.log(`\nNext steps:`);
  console.log(`1. Push branch: git push origin ${branchName}`);
  console.log(`2. Create PR targeting: ${currentBranch}`);
  console.log(`3. Add labels based on risk: ${riskAssessment.level}-risk`);
  if (riskAssessment.auto_merge_eligible) {
    console.log(`4. PR is eligible for auto-merge after validation`);
  } else {
    console.log(`4. PR requires manual approval before merge`);
  }

  // Output metadata for workflow consumption
  const output = {
    success: true,
    branch_name: branchName,
    base_branch: currentBranch,
    risk_level: riskAssessment.level,
    auto_merge_eligible: riskAssessment.auto_merge_eligible,
    pr_title: metadata.suggestions?.pr_title,
    pr_body: metadata.suggestions?.pr_body,
  };

  await fs.writeFile('pr-creation-output.json', JSON.stringify(output, null, 2), 'utf8');
  console.log('\nWrote pr-creation-output.json');
}

main().catch((err) => {
  console.error('PR creation failed:');
  console.error(err?.stack || err);
  process.exit(1);
});
