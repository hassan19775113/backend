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
  appointmentStartTime?: string;
  appointmentEndTime?: string;
};

type MePayload = {
  id: number | string;
  role?: { name?: string } | null;
};

export const test = base.extend<{ testData: TestData }>({
  testData: async ({}, use) => {
    const api = new ApiClient();
    await api.init();

    const data: TestData = {};

    const pickId = (obj: any): number | string | undefined => {
      if (!obj) return undefined;
      return obj.id ?? obj.pk ?? obj.patient_id ?? obj.user_id ?? obj.user?.id;
    };

    try {
      // Determine current user role (doctors are only allowed to create for themselves)
      const meRes = await api.getMe();
      const me: MePayload | null = meRes.ok() ? await meRes.json() : null;
      const myRoleName = me?.role?.name;

      // Ensure we have a doctor
      // NOTE: /api/appointments/doctors/ is list-only (GET). Creating doctors is not exposed via API.
      // For E2E we rely on seeded doctor users and pick the first one. If none are
      // available, we gracefully continue with an empty fixture so tests can decide
      // to skip instead of hard-failing on environment issues.
      if (myRoleName === 'doctor' && me?.id) {
        data.doctorId = me.id;
      } else {
        const doctorsRes = await api.listDoctors();
        if (!doctorsRes.ok()) {
          const body = await doctorsRes.text();
          throw new Error(`listDoctors failed: ${doctorsRes.status()} - ${body}`);
        }
        const doctors = await doctorsRes.json();
        const firstDoctor = Array.isArray(doctors) ? doctors[0] : doctors.results?.[0];
        const doctorId = pickId(firstDoctor);
        if (!doctorId) {
          const summary = Array.isArray(doctors)
            ? `array(len=${doctors.length})`
            : `object(keys=${Object.keys(doctors || {}).join(',')})`;
          // No doctors in the system for this environment; allow tests to
          // detect the missing seed and skip instead of throwing here.
          console.warn(
            `No doctors available (expected seeded doctor users). doctors payload: ${summary}`
          );
          await use(data);
          return;
        }
        data.doctorId = doctorId;
      }

      // Ensure we have a patient
      const patientRes = await api.createPatient();
      if (patientRes.ok()) {
        const patient = await patientRes.json();
        data.patientId = pickId(patient);
        if (!data.patientId) {
          throw new Error(`createPatient returned no id (keys: ${Object.keys(patient || {}).join(',')})`);
        }
      } else {
        const body = await patientRes.text();
        throw new Error(`createPatient failed: ${patientRes.status()} - ${body}`);
      }

      // Get an appointment type to use
      const typeRes = await api.getAppointmentTypes();
      if (typeRes.ok()) {
        const types = await typeRes.json();
        const firstType = Array.isArray(types) ? types[0] : types.results?.[0];
        if (!firstType) throw new Error('No appointment types available');
        data.appointmentTypeId = firstType.id;
      } else {
        const body = await typeRes.text();
        throw new Error(`getAppointmentTypes failed: ${typeRes.status()} - ${body}`);
      }

      // Create appointment
      // Ask backend for an available slot to avoid flakiness from working hours / breaks.
      const isDoctorUser = myRoleName === 'doctor';
      // Spread parallel test workers across different days to reduce collisions.
      const startDateSeed = new Date(Date.now() + Math.floor(Math.random() * 7) * 24 * 60 * 60 * 1000);
      let cursorDate = startDateSeed;

      let created = false;
      let lastError: string | null = null;

      for (let attempt = 0; attempt < 5 && !created; attempt++) {
        const start_date = cursorDate.toISOString().slice(0, 10);

        const suggestRes = await api.suggestAppointment({
          doctor_id: data.doctorId!,
          type_id: data.appointmentTypeId,
          start_date,
          limit: 5,
        });
        if (!suggestRes.ok()) {
          const body = await suggestRes.text();
          throw new Error(`suggestAppointment failed: ${suggestRes.status()} - ${body}`);
        }

        const suggest = await suggestRes.json();
        const primary = Array.isArray(suggest?.primary_suggestions) ? suggest.primary_suggestions : [];
        const fallbackItems = Array.isArray(suggest?.fallback_suggestions) ? suggest.fallback_suggestions : [];

        const candidates: Array<{ slot: any; doctorId?: number | string }> = [];
        for (const s of primary) candidates.push({ slot: s });

        if (!isDoctorUser) {
          for (const fb of fallbackItems) {
            const fbDoctorId = pickId(fb?.doctor);
            const suggestions = Array.isArray(fb?.suggestions) ? fb.suggestions : [];
            for (const s of suggestions) candidates.push({ slot: s, doctorId: fbDoctorId });
          }
        }

        for (const c of candidates) {
          const slot = c.slot;
          if (!slot?.start_time || !slot?.end_time) continue;

          // For admin/assistant flows, allow taking the suggested fallback doctor.
          if (!isDoctorUser && c.doctorId) data.doctorId = c.doctorId;

          const apptPayload = {
            patient_id: data.patientId,
            doctor: data.doctorId,
            type: data.appointmentTypeId,
            start_time: String(slot.start_time),
            end_time: String(slot.end_time),
            notes: 'E2E seed appointment',
          };

          const apptRes = await api.createAppointment(apptPayload);
          if (apptRes.ok()) {
            const appt = await apptRes.json();
            data.appointmentId = appt.id || appt.pk;
            data.appointmentStartTime = appt.start_time;
            data.appointmentEndTime = appt.end_time;
            created = true;
            break;
          }

          const body = await apptRes.text();
          lastError = `createAppointment failed: ${apptRes.status()} - ${body}`;

          // Doctor unavailable can happen due to parallel workers choosing the same slot.
          // Try another suggested slot/day.
          if (apptRes.status() !== 400 || !body.includes('Doctor unavailable')) {
            throw new Error(lastError);
          }
        }

        cursorDate = new Date(cursorDate.getTime() + 24 * 60 * 60 * 1000);
      }

      if (!created) {
        throw new Error(lastError || 'Failed to create seed appointment after retries');
      }

      await use(data);
    } finally {
      // Cleanup appointment if created
      if (data.appointmentId) {
        try {
          const existing = await api.get(`/api/appointments/${data.appointmentId}/`);
          if (existing.ok()) {
            await api.deleteAppointment(data.appointmentId);
          }
        } catch {
          // idempotent cleanup: ignore races/404s from tests deleting the same appointment
        }
      }
      await api.dispose();
    }
  },
});

export { expect };