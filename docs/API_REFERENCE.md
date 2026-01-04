# API Referenz (PraxiApp Backend)

Diese Referenz ist eine **entwicklerorientierte** Übersicht der vorhandenen Endpunkte.

## Allgemeines

- Base URL (lokal): `http://localhost:8000`
- Auth: JWT (`Authorization: Bearer <access>`)
- DEV zusätzlich: SessionAuthentication (Browsable API) → CSRF kann relevant sein
- Pagination (typisch):
  - Response: `{count, next, previous, results}`

## Auth / Core (`/api/…`)

### `GET /api/health/`

- Zweck: einfacher Healthcheck (DB ping)
- Auth: keine
- Response: `{ "status": "ok" }` oder `{ "status": "error", "detail": "…" }`

### `POST /api/auth/login/`

- Zweck: JWT Login
- Body:
  - `username: string`
  - `password: string`
- Response:
  - `user: {id, username, email, first_name, last_name, role}`
  - `access: string`
  - `refresh: string`

### `POST /api/auth/refresh/`

- Body: `{ "refresh": "…" }`
- Response: `{ "access": "…" }`

### `GET /api/auth/me/`

- Auth: required
- Response: User + nested role

## Appointments / Operations (`/api/…`)

Quelle: `praxi_backend/appointments/urls.py`

### Termine

- `GET/POST /api/appointments/`
- `GET /api/appointments/suggest/`
- `GET/PATCH/DELETE /api/appointments/<id>/`

**Validierungshinweise (Create/Update):**
- `patient_id` muss positive int sein
- `doctor` muss Rolle `doctor` haben
- Wenn Request-User Rolle `doctor` hat: darf nur eigene Termine anlegen/ändern
- `start_time < end_time`
- Arbeitszeiten müssen Slot abdecken:
  - `PracticeHours` (praxisweit)
  - `DoctorHours` (arztbezogen)
  - keine Überlappung mit `DoctorAbsence`/`DoctorBreak`
- Optional: Ressourcen (`resource_ids`) müssen existieren und aktiv sein

### Termin-Typen

- `GET/POST /api/appointment-types/`
- `GET/PATCH/DELETE /api/appointment-types/<id>/`

### OPs

- `GET/POST /api/operations/`
- `GET /api/operations/suggest/`
- `GET/PATCH/DELETE /api/operations/<id>/`

### OP-Typen

- `GET/POST /api/operation-types/`
- `GET/PATCH/DELETE /api/operation-types/<id>/`

### Ressourcen

- `GET/POST /api/resources/`
- `GET/PATCH/DELETE /api/resources/<id>/`
- `GET /api/resource-calendar/`
- `GET /api/resource-calendar/resources/`

### Kalender (API)

- `GET /api/calendar/day/`
- `GET /api/calendar/week/`
- `GET /api/calendar/month/`

### Praxis-/Arztzeiten

- `GET/POST /api/practice-hours/`
- `GET/PATCH/DELETE /api/practice-hours/<id>/`
- `GET/POST /api/doctor-hours/`
- `GET/PATCH/DELETE /api/doctor-hours/<id>/`
- `GET/POST /api/doctor-absences/`
- `GET/PATCH/DELETE /api/doctor-absences/<id>/`
- `GET/POST /api/doctor-breaks/`
- `GET/PATCH/DELETE /api/doctor-breaks/<id>/`

### Patient Flow

- `GET/POST /api/patient-flow/`
- `GET /api/patient-flow/live/`
- `GET/PATCH/DELETE /api/patient-flow/<id>/`
- `POST /api/patient-flow/<id>/status/`

### OP Dashboard / Timeline / Stats

- `GET /api/op-dashboard/`
- `GET /api/op-dashboard/live/`
- `POST /api/op-dashboard/<id>/status/`
- `GET /api/op-timeline/`
- `GET /api/op-timeline/rooms/`
- `GET /api/op-timeline/live/`

- `GET /api/op-stats/overview/` (`?date=` oder `?from=&to=`)
- `GET /api/op-stats/rooms/`
- `GET /api/op-stats/devices/`
- `GET /api/op-stats/surgeons/`
- `GET /api/op-stats/types/`

## Patients Cache (`/api/patients/…`)

Quelle: `praxi_backend/patients/urls.py`

- `GET/POST /api/patients/`
- `GET/PUT/PATCH /api/patients/<id>/`

Audit:
- Create: `patient_created`
- Update: `patient_updated`

## Medical (Legacy, read-only) (`/api/medical/…`)

Quelle: `praxi_backend/medical/urls.py`

- `GET /api/medical/patients/`
- `GET /api/medical/patients/search/?q=…`
- `GET /api/medical/patients/<id>/`

Audit:
- List: `patient_list`
- Detail: `patient_view`
- Search: `patient_search` (Meta enthält Query)
