import { request, APIRequestContext } from '@playwright/test';
import fs from 'fs';
import path from 'path';

// Simple API client wrapper using storageState for authenticated requests.
// Uses BASE_URL env (defaults to http://localhost:8000) and tests/fixtures/storageState.json.
// Provides helpers for common API endpoints seen in the app.

// Resolve relative to repo root to avoid __dirname differences in TS transpilation output
const STORAGE_STATE = path.resolve(process.cwd(), 'tests', 'fixtures', 'storageState.json');
const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';

export class ApiClient {
  private ctx: APIRequestContext | null = null;

  private generateLegacyPatientId(): number {
    // Patient.id is a legacy integer PK (required).
    // Use epoch milliseconds modulo a safe 32-bit-ish range to minimize collisions
    // while staying under the signed 32-bit int max.
    const epochMs = Date.now();
    const base = epochMs % 2_000_000_000;
    const jitter = Math.floor(Math.random() * 10_000);
    return base + jitter;
  }

  private getAccessTokenFromStorageState(): string {
    const raw = fs.readFileSync(STORAGE_STATE, 'utf-8');
    const json = JSON.parse(raw);
    const origins = Array.isArray(json?.origins) ? json.origins : [];
    for (const origin of origins) {
      const items = Array.isArray(origin?.localStorage) ? origin.localStorage : [];
      const match = items.find((i: any) => i?.name === 'access_token');
      if (match?.value) return String(match.value);
    }
    throw new Error('access_token not found in storageState.json (run Playwright globalSetup first)');
  }

  async init() {
    const accessToken = this.getAccessTokenFromStorageState();
    this.ctx = await request.newContext({
      baseURL: BASE_URL,
      storageState: STORAGE_STATE,
      extraHTTPHeaders: {
        Authorization: `Bearer ${accessToken}`,
      },
    });
  }

  async dispose() {
    if (this.ctx) await this.ctx.dispose();
  }

  // Generic wrappers
  async get(url: string, params?: Record<string, string>) {
    if (!this.ctx) throw new Error('ApiClient not initialized');
    const search = params ? `?${new URLSearchParams(params).toString()}` : '';
    return this.ctx.get(`${url}${search}`);
  }

  async post(url: string, data?: any) {
    if (!this.ctx) throw new Error('ApiClient not initialized');
    return this.ctx.post(url, { data });
  }

  async put(url: string, data?: any) {
    if (!this.ctx) throw new Error('ApiClient not initialized');
    return this.ctx.put(url, { data });
  }

  async del(url: string) {
    if (!this.ctx) throw new Error('ApiClient not initialized');
    return this.ctx.delete(url);
  }

  // Helpers for domain resources
  async listDoctors() {
    return this.get('/api/appointments/doctors/');
  }

  async listAppointmentTypes() {
    return this.get('/api/appointment-types/');
  }

  async getMe() {
    return this.get('/api/auth/me/');
  }

  async suggestAppointment(params: {
    doctor_id: number | string;
    type_id?: number | string;
    duration_minutes?: number;
    start_date?: string;
    limit?: number;
    resource_ids?: Array<number | string>;
  }) {
    const query: Record<string, string> = {
      doctor_id: String(params.doctor_id),
    };
    if (params.type_id !== undefined) query.type_id = String(params.type_id);
    if (params.duration_minutes !== undefined) query.duration_minutes = String(params.duration_minutes);
    if (params.start_date !== undefined) query.start_date = String(params.start_date);
    if (params.limit !== undefined) query.limit = String(params.limit);
    if (params.resource_ids && params.resource_ids.length) query.resource_ids = params.resource_ids.map(String).join(',');
    return this.get('/api/appointments/suggest/', query);
  }

  async listAppointments(params?: Record<string, string>) {
    return this.get('/api/appointments/', params);
  }

  async createAppointment(payload: any) {
    // Payload should match backend API: patient_id, doctor, type, start_time, end_time, notes, resource_ids?
    return this.post('/api/appointments/', payload);
  }

   async deleteAppointment(id: string | number) {
    return this.del(`/api/appointments/${id}/`);
  }

  async getDoctors() {
    return this.listDoctors();
  }

  async getPatients() {
    return this.get('/api/patients/');
  }

  async getAppointmentTypes() {
    return this.listAppointmentTypes();
  }

  async createDoctor(payload?: Record<string, any>) {
    const body = payload || {
      name: `E2E Doctor ${Date.now()}`,
    };
    // Endpoint guessed from existing doctors list: /api/appointments/doctors/
    return this.post('/api/appointments/doctors/', body);
  }

  async createPatient(payload?: Record<string, any>) {
    const base = payload || {
      first_name: 'E2E',
      last_name: `Patient ${Date.now()}`,
    };
    const hasExplicitId = base?.id !== undefined && base?.id !== null;

    const makeBody = () => ({
      id: hasExplicitId ? base.id : this.generateLegacyPatientId(),
      ...base,
    });

    const maxAttempts = hasExplicitId ? 1 : 6;
    let lastResponse: any = null;

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      const body = makeBody();
      const response = await this.post('/api/patients/', body);
      if (response.ok()) {
        return response;
      }

      lastResponse = response;
      const text = await response.text();
      const isDuplicateId =
        text.includes('duplicate key value violates unique constraint') &&
        (text.includes('patients_pkey1') || text.includes('Key (id)=') || text.includes('UNIQUE constraint failed'));

      if (!isDuplicateId || hasExplicitId || attempt === maxAttempts) {
        return response;
      }
    }

    return lastResponse;
  }

  async checkAvailability(startISO: string, endISO: string, excludeId?: string | number) {
    const params: Record<string, string> = { start: startISO, end: endISO };
    if (excludeId) params.exclude_appointment_id = String(excludeId);
    return this.get('/api/availability/', params);
  }
}

// Convenience helper to run with auto-init/teardown
export async function withApiClient(fn: (api: ApiClient) => Promise<void>) {
  const api = new ApiClient();
  await api.init();
  try {
    await fn(api);
  } finally {
    await api.dispose();
  }
}
