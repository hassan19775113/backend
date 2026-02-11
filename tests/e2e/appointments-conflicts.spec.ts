import { test, expect } from '../fixtures/testdata.setup';
import { ApiClient } from '../../api-client';
import { CalendarPage } from '../pages/calendar-page';
import { AppointmentModalPage } from '../pages/appointment-modal-page';
import { waitForOptionValue, waitForOptionValueMissing } from '../utils/select-utils';

type AvailabilityDoctor = { id: number; name?: string };

type AppointmentDetail = {
  id: number;
  patient_id: number;
  doctor: number;
  start_time: string;
  end_time: string;
};

function pad2(n: number) {
  return String(n).padStart(2, '0');
}

/**
 * Convert an appointment ISO datetime into the calendar modal's expected local inputs.
 * The modal builds a *local* Date from YYYY-MM-DD + HH:MM and then calls toISOString() for /api/availability/.
 */
function toModalDateTimeInputs(isoStart: string, isoEnd: string) {
  const start = new Date(isoStart);
  const end = new Date(isoEnd);

  const dateStr = `${start.getFullYear()}-${pad2(start.getMonth() + 1)}-${pad2(start.getDate())}`;
  const startStr = `${pad2(start.getHours())}:${pad2(start.getMinutes())}`;
  const endStr = `${pad2(end.getHours())}:${pad2(end.getMinutes())}`;

  return { dateStr, startStr, endStr };
}

async function createPatientId(api: ApiClient, suffix: string): Promise<number> {
  const res = await api.createPatient({
    first_name: 'E2E',
    last_name: `Conflicts ${suffix} ${Date.now()}`,
  });
  if (!res.ok()) {
    throw new Error(`createPatient failed: ${res.status()}`);
  }
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
  if (!appt?.start_time || !appt?.end_time || !appt?.doctor || !appt?.patient_id) {
    throw new Error('Appointment detail missing required fields');
  }
  return appt;
}

test('UI: calendar modal filters out booked doctor + patient for overlapping time', async ({
  page,
  baseURL,
  testData,
}) => {
  // Deterministic baseline: provided by testdata.setup.ts
  // - seeded doctor
  // - freshly created patient
  // - freshly created appointment (will be cleaned up by fixture)
  expect(testData.appointmentId).toBeTruthy();
  expect(testData.doctorId).toBeTruthy();
  expect(testData.patientId).toBeTruthy();

  const api = new ApiClient();
  await api.init();
  try {
    // Create another patient BEFORE opening the calendar page.
    // The modal loads all patients on init; creating first avoids flaky "missing in dropdown".
    const freePatientId = await createPatientId(api, 'FREE');

    const baseline = await getAppointmentOrThrow(api, testData.appointmentId!);
    const { dateStr, startStr, endStr } = toModalDateTimeInputs(
      baseline.start_time,
      baseline.end_time
    );

    const calendar = new CalendarPage(page);
    const modal = new AppointmentModalPage(page);

    await calendar.goto(baseURL!);
    await calendar.openNewAppointment();
    await modal.expectOpen();

    const bookedDoctorId = String(testData.doctorId);
    const bookedPatientId = String(testData.patientId);
    const freePatientIdStr = String(freePatientId);

    // Wait until dropdown data is loaded (unfiltered state).
    // We expect the booked doctor and both patients to be present BEFORE availability filtering.
    await waitForOptionValue(modal.doctorSelect, bookedDoctorId);
    await waitForOptionValue(modal.patientSelect, bookedPatientId);
    await waitForOptionValue(modal.patientSelect, freePatientIdStr);

    // Trigger availability filtering for the exact booked time range.
    // The modal will call /api/availability/ and replace doctor/patient dropdown contents.
    await modal.updateTimesAndWaitForAvailability(dateStr, startStr, endStr);

    // Assert the booked doctor is filtered out.
    await waitForOptionValueMissing(modal.doctorSelect, bookedDoctorId);

    // Assert the booked patient is filtered out, but the free patient remains selectable.
    await waitForOptionValueMissing(modal.patientSelect, bookedPatientId);
    await waitForOptionValue(modal.patientSelect, freePatientIdStr);
  } finally {
    await api.dispose();
  }
});

test('API: rejects overlapping appointment for the same doctor', async ({ testData }) => {
  expect(testData.appointmentId).toBeTruthy();
  expect(testData.appointmentTypeId).toBeTruthy();
  expect(testData.doctorId).toBeTruthy();

  const api = new ApiClient();
  await api.init();
  try {
    const baseline = await getAppointmentOrThrow(api, testData.appointmentId!);
    const otherPatientId = await createPatientId(api, 'OTHER');

    const overlappingPayload = {
      patient_id: otherPatientId,
      doctor: Number(testData.doctorId),
      type: Number(testData.appointmentTypeId),
      start_time: baseline.start_time,
      end_time: baseline.end_time,
      notes: 'E2E overlapping (doctor) appointment',
    };

    const res = await api.createAppointment(overlappingPayload);
    expect(res.ok()).toBeFalsy();
    expect(res.status()).toBe(400);

    const body = await res.json();
    // From appointments.validators.raise_doctor_unavailable()
    expect(body?.detail).toBe('Doctor unavailable.');
    expect(Array.isArray(body?.alternatives)).toBeTruthy();
  } finally {
    await api.dispose();
  }
});

test('API: rejects overlapping appointment for the same patient (different doctor)', async ({ testData }) => {
  expect(testData.appointmentId).toBeTruthy();
  expect(testData.appointmentTypeId).toBeTruthy();
  expect(testData.patientId).toBeTruthy();
  expect(testData.doctorId).toBeTruthy();

  const api = new ApiClient();
  await api.init();
  try {
    const baseline = await getAppointmentOrThrow(api, testData.appointmentId!);

    // Pick an alternative doctor that is available for the same time window.
    // If there is only one doctor in the system, this test should skip gracefully.
    const availRes = await api.checkAvailability(baseline.start_time, baseline.end_time);
    if (!availRes.ok()) {
      test.skip(true, 'Availability endpoint failed; cannot select alternate doctor');
      return;
    }

    const avail = await availRes.json();
    const doctors: AvailabilityDoctor[] = Array.isArray(avail?.available_doctors)
      ? avail.available_doctors
      : [];
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

    const body = await res.json();
    // From appointments.validators.validate_no_patient_appointment_overlap()
    expect(String(body?.detail || '')).toContain('patient already has an appointment');
  } finally {
    await api.dispose();
  }
});
