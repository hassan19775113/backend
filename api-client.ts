import { request, APIRequestContext } from '@playwright/test';
import path from 'path';

// Simple API client wrapper using storageState for authenticated requests.
// Uses BASE_URL env (defaults to http://localhost:8000) and tests/fixtures/storageState.json.
// Provides helpers for common API endpoints seen in the app.

const STORAGE_STATE = path.join(__dirname, '..', 'fixtures', 'storageState.json');
const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';

export class ApiClient {
  private ctx: APIRequestContext | null = null;

  async init() {
    this.ctx = await request.newContext({ baseURL: BASE_URL, storageState: STORAGE_STATE });
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
    const body = payload || {
      first_name: 'E2E',
      last_name: `Patient ${Date.now()}`,
    };
    // Endpoint derived from index links (/api/patients)
    return this.post('/api/patients/', body);
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
