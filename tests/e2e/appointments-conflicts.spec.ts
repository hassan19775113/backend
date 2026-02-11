import { test, expect } from '@playwright/test';
import { ApiClient } from '../../api-client';
import { CalendarPage } from '../pages/calendar-page';
import { AppointmentModalPage } from '../pages/appointment-modal-page';

type AvailabilityDoctor = { id: number; name?: string };

type Slot = {
  dateStr: string; // YYYY-MM-DD (local)
  startStr: string; // HH:MM (local)
  endStr: string; // HH:MM (local)
  start: Date;
  end: Date;
  doctorId: number;
};

function pad2(n: number) {
  return String(n).padStart(2, '0');
}

function toDateStrLocal(d: Date) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

function toTimeStrLocal(d: Date) {
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

function atLocalTime(base: Date, daysFromNow: number, hour: number, minute: number) {
  const d = new Date(base);
  d.setDate(d.getDate() + daysFromNow);
  d.setHours(hour, minute, 0, 0);
  return d;
}

async function getFirstAppointmentTypeId(api: ApiClient): Promise<number> {
  const typeRes = await api.getAppointmentTypes();
  if (!typeRes.ok()) throw new Error(`getAppointmentTypes failed: ${typeRes.status()}`);
  const types = await typeRes.json();
  const firstType = Array.isArray(types) ? types[0] : types.results?.[0];
  if (!firstType?.id) throw new Error('No appointment types available');
  return Number(firstType.id);
}

async function createPatientId(api: ApiClient, suffix: string): Promise<number> {
  const res = await api.createPatient({ first_name: 'E2E', last_name: `Conflicts ${suffix} ${Date.now()}` });
  if (!res.ok()) throw new Error(`createPatient failed: ${res.status()}`);
  const p = await res.json();
  const id = p.id || p.pk;
  if (!id) throw new Error('createPatient: missing id');
  return Number(id);
}

async function findAvailableSlot(api: ApiClient): Promise<Slot> {
  // Try a couple of days/hours to reduce flake from seeded appointments.
  const now = new Date();
  const durationMin = 30;

  for (let dayOffset = 0; dayOffset <= 14; dayOffset++) {
    for (const hour of [9, 10, 11, 12, 13, 14, 15, 16]) {
      const start = atLocalTime(now, dayOffset, hour, 0);
      const end = new Date(start.getTime() + durationMin * 60 * 1000);

      const availRes = await api.checkAvailability(start.toISOString(), end.toISOString());
      if (!availRes.ok()) continue;
      const data = await availRes.json();
      const doctors: AvailabilityDoctor[] = Array.isArray(data?.available_doctors)
        ? data.available_doctors
        : [];

      const doctor = doctors.find((d) => d?.id);
      if (!doctor?.id) continue;

      return {
        dateStr: toDateStrLocal(start),
        startStr: toTimeStrLocal(start),
        endStr: toTimeStrLocal(end),
        start,
        end,
        doctorId: Number(doctor.id),
      };
    }
  }

  throw new Error('Could not find an available doctor slot via /api/availability/');
}

async function createAppointmentWithRetries(api: ApiClient, opts: {
  patientId: number;
  typeId: number;
  notes: string;
}): Promise<{ appointmentId: number; slot: Slot }> {
  // We retry because between availability check and create, other tests might book a slot.
  for (let attempt = 1; attempt <= 6; attempt++) {
    const slot = await findAvailableSlot(api);
    const payload = {
      patient_id: opts.patientId,
      doctor: slot.doctorId,
      type: opts.typeId,
      start_time: slot.start.toISOString(),
      end_time: slot.end.toISOString(),
      notes: opts.notes,
    };
    const res = await api.createAppointment(payload);
    if (!res.ok()) continue;
    const appt = await res.json();
    const id = appt.id || appt.pk;
    if (!id) throw new Error('createAppointment: missing id');
    return { appointmentId: Number(id), slot };
  }

  throw new Error('Failed to create a baseline appointment after retries');
}

test('calendar modal filters out booked doctor + patient for overlapping time', async ({ page, baseURL }) => {
  const api = new ApiClient();
  await api.init();

  let appointmentId: number | null = null;
  try {
    const typeId = await getFirstAppointmentTypeId(api);
    const patient1Id = await createPatientId(api, 'P1');
    const patient2Id = await createPatientId(api, 'P2');

    const created = await createAppointmentWithRetries(api, {
      patientId: patient1Id,
      typeId,
      notes: 'E2E baseline appointment for conflict filtering',
    });
    appointmentId = created.appointmentId;

    const calendar = new CalendarPage(page);
    const modal = new AppointmentModalPage(page);

    await calendar.goto(baseURL!);
    await calendar.openNewAppointment();
    await modal.expectOpen();

    // Trigger availability filtering for the exact booked time range.
    await modal.dateInput.fill(created.slot.dateStr);
    await modal.startTimeInput.fill(created.slot.startStr);
    await modal.endTimeInput.fill(created.slot.endStr);

    const bookedDoctorId = String(created.slot.doctorId);

    await expect
      .poll(
        async () => {
          const values = await modal.doctorSelect.evaluate((select: HTMLSelectElement) =>
            Array.from(select.querySelectorAll('option')).map((o) => o.getAttribute('value') || '')
          );
          return values.includes(bookedDoctorId);
        },
        { timeout: 10_000, message: 'Waiting for doctor availability filtering to apply' }
      )
      .toBeFalsy();

    const bookedPatientId = String(patient1Id);
    const stillFreePatientId = String(patient2Id);

    await expect
      .poll(
        async () => {
          const values = await modal.patientSelect.evaluate((select: HTMLSelectElement) =>
            Array.from(select.querySelectorAll('option')).map((o) => o.getAttribute('value') || '')
          );
          return {
            hasBooked: values.includes(bookedPatientId),
            hasFree: values.includes(stillFreePatientId),
          };
        },
        { timeout: 10_000, message: 'Waiting for patient availability filtering to apply' }
      )
      .toEqual({ hasBooked: false, hasFree: true });
  } finally {
    if (appointmentId) {
      await api.deleteAppointment(appointmentId);
    }
    await api.dispose();
  }
});

test('API rejects overlapping appointment for the same doctor', async () => {
  const api = new ApiClient();
  await api.init();

  const createdIds: number[] = [];
  try {
    const typeId = await getFirstAppointmentTypeId(api);
    const patient1Id = await createPatientId(api, 'P1');
    const patient2Id = await createPatientId(api, 'P2');

    const baseline = await createAppointmentWithRetries(api, {
      patientId: patient1Id,
      typeId,
      notes: 'E2E baseline appointment for doctor conflict API',
    });
    createdIds.push(baseline.appointmentId);

    const overlappingPayload = {
      patient_id: patient2Id,
      doctor: baseline.slot.doctorId,
      type: typeId,
      start_time: baseline.slot.start.toISOString(),
      end_time: baseline.slot.end.toISOString(),
      notes: 'E2E overlapping (doctor) appointment',
    };

    const res = await api.createAppointment(overlappingPayload);
    expect(res.ok()).toBeFalsy();
    expect(res.status()).toBe(400);

    const body = await res.json();
    expect(body).toBeTruthy();
    // Backend payload comes from doctor_unavailable_payload()
    expect(body.detail).toBe('Doctor unavailable.');
    expect(Array.isArray(body.alternatives)).toBeTruthy();
  } finally {
    for (const id of createdIds) {
      await api.deleteAppointment(id);
    }
    await api.dispose();
  }
});

test('API rejects overlapping appointment for the same patient (different doctor)', async () => {
  const api = new ApiClient();
  await api.init();

  const createdIds: number[] = [];
  try {
    const typeId = await getFirstAppointmentTypeId(api);
    const patientId = await createPatientId(api, 'P');

    const baseline = await createAppointmentWithRetries(api, {
      patientId,
      typeId,
      notes: 'E2E baseline appointment for patient conflict API',
    });
    createdIds.push(baseline.appointmentId);

    // Find another doctor that is available for the same time window.
    const availRes = await api.checkAvailability(
      baseline.slot.start.toISOString(),
      baseline.slot.end.toISOString()
    );
    if (!availRes.ok()) {
      test.skip(true, 'Availability endpoint failed; cannot select alternate doctor');
      return;
    }

    const avail = await availRes.json();
    const doctors: AvailabilityDoctor[] = Array.isArray(avail?.available_doctors)
      ? avail.available_doctors
      : [];
    const otherDoctorId = doctors.find((d) => d?.id && Number(d.id) !== baseline.slot.doctorId)?.id;

    if (!otherDoctorId) {
      test.skip(true, 'No second available doctor to test patient overlap');
      return;
    }

    const overlappingPayload = {
      patient_id: patientId,
      doctor: Number(otherDoctorId),
      type: typeId,
      start_time: baseline.slot.start.toISOString(),
      end_time: baseline.slot.end.toISOString(),
      notes: 'E2E overlapping (patient) appointment',
    };

    const res = await api.createAppointment(overlappingPayload);
    expect(res.ok()).toBeFalsy();
    expect(res.status()).toBe(400);

    const body = await res.json();
    expect(body?.detail).toContain('patient already has an appointment');
  } finally {
    for (const id of createdIds) {
      await api.deleteAppointment(id);
    }
    await api.dispose();
  }
});
