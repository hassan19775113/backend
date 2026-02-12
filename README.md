# PraxiApp Backend (Django / DRF)

PraxiApp ist ein Backend für Praxis-Workflows (Termine, OP-Planung, Ressourcen, Patientenfluss) mit einem klaren Fokus auf **RBAC**, **Audit Logging** und einer **Single-Datenbank-Architektur** (eine Django-managed PostgreSQL DB unter Alias `default`).

Dieses Repository enthält:
- eine **REST API** unter `/api/…` (Django REST Framework)
- ein **staff-only Dashboard** unter `/praxi_backend/dashboard/…` (server-rendered HTML)
- einen **(custom) Admin-Bereich** unter `/praxi_backend/…` sowie den Standard-Django-Admin `/admin/`

> Hinweis: Diese Dokumentation basiert ausschließlich auf dem aktuellen Stand dieses Repos (Ordner `praxi_backend/`, `DEPLOYMENT.md`, etc.).

## Inhalt

- [Fachliche Zielsetzung & Use Cases](#fachliche-zielsetzung--use-cases)
- [Technischer Überblick](#technischer-überblick)
- [Architektur & Module](#architektur--module)
- [Datenfluss (Textdiagramme)](#datenfluss-textdiagramme)
- [Datenbankkonzept (Single-DB)](#datenbankkonzept-single-db)
- [Lokale Installation (Windows/DEV)](#lokale-installation-windowsdev)
- [Deployment (Windows-native / Bare Metal)](#deployment-windows-native--bare-metal)
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

- **Patientendaten**
  - Patientenstammdaten liegen als managed Daten in der App `patients` (System-DB / `default`).

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
  - `dashboard/` – staff-only HTML-Dashboard
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

- `praxi_backend.patients`
  - Managed Patient master: `patients` (Tabelle)
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
            ├─ ORM .using('default')
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

## Datenbankkonzept (Single-DB)

| Alias | Zweck | Schreibzugriff | Beispiele |
|------:|------|----------------|----------|
| `default` | System-DB (Django-managed) | Read/Write | Users/Roles, Termine, OPs, PatientFlow, Patients, AuditLog |

### Wichtige Regeln

- Patient wird in Terminen/OPs als `patient_id: int` referenziert.
- Migrationen laufen nur auf `default`.

---

## Lokale Installation (Windows/DEV)

### Voraussetzungen

- Python 3.12 (empfohlen)

### Setup (PostgreSQL, Windows-native)

1. Virtuelle Umgebung aktivieren (bereits im Repo vorhanden: `.venv312/`)
2. Dependencies installieren aus `backend/requirements.txt`
3. `.env` konfigurieren (siehe `backend/.env.example`) und PostgreSQL lokal starten
4. Starten via `backend/manage.py` (setzt standardmäßig `praxi_backend.settings.dev`)

Wichtige DEV-Eigenschaften:
- DEV nutzt PostgreSQL (`default`)
- DRF ist paginiert (`PAGE_SIZE=50`)
- JWT + SessionAuthentication aktiv (Browsable API; CSRF beachten)

### Datenbank/Migrationen

- DEV/Prod: `python backend/manage.py migrate --database=default`

---

## Deployment (Windows-native / Bare Metal)

Siehe `infrastructure/docs/notes/DEPLOYMENT.md`.

Im Ordner `infrastructure/systemd/` liegen Service-Files und `install-services.sh` (Linux). Für Windows wird das Projekt typischerweise via `python backend/manage.py runserver` (DEV) oder Gunicorn/Reverse-Proxy (PROD) betrieben.

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

### Beispiel: Login + Auth Header

- Login: `POST /api/auth/login/` mit `{"username": "…", "password": "…"}`
- Danach: `Authorization: Bearer <access>`

---

## Sicherheit, Datenschutz, medizinische Anforderungen

- **Datenschutz/PHI-Minimierung**: Patient wird API-intern als `patient_id` referenziert; AuditLog speichert `patient_id`, Action, Timestamp und optional `meta`.
- **RBAC**: Rollen steuern Read/Write (z. B. billing meist read-only). Teilweise zusätzliche object-level Regeln (z. B. Arzt nur eigene Termine/OPs).
- **CSRF**: In DEV ist SessionAuthentication aktiv (Browsable API) → unsafe requests können CSRF benötigen. In Prod wird JWT-only genutzt.

---

## Coding-Guidelines & Konventionen

### Import-Regel

- Produktivcode: **vollqualifizierte Imports**
  - ✅ `from praxi_backend.appointments.models import Appointment`
- Tests dürfen (historisch) kürzere Imports nutzen, sollen aber bevorzugt ebenfalls vollqualifiziert sein.

### DB-Regeln

- QuerySets/Serializer-QuerySets verwenden explizit `...objects.using('default')`.
- Patientenreferenzen in Terminen/OPs sind `patient_id: int` (kein ForeignKey).

### RBAC Pattern

- Permission-Klassen definieren i. d. R. `read_roles` / `write_roles` und prüfen optional object-level.

### Audit

- Patient-relevante Aktionen sollten `log_patient_action()` schreiben.

---

## Releases & Changelog (Conventional Commits)

Dieses Repo nutzt **Conventional Commits** als Basis für ein sauberes Changelog. (CI-Workflows dafür sind bewusst minimal gehalten und werden bei Bedarf wieder eingeführt.)

### Commit-Konvention

Beispiele:

- `feat(appointments): add conflict rule for resources`
- `fix(auth): handle refresh token rotation`
- `chore(ci): pin playwright version`

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

---

## Self-Healing CI Pipeline

- Invariants: storageState liegt unter tests/fixtures/storageState.json und wird über process.cwd() aufgelöst; nie __dirname oder .auth/user.json verwenden.
- Fixes werden auf Branch ai-fix gepusht; niemals direkt auf main.

### Design (Single Orchestrator)
- `agent-engine.yml` ist der einzige Orchestrator.
- Wenn E2E fehlschlägt, läuft `tools/ai-startup-fix-agent/startup-fix.js` (Fix-Agent) und pusht Fixes auf `ai-fix`.
- Danach stellt `tools/auto-self-heal.ts` (Supervisor) sicher, dass ein PR von `ai-fix` nach `main` existiert.

Safety: Fixes sind auf `tests/**`, `playwright.config.ts` und CI-Workflow-Dateien beschränkt; kein Push nach `main`.

---

## Weiterführende Dokumente

- `DEPLOYMENT.md` – Deployment-Checkliste
- `praxi_backend/MIGRATION_PLAN.md` – Migrations-/Architekturhinweise
- `praxi_backend/appointments/SCHEDULING_OPTIMIZATION.md` – Scheduling-Optimierung
- `praxi_backend/static/docs/*` – Design-System/Frontend-Docs (statische Dokumente)
- `docs/ONBOARDING.md` – Entwickler-Onboarding (wird gepflegt)
- `docs/ci-cd-troubleshooting.md` – CI/CD Troubleshooting Guide (Logs, häufige Fehler, Eskalation)
- `docs/API_REFERENCE.md` – Detaillierte API-Referenz (wird gepflegt)
- `docs/ARCHITECTURE.md` – Architektur im Detail (wird gepflegt)
- `docs/ARCHITECTURE_REVIEW.md` – Analyse + Empfehlungen (wird gepflegt)
