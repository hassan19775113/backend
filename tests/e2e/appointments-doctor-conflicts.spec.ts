import { test, expect } from '../fixtures/testdata.setup';
import { ApiClient } from '../../api-client';
import { CalendarPage } from '../pages/calendar-page';
import { AppointmentModalPage } from '../pages/appointment-modal-page';
import { waitForOptionValue, waitForOptionValueMissing } from '../utils/select-utils';

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
    last_name: `DoctorConflict ${suffix} ${Date.now()}`,
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

test('UI: booked doctor is filtered out for an overlapping slot', async ({ page, baseURL, testData }) => {
  // Baseline appointment created deterministically by testdata.setup.ts
  if (!testData.appointmentId || !testData.doctorId || !testData.patientId) {
    test.skip(true, 'Seed data incomplete for doctor conflict UI test');
    return;
  }

  const api = new ApiClient();
  await api.init();

  try {
    // Create an additional patient BEFORE opening the modal.
    // The modal loads patients once; creating first avoids dropdown race/flakiness.
    const freePatientId = await createPatientId(api, 'FREE');

    const baseline = await getAppointmentOrThrow(api, testData.appointmentId!);
    const { dateStr, startStr, endStr } = toModalDateTimeInputs(baseline.start_time, baseline.end_time);

    const calendar = new CalendarPage(page);
    const modal = new AppointmentModalPage(page);

    await calendar.goto(baseURL!);
    await calendar.openNewAppointment();
    await modal.expectOpen();

    const bookedDoctorId = String(baseline.doctor);
    const bookedPatientId = String(baseline.patient_id);

    // Ensure the dropdowns are populated (unfiltered state).
    await waitForOptionValue(modal.doctorSelect, bookedDoctorId);
    await waitForOptionValue(modal.patientSelect, bookedPatientId);
    await waitForOptionValue(modal.patientSelect, String(freePatientId));

    // Trigger availability filtering for the time window that is already booked.
    const availabilityResponse = await modal.updateTimesAndWaitForAvailability(dateStr, startStr, endStr);
    if (!availabilityResponse.ok()) {
      const body = await availabilityResponse.text();
      throw new Error(
        `UI availability check failed: ${availabilityResponse.status()} ${availabilityResponse.statusText()} - ${body}`
      );
    }

    // The doctor with an existing appointment must be absent from the available list.
    await waitForOptionValueMissing(modal.doctorSelect, bookedDoctorId);
  } finally {
    await api.dispose();
  }
});

test('API: rejects overlapping appointment for the same doctor', async ({ testData }) => {
  if (!testData.appointmentId || !testData.appointmentTypeId || !testData.doctorId) {
    test.skip(true, 'Seed data incomplete for doctor conflict API test');
    return;
  }

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

    // From appointments.validators.raise_doctor_unavailable()
    const body = await res.json();
    const detail = body?.detail;
    const detailText = Array.isArray(detail) ? String(detail[0] ?? '') : String(detail ?? '');
    expect(detailText).toBe('Doctor unavailable.');
    expect(Array.isArray(body?.alternatives)).toBeTruthy();
  } finally {
    await api.dispose();
  }
});
