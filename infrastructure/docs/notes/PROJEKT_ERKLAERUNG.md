# PraxiApp Backend - Projekterklärung für neue Entwickler

## 📋 Inhaltsverzeichnis

1. [Projektübersicht](#projektübersicht)
2. [Architektur im Detail](#architektur-im-detail)
3. [Wichtige Module und deren Zweck](#wichtige-module-und-deren-zweck)
4. [Datenbankarchitektur (Single-DB)](#datenbankarchitektur-single-db)
5. [Scheduling-Engine (Kernkomponente)](#scheduling-engine-kernkomponente)
6. [API-Struktur](#api-struktur)
7. [Sicherheit & Berechtigungen (RBAC)](#sicherheit--berechtigungen-rbac)
8. [Entwicklungsworkflow](#entwicklungsworkflow)
9. [Häufige Aufgaben & Troubleshooting](#häufige-aufgaben--troubleshooting)

---

## Projektübersicht

**PraxiApp** ist ein Django-basiertes Backend für die Verwaltung von Arztpraxen. Es verwaltet:

- **Termine (Appointments)**: Ambulante Patientenbesuche
- **Operationen (Operations)**: OP-Planung mit Ressourcen (Räume, Geräte)
- **Patientenfluss (Patient Flow)**: Status-Tracking während der Behandlung
- **Ressourcenverwaltung**: Räume und medizinische Geräte
- **Arbeitszeiten & Verfügbarkeit**: Praxis- und Arztzeiten, Abwesenheiten, Pausen

### Tech-Stack

- **Python 3.12** / **Django 5.x**
- **Django REST Framework** (DRF) für REST-APIs
- **JWT-Authentifizierung** (`djangorestframework-simplejwt`)
- **PostgreSQL** (Single-DB; `default`)
- Optional: **Celery + Redis** (vorbereitet, aktuell nicht aktiv genutzt)

---

## Architektur im Detail

### Projektstruktur

```
backend/
├── praxi_backend/              # Haupt-Django-Projekt
│   ├── core/                   # Kernfunktionalität
│   │   ├── models.py           # User, Role, AuditLog
│   │   ├── views.py            # Auth-Endpunkte (/api/auth/*)
│   │   ├── permissions.py      # Basis-Permissions
│   │   └── utils.py            # log_patient_action() für Audit
│   │
│   ├── appointments/           # Termine & OPs (Kern-App)
│   │   ├── models.py           # Appointment, Operation, Resource, etc.
│   │   ├── views.py            # API-Endpunkte
│   │   ├── serializers.py      # DRF-Serializer
│   │   ├── permissions.py      # RBAC-Regeln
│   │   ├── services/
│   │   │   └── scheduling.py   # ⭐ KERN: Scheduling-Engine
│   │   └── exceptions.py       # Custom Exceptions
│   │
│   ├── patients/               # Patienten (managed, System-DB)
│   │   └── models.py           # Patient master + notes/documents
│   │
│   ├── dashboard/              # Staff-only HTML-Dashboard
│   │   ├── templates/          # Django-Templates
│   │   └── *.py                # Dashboard-Views
│   │
│   ├── settings.py             # Basis-Settings
│   ├── settings_dev.py         # Development (PostgreSQL; ggf. Shim)
│   ├── settings_prod.py        # Production (PostgreSQL; ggf. Shim)
│   └── db_router.py            # Deprecated stub (Single-DB)
│
├── manage.py                   # Django-Management
├── requirements.txt            # Python-Dependencies
└── README.md                   # Hauptdokumentation
```

### Layering (Schichtenarchitektur)

```
┌─────────────────────────────────────┐
│  API Layer (DRF Views)              │  ← /api/appointments/, /api/operations/
│  - Authentifizierung (JWT)          │
│  - Permission-Checks (RBAC)         │
│  - Request/Response-Handling        │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Business Logic Layer                │
│  - Serializers (Validierung)         │
│  - Scheduling-Services               │  ← scheduling.py
│  - Exception-Handling                │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Data Layer (Models)                 │
│  - Django ORM                        │
│  - .using('default')                 │
└──────────────────────────────────────┘
```

---

## Wichtige Module und deren Zweck

### 1. `praxi_backend.core`

**Zweck**: Basis-Funktionalität (User, Rollen, Audit)

**Modelle**:
- `User`: Custom User-Model mit `role` (ForeignKey zu `Role`)
- `Role`: Rollen (admin, assistant, doctor, billing, nurse)
- `AuditLog`: Protokollierung von Patient-Aktionen

**Endpunkte**:
- `POST /api/auth/login/` - JWT-Login
- `POST /api/auth/refresh/` - Token-Erneuerung
- `GET /api/auth/me/` - Aktueller User
- `GET /api/health/` - Healthcheck

**Wichtige Funktionen**:
```python
from praxi_backend.core.utils import log_patient_action

# Audit-Log schreiben
log_patient_action(user, 'appointment_create', patient_id, meta={...})
```

### 2. `praxi_backend.appointments` ⭐

**Zweck**: Kern-App für Termine, OPs, Scheduling

**Hauptmodelle**:

| Modell | Zweck |
|--------|-------|
| `Appointment` | Termine (ambulant) |
| `AppointmentType` | Terminarten (z.B. "Kontrolle", "Erstbesuch") |
| `Operation` | Operationen (stationär) |
| `OperationType` | OP-Typen (mit prep/op/post-Dauer) |
| `Resource` | Räume (`type='room'`) & Geräte (`type='device'`) |
| `PracticeHours` | Praxisöffnungszeiten (wochentagsweise) |
| `DoctorHours` | Arzt-Arbeitszeiten (individuell) |
| `DoctorAbsence` | Abwesenheiten (Urlaub, Krankheit) |
| `DoctorBreak` | Pausen (praxisweit oder arztspezifisch) |
| `PatientFlow` | Patientenfluss-Status (registered → waiting → ... → done) |

**Services**:
- `services/scheduling.py` - **Kernkomponente** (siehe unten)

**Endpunkte** (Auszug):
- `GET/POST /api/appointments/`
- `GET /api/appointments/suggest/` - Terminvorschläge
- `GET/POST /api/operations/`
- `GET /api/operations/suggest/` - OP-Vorschläge
- `GET /api/calendar/day|week|month/` - Kalender-Ansichten
- `GET /api/op-dashboard/` - OP-Dashboard
- `GET /api/op-timeline/` - OP-Timeline
- `GET /api/op-stats/*` - OP-Statistiken

### 3. `praxi_backend.patients`

**Zweck**: Patient-Stammdaten (managed) in der System-DB

- Tabelle `patients`
- CRUD möglich (rollenbasiert)
- `billing`-Rolle: read-only

**Endpunkte**:
- `GET/POST /api/patients/`
- `GET/PUT/PATCH /api/patients/<id>/`

### 4. `praxi_backend.dashboard`

**Zweck**: Staff-only HTML-Dashboard (server-rendered)

- Django-Templates
- Kalender-Ansichten
- Statistiken & KPIs
- Zugriff: `/praxi_backend/dashboard/...`

---

## Datenbankarchitektur (Single-DB)

**PraxiApp** nutzt eine **Single-Database-Architektur** (PostgreSQL "default"):

- Django-Systemtabellen (auth, sessions, etc.)
- App-Daten (`core`, `appointments`, `patients`, `dashboard`)

### Wichtige Regeln

1. **Keine Patient-ForeignKeys**
    - Patient wird in Terminen/OPs als `patient_id: int` gespeichert
    - Dadurch bleibt das Schema robust und unabhängig (auch ohne Cross-DB-Setup)

2. **Migrationen**
    - Migrationen laufen auf `default`: `python manage.py migrate --database=default`

### Beispiel: Patient-Referenz

```python
# ❌ FALSCH (Cross-DB FK nicht möglich)
class Appointment(models.Model):
    patient = models.ForeignKey('patients.Patient', ...)  # nicht vorgesehen

# ✅ RICHTIG
class Appointment(models.Model):
    patient_id = models.IntegerField()  # Nur ID, kein FK
```

---

## Scheduling-Engine (Kernkomponente)

**Datei**: `praxi_backend/appointments/services/scheduling.py`

### Zweck

Zentrale Logik für:
- Konfliktprüfung (Termine, OPs, Ressourcen)
- Arbeitszeiten-Validierung
- Abwesenheits-/Pausenprüfung
- Verfügbarkeitsprüfung
- Termin-/OP-Planung

### Architektur-Regeln (aus Code-Kommentaren)

```
Architecture Rules:
- All DB access uses .using('default')
- patient_id is always an integer (not a FK)
- All exceptions are custom types from appointments.exceptions
- Views translate exceptions to appropriate DRF responses
```

### Hauptfunktionen

#### 1. Konfliktprüfung

```python
# Termin-Konflikte prüfen
conflicts = check_appointment_conflicts(
    date=date,
    start_time=start_time,
    end_time=end_time,
    doctor_id=doctor_id,
    room_id=room_id,
    resource_ids=[...],
    exclude_appointment_id=appointment_id,  # Für Updates
)

# Operation-Konflikte prüfen
conflicts = check_operation_conflicts(
    date=date,
    start_time=start_time,
    end_time=end_time,
    primary_surgeon_id=...,
    assistant_id=...,
    anesthesist_id=...,
    room_id=...,
    device_ids=[...],
    exclude_operation_id=operation_id,
)

# Patient-Konflikte prüfen
conflicts = check_patient_conflicts(
    patient_id=patient_id,
    start_time=start_time,
    end_time=end_time,
    exclude_appointment_id=...,
    exclude_operation_id=...,
)
```

**Geprüfte Konflikte**:
- Arzt hat überlappende Termine/OPs
- Raum ist bereits belegt (Termin oder OP)
- Gerät ist bereits belegt
- Patient hat bereits Termin/OP zur gleichen Zeit

#### 2. Validierung

```python
# Arbeitszeiten prüfen
validate_working_hours(
    date=date,
    start_time=start_time,
    end_time=end_time,
    doctor_id=doctor_id,
)
# Raises: WorkingHoursViolation

# Abwesenheiten prüfen
validate_doctor_absences(
    date=date,
    doctor_id=doctor_id,
    start_time=start_time,
    end_time=end_time,
)
# Raises: DoctorAbsentError

# Pausen prüfen
validate_doctor_breaks(
    date=date,
    start_time=start_time,
    end_time=end_time,
    doctor_id=doctor_id,
)
# Raises: DoctorBreakConflict
```

#### 3. Planung (High-Level)

```python
# Termin planen (mit vollständiger Validierung)
appointment = plan_appointment(
    data={
        'patient_id': 123,
        'doctor_id': 5,
        'start_time': datetime(...),
        'end_time': datetime(...),
        'type_id': 1,
        'resource_ids': [10, 11],
        'status': 'scheduled',
        'notes': '...',
    },
    user=request.user,
    skip_conflict_check=False,  # Normalerweise False
)

# Operation planen
operation = plan_operation(
    data={
        'patient_id': 123,
        'primary_surgeon_id': 5,
        'assistant_id': 6,
        'anesthesist_id': 7,
        'op_room_id': 10,
        'op_type_id': 2,
        'start_time': datetime(...),
        'op_device_ids': [20, 21],
        'status': 'planned',
        'notes': '...',
    },
    user=request.user,
    skip_conflict_check=False,
)
```

**Was passiert intern**:
1. Datenvalidierung (required fields, Zeiten)
2. Arbeitszeiten-Validierung
3. Abwesenheitsprüfung
4. Pausenprüfung
5. Konfliktprüfung (Arzt, Raum, Gerät, Patient)
6. Erstellung des Objekts
7. Audit-Log (`log_patient_action`)

#### 4. Verfügbarkeitsprüfung (Non-Exception)

```python
# Arzt verfügbar?
available = check_doctor_availability(
    start_time=...,
    end_time=...,
    doctor_id=...,
    exclude_appointment_id=...,
)
# Returns: bool (keine Exception!)

# Raum verfügbar?
available = check_room_availability(
    start_time=...,
    end_time=...,
    room_id=...,
    exclude_appointment_id=...,
    exclude_operation_id=...,
)

# Verfügbare Ärzte/Räume
doctors = get_available_doctors(start_time=..., end_time=...)
rooms = get_available_rooms(start_time=..., end_time=...)
```

### Custom Exceptions

Alle Exceptions sind in `praxi_backend/appointments/exceptions.py`:

- `InvalidSchedulingData` - Ungültige Eingabedaten
- `WorkingHoursViolation` - Außerhalb der Arbeitszeiten
- `DoctorAbsentError` - Arzt ist abwesend
- `DoctorBreakConflict` - Überschneidung mit Pause
- `SchedulingConflictError` - Konflikt mit anderem Termin/OP

**Verwendung in Views**:
```python
from praxi_backend.appointments.exceptions import SchedulingConflictError

try:
    appointment = plan_appointment(data, user)
except SchedulingConflictError as e:
    return Response(
        {'conflicts': [c.to_dict() for c in e.conflicts]},
        status=status.HTTP_409_CONFLICT,
    )
```

---

## API-Struktur

### URL-Pattern

```
/api/
├── auth/                    # Core (Login, Refresh, Me)
├── health/                  # Healthcheck
├── appointments/            # Termine
│   ├── suggest/             # Terminvorschläge
│   └── <id>/                # Detail
├── appointment-types/        # Terminarten
├── operations/               # Operationen
│   ├── suggest/              # OP-Vorschläge
│   └── <id>/                 # Detail
├── operation-types/          # OP-Typen
├── calendar/                 # Kalender (day/week/month)
├── practice-hours/           # Praxisöffnungszeiten
├── doctor-hours/             # Arzt-Arbeitszeiten
├── doctor-absences/         # Abwesenheiten
├── doctor-breaks/            # Pausen
├── resources/                # Räume & Geräte
├── resource-calendar/        # Ressourcen-Kalender
├── patient-flow/             # Patientenfluss
├── op-dashboard/             # OP-Dashboard
├── op-timeline/              # OP-Timeline
├── op-stats/                 # OP-Statistiken
└── patients/                 # Patienten-Stammdaten
```

### Request/Response-Beispiel

**Termin erstellen**:
```http
POST /api/appointments/
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
  "patient_id": 123,
  "doctor_id": 5,
  "start_time": "2024-01-15T10:00:00Z",
  "end_time": "2024-01-15T10:30:00Z",
  "type_id": 1,
  "resource_ids": [10],
  "notes": "Kontrolle"
}
```

**Response (Success)**:
```json
{
  "id": 42,
  "patient_id": 123,
  "doctor": {
    "id": 5,
    "username": "dr.smith",
    "full_name": "Dr. Smith"
  },
  "start_time": "2024-01-15T10:00:00Z",
  "end_time": "2024-01-15T10:30:00Z",
  "type": {
    "id": 1,
    "name": "Kontrolle",
    "color": "#2E8B57"
  },
  "status": "scheduled",
  "resources": [...],
  "created_at": "..."
}
```

**Response (Conflict)**:
```json
{
  "detail": "Scheduling conflict detected",
  "conflicts": [
    {
      "type": "doctor_conflict",
      "model": "Appointment",
      "id": 41,
      "message": "Doctor has overlapping appointment #41"
    }
  ]
}
```

### Paginierung

Die meisten List-Endpunkte sind paginiert:
```json
{
  "count": 150,
  "next": "http://.../api/appointments/?page=2",
  "previous": null,
  "results": [...]
}
```

---

## Sicherheit & Berechtigungen (RBAC)

### Rollen

| Rolle | Beschreibung | Zugriff |
|-------|--------------|---------|
| `admin` | Praxis-Admin/Leitung | Vollzugriff (CRUD) |
| `assistant` | MFA/Assistenz | Termine/Ressourcen pflegen, OP-Planung |
| `doctor` | Arzt | Eigene Termine/OPs (eingeschränkt) |
| `billing` | Abrechnung | Meist read-only |
| `nurse` | Pflege | Je nach Endpoint |

### Permission-Pattern

**Beispiel**: `AppointmentPermission`

```python
class AppointmentPermission(BasePermission):
    read_roles = ['admin', 'assistant', 'doctor', 'billing', 'nurse']
    write_roles = ['admin', 'assistant']
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        role_name = request.user.role.name if request.user.role else None
        
        if request.method in SAFE_METHODS:
            return role_name in self.read_roles
        return role_name in self.write_roles
    
    def has_object_permission(self, request, view, obj):
        # Arzt darf nur eigene Termine ändern
        if request.user.role.name == 'doctor':
            if request.method not in SAFE_METHODS:
                return obj.doctor_id == request.user.id
        return True
```

**Verwendung in Views**:
```python
class AppointmentListCreateView(generics.ListCreateAPIView):
    permission_classes = [AppointmentPermission]
    # ...
```

### Audit-Logging

Alle patientenbezogenen Aktionen werden protokolliert:

```python
from praxi_backend.core.utils import log_patient_action

# In View nach erfolgreicher Aktion
log_patient_action(
    user=request.user,
    action='appointment_create',
    patient_id=appointment.patient_id,
    meta={'appointment_id': appointment.id}
)
```

**AuditLog-Felder**:
- `user` - Wer hat die Aktion durchgeführt
- `role_name` - Rolle zum Zeitpunkt der Aktion
- `action` - Aktion (z.B. 'appointment_create', 'operation_update')
- `patient_id` - Betroffener Patient
- `timestamp` - Zeitpunkt
- `meta` - Zusätzliche Daten (JSON)

---

## Entwicklungsworkflow

### Lokale Entwicklung (Windows/DEV)

1. **Virtuelle Umgebung aktivieren**
   ```bash
   # .venv/ sollte bereits existieren
   .venv\Scripts\activate
   ```

2. **Dependencies installieren**
   ```bash
   pip install -r praxi_backend/requirements.txt
   ```

3. **Datenbank migrieren**
   ```bash
    python manage.py migrate --database=default
   ```

4. **Server starten**
   ```bash
   python manage.py runserver
   ```

5. **Testdaten erstellen (optional)**
   ```bash
   python manage.py seed  # Falls vorhanden
   ```

### Wichtige Management-Commands

```bash
# Migrationen erstellen
python manage.py makemigrations

# Migrationen anwenden
python manage.py migrate

# Superuser erstellen
python manage.py createsuperuser

# Shell (mit DB-Zugriff)
python manage.py shell

# Tests ausführen
python manage.py test
```

### Code-Standards

1. **Imports**: Vollqualifiziert
   ```python
   # ✅ RICHTIG
   from praxi_backend.appointments.models import Appointment
   
   # ❌ FALSCH (in Produktivcode)
   from appointments.models import Appointment
   ```

2. **DB-Zugriff**: Bei kritischen Querysets explizit `.using('default')`
   ```python
   # ✅ RICHTIG
   Appointment.objects.using('default').filter(...)
   ```

3. **Exceptions**: Custom Exceptions aus `appointments.exceptions`
   ```python
   from praxi_backend.appointments.exceptions import SchedulingConflictError
   ```

4. **Audit**: Patient-Aktionen protokollieren
   ```python
   log_patient_action(user, 'action_name', patient_id)
   ```

---

## Häufige Aufgaben & Troubleshooting

### 1. Neuen Endpoint hinzufügen

**Schritte**:
1. Model in `models.py` definieren (falls nötig)
2. Serializer in `serializers.py` erstellen
3. Permission in `permissions.py` definieren
4. View in `views.py` erstellen
5. URL in `urls.py` registrieren
6. Migration erstellen (falls Model geändert)

**Beispiel**:
```python
# serializers.py
class MyResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MyResource
        fields = '__all__'

# views.py
class MyResourceListView(generics.ListCreateAPIView):
    queryset = MyResource.objects.using('default').all()
    serializer_class = MyResourceSerializer
    permission_classes = [MyResourcePermission]

# urls.py
path('my-resources/', MyResourceListView.as_view(), name='my_resources_list'),
```

### 2. Scheduling-Logik erweitern

**Wo**: `praxi_backend/appointments/services/scheduling.py`

**Beispiel: Neue Validierung hinzufügen**
```python
def validate_custom_rule(*, date: date, doctor_id: int) -> None:
    """Neue Validierungsregel."""
    # Prüfung durchführen
    if not condition_met:
        raise CustomSchedulingError(...)

# In plan_appointment() einfügen:
def plan_appointment(...):
    # ... bestehende Validierungen ...
    
    # Neue Validierung
    validate_custom_rule(date=appt_date, doctor_id=doctor_id)
    
    # ... Rest ...
```

### 3. Häufige Fehler

#### 403 Forbidden
- **Ursache**: JWT fehlt/ungültig oder Rolle hat keine Berechtigung
- **Lösung**: 
  - `Authorization: Bearer <token>` prüfen
  - Token erneuern: `POST /api/auth/refresh/`
  - Rolle in Permission-Klasse prüfen

#### 400 Bad Request
- **Ursache**: Ungültige Daten (z.B. `start_time >= end_time`)
- **Lösung**: Request-Body validieren, Serializer-Fehler prüfen

#### 409 Conflict (Scheduling)
- **Ursache**: Konflikt erkannt (Arzt/Raum/Gerät belegt)
- **Lösung**: `conflicts`-Array in Response prüfen, Zeit/Ressource ändern

#### "Doctor unavailable"
- **Ursache**: Keine `PracticeHours`/`DoctorHours` definiert
- **Lösung**: Arbeitszeiten für Praxis/Arzt anlegen

#### DB-Fehler (Patient-Referenzen)
- **Ursache**: Patient wird als ForeignKey modelliert oder inkonsistent referenziert
- **Lösung**: `patient_id: int` verwenden (Appointments/Operations speichern nur die ID)

### 4. Debugging

**Django Shell**:
```bash
python manage.py shell
```

```python
from praxi_backend.appointments.models import Appointment
from praxi_backend.appointments.services.scheduling import check_appointment_conflicts
from datetime import datetime, time

# Termine prüfen
appts = Appointment.objects.using('default').filter(doctor_id=5)
print(list(appts))

# Konflikte prüfen
conflicts = check_appointment_conflicts(
    date=date.today(),
    start_time=datetime(2024, 1, 15, 10, 0),
    end_time=datetime(2024, 1, 15, 10, 30),
    doctor_id=5,
)
print(conflicts)
```

**Logging**:
- Django-Logs: `settings.LOGGING` prüfen
- Audit-Logs: `AuditLog.objects.using('default').all()`

### 5. Tests

**Tests ausführen**:
```bash
# Alle Tests
python manage.py test

# Spezifische App
python manage.py test praxi_backend.appointments

# Spezifischer Test
python manage.py test praxi_backend.appointments.tests.test_scheduling_engine
```

**Test-Struktur**:
- `praxi_backend/appointments/tests/` - Umfangreiche Test-Suite
- `test_scheduling_engine.py` - Scheduling-Tests
- `test_conflicts.py` - Konfliktprüfung
- `test_working_hours_validation.py` - Arbeitszeiten

---

## Zusammenfassung: Wichtigste Punkte

1. **Single-DB**: PostgreSQL auf `default`
2. **Patient-ID**: Immer `int` (keine Patient-FKs in Appointments/Operations)
3. **Scheduling-Engine**: Zentrale Logik in `services/scheduling.py`
4. **RBAC**: Rollen steuern Zugriff (admin, assistant, doctor, billing)
5. **Audit**: `log_patient_action()` für patientenbezogene Aktionen
6. **Imports**: Vollqualifiziert (`praxi_backend.appointments.*`)
7. **DB-Zugriff**: `.using('default')` wo Routing explizit sein soll

---

## Weiterführende Dokumentation

- `README.md` - Hauptdokumentation
- `DEPLOYMENT.md` - Deployment-Checkliste
- `praxi_backend/appointments/SCHEDULING_OPTIMIZATION.md` - Scheduling-Optimierung
- `docs/ONBOARDING.md` - Entwickler-Onboarding (falls vorhanden)
- `docs/API_REFERENCE.md` - Detaillierte API-Referenz (falls vorhanden)

---

**Viel Erfolg beim Entwickeln! 🚀**

Bei Fragen: Code-Kommentare in `scheduling.py` und `models.py` sind sehr ausführlich und helfen beim Verständnis.
