import { expect, Locator } from '@playwright/test';

export async function getSelectOptionValues(select: Locator): Promise<string[]> {
  return select.evaluate((el: HTMLSelectElement) =>
    Array.from(el.querySelectorAll('option')).map((o) => (o.getAttribute('value') || '').trim())
  );
}

export async function getFirstNonEmptyOptionLabel(select: Locator): Promise<string | null> {
  return select.evaluate((el: HTMLSelectElement) => {
    const opts = Array.from(el.querySelectorAll('option'));
    const first = opts.find((o) => (o.value || '').trim().length > 0);
    return first?.textContent?.trim() || null;
  });
}

export async function waitForFirstNonEmptyOptionLabel(
  select: Locator,
  options?: { timeout?: number; message?: string }
): Promise<string> {
  const timeout = options?.timeout ?? 10_000;
  const message = options?.message ?? 'Waiting for select options to load';

  await expect
    .poll(() => getFirstNonEmptyOptionLabel(select), {
      timeout,
      message,
    })
    .not.toBeNull();

  return String(await getFirstNonEmptyOptionLabel(select));
}

export async function waitForOptionValue(select: Locator, value: string, timeout = 10_000) {
  await expect
    .poll(async () => {
      const values = await getSelectOptionValues(select);
      return values.includes(value);
    }, { timeout })
    .toBeTruthy();
}

export async function waitForOptionValueMissing(select: Locator, value: string, timeout = 10_000) {
  await expect
    .poll(async () => {
      const values = await getSelectOptionValues(select);
      return values.includes(value);
    }, { timeout })
    .toBeFalsy();
}
