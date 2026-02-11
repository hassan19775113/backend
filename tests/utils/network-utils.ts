import { Page, Response } from '@playwright/test';

export async function waitForResponseAfter<T>(
  page: Page,
  action: () => Promise<T> | T,
  predicate: (response: Response) => boolean,
  timeout = 10_000
): Promise<{ actionResult: T; response: Response }> {
  const wait = page.waitForResponse(predicate, { timeout });
  const actionResult = await action();
  const response = await wait;
  return { actionResult, response };
}
