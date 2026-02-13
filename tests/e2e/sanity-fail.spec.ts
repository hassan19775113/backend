import { test, expect } from '@playwright/test';

// This spec exists to validate the failure-handling pipeline.
// It is disabled by default so normal CI runs stay green.

const isCI = process.env.CI === 'true' || process.env.GITHUB_ACTIONS === 'true';

if (!isCI && process.env.SANITY_FORCE_FAIL === '1') {
	test('SANITY: force failure', async () => {
		expect(1).toBe(2);
	});
}