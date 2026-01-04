"""
Chart-Daten-Generatoren für das Patienten-Dashboard.

Dieses Modul erzeugt Chart.js-kompatible Datenstrukturen für:
- Vitaldaten-Trends (Line Charts)
- Laborwert-Verlauf (Line Charts)
- Diagnose-Verteilung (Bar/Pie Charts)
- Termin-Timeline (Timeline)
- Medikationshistorie (Bar Chart)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from django.utils import timezone

from praxi_backend.appointments.models import Appointment

from .patient_kpis import (
    _generate_demo_labs,
    _generate_demo_vitals,
    _generate_demo_diagnoses,
    _generate_demo_medications,
    get_chronic_conditions,
)


# ============================================================================
# Vitaldaten-Charts
# ============================================================================

def get_blood_pressure_chart(patient_id: int) -> dict[str, Any]:
    """
    Generiert Blutdruck-Trend Chart (Systolisch/Diastolisch).
    """
    vitals = _generate_demo_vitals(patient_id)
    
    if not vitals:
        return {'labels': [], 'datasets': []}
    
    labels = [v['date'] for v in vitals]
    
    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'Systolisch',
                'data': [v['systolic'] for v in vitals],
                'borderColor': '#DC3545',
                'backgroundColor': 'rgba(220, 53, 69, 0.1)',
                'fill': False,
                'tension': 0.3,
            },
            {
                'label': 'Diastolisch',
                'data': [v['diastolic'] for v in vitals],
                'borderColor': '#007BFF',
                'backgroundColor': 'rgba(0, 123, 255, 0.1)',
                'fill': False,
                'tension': 0.3,
            },
        ],
        'reference_lines': [
            {'label': 'Systolisch Normal (max)', 'value': 140, 'color': '#FFC107'},
            {'label': 'Diastolisch Normal (max)', 'value': 90, 'color': '#FFC107'},
        ],
    }


def get_pulse_chart(patient_id: int) -> dict[str, Any]:
    """
    Generiert Puls-Trend Chart.
    """
    vitals = _generate_demo_vitals(patient_id)
    
    if not vitals:
        return {'labels': [], 'datasets': []}
    
    labels = [v['date'] for v in vitals]
    
    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'Puls (bpm)',
                'data': [v['pulse'] for v in vitals],
                'borderColor': '#E83E8C',
                'backgroundColor': 'rgba(232, 62, 140, 0.1)',
                'fill': True,
                'tension': 0.3,
            },
        ],
        'reference_lines': [
            {'label': 'Normal (max)', 'value': 100, 'color': '#FFC107'},
            {'label': 'Normal (min)', 'value': 60, 'color': '#FFC107'},
        ],
    }


def get_bmi_chart(patient_id: int) -> dict[str, Any]:
    """
    Generiert BMI-Trend Chart.
    """
    vitals = _generate_demo_vitals(patient_id)
    
    if not vitals:
        return {'labels': [], 'datasets': []}
    
    labels = [v['date'] for v in vitals]
    
    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'BMI',
                'data': [v['bmi'] for v in vitals],
                'borderColor': '#6F42C1',
                'backgroundColor': 'rgba(111, 66, 193, 0.1)',
                'fill': True,
                'tension': 0.3,
            },
        ],
        'reference_lines': [
            {'label': 'Übergewicht', 'value': 25, 'color': '#FFC107'},
            {'label': 'Adipositas', 'value': 30, 'color': '#DC3545'},
        ],
        'zones': [
            {'min': 0, 'max': 18.5, 'color': 'rgba(255, 193, 7, 0.1)', 'label': 'Untergewicht'},
            {'min': 18.5, 'max': 25, 'color': 'rgba(40, 167, 69, 0.1)', 'label': 'Normal'},
            {'min': 25, 'max': 30, 'color': 'rgba(255, 193, 7, 0.1)', 'label': 'Übergewicht'},
            {'min': 30, 'max': 50, 'color': 'rgba(220, 53, 69, 0.1)', 'label': 'Adipositas'},
        ],
    }


def get_spo2_chart(patient_id: int) -> dict[str, Any]:
    """
    Generiert SpO2-Trend Chart.
    """
    vitals = _generate_demo_vitals(patient_id)
    
    if not vitals:
        return {'labels': [], 'datasets': []}
    
    labels = [v['date'] for v in vitals]
    
    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'SpO2 (%)',
                'data': [v['spo2'] for v in vitals],
                'borderColor': '#20C997',
                'backgroundColor': 'rgba(32, 201, 151, 0.1)',
                'fill': True,
                'tension': 0.3,
            },
        ],
        'reference_lines': [
            {'label': 'Normal (min)', 'value': 95, 'color': '#FFC107'},
        ],
    }


def get_all_vitals_chart(patient_id: int) -> dict[str, Any]:
    """
    Kombiniertes Vitaldaten-Chart (normalisiert).
    """
    vitals = _generate_demo_vitals(patient_id)
    
    if not vitals:
        return {'labels': [], 'datasets': []}
    
    labels = [v['date'] for v in vitals]
    
    # Normalisierung auf 0-100 Skala für Vergleichbarkeit
    def normalize(values: list, min_val: float, max_val: float) -> list:
        return [
            round((v - min_val) / (max_val - min_val) * 100, 1) 
            for v in values
        ]
    
    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'Blutdruck (norm.)',
                'data': normalize([v['systolic'] for v in vitals], 80, 200),
                'borderColor': '#DC3545',
                'fill': False,
                'tension': 0.3,
            },
            {
                'label': 'Puls (norm.)',
                'data': normalize([v['pulse'] for v in vitals], 40, 120),
                'borderColor': '#E83E8C',
                'fill': False,
                'tension': 0.3,
            },
            {
                'label': 'BMI (norm.)',
                'data': normalize([v['bmi'] for v in vitals], 15, 40),
                'borderColor': '#6F42C1',
                'fill': False,
                'tension': 0.3,
            },
            {
                'label': 'SpO2 (norm.)',
                'data': normalize([v['spo2'] for v in vitals], 85, 100),
                'borderColor': '#20C997',
                'fill': False,
                'tension': 0.3,
            },
        ],
    }


# ============================================================================
# Laborwert-Charts
# ============================================================================

def get_lab_value_chart(patient_id: int, lab_key: str) -> dict[str, Any]:
    """
    Generiert Chart für einen einzelnen Laborwert über Zeit.
    """
    labs = _generate_demo_labs(patient_id)
    
    if not labs:
        return {'labels': [], 'datasets': []}
    
    # Labs sind chronologisch absteigend, umkehren
    labs = list(reversed(labs))
    
    labels = [lab['date'] for lab in labs]
    values = []
    normal_min = None
    normal_max = None
    unit = ''
    name = lab_key
    
    for lab in labs:
        lab_data = lab['values'].get(lab_key, {})
        values.append(lab_data.get('value'))
        if normal_min is None:
            normal_min = lab_data.get('normal_min')
            normal_max = lab_data.get('normal_max')
            unit = lab_data.get('unit', '')
            name = lab_data.get('name', lab_key)
    
    return {
        'labels': labels,
        'datasets': [
            {
                'label': f'{name} ({unit})',
                'data': values,
                'borderColor': '#007BFF',
                'backgroundColor': 'rgba(0, 123, 255, 0.1)',
                'fill': True,
                'tension': 0.3,
            },
        ],
        'reference_lines': [
            {'label': 'Normal (max)', 'value': normal_max, 'color': '#28A745'},
            {'label': 'Normal (min)', 'value': normal_min, 'color': '#28A745'},
        ] if normal_min is not None else [],
    }


def get_key_labs_chart(patient_id: int) -> dict[str, Any]:
    """
    Generiert Multi-Line Chart für wichtige Laborwerte.
    """
    labs = _generate_demo_labs(patient_id)
    
    if not labs:
        return {'labels': [], 'datasets': []}
    
    labs = list(reversed(labs))
    labels = [lab['date'] for lab in labs]
    
    key_labs = ['hba1c', 'crp', 'glucose']
    colors = ['#DC3545', '#FFC107', '#007BFF']
    
    datasets = []
    for lab_key, color in zip(key_labs, colors):
        values = []
        name = lab_key
        
        for lab in labs:
            lab_data = lab['values'].get(lab_key, {})
            values.append(lab_data.get('value'))
            if name == lab_key:
                name = lab_data.get('name', lab_key)
        
        datasets.append({
            'label': name,
            'data': values,
            'borderColor': color,
            'fill': False,
            'tension': 0.3,
        })
    
    return {
        'labels': labels,
        'datasets': datasets,
    }


def get_lab_status_summary(patient_id: int) -> dict[str, Any]:
    """
    Generiert Zusammenfassung der Laborwert-Stati für Ampel-Darstellung.
    """
    labs = _generate_demo_labs(patient_id)
    
    if not labs:
        return {'values': [], 'summary': {'green': 0, 'yellow': 0, 'red': 0}}
    
    latest = labs[0]
    values = []
    summary = {'green': 0, 'yellow': 0, 'red': 0}
    
    for key, lab_data in latest['values'].items():
        value = lab_data['value']
        normal_min = lab_data['normal_min']
        normal_max = lab_data['normal_max']
        
        tolerance = (normal_max - normal_min) * 0.2
        
        if normal_min <= value <= normal_max:
            status = 'green'
        elif value < normal_min:
            status = 'yellow' if value >= normal_min - tolerance else 'red'
        else:
            status = 'yellow' if value <= normal_max + tolerance else 'red'
        
        summary[status] += 1
        values.append({
            'key': key,
            'name': lab_data['name'],
            'value': value,
            'unit': lab_data['unit'],
            'status': status,
            'normal_range': f"{normal_min} - {normal_max}",
        })
    
    return {
        'date': latest['date'],
        'values': values,
        'summary': summary,
    }


# ============================================================================
# Diagnose-Charts
# ============================================================================

def get_diagnoses_by_severity_chart(patient_id: int) -> dict[str, Any]:
    """
    Generiert Chart für Diagnosen nach Schweregrad.
    """
    conditions = get_chronic_conditions(patient_id)
    
    by_severity = conditions['by_severity']
    
    return {
        'labels': ['Hoch', 'Mittel', 'Niedrig'],
        'datasets': [
            {
                'label': 'Diagnosen',
                'data': [
                    len(by_severity['high']),
                    len(by_severity['medium']),
                    len(by_severity['low']),
                ],
                'backgroundColor': ['#DC3545', '#FFC107', '#28A745'],
                'borderWidth': 0,
            },
        ],
    }


def get_diagnoses_timeline(patient_id: int) -> list[dict]:
    """
    Generiert Timeline-Daten für Diagnosen.
    """
    diagnoses = _generate_demo_diagnoses(patient_id)
    
    timeline = []
    for d in sorted(diagnoses, key=lambda x: x.get('diagnosed_date', ''), reverse=True):
        timeline.append({
            'date': d.get('diagnosed_date'),
            'icd': d.get('icd'),
            'name': d.get('name'),
            'chronic': d.get('chronic', False),
            'active': d.get('active', True),
            'severity': d.get('severity', 'low'),
            'severity_color': {
                'high': '#DC3545',
                'medium': '#FFC107',
                'low': '#28A745',
            }.get(d.get('severity', 'low')),
        })
    
    return timeline


# ============================================================================
# Termin-Charts
# ============================================================================

def get_appointment_history_chart(patient_id: int, months: int = 12) -> dict[str, Any]:
    """
    Generiert Chart für Terminhistorie nach Monat.
    """
    tz = timezone.get_current_timezone()
    now = timezone.now()
    start_date = now - timedelta(days=months * 30)
    
    appointments = Appointment.objects.using('default').filter(
        patient_id=patient_id,
        start_time__gte=start_date,
    ).order_by('start_time')
    
    # Gruppieren nach Monat
    monthly_data: dict[str, dict] = {}
    
    for appt in appointments:
        month_key = appt.start_time.strftime('%Y-%m')
        if month_key not in monthly_data:
            monthly_data[month_key] = {'completed': 0, 'cancelled': 0, 'no_show': 0}
        
        if appt.status == 'completed':
            monthly_data[month_key]['completed'] += 1
        elif appt.status == 'cancelled':
            monthly_data[month_key]['cancelled'] += 1
        elif appt.status == 'scheduled' and appt.start_time < now:
            monthly_data[month_key]['no_show'] += 1
    
    labels = sorted(monthly_data.keys())
    
    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'Wahrgenommen',
                'data': [monthly_data[m]['completed'] for m in labels],
                'backgroundColor': '#28A745',
            },
            {
                'label': 'Storniert',
                'data': [monthly_data[m]['cancelled'] for m in labels],
                'backgroundColor': '#6C757D',
            },
            {
                'label': 'No-Show',
                'data': [monthly_data[m]['no_show'] for m in labels],
                'backgroundColor': '#DC3545',
            },
        ],
    }


def get_appointment_timeline(patient_id: int, limit: int = 20) -> list[dict]:
    """
    Generiert Timeline-Daten für Termine.
    """
    tz = timezone.get_current_timezone()
    now = timezone.now()
    
    # Vergangene Termine
    past = Appointment.objects.using('default').filter(
        patient_id=patient_id,
        start_time__lt=now,
    ).order_by('-start_time')[:limit // 2]
    
    # Zukünftige Termine
    future = Appointment.objects.using('default').filter(
        patient_id=patient_id,
        start_time__gte=now,
    ).order_by('start_time')[:limit // 2]
    
    timeline = []
    
    for appt in future:
        timeline.append({
            'id': appt.id,
            'date': appt.start_time.isoformat(),
            'end_date': appt.end_time.isoformat(),
            'type': getattr(appt.type, 'name', 'Termin') if appt.type else 'Termin',
            'type_color': getattr(appt.type, 'color', '#007BFF') if appt.type else '#007BFF',
            'status': appt.status,
            'status_label': {
                'scheduled': 'Geplant',
                'confirmed': 'Bestätigt',
                'completed': 'Abgeschlossen',
                'cancelled': 'Storniert',
            }.get(appt.status, appt.status),
            'is_future': True,
            'doctor_name': appt.doctor.get_full_name() if appt.doctor else 'Unbekannt',
        })
    
    for appt in past:
        timeline.append({
            'id': appt.id,
            'date': appt.start_time.isoformat(),
            'end_date': appt.end_time.isoformat(),
            'type': getattr(appt.type, 'name', 'Termin') if appt.type else 'Termin',
            'type_color': getattr(appt.type, 'color', '#6C757D') if appt.type else '#6C757D',
            'status': appt.status,
            'status_label': {
                'scheduled': 'Nicht erschienen',
                'confirmed': 'Nicht erschienen',
                'completed': 'Abgeschlossen',
                'cancelled': 'Storniert',
            }.get(appt.status, appt.status),
            'is_future': False,
            'doctor_name': appt.doctor.get_full_name() if appt.doctor else 'Unbekannt',
        })
    
    return sorted(timeline, key=lambda x: x['date'], reverse=True)


# ============================================================================
# Medikations-Charts
# ============================================================================

def get_medication_compliance_chart(patient_id: int) -> dict[str, Any]:
    """
    Generiert Chart für Medikations-Compliance.
    """
    medications = _generate_demo_medications(patient_id)
    
    active_meds = [m for m in medications if m.get('active')]
    
    if not active_meds:
        return {'labels': [], 'datasets': []}
    
    labels = [m['name'] for m in active_meds]
    compliance_values = [m.get('compliance', 0) for m in active_meds]
    
    # Farben basierend auf Compliance
    colors = []
    for c in compliance_values:
        if c >= 90:
            colors.append('#28A745')
        elif c >= 75:
            colors.append('#20C997')
        elif c >= 60:
            colors.append('#FFC107')
        else:
            colors.append('#DC3545')
    
    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'Compliance (%)',
                'data': compliance_values,
                'backgroundColor': colors,
                'borderWidth': 0,
            },
        ],
    }


def get_medication_timeline(patient_id: int) -> list[dict]:
    """
    Generiert Timeline-Daten für Medikamente.
    """
    medications = _generate_demo_medications(patient_id)
    
    return sorted(medications, key=lambda x: x.get('start_date', ''), reverse=True)


# ============================================================================
# Sammelfunktionen
# ============================================================================

def get_all_patient_charts(patient_id: int) -> dict[str, Any]:
    """
    Sammelt alle Chart-Daten für einen Patienten.
    """
    return {
        'vitals': {
            'blood_pressure': get_blood_pressure_chart(patient_id),
            'pulse': get_pulse_chart(patient_id),
            'bmi': get_bmi_chart(patient_id),
            'spo2': get_spo2_chart(patient_id),
            'combined': get_all_vitals_chart(patient_id),
        },
        'labs': {
            'key_labs': get_key_labs_chart(patient_id),
            'status_summary': get_lab_status_summary(patient_id),
            'hba1c': get_lab_value_chart(patient_id, 'hba1c'),
            'crp': get_lab_value_chart(patient_id, 'crp'),
            'glucose': get_lab_value_chart(patient_id, 'glucose'),
        },
        'diagnoses': {
            'by_severity': get_diagnoses_by_severity_chart(patient_id),
            'timeline': get_diagnoses_timeline(patient_id),
        },
        'appointments': {
            'history': get_appointment_history_chart(patient_id),
            'timeline': get_appointment_timeline(patient_id),
        },
        'medications': {
            'compliance': get_medication_compliance_chart(patient_id),
            'timeline': get_medication_timeline(patient_id),
        },
    }
