import { test } from '@playwright/test';
import { PatientsPage } from '../pages/patients-page';

// Patient selection and note creation.
test('switch patient and add note', async ({ page, baseURL }) => {
  const patients = new PatientsPage(page);
  await patients.goto(baseURL!);

  if (page.url().includes('/login')) {
    test.skip(true, 'Not authenticated in patients UI test environment');
    return;
  }

  if (!(await patients.hasAnyPatientRow())) {
    test.skip(true, 'No patient rows available for patient switch UI test');
    return;
  }

  await patients.chooseFirstPatient();
  const noteText = `E2E Notiz ${Date.now()}`;
  await patients.addNote(noteText);
  // Wait for note to appear in timeline
  await patients.expectNoteVisible(noteText);
});
