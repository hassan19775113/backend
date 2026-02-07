import base, { expect } from '@playwright/test';
import { ApiClient } from '../../api-client';

// Extended test fixture that provisions test data (doctor, patient, appointment) before each test
// and cleans up created appointments after each test. Doctor/Patient deletion endpoints are not
// defined here; adjust if available.

type TestData = {
  doctorId?: number | string;
  patientId?: number | string;
  appointmentId?: number | string;
  appointmentTypeId?: number | string;
};

export const test = base.extend<{ testData: TestData }>({
  testData: async ({}, use) => {
    const api = new ApiClient();
    await api.init();

    const data: TestData = {};

    try {
      // Ensure we have a doctor
      const doctorRes = await api.createDoctor();
      if (doctorRes.ok()) {
        const doctor = await doctorRes.json();
        data.doctorId = doctor.id || doctor.pk;
      } else {
        throw new Error(`createDoctor failed: ${doctorRes.status()}`);
      }

      // Ensure we have a patient
      const patientRes = await api.createPatient();
      if (patientRes.ok()) {
        const patient = await patientRes.json();
        data.patientId = patient.id || patient.pk;
      } else {
        throw new Error(`createPatient failed: ${patientRes.status()}`);
      }

      // Get an appointment type to use
      const typeRes = await api.getAppointmentTypes();
      if (typeRes.ok()) {
        const types = await typeRes.json();
        const firstType = Array.isArray(types) ? types[0] : types.results?.[0];
        if (!firstType) throw new Error('No appointment types available');
        data.appointmentTypeId = firstType.id;
      } else {
        throw new Error(`getAppointmentTypes failed: ${typeRes.status()}`);
      }

      // Create appointment
      const start = new Date();
      const end = new Date(start.getTime() + 30 * 60 * 1000);
      const apptPayload = {
        patient_id: data.patientId,
        doctor: data.doctorId,
        type: data.appointmentTypeId,
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        notes: 'E2E seed appointment',
      };
      const apptRes = await api.createAppointment(apptPayload);
      if (apptRes.ok()) {
        const appt = await apptRes.json();
        data.appointmentId = appt.id || appt.pk;
      } else {
        throw new Error(`createAppointment failed: ${apptRes.status()}`);
      }

      await use(data);
    } finally {
      // Cleanup appointment if created
      if (data.appointmentId) {
        await api.deleteAppointment(data.appointmentId);
      }
      await api.dispose();
    }
  },
});

export { expect };