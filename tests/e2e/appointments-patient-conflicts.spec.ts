import { test, expect } from '../fixtures/testdata.setup';
import { ApiClient } from '../../api-client';
import { CalendarPage } from '../pages/calendar-page';
import { AppointmentModalPage } from '../pages/appointment-modal-page';
import { waitForOptionValue, waitForOptionValueMissing } from '../utils/select-utils';
import { toModalDateTimeInputsInBrowser } from '../utils/modal-datetime';

type AvailabilityDoctor = { id: number; name?: string };

type AppointmentDetail = {
  id: number;
  patient_id: number;
  doctor: number;
  start_time: string;
  end_time: string;
};

async function createPatientId(api: ApiClient, suffix: string): Promise<number> {
  const res = await api.createPatient({
    first_name: 'E2E',
    last_name: `PatientConflict ${suffix} ${Date.now()}`,
  });
  if (!res.ok()) throw new Error(`createPatient failed: ${res.status()}`);
  const p = await res.json();
  const id = p.id || p.pk;
  if (!id) throw new Error('createPatient: missing id');
  return Number(id);
}

async function getAppointmentOrThrow(api: ApiClient, id: number | string): Promise<AppointmentDetail> {
  const res = await api.get(`/api/appointments/${id}/`);
  if (!res.ok()) {
    const body = await res.text();
    throw new Error(`GET /api/appointments/${id}/ failed: ${res.status()} - ${body}`);
  }
  const appt = (await res.json()) as AppointmentDetail;
  if (!appt?.start_time || !appt?.end_time) throw new Error('Appointment detail missing times');
  return appt;
}

test('UI: booked patient is filtered out for an overlapping slot', async ({ page, baseURL, testData }) => {
  // Baseline appointment created deterministically by testdata.setup.ts
  if (!testData.appointmentId || !testData.patientId) {
    test.skip(true, 'Seed data incomplete for patient conflict UI test');
    return;
  }

  const api = new ApiClient();
  await api.init();

  try {
    // Create a second patient BEFORE opening the modal so it appears in the initial dropdown.
    const freePatientId = await createPatientId(api, 'FREE');

    const baseline = await getAppointmentOrThrow(api, testData.appointmentId!);
    const { dateStr, startStr, endStr } = await toModalDateTimeInputsInBrowser(
      page,
      baseline.start_time,
      baseline.end_time
    );

    const calendar = new CalendarPage(page);
    const modal = new AppointmentModalPage(page);

    await calendar.goto(baseURL!);
    await calendar.openNewAppointment();
    await modal.expectOpen();

    const bookedPatientId = String(baseline.patient_id);
    const freePatientIdStr = String(freePatientId);

    // Ensure dropdowns are populated (unfiltered).
    await waitForOptionValue(modal.patientSelect, bookedPatientId);
    await waitForOptionValue(modal.patientSelect, freePatientIdStr);

    // Trigger availability filtering.
    const availabilityResponse = await modal.updateTimesAndWaitForAvailability(dateStr, startStr, endStr);
    if (!availabilityResponse.ok()) {
      const body = await availabilityResponse.text();
      throw new Error(
        `UI availability check failed: ${availabilityResponse.status()} ${availabilityResponse.statusText()} - ${body}`
      );
    }

    // Patient with an existing appointment in this window must be absent.
    await waitForOptionValueMissing(modal.patientSelect, bookedPatientId);

    // A different patient should still be available.
    await waitForOptionValue(modal.patientSelect, freePatientIdStr);
  } finally {
    await api.dispose();
  }
});

test('API: rejects overlapping appointment for the same patient (different doctor)', async ({ testData }) => {
  if (!testData.appointmentId || !testData.appointmentTypeId || !testData.patientId || !testData.doctorId) {
    test.skip(true, 'Seed data incomplete for patient conflict API test');
    return;
  }

  const api = new ApiClient();
  await api.init();

  try {
    const baseline = await getAppointmentOrThrow(api, testData.appointmentId!);

    // We need a *different* doctor who is available for this window; otherwise we'd fail with
    // "Doctor unavailable" before we can assert the patient overlap validation.
    const availRes = await api.checkAvailability(baseline.start_time, baseline.end_time);
    if (!availRes.ok()) {
      test.skip(true, 'Availability endpoint failed; cannot select alternate doctor');
      return;
    }

    const avail = await availRes.json();
    const doctors: AvailabilityDoctor[] = Array.isArray(avail?.available_doctors) ? avail.available_doctors : [];
    const otherDoctorId = doctors.find((d) => d?.id && Number(d.id) !== Number(testData.doctorId))?.id;

    if (!otherDoctorId) {
      test.skip(true, 'No second available doctor to test patient overlap');
      return;
    }

    const overlappingPayload = {
      patient_id: Number(testData.patientId),
      doctor: Number(otherDoctorId),
      type: Number(testData.appointmentTypeId),
      start_time: baseline.start_time,
      end_time: baseline.end_time,
      notes: 'E2E overlapping (patient) appointment',
    };

    const res = await api.createAppointment(overlappingPayload);
    expect(res.ok()).toBeFalsy();
    expect(res.status()).toBe(400);

    // From appointments.validators.validate_no_patient_appointment_overlap()
    const body = await res.json();
    expect(String(body?.detail || '')).toContain('patient already has an appointment');
  } finally {
    await api.dispose();
  }
});
