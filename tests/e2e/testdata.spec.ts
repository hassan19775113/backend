import { test, expect } from '../fixtures/testdata.setup';
import { ApiClient } from '../../api-client';

// Validates helper flows for creating and deleting resources
test('create doctor/patient/appointment via helpers', async ({ testData }) => {
  expect(testData.doctorId).toBeTruthy();
  expect(testData.patientId).toBeTruthy();
  expect(testData.appointmentId).toBeTruthy();
});

test('delete appointment works', async ({ testData }) => {
  const api = new ApiClient();
  await api.init();
  try {
    expect(testData.appointmentId).toBeTruthy();
    if (testData.appointmentId) {
      const delRes = await api.deleteAppointment(testData.appointmentId);
      expect(delRes.ok()).toBeTruthy();
    }
  } finally {
    await api.dispose();
  }
});
