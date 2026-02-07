import { test } from '@playwright/test';
import { PatientsPage } from '../pages/patients-page';

// Patient selection and note creation.
test('switch patient and add note', async ({ page, baseURL }) => {
  const patients = new PatientsPage(page);
  await patients.goto(baseURL!);

  await patients.chooseFirstPatient();
  const noteText = `E2E Notiz ${Date.now()}`;
  await patients.addNote(noteText);
  // Wait for note to appear in timeline
  await patients.expectNoteVisible(noteText);
});
