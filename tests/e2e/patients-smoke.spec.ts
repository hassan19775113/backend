import { test, expect } from '../fixtures/testdata.setup';
import { PatientsPage } from '../pages/patients-page';

test('patients list loads and shows at least one patient', async ({ page, baseURL, testData }) => {
  await expect(testData.patientId, 'testData fixture should create a patient').toBeTruthy();

  const patients = new PatientsPage(page);

  await page.goto(`${baseURL}/praxi_backend/patients/`);
  await page.waitForLoadState('domcontentloaded');

  if (page.url().includes('/admin/login')) {
    throw new Error('Patients page redirected to login; authentication/session missing');
  }

  // /praxi_backend/patients/ may redirect to /praxi_backend/dashboard/patients/
  await page.waitForURL(/\/praxi_backend\/(dashboard\/patients|patients)\/?/);

  await expect(patients.patientsTable).toBeVisible();

  await expect
    .poll(async () => await patients.patientRows.count(), {
      timeout: 10_000,
      message: 'Patients table should contain at least one patient row',
    })
    .toBeGreaterThan(0);
});
