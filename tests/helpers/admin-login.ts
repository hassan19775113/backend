import { Page, expect } from '@playwright/test';

/**
 * Safe Django Admin login helper.
 *
 * Detection rule (critical): only treat the page as the login form when BOTH
 * #id_username and #id_password exist. Many admin create/change forms include
 * #id_username but do NOT include #id_password.
 */
export async function adminLoginIfNeeded(page: Page, username?: string, password?: string): Promise<void> {
  const hasUsername = (await page.locator('#id_username').count()) > 0;
  if (!hasUsername) return;

  const hasPassword = (await page.locator('#id_password').count()) > 0;
  if (!hasPassword) return;

  if (!username || !password) {
    throw new Error(
      'Admin login required but credentials missing: set E2E_USER and E2E_PASSWORD in the environment.'
    );
  }

  const userInput = page.locator('#id_username');
  const passInput = page.locator('#id_password');

  await expect(userInput).toBeVisible();
  await expect(passInput).toBeVisible();

  await userInput.fill(username);
  await passInput.fill(password);

  const submit = page.locator('input[type="submit"], button[type="submit"]').first();
  await expect(submit).toBeVisible();

  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
    submit.click(),
  ]);
}
