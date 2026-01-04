# Scheduling-Engine Optimierungsanalyse

**Generiert:** 29. Dezember 2025  
**Projekt:** PraxiApp Backend  
**Analysierte Dateien:** ~6.000 Codezeilen

---

## Inhaltsverzeichnis

1. [Executive Summary](#1-executive-summary)
2. [Algorithmische Optimierungen](#2-algorithmische-optimierungen)
3. [Datenbank-Optimierungen](#3-datenbank-optimierungen)
4. [Architektur-Optimierungen](#4-architektur-optimierungen)
5. [Code-Optimierungen](#5-code-optimierungen)
6. [Performance-Optimierungen](#6-performance-optimierungen)
7. [Stabilitäts-Optimierungen](#7-stabilitäts-optimierungen)
8. [Priorisierte Empfehlungsliste](#8-priorisierte-empfehlungsliste)
9. [Konkrete Code-Beispiele](#9-konkrete-code-beispiele)
10. [Architekturverstöße](#10-architekturverstöße)
11. [Zukünftige Erweiterungen](#11-zukünftige-erweiterungen)

---

## 1. Executive Summary

### Aktuelle Situation

Die Scheduling-Engine ist funktional vollständig, hat jedoch erhebliche Performance-Probleme:

| Metrik | Aktuell | Optimal |
|--------|---------|---------|
| Queries für Terminvorschlag | 40-2.928 | 5-10 |
| Queries für Monatskalender | 1.200+ | 20-30 |
| Queries für OP-Vorschlag | 1.200-1.800 | 50-100 |
| Konfliktprüfung (Termin) | 6 Queries | 2 Queries |
| Konfliktprüfung (OP) | 14 Queries | 4 Queries |

### Hauptprobleme

1. **N+1 Query-Pattern** in `suggest_slots()` und Kalenderansichten
2. **Fehlende Composite-Indizes** für häufige Filterungen
3. **Serializer-Validierung in Schleifen** bei OP-Vorschlägen
4. **Lineare Overlap-Prüfung** statt sortierter Intervalle
5. **Keine Caching-Strategie** für statische Daten

---

## 2. Algorithmische Optimierungen

### 2.1 Reduktion der Datenbankabfragen

#### Problem: `suggest_slots()` macht 6-8 Queries pro Tag

**Aktuell (scheduling.py, Zeilen 82-127):**
```python
def suggest_slots(doctor, date, duration_minutes, ...):
    # Jeder Aufruf macht separate Queries
    practice_hours = list(PracticeHours.objects.using('default').filter(weekday=weekday)...)
    doctor_hours = list(DoctorHours.objects.using('default').filter(doctor=doctor, weekday=weekday)...)
    absent = DoctorAbsence.objects.using('default').filter(...).exists()
    existing = list(Appointment.objects.using('default').filter(...))
    break_rows = list(DoctorBreak.objects.using('default').filter(...))
    resource_rows = list(AppointmentResource.objects.using('default').filter(...))
```

**Optimiert:**
```python
def suggest_slots_optimized(doctor, date_range, duration_minutes, ...):
    """Batch-Load aller Daten für einen Datumsbereich."""
    start_date, end_date = date_range
    
    # EINE Query für alle Tage - Prefetch alles
    practice_hours_map = _build_practice_hours_cache()  # Cached
    
    doctor_hours_map = {
        dh.weekday: dh for dh in 
        DoctorHours.objects.using('default').filter(
            doctor=doctor, 
            weekday__in=range(7),
            active=True
        )
    }
    
    # Batch-Load für Datumsbereich
    absences = set(
        DoctorAbsence.objects.using('default').filter(
            doctor=doctor,
            start_date__lte=end_date,
            end_date__gte=start_date
        ).values_list('start_date', 'end_date')
    )
    
    existing_appointments = list(
        Appointment.objects.using('default').filter(
            doctor=doctor,
            date__range=(start_date, end_date),
            status__in=['scheduled', 'confirmed']
        ).select_related('appointment_type')
    )
    
    # Gruppierung nach Datum
    appts_by_date = defaultdict(list)
    for appt in existing_appointments:
        appts_by_date[appt.date].append(appt)
    
    # Jetzt iterieren OHNE weitere Queries
    for current_date in date_range_iterator(start_date, end_date):
        weekday = current_date.weekday()
        day_appts = appts_by_date.get(current_date, [])
        # ... Slot-Berechnung ohne DB-Zugriff
```

**Einsparung:** Von 8 Queries pro Tag auf 4 Queries für den gesamten Zeitraum.

---

### 2.2 Nutzung von QuerySets statt Python-Loops

#### Problem: Lineare Overlap-Prüfung in `overlaps_any()`

**Aktuell (scheduling.py, Zeilen 183-196):**
```python
def overlaps_any(candidate_start, candidate_end):
    for appt in existing:  # O(n)
        if appt.start_time < candidate_end and appt.end_time > candidate_start:
            return True
    return False
```

**Optimiert mit sortiertem Intervall-Ansatz:**
```python
from bisect import bisect_left, bisect_right

def build_sorted_intervals(appointments):
    """Erstellt sortierte Intervall-Listen für O(log n) Lookup."""
    intervals = sorted(
        [(appt.start_time, appt.end_time, appt.id) for appt in appointments],
        key=lambda x: x[0]
    )
    start_times = [i[0] for i in intervals]
    return intervals, start_times

def overlaps_any_optimized(candidate_start, candidate_end, intervals, start_times):
    """O(log n) Overlap-Prüfung statt O(n)."""
    # Finde alle Intervalle, die vor candidate_end starten
    right_idx = bisect_left(start_times, candidate_end)
    
    # Prüfe nur diese Kandidaten
    for i in range(right_idx):
        _, end_time, _ = intervals[i]
        if end_time > candidate_start:
            return True
    return False
```

**Komplexität:** Von O(n) auf O(log n + k) wobei k = überlappende Termine.

---

### 2.3 Optimierung der Konfliktprüfungs-Algorithmen

#### Problem: `check_appointment_conflict()` macht 6 separate Queries

**Aktuell (services/scheduling.py, Zeilen 86-182):**
```python
def check_appointment_conflict(doctor_id, date, start_time, end_time, ...):
    # Query 1: Doctor appointments
    doctor_appts = Appointment.objects.using('default').filter(doctor_id=doctor_id, ...)
    
    # Query 2: Doctor operations
    doctor_ops = Operation.objects.using('default').filter(
        Q(primary_surgeon_id=doctor_id) | Q(assistant_id=doctor_id) | Q(anesthesist_id=doctor_id), ...
    )
    
    # Query 3: Resources
    resources = Resource.objects.using('default').filter(id__in=all_resource_ids)
    
    # Query 4: AppointmentResource conflicts
    ar_conflicts = AppointmentResource.objects.using('default').filter(...)
    
    # Query 5: Operation room conflicts
    op_room_conflicts = Operation.objects.using('default').filter(...)
    
    # Query 6: OperationDevice conflicts
    od_conflicts = OperationDevice.objects.using('default').filter(...)
```

**Optimiert mit Combined Query:**
```python
def check_appointment_conflict_optimized(doctor_id, date, start_time, end_time, resource_ids=None, exclude_id=None):
    """Optimierte Konfliktprüfung mit 2 Queries statt 6."""
    from django.db.models import Q, Value, CharField
    from django.db.models.functions import Concat
    
    time_overlap = Q(
        date=date,
        start_time__lt=end_time,
        end_time__gt=start_time
    )
    
    exclude_filter = Q(id=exclude_id) if exclude_id else Q()
    
    # Query 1: Alle Termin-Konflikte in einer Query
    appointment_conflicts = Appointment.objects.using('default').filter(
        time_overlap
    ).filter(
        Q(doctor_id=doctor_id) |  # Arzt-Konflikt
        Q(id__in=AppointmentResource.objects.filter(
            resource_id__in=resource_ids or []
        ).values('appointment_id'))  # Ressourcen-Konflikt
    ).exclude(
        exclude_filter
    ).select_related('doctor', 'appointment_type').prefetch_related(
        'appointmentresource_set__resource'
    )
    
    # Query 2: Alle OP-Konflikte in einer Query
    operation_conflicts = Operation.objects.using('default').filter(
        date=date,
        start_time__lt=end_time,
        end_time__gt=start_time
    ).filter(
        Q(primary_surgeon_id=doctor_id) |
        Q(assistant_id=doctor_id) |
        Q(anesthesist_id=doctor_id) |
        Q(op_room_id__in=[r for r in (resource_ids or []) if Resource.objects.filter(id=r, type='room').exists()])
    ).select_related('primary_surgeon', 'op_room')
    
    return {
        'has_conflict': appointment_conflicts.exists() or operation_conflicts.exists(),
        'appointment_conflicts': list(appointment_conflicts),
        'operation_conflicts': list(operation_conflicts),
    }
```

**Einsparung:** Von 6 Queries auf 2 Queries.

---

### 2.4 Caching-Strategien (nur default-DB)

#### Problem: `PracticeHours` und `DoctorHours` werden ständig neu geladen

**Aktuell:** Jeder `suggest_slots()`-Aufruf lädt die gleichen statischen Daten.

**Optimiert mit Django Cache:**
```python
from django.core.cache import cache
from django.conf import settings

PRACTICE_HOURS_CACHE_KEY = 'scheduling:practice_hours:all'
DOCTOR_HOURS_CACHE_KEY_TEMPLATE = 'scheduling:doctor_hours:{doctor_id}'
CACHE_TIMEOUT = 300  # 5 Minuten

def get_practice_hours_cached():
    """Cached Practice Hours - ändern sich selten."""
    cached = cache.get(PRACTICE_HOURS_CACHE_KEY)
    if cached is not None:
        return cached
    
    practice_hours = {}
    for ph in PracticeHours.objects.using('default').filter(active=True):
        if ph.weekday not in practice_hours:
            practice_hours[ph.weekday] = []
        practice_hours[ph.weekday].append({
            'start': ph.start_time,
            'end': ph.end_time,
        })
    
    cache.set(PRACTICE_HOURS_CACHE_KEY, practice_hours, CACHE_TIMEOUT)
    return practice_hours

def get_doctor_hours_cached(doctor_id):
    """Cached Doctor Hours pro Arzt."""
    cache_key = DOCTOR_HOURS_CACHE_KEY_TEMPLATE.format(doctor_id=doctor_id)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    
    doctor_hours = {}
    for dh in DoctorHours.objects.using('default').filter(doctor_id=doctor_id, active=True):
        doctor_hours[dh.weekday] = {
            'start': dh.start_time,
            'end': dh.end_time,
        }
    
    cache.set(cache_key, doctor_hours, CACHE_TIMEOUT)
    return doctor_hours

def invalidate_hours_cache(doctor_id=None):
    """Cache invalidieren bei Änderungen."""
    cache.delete(PRACTICE_HOURS_CACHE_KEY)
    if doctor_id:
        cache.delete(DOCTOR_HOURS_CACHE_KEY_TEMPLATE.format(doctor_id=doctor_id))
```

**Nutzung in Views:**
```python
# In DoctorHoursViewSet.perform_update():
def perform_update(self, serializer):
    instance = serializer.save()
    invalidate_hours_cache(doctor_id=instance.doctor_id)
```

---

## 3. Datenbank-Optimierungen

### 3.1 Index-Vorschläge

#### Fehlende Indizes (models.py)

```python
# In praxi_backend/appointments/models.py

class Appointment(models.Model):
    # ... fields ...
    
    class Meta:
        ordering = ['-date', '-start_time', '-id']
        indexes = [
            # Primärer Index für Konfliktprüfung
            models.Index(fields=['doctor', 'date', 'start_time', 'end_time'], 
                        name='appt_doctor_date_time_idx'),
            # Index für Kalenderansichten
            models.Index(fields=['date', 'status'], 
                        name='appt_date_status_idx'),
            # Index für Patientenhistorie
            models.Index(fields=['patient_id', 'date'], 
                        name='appt_patient_date_idx'),
        ]


class Operation(models.Model):
    # ... fields ...
    
    class Meta:
        ordering = ['-date', '-start_time', '-id']
        indexes = [
            # Index für OP-Saal Planung
            models.Index(fields=['op_room', 'date', 'start_time', 'end_time'], 
                        name='op_room_date_time_idx'),
            # Index für Chirurgen-Planung
            models.Index(fields=['primary_surgeon', 'date'], 
                        name='op_surgeon_date_idx'),
            # Index für Team-Konflikte (Assistent/Anästhesist)
            models.Index(fields=['date', 'start_time', 'end_time'], 
                        name='op_date_time_idx'),
        ]


class DoctorAbsence(models.Model):
    # ... fields ...
    
    class Meta:
        indexes = [
            models.Index(fields=['doctor', 'start_date', 'end_date'], 
                        name='absence_doctor_dates_idx'),
        ]


class DoctorBreak(models.Model):
    # ... fields ...
    
    class Meta:
        indexes = [
            models.Index(fields=['doctor', 'date', 'start_time', 'end_time'], 
                        name='break_doctor_date_time_idx'),
        ]


class AppointmentResource(models.Model):
    # ... fields ...
    
    class Meta:
        indexes = [
            models.Index(fields=['resource', 'appointment'], 
                        name='apptres_resource_appt_idx'),
        ]


class OperationDevice(models.Model):
    # ... fields ...
    
    class Meta:
        indexes = [
            models.Index(fields=['device', 'operation'], 
                        name='opdev_device_op_idx'),
        ]
```

### 3.2 Composite-Indizes für Konfliktprüfungen

**Migration erstellen:**
```python
# 0011_add_scheduling_indexes.py

from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('appointments', '0010_alter_appointmentresource_id_alter_operation_id_and_more'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(
                fields=['doctor', 'date', 'start_time', 'end_time'],
                name='appt_conflict_check_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='operation',
            index=models.Index(
                fields=['op_room', 'date', 'start_time', 'end_time'],
                name='op_room_conflict_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='operation',
            index=models.Index(
                fields=['date', 'start_time', 'end_time'],
                name='op_time_overlap_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='doctorbreak',
            index=models.Index(
                fields=['doctor', 'date', 'start_time'],
                name='break_doctor_time_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='doctorabsence',
            index=models.Index(
                fields=['doctor', 'start_date', 'end_date'],
                name='absence_range_idx'
            ),
        ),
    ]
```

### 3.3 Query-Rewrites mit Q-Objekten

#### Problem: Mehrere separate Queries für Arzt-Verfügbarkeit

**Aktuell:**
```python
# 3 separate Queries
appts = Appointment.objects.filter(doctor=doctor, date=date)
breaks = DoctorBreak.objects.filter(doctor=doctor, date=date)
absences = DoctorAbsence.objects.filter(doctor=doctor, start_date__lte=date, end_date__gte=date)
```

**Optimiert mit UNION-ähnlicher Abfrage:**
```python
from django.db.models import Q, Value, CharField
from django.db.models.functions import Cast
from itertools import chain

def get_doctor_busy_periods(doctor_id, date):
    """Alle blockierten Zeiträume in EINER Query (Union über 3 Quellen)."""
    
    # Termine als Busy-Periods
    appt_busy = Appointment.objects.using('default').filter(
        doctor_id=doctor_id,
        date=date,
        status__in=['scheduled', 'confirmed']
    ).values('start_time', 'end_time').annotate(
        source=Value('appointment', CharField())
    )
    
    # Pausen als Busy-Periods
    break_busy = DoctorBreak.objects.using('default').filter(
        doctor_id=doctor_id,
        date=date
    ).values('start_time', 'end_time').annotate(
        source=Value('break', CharField())
    )
    
    # Union (in Python, da Django UNION kompliziert ist)
    busy_periods = list(chain(appt_busy, break_busy))
    
    # Abwesenheiten separat (Ganztags)
    is_absent = DoctorAbsence.objects.using('default').filter(
        doctor_id=doctor_id,
        start_date__lte=date,
        end_date__gte=date
    ).exists()
    
    return {
        'is_absent': is_absent,
        'busy_periods': sorted(busy_periods, key=lambda x: x['start_time'])
    }
```

---

## 4. Architektur-Optimierungen

### 4.1 Trennung von Validierungs- und Konfliktlogik

#### Problem: Serializer-Validierung enthält Konfliktlogik

**Aktuell (serializers.py):**
```python
class AppointmentCreateUpdateSerializer(serializers.ModelSerializer):
    def validate(self, data):
        # Konfliktprüfung direkt im Serializer
        conflicts = check_appointment_conflict(...)
        if conflicts['has_conflict']:
            raise ValidationError(...)
```

**Optimiert mit separater Service-Schicht:**
```python
# services/appointment_service.py
class AppointmentService:
    """Service-Klasse für Termin-Operationen."""
    
    @staticmethod
    def validate_appointment_data(data, exclude_id=None):
        """Reine Datenvalidierung ohne Konfliktprüfung."""
        errors = {}
        
        if data.get('end_time') <= data.get('start_time'):
            errors['end_time'] = 'Endzeit muss nach Startzeit liegen.'
        
        if data.get('duration_minutes', 0) <= 0:
            errors['duration_minutes'] = 'Dauer muss positiv sein.'
        
        return errors
    
    @staticmethod
    def check_conflicts(data, exclude_id=None):
        """Separate Konfliktprüfung."""
        return check_appointment_conflict(
            doctor_id=data['doctor'].id if hasattr(data['doctor'], 'id') else data['doctor'],
            date=data['date'],
            start_time=data['start_time'],
            end_time=data['end_time'],
            resource_ids=data.get('resource_ids'),
            exclude_id=exclude_id
        )
    
    @classmethod
    def create_appointment(cls, data, user):
        """Termin erstellen mit Validierung und Konfliktprüfung."""
        # 1. Datenvalidierung
        validation_errors = cls.validate_appointment_data(data)
        if validation_errors:
            raise ValidationError(validation_errors)
        
        # 2. Konfliktprüfung
        conflicts = cls.check_conflicts(data)
        if conflicts['has_conflict']:
            raise ConflictError(conflicts)
        
        # 3. Erstellen
        appointment = Appointment.objects.using('default').create(**data)
        
        # 4. Audit-Log
        log_patient_action(user, 'appointment_create', patient_id=data['patient_id'])
        
        return appointment
```

### 4.2 Vereinheitlichung der Fehlerbehandlung

**Neue Exception-Klassen:**
```python
# services/exceptions.py

class SchedulingException(Exception):
    """Basis-Exception für Scheduling-Fehler."""
    pass

class ConflictError(SchedulingException):
    """Konflikt bei Terminplanung."""
    def __init__(self, conflicts):
        self.conflicts = conflicts
        super().__init__(self._format_message())
    
    def _format_message(self):
        messages = []
        for conf in self.conflicts.get('details', []):
            messages.append(f"{conf['type']}: {conf['description']}")
        return '; '.join(messages) or 'Konflikt erkannt'

class WorkingHoursViolation(SchedulingException):
    """Termin außerhalb der Arbeitszeiten."""
    pass

class DoctorUnavailable(SchedulingException):
    """Arzt ist nicht verfügbar (Abwesenheit/Pause)."""
    pass

class ResourceConflict(SchedulingException):
    """Ressourcenkonflikt (Raum/Gerät)."""
    pass
```

### 4.3 Konsolidierung der Scheduling-Services

**Aktuelle Struktur:**
```
services/
├── __init__.py
├── scheduling_simulation.py     # Test-Infrastruktur
├── scheduling_benchmark.py      # Performance-Tests
└── scheduling_conflict_report.py # Reporting
```

**Optimierte Struktur:**
```
services/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── conflict_detection.py    # Konfliktprüfung
│   ├── slot_finding.py          # Slot-Suche
│   ├── availability.py          # Verfügbarkeitsprüfung
│   └── caching.py               # Cache-Strategien
├── appointment_service.py       # Termin-Service
├── operation_service.py         # OP-Service
├── testing/
│   ├── __init__.py
│   ├── simulation.py            # Simulationen
│   ├── benchmark.py             # Benchmarks
│   └── conflict_report.py       # Reports
└── exceptions.py                # Einheitliche Exceptions
```

---

## 5. Code-Optimierungen

### 5.1 Entfernen redundanter Logik

#### Problem: Doppelte Datumsvalidierung

**Aktuell:**
```python
# In scheduling.py
def suggest_slots(doctor, date, ...):
    if date < timezone.now().date():
        return []  # Validierung 1

# In views.py
class AppointmentSuggestView(APIView):
    def get(self, request):
        date = parse_date(request.query_params.get('date'))
        if date < timezone.now().date():
            return Response({'error': 'Datum in der Vergangenheit'}, status=400)  # Validierung 2
```

**Optimiert:**
```python
# services/validators.py
def validate_scheduling_date(date, allow_past=False):
    """Zentrale Datumsvalidierung."""
    if date is None:
        raise ValidationError({'date': 'Datum ist erforderlich.'})
    
    if not allow_past and date < timezone.now().date():
        raise ValidationError({'date': 'Datum darf nicht in der Vergangenheit liegen.'})
    
    return date

# Verwendung in Views und Services
from services.validators import validate_scheduling_date

date = validate_scheduling_date(request.query_params.get('date'))
```

### 5.2 Vereinfachung von Bedingungen

**Aktuell:**
```python
if practice_hours is not None and len(practice_hours) > 0:
    # ...
```

**Optimiert:**
```python
if practice_hours:  # Truthy-Check ist ausreichend
    # ...
```

### 5.3 Hilfsfunktionen für wiederkehrende Muster

```python
# services/utils.py

from datetime import datetime, time, timedelta
from typing import Tuple, List

def time_ranges_overlap(range1: Tuple[time, time], range2: Tuple[time, time]) -> bool:
    """Prüft ob zwei Zeitbereiche überlappen."""
    start1, end1 = range1
    start2, end2 = range2
    return start1 < end2 and end1 > start2

def merge_overlapping_intervals(intervals: List[Tuple[time, time]]) -> List[Tuple[time, time]]:
    """Führt überlappende Intervalle zusammen."""
    if not intervals:
        return []
    
    sorted_intervals = sorted(intervals, key=lambda x: x[0])
    merged = [sorted_intervals[0]]
    
    for start, end in sorted_intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    
    return merged

def time_to_minutes(t: time) -> int:
    """Konvertiert time zu Minuten seit Mitternacht."""
    return t.hour * 60 + t.minute

def minutes_to_time(minutes: int) -> time:
    """Konvertiert Minuten seit Mitternacht zu time."""
    return time(hour=minutes // 60, minute=minutes % 60)
```

### 5.4 Reduktion von Duplikaten

**Aktuell: Gleiche Filterlogik in mehreren Views:**
```python
# In CalendarDayView
qs = Appointment.objects.filter(
    date=date,
    status__in=['scheduled', 'confirmed', 'completed']
).select_related('doctor', 'appointment_type')

# In CalendarWeekView
qs = Appointment.objects.filter(
    date__range=(start, end),
    status__in=['scheduled', 'confirmed', 'completed']
).select_related('doctor', 'appointment_type')

# In CalendarMonthView
qs = Appointment.objects.filter(
    date__range=(start, end),
    status__in=['scheduled', 'confirmed', 'completed']
).select_related('doctor', 'appointment_type')
```

**Optimiert mit QuerySet-Manager:**
```python
# models.py
class AppointmentQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status__in=['scheduled', 'confirmed', 'completed'])
    
    def for_date(self, date):
        return self.filter(date=date)
    
    def for_date_range(self, start, end):
        return self.filter(date__range=(start, end))
    
    def with_relations(self):
        return self.select_related('doctor', 'appointment_type').prefetch_related(
            'appointmentresource_set__resource'
        )

class AppointmentManager(models.Manager):
    def get_queryset(self):
        return AppointmentQuerySet(self.model, using=self._db)
    
    def active(self):
        return self.get_queryset().active()

class Appointment(models.Model):
    # ... fields ...
    objects = AppointmentManager()

# Verwendung
Appointment.objects.using('default').active().for_date_range(start, end).with_relations()
```

---

## 6. Performance-Optimierungen

### 6.1 Basierend auf Benchmark-Analyse

| Funktion | Problem | Lösung | Einsparung |
|----------|---------|--------|------------|
| `suggest_slots()` | 8 Queries/Tag | Batch-Loading | -90% |
| `check_appointment_conflict()` | 6 Queries | Combined Query | -66% |
| `check_operation_conflict()` | 14 Queries | Batching | -71% |
| `availability_for_range()` loop | N×8 Queries | Prefetch | -95% |
| OP-Vorschlag Serializer-Loop | 120×15 Queries | Pre-Validierung | -99% |

### 6.2 Vorschläge zur Vorvalidierung

**Problem: Serializer-Validierung in Schleife (views.py, Zeilen 1865-1880):**
```python
while candidate < window_end_dt and len(suggestions) < limit:
    ser = OperationCreateUpdateSerializer(data=payload, context={'request': request})
    if ser.is_valid():  # Vollständige Validierung inkl. DB-Queries!
        suggestions.append(...)
    candidate = candidate + step
```

**Optimiert mit Pre-Validierung:**
```python
def suggest_operation_slots_optimized(request, operation_data, limit=3):
    """OP-Slots finden ohne Serializer in der Schleife."""
    
    # 1. Statische Validierung EINMAL vorab
    required_fields = ['primary_surgeon', 'op_room', 'duration_minutes']
    for field in required_fields:
        if field not in operation_data:
            raise ValidationError({field: 'Pflichtfeld'})
    
    # 2. Batch-Load aller relevanten Daten
    date_range = (operation_data['date'], operation_data['date'] + timedelta(days=30))
    
    room_bookings = Operation.objects.using('default').filter(
        op_room=operation_data['op_room'],
        date__range=date_range,
        status__in=['scheduled', 'in_progress']
    ).values('date', 'start_time', 'end_time')
    
    surgeon_bookings = get_doctor_busy_periods_batch(
        doctor_id=operation_data['primary_surgeon'],
        date_range=date_range
    )
    
    # 3. Slot-Suche OHNE DB-Queries
    suggestions = []
    for date in date_range_iterator(*date_range):
        free_slots = find_free_slots(
            date=date,
            duration=operation_data['duration_minutes'],
            room_bookings=room_bookings,
            surgeon_bookings=surgeon_bookings,
            working_hours=get_practice_hours_cached()
        )
        suggestions.extend(free_slots)
        if len(suggestions) >= limit:
            break
    
    # 4. Finale Validierung NUR für gefundene Slots
    validated_suggestions = []
    for slot in suggestions[:limit]:
        payload = {**operation_data, 'date': slot['date'], 'start_time': slot['start_time']}
        ser = OperationCreateUpdateSerializer(data=payload, context={'request': request})
        if ser.is_valid():
            validated_suggestions.append(slot)
    
    return validated_suggestions
```

### 6.3 Parallelisierung (falls sinnvoll)

**Hinweis:** Django ORM ist nicht thread-safe. Parallelisierung sollte nur mit Celery Tasks erfolgen.

```python
# Nur für SEHR große Operationen sinnvoll
from celery import group
from praxi_backend.appointments.tasks import find_slots_for_doctor

def find_slots_parallel(doctors, date_range, duration):
    """Parallele Slot-Suche für mehrere Ärzte via Celery."""
    job = group(
        find_slots_for_doctor.s(doctor.id, date_range, duration)
        for doctor in doctors
    )
    result = job.apply_async()
    return result.get(timeout=30)
```

**Empfehlung:** Parallelisierung erst bei >10 Ärzten und Monatsansichten sinnvoll.

---

## 7. Stabilitäts-Optimierungen

### 7.1 Verbesserung der Fehlerrobustheit

```python
# services/core/conflict_detection.py

from contextlib import contextmanager
import logging

logger = logging.getLogger('scheduling')

@contextmanager
def conflict_check_transaction():
    """Atomare Konfliktprüfung mit Rollback bei Fehlern."""
    from django.db import transaction
    try:
        with transaction.atomic(using='default'):
            yield
    except Exception as e:
        logger.error(f"Konfliktprüfung fehlgeschlagen: {e}", exc_info=True)
        raise SchedulingException(f"Konfliktprüfung nicht möglich: {e}")

def check_appointment_conflict_safe(doctor_id, date, start_time, end_time, **kwargs):
    """Robuste Konfliktprüfung mit Fehlerbehandlung."""
    try:
        with conflict_check_transaction():
            return check_appointment_conflict(doctor_id, date, start_time, end_time, **kwargs)
    except SchedulingException:
        raise
    except Exception as e:
        logger.exception("Unerwarteter Fehler bei Konfliktprüfung")
        # Fail-Safe: Im Zweifelsfall Konflikt annehmen
        return {'has_conflict': True, 'error': str(e)}
```

### 7.2 Edge-Case-Behandlung

```python
def validate_time_window(start_time, end_time, date=None):
    """Validiert Zeitfenster mit Edge-Cases."""
    if start_time is None or end_time is None:
        raise ValidationError("Start- und Endzeit sind erforderlich")
    
    if start_time >= end_time:
        raise ValidationError("Startzeit muss vor Endzeit liegen")
    
    # Edge-Case: Termin über Mitternacht
    if date and end_time < start_time:
        raise ValidationError("Termine über Mitternacht werden nicht unterstützt")
    
    # Edge-Case: Extrem lange Termine
    duration = datetime.combine(date or datetime.min.date(), end_time) - \
               datetime.combine(date or datetime.min.date(), start_time)
    if duration > timedelta(hours=12):
        logger.warning(f"Ungewöhnlich langer Termin: {duration}")

def validate_patient_id(patient_id):
    """Validiert patient_id (Integer, keine FK)."""
    if patient_id is None:
        raise ValidationError("patient_id ist erforderlich")
    
    if not isinstance(patient_id, int):
        try:
            patient_id = int(patient_id)
        except (TypeError, ValueError):
            raise ValidationError("patient_id muss eine Ganzzahl sein")
    
    if patient_id <= 0:
        raise ValidationError("patient_id muss positiv sein")
    
    return patient_id
```

### 7.3 Deterministisches Verhalten

```python
def suggest_slots_deterministic(doctor, date, duration_minutes, limit=5, **kwargs):
    """Deterministische Slot-Vorschläge mit konsistenter Sortierung."""
    slots = suggest_slots(doctor, date, duration_minutes, limit=limit * 2, **kwargs)
    
    # Konsistente Sortierung
    sorted_slots = sorted(slots, key=lambda s: (s['date'], s['start_time']))
    
    return sorted_slots[:limit]
```

### 7.4 Logging-Strategie

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'scheduling': {
            'format': '[{asctime}] {levelname} scheduling.{module}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'scheduling_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/scheduling.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'scheduling',
        },
    },
    'loggers': {
        'scheduling': {
            'handlers': ['scheduling_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Verwendung
import logging
logger = logging.getLogger('scheduling')

def suggest_slots(doctor, date, duration_minutes, **kwargs):
    logger.info(f"Slot-Suche: doctor={doctor.id}, date={date}, duration={duration_minutes}")
    try:
        slots = _suggest_slots_internal(doctor, date, duration_minutes, **kwargs)
        logger.info(f"Gefunden: {len(slots)} Slots")
        return slots
    except Exception as e:
        logger.exception(f"Slot-Suche fehlgeschlagen")
        raise
```

---

## 8. Priorisierte Empfehlungsliste

### 🔴 HOCH: Sofort optimieren

| # | Optimierung | Datei | Impact | Aufwand |
|---|-------------|-------|--------|---------|
| 1 | Batch-Loading in `suggest_slots()` | scheduling.py | -90% Queries | 4h |
| 2 | Combined Query für Konfliktprüfung | services/scheduling.py | -66% Queries | 3h |
| 3 | Serializer aus OP-Vorschlag-Loop entfernen | views.py | -99% Queries | 4h |
| 4 | Composite-Indizes hinzufügen | models.py | -50% Query-Zeit | 1h |
| 5 | Cache für Practice/Doctor Hours | scheduling.py | -80% Queries | 2h |

### 🟡 MITTEL: Sollte optimiert werden

| # | Optimierung | Datei | Impact | Aufwand |
|---|-------------|-------|--------|---------|
| 6 | Sortierte Intervalle für Overlap-Prüfung | scheduling.py | O(log n) statt O(n) | 3h |
| 7 | QuerySet-Manager für Appointments | models.py | Code-Reduktion | 2h |
| 8 | Einheitliche Exception-Klassen | services/exceptions.py | Wartbarkeit | 2h |
| 9 | Batch-Load in Kalender-Views | views.py | -60% Queries | 4h |
| 10 | Zentrale Validierungsfunktionen | services/validators.py | Code-Reduktion | 2h |

### 🟢 NIEDRIG: Kann später optimiert werden

| # | Optimierung | Datei | Impact | Aufwand |
|---|-------------|-------|--------|---------|
| 11 | Service-Schicht-Refactoring | services/ | Architektur | 8h |
| 12 | Logging-Strategie implementieren | settings.py | Debugging | 2h |
| 13 | Parallelisierung mit Celery | tasks.py | Skalierbarkeit | 8h |
| 14 | Prefetch für Resource-Relations | views.py | -20% Queries | 2h |
| 15 | Time-Utility-Funktionen | services/utils.py | Lesbarkeit | 1h |

---

## 9. Konkrete Code-Beispiele

### 9.1 Vorher/Nachher: Batch-Loading

**VORHER (scheduling.py):**
```python
def availability_for_range(doctor, start_date, end_date, duration_minutes, ...):
    results = []
    current = start_date
    while current <= end_date:
        # 8 Queries pro Tag!
        day_slots = suggest_slots(doctor, current, duration_minutes, ...)
        results.append({'date': current, 'slots': day_slots})
        current += timedelta(days=1)
    return results
```

**NACHHER:**
```python
def availability_for_range_optimized(doctor, start_date, end_date, duration_minutes, ...):
    # 1. Batch-Load ALLER Daten (4 Queries total)
    context = AvailabilityContext(doctor, start_date, end_date)
    context.load_all()
    
    results = []
    current = start_date
    while current <= end_date:
        # 0 Queries - alles aus dem Context
        day_slots = find_slots_from_context(context, current, duration_minutes)
        results.append({'date': current, 'slots': day_slots})
        current += timedelta(days=1)
    
    return results

class AvailabilityContext:
    def __init__(self, doctor, start_date, end_date):
        self.doctor = doctor
        self.start_date = start_date
        self.end_date = end_date
        
    def load_all(self):
        # Query 1: Practice Hours (cached)
        self.practice_hours = get_practice_hours_cached()
        
        # Query 2: Doctor Hours
        self.doctor_hours = {
            dh.weekday: dh for dh in
            DoctorHours.objects.using('default').filter(
                doctor=self.doctor, active=True
            )
        }
        
        # Query 3: Absences
        self.absences = list(DoctorAbsence.objects.using('default').filter(
            doctor=self.doctor,
            start_date__lte=self.end_date,
            end_date__gte=self.start_date
        ))
        
        # Query 4: Appointments + Breaks in einem Batch
        self.appointments_by_date = self._group_by_date(
            Appointment.objects.using('default').filter(
                doctor=self.doctor,
                date__range=(self.start_date, self.end_date),
                status__in=['scheduled', 'confirmed']
            )
        )
        
        self.breaks_by_date = self._group_by_date(
            DoctorBreak.objects.using('default').filter(
                doctor=self.doctor,
                date__range=(self.start_date, self.end_date)
            )
        )
    
    def _group_by_date(self, queryset):
        from collections import defaultdict
        grouped = defaultdict(list)
        for obj in queryset:
            grouped[obj.date].append(obj)
        return grouped
```

### 9.2 Vorher/Nachher: Konfliktprüfung

**VORHER (6 Queries):**
```python
def check_appointment_conflict(doctor_id, date, start_time, end_time, resource_ids=None, exclude_id=None):
    conflicts = []
    
    # Query 1
    doctor_appts = Appointment.objects.using('default').filter(
        doctor_id=doctor_id, date=date,
        start_time__lt=end_time, end_time__gt=start_time,
        status__in=['scheduled', 'confirmed']
    )
    if exclude_id:
        doctor_appts = doctor_appts.exclude(id=exclude_id)
    
    # Query 2
    doctor_ops = Operation.objects.using('default').filter(
        Q(primary_surgeon_id=doctor_id) | Q(assistant_id=doctor_id) | Q(anesthesist_id=doctor_id),
        date=date, start_time__lt=end_time, end_time__gt=start_time
    )
    
    # ... 4 weitere Queries für Ressourcen
```

**NACHHER (2 Queries):**
```python
def check_appointment_conflict_v2(doctor_id, date, start_time, end_time, resource_ids=None, exclude_id=None):
    """Optimierte Konfliktprüfung mit 2 Queries."""
    from django.db.models import Q, Exists, OuterRef
    
    time_overlap = Q(date=date, start_time__lt=end_time, end_time__gt=start_time)
    active_status = Q(status__in=['scheduled', 'confirmed'])
    
    # Query 1: Alle Termin-bezogenen Konflikte
    appointment_conflict_q = Appointment.objects.using('default').filter(
        time_overlap & active_status
    ).filter(
        Q(doctor_id=doctor_id) |  # Arzt doppelt gebucht
        Q(appointmentresource__resource_id__in=resource_ids or [])  # Ressource belegt
    )
    
    if exclude_id:
        appointment_conflict_q = appointment_conflict_q.exclude(id=exclude_id)
    
    appt_conflicts = list(appointment_conflict_q.select_related(
        'doctor', 'appointment_type'
    ).prefetch_related('appointmentresource_set__resource').distinct())
    
    # Query 2: Alle OP-bezogenen Konflikte
    room_ids = [r for r in (resource_ids or []) 
                if Resource.objects.filter(id=r, type='room').exists()]
    
    operation_conflict_q = Operation.objects.using('default').filter(
        date=date, start_time__lt=end_time, end_time__gt=start_time
    ).filter(
        Q(primary_surgeon_id=doctor_id) |
        Q(assistant_id=doctor_id) |
        Q(anesthesist_id=doctor_id) |
        Q(op_room_id__in=room_ids)
    )
    
    op_conflicts = list(operation_conflict_q.select_related(
        'primary_surgeon', 'op_room'
    ))
    
    return {
        'has_conflict': bool(appt_conflicts or op_conflicts),
        'appointment_conflicts': appt_conflicts,
        'operation_conflicts': op_conflicts,
    }
```

### 9.3 Vorher/Nachher: OP-Vorschlag

**VORHER (1800 Queries für 3 Slots):**
```python
def suggest_operation_slots(request, ...):
    suggestions = []
    candidate = start_datetime
    
    while candidate < window_end and len(suggestions) < limit:
        payload = {..., 'start_time': candidate.time()}
        ser = OperationCreateUpdateSerializer(data=payload, context={'request': request})
        
        if ser.is_valid():  # 15+ Queries!
            suggestions.append({'start_time': candidate.time(), ...})
        
        candidate += timedelta(minutes=5)
    
    return suggestions
```

**NACHHER (50 Queries für 3 Slots):**
```python
def suggest_operation_slots_v2(request, op_data, limit=3):
    # 1. Pre-Load (5 Queries)
    context = OperationSlotContext(op_data)
    context.load()
    
    # 2. Slot-Suche ohne DB (0 Queries)
    potential_slots = []
    for slot in context.iterate_slots():
        if context.is_slot_available(slot):
            potential_slots.append(slot)
            if len(potential_slots) >= limit * 3:  # Buffer
                break
    
    # 3. Finale Validierung nur für Kandidaten (limit × 15 Queries)
    validated = []
    for slot in potential_slots:
        if len(validated) >= limit:
            break
        
        ser = OperationCreateUpdateSerializer(
            data={**op_data, 'start_time': slot['start_time']},
            context={'request': request}
        )
        if ser.is_valid():
            validated.append(slot)
    
    return validated
```

---

## 10. Architekturverstöße

### 10.1 Erkannte Verstöße

| # | Verstoß | Datei | Regel | Schwere |
|---|---------|-------|-------|---------|
| 1 | ForeignKey zu User ohne `.using('default')` in manchen QuerySets | views.py | DB-Routing | Mittel |
| 2 | Direkte Model-Queries statt Service-Layer | views.py | Separation of Concerns | Niedrig |
| 3 | Keine Audit-Logs bei manchen Patient-Aktionen | views.py | Audit-Logging | Hoch |
| 4 | Inkonsistente Fehlerbehandlung | diverse | Exception-Handling | Mittel |

### 10.2 Korrekturvorschläge

**Verstoß 1: DB-Routing**
```python
# FALSCH
User.objects.filter(role__name='doctor')

# RICHTIG
User.objects.using('default').filter(role__name='doctor')
```

**Verstoß 3: Fehlende Audit-Logs**
```python
# In jeder View, die patient_id verwendet
def perform_update(self, serializer):
    instance = serializer.save()
    log_patient_action(self.request.user, 'appointment_update', patient_id=instance.patient_id)
```

---

## 11. Zukünftige Erweiterungen

### 11.1 Empfohlene Erweiterungen

1. **Read-Through Cache für Kalender**
   - Redis-basierter Cache für Tages/Wochen-Ansichten
   - Invalidierung bei Termin-Änderungen

2. **Async Slot-Suche**
   - Celery-Task für Fallback-Arzt-Suche
   - WebSocket-Benachrichtigung wenn Slots gefunden

3. **Intelligente Slot-Priorisierung**
   - ML-basierte Vorhersage bevorzugter Zeiten
   - Berücksichtigung historischer Buchungsmuster

4. **Batch-Operationen**
   - Massenimport von Terminen
   - Optimierte Konfliktprüfung für Batches

### 11.2 Technische Schulden

| Bereich | Beschreibung | Aufwand |
|---------|--------------|---------|
| Test-Coverage | Mehr Edge-Case-Tests für Konfliktprüfung | 4h |
| Dokumentation | API-Dokumentation für Scheduling-Endpoints | 2h |
| Monitoring | Query-Count-Metriken in Production | 3h |
| Migrations | Index-Migrationen erstellen und testen | 2h |

---

## Zusammenfassung

Die Scheduling-Engine ist funktional robust, hat aber signifikante Performance-Probleme durch:

1. **N+1 Query-Patterns** in der Slot-Suche
2. **Fehlende Indizes** für häufige Filterungen
3. **Serializer-Validierung in Schleifen**
4. **Keine Caching-Strategie**

Die Top-5-Optimierungen würden die Query-Last um **80-90%** reduzieren und sollten innerhalb von **2 Sprints** umgesetzt werden.
