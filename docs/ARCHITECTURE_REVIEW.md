# Architektur-Analyse (Stärken/Schwächen & Empfehlungen)

## Stärken

### 1) Klare Dual-DB Trennung (System vs. Legacy)

- Patientendaten aus der Legacy-DB werden **nicht** von Django migriert (`managed=False`).
- Fachliche Daten (Termine/OPs/Flow) liegen in einer Django-managed DB.
- Die Regel "Patient wird als `patient_id` referenziert" vermeidet Cross-DB-FK-Probleme.

### 2) RBAC als First-Class Concern

- Viele Endpunkte nutzen dedizierte Permission-Klassen.
- Rollenmodell ist im System-DB-Kontext zentral verankert (`core.Role`, `core.User`).

### 3) Audit Logging vorhanden

- `core.AuditLog` zeichnet patientenbezogene Aktionen nach.
- Gute Grundlage für medizinische Nachvollziehbarkeit (Wer hat wann was getan?).

### 4) Deployment-Story ist realistisch

- Docker DEV/PROD Compose vorhanden.
- Prod-Konfiguration umfasst Security-Defaults (HTTPS/HSTS, Cookie Security, Throttling).

## Schwächen / Risiken

### 1) Validierungslogik teils sehr dicht im Serializer

- Beispiel: `AppointmentCreateUpdateSerializer.validate()` enthält viele Regeln (Rollenprüfung, Ressourcen, Arbeitszeiten, Absence/Break, Alternativen-Suche).
- Risiko: schwer testbar/erweiterbar; Änderungen können Seiteneffekte erzeugen.

Empfehlung:
- Komplexe Scheduling-/Validierungslogik in Service-Layer kapseln.

### 2) Observability (strukturierte Fehler) ist uneinheitlich

- DRF liefert zwar serializer errors, aber bei 403/400 ist nicht immer sofort sichtbar, *welche* Regel gegriffen hat.

Empfehlung:
- Konsistentes Error-Schema (z. B. `code`, `detail`, `fields`, `meta`) + optional correlation-id.

### 3) DEV-Settings (SessionAuth + CSRF) erzeugen Reibung

- SessionAuthentication ist gut für Browsable API, führt aber häufig zu CSRF-Problemen, wenn Frontend Credentials/Cookies sendet.

Empfehlung:
- DEV klar trennen: entweder
  - „API-only JWT“ (kein SessionAuth), oder
  - gezielte CSRF-Doku + Frontend-Konfiguration.

### 4) Celery-Infrastruktur ist vorhanden, aber derzeit ohne Tasks

- Das ist nicht schlimm, aber Dokumentation sollte klar machen, dass kein Business-Processing darauf basiert.

Empfehlung:
- Wenn keine Tasks geplant sind: optional Celery/Redis aus minimalem Setup entfernen.

## Empfehlungen (Roadmap)

### Kurzfristig (1–3 Tage)

- OpenAPI/Swagger generation (DRF schema) einführen (auch intern) → beschleunigt Onboarding.
- RBAC-Matrix als Tabelle dokumentieren (Endpoint × Rolle × read/write).
- Einheitliches Error-Schema + Logging (ohne PII/PHI).

### Mittelfristig (1–2 Wochen)

- Scheduling/Validierung in Services auslagern und unit-testbar machen.
- Konsistente DB-Routing-Helfer einführen (z. B. Repository/Manager pro Modell).

### Langfristig

- Domain-driven Module (z. B. `scheduling`, `ops`, `patient_flow`) mit klaren Interfaces.
- Hintergrundverarbeitung (z. B. Sync zwischen medical → patients cache) als definierter Prozess (wenn fachlich benötigt).
