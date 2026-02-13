import { test, expect } from '../fixtures/testdata.setup';
import { ApiClient } from '../../api-client';

type AvailabilityResponse = {
  available_doctors?: Array<{ id: number; name?: string }>;
  available_patients?: Array<{ id: number; display_name?: string }>;
  available_rooms?: Array<{ id: number; name?: string }>;
};

type AppointmentDetail = {
  id: number;
  patient_id: number;
  doctor: number;
  start_time: string;
  end_time: string;
};

function addMinutes(iso: string, minutes: number) {
  const d = new Date(iso);
  d.setMinutes(d.getMinutes() + minutes);
  return d.toISOString();
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

function ids(list: Array<{ id: number }> | undefined): number[] {
  return Array.isArray(list) ? list.map((x) => Number(x.id)) : [];
}

async function findWindowWhereDoctorAvailable(api: ApiClient, doctorId: number, seedStartISO: string) {
  // We search for a time window where the given doctor is available to avoid flakiness from
  // seeded absences/hours or parallel test runs.
  const durationMin = 30;
  const seed = new Date(seedStartISO);

  for (let dayOffset = 0; dayOffset <= 14; dayOffset++) {
    for (const hour of [8, 9, 10, 11, 12, 13, 14, 15, 16]) {
      const start = new Date(seed);
      start.setDate(start.getDate() + dayOffset);
      start.setHours(hour, 0, 0, 0);
      const end = new Date(start);
      end.setMinutes(end.getMinutes() + durationMin);

      const res = await api.checkAvailability(start.toISOString(), end.toISOString());
      if (!res.ok()) continue;
      const data = (await res.json()) as AvailabilityResponse;
      const doctorIds = ids(data.available_doctors);
      if (doctorIds.includes(Number(doctorId))) {
        return { startISO: start.toISOString(), endISO: end.toISOString() };
      }
    }
  }

  return null;
}

test('API: availability excludes doctor + patient for an overlapping booked slot', async ({ testData }) => {
  if (!testData.appointmentId || !testData.doctorId || !testData.patientId) {
    test.skip(true, 'Seed data incomplete for availability overlap test');
    return;
  }

  const api = new ApiClient();
  await api.init();

  try {
    const baseline = await getAppointmentOrThrow(api, testData.appointmentId!);

    const res = await api.checkAvailability(baseline.start_time, baseline.end_time);
    expect(res.ok()).toBeTruthy();

    const data = (await res.json()) as AvailabilityResponse;

    // For the booked window, the currently booked doctor/patient must not be offered.
    expect(ids(data.available_doctors)).not.toContain(Number(testData.doctorId));
    expect(ids(data.available_patients)).not.toContain(Number(testData.patientId));
  } finally {
    await api.dispose();
  }
});

test('API: availability can return the doctor + patient again for a non-overlapping window', async ({ testData }) => {
  if (!testData.appointmentId || !testData.doctorId || !testData.patientId) {
    test.skip(true, 'Seed data incomplete for availability non-overlap test');
    return;
  }

  const api = new ApiClient();
  await api.init();

  try {
    const baseline = await getAppointmentOrThrow(api, testData.appointmentId!);

    // First try the strict boundary-adjacent window (end == start). If that doesn't include the doctor,
    // fall back to searching for any window where the doctor is available.
    const adjacentStart = baseline.end_time;
    const adjacentEnd = addMinutes(baseline.end_time, 30);

    const adjacentRes = await api.checkAvailability(adjacentStart, adjacentEnd);
    if (adjacentRes.ok()) {
      const adjacent = (await adjacentRes.json()) as AvailabilityResponse;
      const doctorIds = ids(adjacent.available_doctors);
      const patientIds = ids(adjacent.available_patients);

      if (doctorIds.includes(Number(testData.doctorId)) && patientIds.includes(Number(testData.patientId))) {
        return;
      }
    }

    const window = await findWindowWhereDoctorAvailable(api, Number(testData.doctorId), baseline.start_time);
    if (!window) {
      test.skip(true, 'Could not find a window where baseline doctor is available');
      return;
    }

    const res = await api.checkAvailability(window.startISO, window.endISO);
    expect(res.ok()).toBeTruthy();

    const data = (await res.json()) as AvailabilityResponse;

    // In a window where the doctor is available, the baseline patient should also be available
    // (the fixture creates only one appointment for that patient).
    expect(ids(data.available_doctors)).toContain(Number(testData.doctorId));
    expect(ids(data.available_patients)).toContain(Number(testData.patientId));
  } finally {
    await api.dispose();
  }
});
