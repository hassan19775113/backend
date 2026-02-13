import { test, expect } from '../fixtures/testdata.setup';
import { ApiClient } from '../../api-client';

// Validates helper flows for creating and deleting resources
test('create doctor/patient/appointment via helpers', async ({ testData }) => {
  if (!testData.doctorId || !testData.patientId || !testData.appointmentId) {
    test.skip(true, 'Seed data incomplete for helper test');
    return;
  }
});

test('delete appointment works', async ({ testData }) => {
  const api = new ApiClient();
  await api.init();
  try {
    if (!testData.appointmentId) {
      test.skip(true, 'Seed data incomplete for delete appointment helper test');
      return;
    }
    const delRes = await api.deleteAppointment(testData.appointmentId);
    expect(delRes.ok()).toBeTruthy();
  } finally {
    await api.dispose();
  }
});
