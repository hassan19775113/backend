# Entwickler-Onboarding (PraxiApp Backend)

Diese Seite ist für Nachfolge-Entwickler gedacht, die das Projekt **ohne Vorwissen** starten, debuggen und erweitern sollen.

## Schnellstart (lokal, Windows, SQLite)

### 1) Voraussetzungen

- Python (empfohlen analog Docker-Image: 3.12)
- (Optional) VS Code + Python Extension

### 2) Settings-Modul

`manage.py` setzt standardmäßig:

- `DJANGO_SETTINGS_MODULE = praxi_backend.settings_dev`

`settings_dev.py` nutzt SQLite (`dev.sqlite3`) und deaktiviert Multi-DB-Routing (alles läuft auf derselben DB-Datei).

### 3) Start

- Migrationen:
  - DEV: `python manage.py migrate`
- Server:
  - `python manage.py runserver`

### 4) Auth testen

- `POST /api/auth/login/`
- `GET /api/auth/me/` mit `Authorization: Bearer <access>`

## Tests ausführen

Das Projekt nutzt einen eigenen Test Runner (`praxi_backend.test_runner.PraxiAppTestRunner`) für die Dual-DB-Architektur.

Empfehlung:
- `python manage.py test praxi_backend`
- oder modulweise, z. B.:
  - `python manage.py test praxi_backend.appointments.tests`

### Typische Test-Fallstricke

- Viele Endpunkte sind paginiert → Tests sollten `results` berücksichtigen.
- Scheduling/Validierung ist strikt → Tests müssen `PracticeHours`/`DoctorHours` setzen.

## Debugging: API-Fehler systematisch eingrenzen

### 403 Forbidden

Checkliste:
1. **Authentication**: ist ein JWT vorhanden und korrekt?
2. **Role**: hat der User eine Rolle (`user.role.name`)?
3. **Permission Klasse**: blockt `read_roles`/`write_roles`?
4. **object-level Regeln**:
   - Arzt darf i. d. R. nur eigene Termine/OPs sehen/bearbeiten.
5. **DEV-spezifisch**: SessionAuthentication kann CSRF erfordern.

### 400 Bad Request

Typische Ursachen:
- Zeiten: `start_time >= end_time`
- Arzt-Rolle: `doctor` Feld zeigt auf User ohne Rolle `doctor`
- Arzt legt Termin für anderen Arzt an (verboten)
- Arbeitszeitregeln: `PracticeHours`/`DoctorHours` fehlen oder decken Slot nicht ab → `Doctor unavailable.`
- Ressourcen: unbekannte oder inaktive IDs

### 500 Internal Server Error

- Stacktrace in Console Logs (DEV Logging ist aktiviert).
- Häufig: DB-Routing/`.using('default')` vergessen (Prod), oder missing env vars in Prod Settings.

## Erweiterungen: Modelle, Serializer, Views

### Neue Felder / neue Modelle

- Änderungen an Django-managed Tabellen gehören in Apps mit DB-Alias `default`.
- Migrationen:
  - `python manage.py makemigrations <app>`
  - Prod: `python manage.py migrate --database=default`

### Neue Endpoints

Muster:
- Permission-Klasse (RBAC Pattern: `read_roles`/`write_roles`)
- Read/Write Serializer trennen, wenn Validierung unterschiedlich ist
- View: `get_queryset()` mit `.using('default')`
- `perform_create/perform_update/perform_destroy`: `log_patient_action()` für patientenbezogene Aktionen

### Neue medizinische Workflows integrieren

- Patient wird systemweit als `patient_id: int` referenziert.
- Keine ForeignKeys in Richtung `medical` DB.
- Wenn Workflow patientenbezogen ist: AuditLog-Aktion definieren und schreiben.

## Struktur-Hinweis: Kompatibilitäts-Wrapper

Im Repo existieren Root-Module `core/` und `appointments/` außerhalb `praxi_backend/`.
- Zweck: Kompatibilität (Re-Exports)
- Regel: Produktivcode & Patches sollten `praxi_backend.<app>.*` nutzen.
