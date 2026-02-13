import { test, expect } from '../fixtures/testdata.setup';
import { ApiClient } from '../../api-client';

type AvailabilityDoctor = { id: number; name?: string };

type AppointmentDetail = {
  id: number;
  patient_id: number;
  doctor: number;
  start_time: string;
  end_time: string;
};

type Resource = { id: number; name: string; type: string; active?: boolean };

async function createPatientId(api: ApiClient, suffix: string): Promise<number> {
  const res = await api.createPatient({
    first_name: 'E2E',
    last_name: `ResourceConflict ${suffix} ${Date.now()}`,
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
  if (!res.ok()) {
    return null;
  }
  const created = (await res.json()) as Resource;
  if (!created?.id) return null;
  return created;
}

function jsonContainsMessage(body: any, needle: string) {
  const raw = typeof body === 'string' ? body : JSON.stringify(body || {});
  return raw.includes(needle);
}

test('API: rejects overlapping appointments sharing the same room resource', async ({ testData }) => {
  // Fixture gives us a deterministic time window via baseline appointment.
  if (!testData.appointmentId || !testData.appointmentTypeId) {
    test.skip(true, 'Seed data incomplete for resource conflict test');
    return;
  }

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

    const patient1Id = await createPatientId(api, 'P1');

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
      // In case resources are not supported/configured in this environment.
      const bodyText = await appt1Res.text();
      test.skip(true, `Could not create resource appointment: ${appt1Res.status()} ${bodyText}`);
      return;
    }

    const appt1 = await appt1Res.json();
    const appt1Id = appt1.id || appt1.pk;
    if (!appt1Id) throw new Error('appt1 missing id');
    createdAppointmentIds.push(appt1Id);

    // For the conflicting appointment, we need a *different* doctor who is still available.
    // If there is only one available doctor in the system, skip gracefully.
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

    const patient2Id = await createPatientId(api, 'P2');

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
    // Clean up appointments created in this test. The baseline appointment is cleaned by fixture.
    for (const id of createdAppointmentIds) {
      await api.deleteAppointment(id);
    }
    await api.dispose();
  }
});
