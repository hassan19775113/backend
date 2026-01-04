# Architektur (PraxiApp Backend)

## Systemkontext

PraxiApp ist ein Backend für Praxisprozesse mit folgenden Hauptkomponenten:

- **REST API** (DRF) für Termin-/OP-/Ressourcen-/PatientFlow-Operationen
- **Dashboard UI** (server-rendered Django Templates) für Staff
- **Dual-Datenbank-Architektur**:
  - `default`: Django-managed Systemdaten + fachliche Planungsdaten
  - `medical`: Legacy Patient DB (read-only, unmanaged models)
- **RBAC** (rollenbasiert) und **Audit Logging**

## Komponentenübersicht

### Django Project

- Root URLs: `praxi_backend/urls.py`
  - `/api/` inkludiert `core`, `appointments`, `patients`
  - `/api/medical/` inkludiert `medical`
  - `/praxiadmin/dashboard/` (Dashboard)
  - `/praxiadmin/` (Custom Admin)

### Apps

#### `praxi_backend.core`

- Modelle: `Role`, `User`, `AuditLog`
- Auth:
  - JWT Login/Refresh/Me
- Utility:
  - `log_patient_action(user, action, patient_id=None, meta=None)`

#### `praxi_backend.appointments`

- Terminplanung:
  - `Appointment`, `AppointmentType`
  - `PracticeHours`, `DoctorHours`, `DoctorAbsence`, `DoctorBreak`
  - `Resource` (room/device), `AppointmentResource`
- OP-Planung:
  - `Operation`, `OperationType`, `OperationDevice`
  - OP Dashboard / Timeline / Stats
- Patientenfluss:
  - `PatientFlow` (Statuskette; appointment oder operation)

Scheduling-Engine:
- `praxi_backend/appointments/scheduling.py`
  - scannt Tage, erzeugt Zeitslots in 5-Minuten-Schritten
  - blockiert bei Konflikten:
    - existierende Termine
    - Pausen/Abwesenheiten
    - Ressourcenbelegung (auch OP-Raum/OP-Geräte)

#### `praxi_backend.patients` (System-DB Cache)

- Tabelle: `patients_cache` (nicht die Legacy Tabelle)
- Zweck: lokale Spiegelung/Ablage ausgewählter Patientendaten

#### `praxi_backend.medical` (Legacy)

- Modell: `Patient` (`managed=False`, DB `medical`)
- Views sind read-only (List/Detail/Search) und auditiert.

#### `praxi_backend.dashboard`

- Staff-only Views (z. B. Kalenderdarstellungen)
- primär HTML-rendering; Ajax API für KPI-Refresh

## Datenmodell-Kernelemente

### Patientenreferenz

- `patient_id: int` ist die **kanonische** Referenz auf den Patienten.
- Keine Cross-DB ForeignKeys.

### Ressourcen

- `Resource.type ∈ {room, device}`
- Termine nutzen Ressourcen via `AppointmentResource` (M2M)
- OPs nutzen OP-Raum (FK) + OP-Geräte (M2M via `OperationDevice`)

### PatientFlow

- Ein Flow gehört zu genau einem Kontext:
  - entweder `appointment` oder `operation` (beide optional, aber fachlich i. d. R. genau eins)

## Querschnitt: RBAC

- Viele Permissions folgen dem Muster `read_roles`/`write_roles`.
- Typische Regeln:
  - billing: read-only
  - doctor: eingeschränkt (eigene Records; teils nur GET)

## Querschnitt: Audit Logging

- Audit schreibt in `core.AuditLog` (System-DB `default`).
- Logging soll keine PHI enthalten (nur `patient_id` + Action + Meta ohne PII).

## Deployment-Architektur

- DEV: `settings_dev.py`, SQLite, optional Docker-Compose dev Stack
- PROD: `settings_prod.py`, Postgres + Redis, Nginx + Gunicorn, WhiteNoise für static

Siehe auch `DEPLOYMENT.md`.
