# PraxiApp Backend (Django / DRF)

PraxiApp ist ein Backend für Praxis-Workflows (Termine, OP-Planung, Ressourcen, Patientenfluss) mit einem klaren Fokus auf **RBAC**, **Audit Logging** und einer **Dual-Datenbank-Architektur** (System-DB + Legacy/Medical-DB).

Dieses Repository enthält:
- eine **REST API** unter `/api/…` (Django REST Framework)
- ein **staff-only Dashboard** unter `/praxiadmin/dashboard/…` (server-rendered HTML)
- einen **(custom) Admin-Bereich** unter `/praxiadmin/…` sowie den Standard-Django-Admin `/admin/`

> Hinweis: Diese Dokumentation basiert ausschließlich auf dem aktuellen Stand dieses Repos (Ordner `praxi_backend/`, `docker-compose.*`, `DEPLOYMENT.md`, etc.).

## Inhalt

- [Fachliche Zielsetzung & Use Cases](#fachliche-zielsetzung--use-cases)
- [Technischer Überblick](#technischer-überblick)
- [Architektur & Module](#architektur--module)
- [Datenfluss (Textdiagramme)](#datenfluss-textdiagramme)
- [Datenbankkonzept (Dual-DB)](#datenbankkonzept-dual-db)
- [Lokale Installation (Windows/DEV)](#lokale-installation-windowsdev)
- [Deployment (Docker + Bare Metal)](#deployment-docker--bare-metal)
- [API-Dokumentation (Kurzreferenz)](#api-dokumentation-kurzreferenz)
- [Sicherheit, Datenschutz, medizinische Anforderungen](#sicherheit-datenschutz-medizinische-anforderungen)
- [Coding-Guidelines & Konventionen](#coding-guidelines--konventionen)
- [Troubleshooting](#troubleshooting)
- [Weiterführende Dokumente](#weiterführende-dokumente)

---

## Fachliche Zielsetzung & Use Cases

### Zielgruppe

- **Praxis-Admin/Leitung (`admin`)**: vollständige Administration (Benutzer/Rollen, Stammdaten, Ressourcen, OP-Typen, Termin-Typen, Planungsregeln)
- **MFA/Assistenz (`assistant`)**: Termin- und Ressourcenpflege, Praxiszeiten, Arztzeiten, OP-Planung (je nach Endpoint)
- **Ärzte (`doctor`)**: Einsicht/Arbeit an *eigenen* Terminen/OPs, eingeschränkte Pflege abhängig vom Endpoint
- **Abrechnung (`billing`)**: i. d. R. **read-only** (z. B. Patientendaten/Termine/OPs einsehen, aber nicht verändern)

### Kern-Workflows (medizinisch/fachlich)

- **Terminverwaltung (Ambulant)**
  - Termintypen (`AppointmentType`) definieren (Dauer/Farbe/aktiv)
  - Termine (`Appointment`) anlegen/ändern/stornieren/abschließen
  - Ressourcen (Raum/Gerät) an Termine binden
  - Terminvorschläge über Sprechzeiten + Konfliktchecks

- **OP-Planung (Stationär/OP)**
  - OP-Typen (`OperationType`) inkl. Vorbereitungs-/OP-/Nachbereitungszeiten
  - Operationen (`Operation`) mit OP-Raum + OP-Geräten planen
  - OP-Dashboard/Timeline/Statistiken zur Auslastung und Ablaufsteuerung

- **Patientenfluss (Patient Flow)**
  - Statuskette (z. B. `registered → waiting → preparing → in_treatment → post_treatment → done`)
  - Verknüpft mit Termin **oder** OP (`PatientFlow.appointment` / `PatientFlow.operation`)

- **Patientendaten (Legacy)**
  - Patientenstammdaten liegen in einer Legacy-DB (App `medical`, read-only)
  - Zusätzlich existiert ein **lokaler Cache** in der System-DB (App `patients`) für schnellere/vereinheitlichte Zugriffe

---

## Technischer Überblick

### Tech-Stack

- Python / Django 5.x
- Django REST Framework
- JWT Auth via `djangorestframework-simplejwt`
- CORS via `django-cors-headers` (DEV)
- WhiteNoise (Prod static)
- Optional: Celery + Redis (Infrastruktur vorhanden; aktuell keine aktiven Tasks)

### Projektstruktur (wichtigste Ordner)

- `praxi_backend/` – **Django Project + Apps**
  - `core/` – User/Role/AuditLog, Auth-Endpunkte
  - `appointments/` – Termine, OPs, Ressourcen, Zeiten, PatientFlow, Scheduling
  - `patients/` – lokaler Patienten-Cache (System-DB)
  - `medical/` – Legacy-Patientenmodelle (unmanaged, read-only)
  - `dashboard/` – staff-only HTML-Dashboard
- `docker-compose.dev.yml`, `docker-compose.prod.yml`, `Dockerfile*` – Container/Deployment
- `DEPLOYMENT.md` – Deployment-Checkliste

> Es existieren außerdem Root-Module `core/` und `appointments/` (außerhalb `praxi_backend/`). Diese sind **Kompatibilitäts-Wrapper** und re-exporten nur Symbole. Produktivcode sollte konsequent `praxi_backend.<app>.*` importieren.

---

## Architektur & Module

### Layering (Model → Serializer → View)

- **Modelle** (`praxi_backend/<app>/models.py`): Datenstruktur, Beziehungen innerhalb der System-DB
- **Serializer** (`serializers.py`): Validierung + API-Repräsentation (Read/Write-Serializer-Muster)
- **Permissions** (`permissions.py` bzw. `core/permissions.py`): Rollen-/Objektregeln
- **Views** (`views.py`): Endpunkte, QuerySets (mit explizitem `.using('default')`), Auditing
- **Dashboard** (`praxi_backend/dashboard/*`): server-rendered UI für Staff (Django templates)

### Apps im Überblick

- `praxi_backend.core`
  - Modelle: `Role`, `User`, `AuditLog`
  - Endpunkte: `/api/health/`, `/api/auth/login/`, `/api/auth/refresh/`, `/api/auth/me/`
  - Utility: `log_patient_action()` schreibt AuditLog in `default`

- `praxi_backend.appointments`
  - Modelle: `Appointment`, `AppointmentType`, `PracticeHours`, `DoctorHours`, `DoctorAbsence`, `DoctorBreak`, `Resource`, `Operation`, `OperationType`, `PatientFlow`, …
  - Scheduler: `scheduling.py` scannt Tage/Zeitslots, prüft Konflikte (Termine, Pausen, Abwesenheiten, Ressourcen, OP-Belegung)
  - API: umfangreich (Termine, OPs, Kalender-Views, Vorschläge, Patient Flow, Dashboard/Stats)

- `praxi_backend.medical`
  - Unmanaged Model: `Patient` (`managed=False`) auf DB-Alias `medical`
  - Views: read-only List/Detail/Search mit Audit

- `praxi_backend.patients`
  - System-DB Cache: `patients_cache` (eigene Tabelle!)
  - CRUD (rollenbasiert; billing read-only)

- `praxi_backend.dashboard`
  - Staff-only HTML Views (z. B. Kalender-Ansicht), Ajax API fürs Dashboard

---

## Datenfluss (Textdiagramme)

### Standard API Request

```
Client
  └─ HTTP Request (JSON, Authorization: Bearer <JWT>)
       └─ DRF View (praxi_backend.<app>.views.*)
            ├─ Authentication (JWT; in DEV zusätzlich SessionAuth möglich)
            ├─ Permission Check (RBAC + ggf. object-level)
            ├─ Serializer.validate()  ← Geschäftsregeln (z.B. Sprechzeiten, Ressourcen)
            ├─ ORM .using('default'|'medical')
            ├─ Audit: log_patient_action(user, action, patient_id, meta)
            └─ HTTP Response (JSON; Listen meist paginiert)
```

### Terminvorschläge (Scheduling)

```
GET /api/appointments/suggest/
  └─ SuggestView
       └─ compute_suggestions_for_doctor(...)
            ├─ liest PracticeHours + DoctorHours
            ├─ prüft DoctorAbsence + DoctorBreak
            ├─ blockt bei bestehenden Appointments
            └─ blockt bei Ressourcen-Konflikten inkl. Operationen (Room/Device)
```

---

## Datenbankkonzept (Dual-DB)

### Zwei DB-Aliase

| Alias | Zweck | Schreibzugriff | Beispiele |
|------:|------|----------------|----------|
| `default` | System-DB (Django-managed) | Read/Write | Users/Roles, Termine, OPs, PatientFlow, Patient-Cache, AuditLog |
| `medical` | Legacy/medizinische DB | **Read-only (fachlich)** | Patientenstamm (`medical.Patient`) |

### Wichtige Regeln

- **Keine Cross-DB ForeignKeys**: Patient wird überall als `patient_id: int` referenziert.
- **Migrationen nur auf `default`**: In Prod steuert `PraxiAppRouter` (`praxi_backend/db_router.py`) das.
- In DEV (`settings_dev.py`) wird bewusst alles auf SQLite gefahren, ohne Router.

---

## Lokale Installation (Windows/DEV)

### Voraussetzungen

- Python (Repo nutzt Docker `python:3.12-slim`; lokal entsprechend empfohlen)
- Optional: Docker Desktop (wenn du dev/prod compose nutzen willst)

### Setup ohne Docker (SQLite, schnellster Start)

1. Virtuelle Umgebung aktivieren (bereits im Repo vorhanden: `.venv/`)
2. Dependencies installieren aus `praxi_backend/requirements.txt`
3. Starten via `manage.py` (setzt standardmäßig `praxi_backend.settings_dev`)

Wichtige DEV-Eigenschaften:
- `settings_dev.py` nutzt SQLite (`dev.sqlite3`) für **default und medical** (vereinfachtes DEV)
- DRF ist paginiert (`PAGE_SIZE=50`)
- JWT + SessionAuthentication aktiv (Browsable API; CSRF beachten)

### Datenbank/Migrationen

- DEV: `python manage.py migrate` (SQLite)
- Prod: `python manage.py migrate --database=default` (**niemals** `--database=medical`)

---

## Deployment (Docker + Bare Metal)

### Docker (empfohlen)

Siehe `DEPLOYMENT.md` sowie:
- `docker-compose.dev.yml` (Dev Stack inkl. Postgres + Redis)
- `docker-compose.prod.yml` (Prod Stack inkl. Nginx + Gunicorn + Postgres + Redis + Celery)

### Bare Metal / Systemd

Im Ordner `systemd/` liegen Service-Files und `install-services.sh`. Die Checkliste in `DEPLOYMENT.md` beschreibt den Ablauf.

---

## API-Dokumentation (Kurzreferenz)

> Viele List-Endpunkte sind paginiert: Response ist typischerweise `{count,next,previous,results}`.

### Core

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/api/health/` | Healthcheck (DB ping) |
| POST | `/api/auth/login/` | JWT Login (access + refresh) |
| POST | `/api/auth/refresh/` | Access Token erneuern |
| GET | `/api/auth/me/` | Aktueller User |

### Appointments / Operations / Scheduling

Aus `praxi_backend/appointments/urls.py` (Auszug):

- Termine
  - `GET/POST /api/appointments/`
  - `GET /api/appointments/suggest/`
  - `GET/PATCH/DELETE /api/appointments/<id>/`
- Termin-Typen
  - `GET/POST /api/appointment-types/`
  - `GET/PATCH/DELETE /api/appointment-types/<id>/`
- OPs
  - `GET/POST /api/operations/`
  - `GET /api/operations/suggest/`
  - `GET/PATCH/DELETE /api/operations/<id>/`
- OP-Dashboard/Timeline/Stats
  - `GET /api/op-dashboard/` (+ `/live/`, `/<id>/status/`)
  - `GET /api/op-timeline/` (+ `/rooms/`, `/live/`)
  - `GET /api/op-stats/*` (overview/rooms/devices/surgeons/types)
- Ressourcen
  - `GET/POST /api/resources/`
  - `GET/PATCH/DELETE /api/resources/<id>/`
  - `GET /api/resource-calendar/` (+ `/resources/`)
- Zeiten
  - `GET/POST /api/practice-hours/`, `GET/PATCH/DELETE /api/practice-hours/<id>/`
  - `GET/POST /api/doctor-hours/`, `GET/PATCH/DELETE /api/doctor-hours/<id>/`
  - `GET/POST /api/doctor-absences/`, `GET/PATCH/DELETE /api/doctor-absences/<id>/`
  - `GET/POST /api/doctor-breaks/`, `GET/PATCH/DELETE /api/doctor-breaks/<id>/`
- Patient Flow
  - `GET/POST /api/patient-flow/`
  - `GET /api/patient-flow/live/`
  - `GET/PATCH/DELETE /api/patient-flow/<id>/`
  - `POST /api/patient-flow/<id>/status/`

### Patients (System-DB Cache)

| Methode | Pfad | Zweck |
|---|---|---|
| GET/POST | `/api/patients/` | Cache-Patienten listen/erstellen |
| GET/PUT/PATCH | `/api/patients/<id>/` | Cache-Patient ändern |

### Medical (Legacy DB, read-only)

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/api/medical/patients/` | Legacy Patientenliste |
| GET | `/api/medical/patients/search/?q=…` | Suche |
| GET | `/api/medical/patients/<id>/` | Detail |

### Beispiel: Login + Auth Header

- Login: `POST /api/auth/login/` mit `{"username": "…", "password": "…"}`
- Danach: `Authorization: Bearer <access>`

---

## Sicherheit, Datenschutz, medizinische Anforderungen

- **Datenschutz/PHI-Minimierung**: Patient wird API-intern als `patient_id` referenziert; AuditLog speichert `patient_id`, Action, Timestamp und optional `meta`.
- **Legacy DB Schutz**: `medical`-Modelle sind `managed=False`; Migrationen sind für `medical` blockiert.
- **RBAC**: Rollen steuern Read/Write (z. B. billing meist read-only). Teilweise zusätzliche object-level Regeln (z. B. Arzt nur eigene Termine/OPs).
- **CSRF**: In DEV ist SessionAuthentication aktiv (Browsable API) → unsafe requests können CSRF benötigen. In Prod wird JWT-only genutzt.

---

## Coding-Guidelines & Konventionen

### Import-Regel

- Produktivcode: **vollqualifizierte Imports**
  - ✅ `from praxi_backend.appointments.models import Appointment`
- Tests dürfen (historisch) kürzere Imports nutzen, sollen aber bevorzugt ebenfalls vollqualifiziert sein.

### Multi-DB Regeln

- In produktiven QuerySets/Serializer-QuerySets: `...objects.using('default')` bzw. `.using('medical')`
- Keine Cross-DB ForeignKeys.

### RBAC Pattern

- Permission-Klassen definieren i. d. R. `read_roles` / `write_roles` und prüfen optional object-level.

### Audit

- Patient-relevante Aktionen sollten `log_patient_action()` schreiben.

---

## Troubleshooting

### Häufige 403 (Forbidden)

- JWT fehlt/ungültig → `Authorization: Bearer …` prüfen
- Rolle passt nicht zu Endpoint (RBAC) → Rolle/Permission-Klasse prüfen
- object-level Deny (z. B. Arzt greift auf fremden Termin zu)
- DEV: SessionAuth aktiv + CSRF fehlt (bei cookie-basierten Requests)

### Häufige 400 (Bad Request)

- Termin/OP-Zeiten invalide (`start_time >= end_time`)
- Arzt nicht mit Rolle `doctor`
- Arzt darf als `doctor` nur eigene Termine ändern
- Arbeitszeiten fehlen: `PracticeHours`/`DoctorHours` sind Voraussetzung → sonst `Doctor unavailable.`
- Ressourcen-IDs unbekannt/inaktiv

### DB/Migrations

- Prod: Migrationen ausschließlich `--database=default`
- medical DB niemals migrieren

---

## Weiterführende Dokumente

- `DEPLOYMENT.md` – Deployment-Checkliste
- `praxi_backend/MIGRATION_PLAN.md` – Migrations-/Architekturhinweise
- `praxi_backend/appointments/SCHEDULING_OPTIMIZATION.md` – Scheduling-Optimierung
- `praxi_backend/static/docs/*` – Design-System/Frontend-Docs (statische Dokumente)
- `docs/ONBOARDING.md` – Entwickler-Onboarding (wird gepflegt)
- `docs/API_REFERENCE.md` – Detaillierte API-Referenz (wird gepflegt)
- `docs/ARCHITECTURE.md` – Architektur im Detail (wird gepflegt)
- `docs/ARCHITECTURE_REVIEW.md` – Analyse + Empfehlungen (wird gepflegt)
