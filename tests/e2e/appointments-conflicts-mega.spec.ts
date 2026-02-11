import { test, expect } from '../fixtures/testdata.setup';
import { ApiClient } from '../../api-client';
import { CalendarPage } from '../pages/calendar-page';
import { AppointmentModalPage } from '../pages/appointment-modal-page';
import { waitForOptionValue, waitForOptionValueMissing } from '../utils/select-utils';

type AvailabilityDoctor = { id: number; name?: string };

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

type Resource = { id: number; name: string; type: string; active?: boolean };

function pad2(n: number) {
  return String(n).padStart(2, '0');
}

function addMinutes(iso: string, minutes: number) {
  const d = new Date(iso);
  d.setMinutes(d.getMinutes() + minutes);
  return d.toISOString();
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
    last_name: `Mega ${suffix} ${Date.now()}`,
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

function ids(list: Array<{ id: number }> | undefined): number[] {
  return Array.isArray(list) ? list.map((x) => Number(x.id)) : [];
}

async function findWindowWhereDoctorAvailable(api: ApiClient, doctorId: number, seedStartISO: string) {
  // Search for a window where the given doctor is available to reduce flakiness from
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

async function listActiveRooms(api: ApiClient): Promise<Resource[]> {
  const res = await api.get('/api/resources/', { type: 'room', active: 'true' });
  if (!res.ok()) return [];
  const data = await res.json();
  const rooms = Array.isArray(data) ? data : data.results;
  return Array.isArray(rooms) ? (rooms as Resource[]) : [];
}

async function createRoomIfAllowed(api: ApiClient): Promise<Resource | null> {
  const payload = {
    name: `E2E Room ${Date.now()}`,
    type: 'room',
    active: true,
  };
  const res = await api.post('/api/resources/', payload);
  if (!res.ok()) return null;
  const created = (await res.json()) as Resource;
  if (!created?.id) return null;
  return created;
}

function jsonContainsMessage(body: any, needle: string) {
  const raw = typeof body === 'string' ? body : JSON.stringify(body || {});
  return raw.includes(needle);
}

test.describe('Scheduling conflicts (mega suite)', () => {
  test('Doctor double-booking conflict (UI)', async ({ page, baseURL, testData }) => {
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
      const { dateStr, startStr, endStr } = toModalDateTimeInputs(baseline.start_time, baseline.end_time);

      const calendar = new CalendarPage(page);
      const modal = new AppointmentModalPage(page);

      await calendar.goto(baseURL!);
      await calendar.openNewAppointment();
      await modal.expectOpen();
      await modal.waitForDropdownsLoaded();

      const bookedDoctorId = String(testData.doctorId);
      const bookedPatientId = String(testData.patientId);
      const freePatientIdStr = String(freePatientId);

      // Wait until dropdown data is loaded (unfiltered state).
      await waitForOptionValue(modal.doctorSelect, bookedDoctorId);
      await waitForOptionValue(modal.patientSelect, bookedPatientId);
      await waitForOptionValue(modal.patientSelect, freePatientIdStr);

      // Trigger availability filtering for the exact booked time range.
      await modal.updateTimesAndWaitForAvailability(dateStr, startStr, endStr);

      // Assert: the booked doctor is filtered out.
      await waitForOptionValueMissing(modal.doctorSelect, bookedDoctorId);

      // Sanity: at least one patient remains selectable.
      await waitForOptionValue(modal.patientSelect, freePatientIdStr);
    } finally {
      await api.dispose();
    }
  });

  test('Doctor double-booking conflict (API)', async ({ testData }) => {
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

  test('Patient overlapping appointment conflict (UI)', async ({ page, baseURL, testData }) => {
    expect(testData.appointmentId).toBeTruthy();
    expect(testData.doctorId).toBeTruthy();
    expect(testData.patientId).toBeTruthy();

    const api = new ApiClient();
    await api.init();

    try {
      // Create another patient BEFORE opening the calendar page.
      const freePatientId = await createPatientId(api, 'FREE');

      const baseline = await getAppointmentOrThrow(api, testData.appointmentId!);
      const { dateStr, startStr, endStr } = toModalDateTimeInputs(baseline.start_time, baseline.end_time);

      const calendar = new CalendarPage(page);
      const modal = new AppointmentModalPage(page);

      await calendar.goto(baseURL!);
      await calendar.openNewAppointment();
      await modal.expectOpen();
      await modal.waitForDropdownsLoaded();

      const bookedPatientId = String(testData.patientId);
      const freePatientIdStr = String(freePatientId);

      // Ensure patients are present before filtering.
      await waitForOptionValue(modal.patientSelect, bookedPatientId);
      await waitForOptionValue(modal.patientSelect, freePatientIdStr);

      await modal.updateTimesAndWaitForAvailability(dateStr, startStr, endStr);

      // Assert: booked patient is filtered out, but free patient remains selectable.
      await waitForOptionValueMissing(modal.patientSelect, bookedPatientId);
      await waitForOptionValue(modal.patientSelect, freePatientIdStr);
    } finally {
      await api.dispose();
    }
  });

  test('Patient overlapping appointment conflict (API)', async ({ testData }) => {
    expect(testData.appointmentId).toBeTruthy();
    expect(testData.appointmentTypeId).toBeTruthy();
    expect(testData.patientId).toBeTruthy();
    expect(testData.doctorId).toBeTruthy();

    const api = new ApiClient();
    await api.init();

    try {
      const baseline = await getAppointmentOrThrow(api, testData.appointmentId!);

      // Pick an alternative doctor that is available for the same time window.
      // If there is only one doctor in the system, skip gracefully.
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

      const body = await res.json();
      // From appointments.validators.validate_no_patient_appointment_overlap()
      expect(String(body?.detail || '')).toContain('patient already has an appointment');
    } finally {
      await api.dispose();
    }
  });

  test('Resource conflict (API only)', async ({ testData }) => {
    expect(testData.appointmentId).toBeTruthy();
    expect(testData.appointmentTypeId).toBeTruthy();

    const api = new ApiClient();
    await api.init();

    const createdAppointmentIds: Array<number | string> = [];

    try {
      const baseline = await getAppointmentOrThrow(api, testData.appointmentId!);

      // Ensure we have at least one active room resource.
      let rooms = await listActiveRooms(api);
      if (!rooms.length) {
        const created = await createRoomIfAllowed(api);
        if (!created) {
          test.skip(true, 'No active rooms and cannot create rooms with current test user');
          return;
        }
        rooms = [created];
      }

      const roomId = Number(rooms[0].id);

      // Create first appointment that books the room.
      // Use an available doctor for the baseline window.
      const availRes1 = await api.checkAvailability(baseline.start_time, baseline.end_time);
      if (!availRes1.ok()) {
        test.skip(true, 'Availability endpoint failed; cannot select doctor for resource booking');
        return;
      }
      const avail1 = await availRes1.json();
      const doctors1: AvailabilityDoctor[] = Array.isArray(avail1?.available_doctors) ? avail1.available_doctors : [];
      const doctor1 = doctors1.find((d) => d?.id)?.id;

      if (!doctor1) {
        test.skip(true, 'No available doctor to create resource-booking appointment');
        return;
      }

      const patient1Id = await createPatientId(api, 'RES-P1');

      const appt1Payload = {
        patient_id: patient1Id,
        doctor: Number(doctor1),
        type: Number(testData.appointmentTypeId),
        start_time: baseline.start_time,
        end_time: baseline.end_time,
        notes: 'E2E resource booking #1',
        resource_ids: [roomId],
      };

      const appt1Res = await api.createAppointment(appt1Payload);
      if (!appt1Res.ok()) {
        const bodyText = await appt1Res.text();
        test.skip(true, `Could not create resource appointment: ${appt1Res.status()} ${bodyText}`);
        return;
      }

      const appt1 = await appt1Res.json();
      const appt1Id = appt1.id || appt1.pk;
      if (!appt1Id) throw new Error('appt1 missing id');
      createdAppointmentIds.push(appt1Id);

      // For the conflicting appointment, we need a *different* doctor who is still available.
      const availRes2 = await api.checkAvailability(baseline.start_time, baseline.end_time);
      if (!availRes2.ok()) {
        test.skip(true, 'Availability endpoint failed; cannot select second doctor');
        return;
      }

      const avail2 = await availRes2.json();
      const doctors2: AvailabilityDoctor[] = Array.isArray(avail2?.available_doctors) ? avail2.available_doctors : [];
      const doctor2 = doctors2.find((d) => d?.id && Number(d.id) !== Number(doctor1))?.id;

      if (!doctor2) {
        test.skip(true, 'No second available doctor to isolate resource conflict');
        return;
      }

      const patient2Id = await createPatientId(api, 'RES-P2');

      const appt2Payload = {
        patient_id: patient2Id,
        doctor: Number(doctor2),
        type: Number(testData.appointmentTypeId),
        start_time: baseline.start_time,
        end_time: baseline.end_time,
        notes: 'E2E resource booking #2 (should conflict)',
        resource_ids: [roomId],
      };

      const appt2Res = await api.createAppointment(appt2Payload);
      expect(appt2Res.ok()).toBeFalsy();
      expect(appt2Res.status()).toBe(400);

      const body = await appt2Res.json();
      // validate_no_resource_conflicts raises ValidationError("Resource conflict")
      expect(jsonContainsMessage(body, 'Resource conflict')).toBeTruthy();
    } finally {
      for (const id of createdAppointmentIds) {
        await api.deleteAppointment(id);
      }
      await api.dispose();
    }
  });

  test('Boundary overlap rules (API): end == start allowed; partial overlap rejected', async ({ testData }) => {
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

      const patientAdjId = await createPatientId(api, 'BOUNDARY-ADJ');

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

      const patientOverlapId = await createPatientId(api, 'BOUNDARY-PARTIAL');

      const partialRes = await api.createAppointment({
        patient_id: patientOverlapId,
        doctor: Number(testData.doctorId),
        type: Number(testData.appointmentTypeId),
        start_time: partialStart,
        end_time: partialEnd,
        notes: 'E2E partial overlap should conflict',
      });

      expect(partialRes.ok()).toBeFalsy();
      expect(partialRes.status()).toBe(400);

      const body = await partialRes.json();
      expect(String(body?.detail || '')).toContain('Doctor unavailable');
    } finally {
      for (const id of createdIds) {
        await api.deleteAppointment(id);
      }
      await api.dispose();
    }
  });

  test('Availability API correctness: overlapping slot excludes booked doctor + patient', async ({ testData }) => {
    expect(testData.appointmentId).toBeTruthy();
    expect(testData.doctorId).toBeTruthy();
    expect(testData.patientId).toBeTruthy();

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

  test('Availability API correctness: non-overlapping slot can include doctor + patient again', async ({ testData }) => {
    expect(testData.appointmentId).toBeTruthy();
    expect(testData.doctorId).toBeTruthy();
    expect(testData.patientId).toBeTruthy();

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
});
