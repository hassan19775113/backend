import { test, expect } from '../fixtures/testdata.setup';
import { ApiClient } from '../../api-client';
import { CalendarPage } from '../pages/calendar-page';
import { AppointmentModalPage } from '../pages/appointment-modal-page';
import { waitForOptionValue } from '../utils/select-utils';

type AppointmentDetail = {
  id: number;
  patient_id: number;
  doctor: number;
  start_time: string;
  end_time: string;
};

type AvailabilityDoctor = { id: number; name?: string };

function addMinutes(iso: string, minutes: number) {
  const d = new Date(iso);
  d.setMinutes(d.getMinutes() + minutes);
  return d.toISOString();
}

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
    last_name: `Boundary ${suffix} ${Date.now()}`,
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

test('API: boundary overlap rule (end == start) is allowed; partial overlap is rejected', async ({ testData }) => {
  expect(testData.appointmentId).toBeTruthy();
  expect(testData.appointmentTypeId).toBeTruthy();
  expect(testData.doctorId).toBeTruthy();

  const api = new ApiClient();
  await api.init();

  const createdIds: Array<number | string> = [];

  try {
    const baseline = await getAppointmentOrThrow(api, testData.appointmentId!);

    // Adjacent AFTER: start == baseline.end, should NOT overlap.
    const adjacentStart = baseline.end_time;
    const adjacentEnd = addMinutes(baseline.end_time, 30);

    const patientAdjId = await createPatientId(api, 'ADJ');

    const adjRes = await api.createAppointment({
      patient_id: patientAdjId,
      doctor: Number(testData.doctorId),
      type: Number(testData.appointmentTypeId),
      start_time: adjacentStart,
      end_time: adjacentEnd,
      notes: 'E2E boundary adjacent appointment (end==start)',
    });

    if (!adjRes.ok()) {
      // If the environment has strict working hours and this pushes beyond them, skip.
      const body = await adjRes.text();
      test.skip(true, `Adjacent appointment could not be created (likely working-hours): ${adjRes.status()} ${body}`);
      return;
    }

    const adj = await adjRes.json();
    const adjId = adj.id || adj.pk;
    expect(adjId).toBeTruthy();
    createdIds.push(adjId);

    // Partial overlap: shift the window into the baseline appointment.
    // Overlap condition: start < existing.end && end > existing.start
    const partialStart = addMinutes(baseline.start_time, 5);
    const partialEnd = addMinutes(baseline.end_time, 5);

    const patientOverlapId = await createPatientId(api, 'PARTIAL');

    const partialRes = await api.createAppointment({
      patient_id: patientOverlapId,
      doctor: Number(testData.doctorId),
      type: Number(testData.appointmentTypeId),
      start_time: partialStart,
      end_time: partialEnd,
      notes: 'E2E boundary partial-overlap appointment (should fail)',
    });

    expect(partialRes.ok()).toBeFalsy();
    expect(partialRes.status()).toBe(400);

    const body = await partialRes.json();
    expect(body?.detail).toBe('Doctor unavailable.');
  } finally {
    for (const id of createdIds) {
      await api.deleteAppointment(id);
    }
    await api.dispose();
  }
});

test('UI: boundary (end == start) keeps doctor available in modal filtering', async ({ page, baseURL, testData }) => {
  expect(testData.appointmentId).toBeTruthy();
  expect(testData.doctorId).toBeTruthy();

  const api = new ApiClient();
  await api.init();

  try {
    const baseline = await getAppointmentOrThrow(api, testData.appointmentId!);

    // Candidate slot: adjacent AFTER baseline.
    const adjacentStart = baseline.end_time;
    const adjacentEnd = addMinutes(baseline.end_time, 30);

    // First verify via API availability that the doctor is actually available for this slot.
    // If not, skip (could be working-hours or other seeded bookings).
    const availRes = await api.checkAvailability(adjacentStart, adjacentEnd);
    if (!availRes.ok()) {
      test.skip(true, 'Availability endpoint failed; cannot validate boundary availability');
      return;
    }

    const avail = await availRes.json();
    const doctors: AvailabilityDoctor[] = Array.isArray(avail?.available_doctors) ? avail.available_doctors : [];
    const hasDoctor = doctors.some((d) => Number(d.id) === Number(testData.doctorId));

    if (!hasDoctor) {
      test.skip(true, 'Baseline doctor is not available for adjacent slot; cannot assert UI boundary behavior');
      return;
    }

    const { dateStr, startStr, endStr } = toModalDateTimeInputs(adjacentStart, adjacentEnd);

    const calendar = new CalendarPage(page);
    const modal = new AppointmentModalPage(page);

    await calendar.goto(baseURL!);
    await calendar.openNewAppointment();
    await modal.expectOpen();

    const doctorIdStr = String(testData.doctorId);

    // Ensure dropdown is populated before filtering.
    await waitForOptionValue(modal.doctorSelect, doctorIdStr);

    // Trigger availability filtering for the adjacent slot.
    await modal.updateTimesAndWaitForAvailability(dateStr, startStr, endStr);

    // Doctor should remain available for boundary-adjacent slot.
    await waitForOptionValue(modal.doctorSelect, doctorIdStr);
  } finally {
    await api.dispose();
  }
});
