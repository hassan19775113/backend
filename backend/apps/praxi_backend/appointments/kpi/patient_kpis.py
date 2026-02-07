"""KPI-Berechnungen für das Patienten-Dashboard.

Moved 1:1 from `praxi_backend.dashboard.patient_kpis` in Phase 2F.
No logic changes intended.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from django.db.models import Count
from django.utils import timezone
from praxi_backend.appointments.models import Appointment
from praxi_backend.core.utils import timed_block
from praxi_backend.patients.models import Patient

logger = logging.getLogger(__name__)


# ============================================================================
# Demo-Daten für Vitaldaten, Laborwerte, Diagnosen
# In einer echten Anwendung würden diese aus der Datenbank kommen
# ============================================================================


def _generate_demo_vitals(patient_id: int, days: int = 90) -> list[dict]:
    """Generiert Demo-Vitaldaten für einen Patienten."""
    random.seed(patient_id + 1000)
    today = date.today()
    vitals = []

    # Basis-Werte mit leichter Variation
    base_systolic = random.randint(115, 145)
    base_diastolic = random.randint(70, 90)
    base_pulse = random.randint(60, 85)
    base_bmi = random.uniform(22, 32)
    base_temp = 36.5
    base_spo2 = random.randint(95, 99)

    for i in range(0, days, 7):  # Wöchentliche Messungen
        measurement_date = today - timedelta(days=days - i)
        vitals.append(
            {
                "date": measurement_date.isoformat(),
                "systolic": base_systolic + random.randint(-10, 10),
                "diastolic": base_diastolic + random.randint(-8, 8),
                "pulse": base_pulse + random.randint(-10, 15),
                "bmi": round(base_bmi + random.uniform(-0.5, 0.5), 1),
                "temperature": round(base_temp + random.uniform(-0.3, 0.8), 1),
                "spo2": min(100, base_spo2 + random.randint(-2, 2)),
            }
        )

    return vitals


def _generate_demo_labs(patient_id: int) -> list[dict]:
    """Generiert Demo-Laborwerte für einen Patienten."""
    random.seed(patient_id + 2000)
    today = date.today()

    labs = []
    lab_dates = [
        today - timedelta(days=7),
        today - timedelta(days=30),
        today - timedelta(days=90),
        today - timedelta(days=180),
    ]

    for lab_date in lab_dates:
        labs.append(
            {
                "date": lab_date.isoformat(),
                "values": {
                    "hba1c": {
                        "value": round(random.uniform(4.5, 8.5), 1),
                        "unit": "%",
                        "normal_min": 4.0,
                        "normal_max": 5.6,
                        "name": "HbA1c",
                    },
                    "crp": {
                        "value": round(random.uniform(0.1, 15.0), 1),
                        "unit": "mg/L",
                        "normal_min": 0,
                        "normal_max": 5.0,
                        "name": "CRP",
                    },
                    "creatinine": {
                        "value": round(random.uniform(0.6, 1.8), 2),
                        "unit": "mg/dL",
                        "normal_min": 0.7,
                        "normal_max": 1.2,
                        "name": "Kreatinin",
                    },
                    "hemoglobin": {
                        "value": round(random.uniform(11.0, 17.0), 1),
                        "unit": "g/dL",
                        "normal_min": 12.0,
                        "normal_max": 16.0,
                        "name": "Hämoglobin",
                    },
                    "leukocytes": {
                        "value": round(random.uniform(3.5, 12.0), 1),
                        "unit": "Tsd/µL",
                        "normal_min": 4.0,
                        "normal_max": 10.0,
                        "name": "Leukozyten",
                    },
                    "cholesterol": {
                        "value": random.randint(150, 280),
                        "unit": "mg/dL",
                        "normal_min": 0,
                        "normal_max": 200,
                        "name": "Cholesterin",
                    },
                    "triglycerides": {
                        "value": random.randint(80, 300),
                        "unit": "mg/dL",
                        "normal_min": 0,
                        "normal_max": 150,
                        "name": "Triglyceride",
                    },
                    "glucose": {
                        "value": random.randint(70, 180),
                        "unit": "mg/dL",
                        "normal_min": 70,
                        "normal_max": 100,
                        "name": "Glukose (nüchtern)",
                    },
                },
            }
        )

    return labs


def _generate_demo_diagnoses(patient_id: int) -> list[dict]:
    """Generiert Demo-Diagnosen für einen Patienten."""
    random.seed(patient_id + 3000)

    all_diagnoses = [
        {"icd": "I10", "name": "Arterielle Hypertonie", "chronic": True, "severity": "medium"},
        {"icd": "E11.9", "name": "Diabetes mellitus Typ 2", "chronic": True, "severity": "medium"},
        {
            "icd": "J06.9",
            "name": "Akute Infektion der oberen Atemwege",
            "chronic": False,
            "severity": "low",
        },
        {"icd": "M54.5", "name": "Kreuzschmerz", "chronic": False, "severity": "low"},
        {"icd": "E78.0", "name": "Hypercholesterinämie", "chronic": True, "severity": "low"},
        {
            "icd": "K21.0",
            "name": "Gastroösophageale Refluxkrankheit",
            "chronic": True,
            "severity": "low",
        },
        {
            "icd": "F32.1",
            "name": "Mittelgradige depressive Episode",
            "chronic": False,
            "severity": "medium",
        },
        {"icd": "G43.9", "name": "Migräne", "chronic": True, "severity": "low"},
        {"icd": "J45.9", "name": "Asthma bronchiale", "chronic": True, "severity": "medium"},
        {"icd": "N40", "name": "Prostatahyperplasie", "chronic": True, "severity": "low"},
    ]

    num_diagnoses = random.randint(1, 5)
    selected = random.sample(all_diagnoses, num_diagnoses)

    today = date.today()
    for diag in selected:
        diag["diagnosed_date"] = (today - timedelta(days=random.randint(30, 1000))).isoformat()
        diag["active"] = random.random() > 0.2

    return selected


def _generate_demo_medications(patient_id: int) -> list[dict]:
    """Generiert Demo-Medikationsplan für einen Patienten."""
    random.seed(patient_id + 4000)

    all_medications = [
        {"name": "Metoprolol 47,5mg", "dosage": "1-0-0", "indication": "Hypertonie"},
        {"name": "Ramipril 5mg", "dosage": "1-0-0", "indication": "Hypertonie"},
        {"name": "Metformin 1000mg", "dosage": "1-0-1", "indication": "Diabetes"},
        {"name": "Simvastatin 20mg", "dosage": "0-0-1", "indication": "Hypercholesterinämie"},
        {"name": "Pantoprazol 40mg", "dosage": "1-0-0", "indication": "Reflux"},
        {"name": "Ibuprofen 400mg", "dosage": "bei Bedarf", "indication": "Schmerzen"},
        {"name": "Salbutamol Spray", "dosage": "bei Bedarf", "indication": "Asthma"},
        {"name": "L-Thyroxin 75µg", "dosage": "1-0-0", "indication": "Hypothyreose"},
    ]

    num_meds = random.randint(0, 5)
    selected = random.sample(all_medications, num_meds)

    today = date.today()
    for med in selected:
        med["start_date"] = (today - timedelta(days=random.randint(30, 365))).isoformat()
        med["active"] = random.random() > 0.1
        med["compliance"] = random.randint(60, 100)

    return selected


def _generate_demo_documents(patient_id: int) -> list[dict]:
    """Generiert Demo-Dokumente für einen Patienten."""
    random.seed(patient_id + 6000)
    today = date.today()

    document_types = [
        ("Arztbrief", "Bericht"),
        ("Befund", "Bericht"),
        ("Laborbericht", "Bericht"),
        ("Röntgenbericht", "Bericht"),
        ("Überweisung", "Dokument"),
        ("AU-Bescheinigung", "Dokument"),
        ("Entlassungsbrief", "Bericht"),
    ]

    items = []
    for i in range(random.randint(2, 6)):
        title, kind = random.choice(document_types)
        days_ago = random.randint(3, 365)
        items.append(
            {
                "id": 100000 + i + 1,
                "title": title,
                "kind": kind,
                "date": (today - timedelta(days=days_ago)).isoformat(),
                "source": "Praxis",
                "url": None,
            }
        )

    items.sort(key=lambda x: x["date"], reverse=True)
    return items


def _generate_demo_prescriptions(patient_id: int) -> list[dict]:
    """Generiert Demo-Rezepte für einen Patienten."""
    random.seed(patient_id + 7000)
    today = date.today()

    meds = [
        "Metoprolol 47,5mg",
        "Ramipril 5mg",
        "Metformin 1000mg",
        "Ibuprofen 400mg",
        "Pantoprazol 40mg",
        "L-Thyroxin 75µg",
    ]

    items = []
    for i in range(random.randint(1, 4)):
        issued = today - timedelta(days=random.randint(10, 180))
        items.append(
            {
                "id": i + 1,
                "medication": random.choice(meds),
                "issued_at": issued.isoformat(),
                "valid_until": (issued + timedelta(days=90)).isoformat(),
                "status": "aktiv" if (today - issued).days <= 90 else "abgelaufen",
            }
        )

    items.sort(key=lambda x: x["issued_at"], reverse=True)
    return items


def _generate_demo_allergies(patient_id: int) -> list[str]:
    """Generiert Demo-Allergien für einen Patienten."""
    random.seed(patient_id + 5000)

    all_allergies = [
        "Penicillin",
        "Acetylsalicylsäure",
        "Iodhaltige Kontrastmittel",
        "Latex",
        "Sulfonamide",
        "Nüsse",
        "Pollen",
        "Hausstaubmilben",
    ]

    if random.random() > 0.6:
        num = random.randint(1, 3)
        return random.sample(all_allergies, num)
    return []


# ============================================================================
# Patientenstatus und Klassifikation
# ============================================================================


@dataclass
class PatientStatus:
    """Patientenstatus-Klassifikation."""

    status: str  # 'active', 'in_treatment', 'inactive', 'risk'
    label: str
    color: str
    icon: str


def calculate_patient_status(patient_id: int) -> PatientStatus:
    """Berechnet den aktuellen Status eines Patienten."""
    now = timezone.now()

    six_months_ago = now - timedelta(days=180)
    twelve_months_ago = now - timedelta(days=365)
    thirty_days_ago = now - timedelta(days=30)

    recent_appointments = (
        Appointment.objects.using("default")
        .filter(
            patient_id=patient_id,
            start_time__gte=six_months_ago,
            status__in=["completed", "confirmed", "scheduled"],
        )
        .count()
    )

    recent_30_days = (
        Appointment.objects.using("default")
        .filter(
            patient_id=patient_id,
            start_time__gte=thirty_days_ago,
            status__in=["completed", "confirmed", "scheduled"],
        )
        .count()
    )

    has_any_recent = (
        Appointment.objects.using("default")
        .filter(patient_id=patient_id, start_time__gte=twelve_months_ago)
        .exists()
    )

    risk_score = calculate_patient_risk_score(patient_id)

    if risk_score["score"] >= 70:
        return PatientStatus(status="risk", label="Risikopatient", color="#DC3545", icon="⚠️")

    if recent_30_days >= 3:
        return PatientStatus(
            status="in_treatment", label="In Behandlung", color="#FFC107", icon="🏥"
        )

    if recent_appointments > 0:
        return PatientStatus(status="active", label="Aktiv", color="#28A745", icon="✓")

    if not has_any_recent:
        return PatientStatus(status="inactive", label="Inaktiv", color="#6C757D", icon="○")

    return PatientStatus(status="active", label="Aktiv", color="#28A745", icon="✓")


# ============================================================================
# Risiko-Score Berechnung
# ============================================================================


def calculate_patient_risk_score(patient_id: int) -> dict[str, Any]:
    """Berechnet einen Risiko-Score."""
    profile = get_patient_profile(patient_id)
    try:
        age = int((profile or {}).get("age") or 50)
    except (TypeError, ValueError):
        age = 50

    score = 0
    factors = []

    # Alters-Risiko (max 20 Punkte)
    if age >= 75:
        score += 20
        factors.append({"name": "Alter ≥75", "points": 20, "severity": "high"})
    elif age >= 65:
        score += 12
        factors.append({"name": "Alter 65-74", "points": 12, "severity": "medium"})
    elif age >= 55:
        score += 5
        factors.append({"name": "Alter 55-64", "points": 5, "severity": "low"})

    # Chronische Erkrankungen (max 30 Punkte)
    diagnoses = _generate_demo_diagnoses(patient_id)
    chronic_count = sum(1 for d in diagnoses if d.get("chronic"))
    chronic_score = min(30, chronic_count * 10)
    if chronic_score > 0:
        score += chronic_score
        factors.append(
            {
                "name": f"{chronic_count} chronische Erkrankung(en)",
                "points": chronic_score,
                "severity": "high" if chronic_count >= 3 else "medium",
            }
        )

    # Vitaldaten-Risiko (max 25 Punkte)
    vitals = _generate_demo_vitals(patient_id)
    if vitals:
        latest = vitals[-1]

        if latest["systolic"] >= 160 or latest["diastolic"] >= 100:
            score += 15
            factors.append({"name": "Blutdruck stark erhöht", "points": 15, "severity": "high"})
        elif latest["systolic"] >= 140 or latest["diastolic"] >= 90:
            score += 8
            factors.append({"name": "Blutdruck erhöht", "points": 8, "severity": "medium"})

        if latest["bmi"] >= 35:
            score += 10
            factors.append(
                {"name": "BMI ≥35 (Adipositas Grad II+)", "points": 10, "severity": "high"}
            )
        elif latest["bmi"] >= 30:
            score += 5
            factors.append({"name": "BMI ≥30 (Adipositas)", "points": 5, "severity": "medium"})

    # Laborwert-Risiko (max 15 Punkte)
    labs = _generate_demo_labs(patient_id)
    if labs:
        latest_labs = labs[0]["values"]
        lab_risk = 0

        hba1c = latest_labs.get("hba1c", {}).get("value", 5.0)
        if hba1c >= 7.5:
            lab_risk += 8
            factors.append({"name": "HbA1c ≥7.5%", "points": 8, "severity": "high"})
        elif hba1c >= 6.5:
            lab_risk += 4
            factors.append({"name": "HbA1c erhöht", "points": 4, "severity": "medium"})

        crp = latest_labs.get("crp", {}).get("value", 1.0)
        if crp >= 10:
            lab_risk += 7
            factors.append({"name": "CRP stark erhöht", "points": 7, "severity": "high"})

        score += min(15, lab_risk)

    # No-Show Risiko (max 10 Punkte)
    now = timezone.now()
    year_ago = now - timedelta(days=365)

    flagged_no_shows = (
        Appointment.objects.using("default")
        .filter(
            patient_id=patient_id,
            start_time__gte=year_ago,
            start_time__lt=now,
            is_no_show=True,
        )
        .count()
    )
    fallback_no_shows = (
        Appointment.objects.using("default")
        .filter(
            patient_id=patient_id,
            start_time__gte=year_ago,
            start_time__lt=now,
            is_no_show=False,
            status__in=["scheduled", "confirmed"],
        )
        .count()
    )
    no_shows = flagged_no_shows + fallback_no_shows

    if no_shows >= 3:
        score += 10
        factors.append({"name": f"{no_shows} No-Shows", "points": 10, "severity": "high"})
    elif no_shows >= 1:
        score += 5
        factors.append({"name": f"{no_shows} No-Show(s)", "points": 5, "severity": "medium"})

    if score >= 70:
        level = "critical"
        level_label = "Kritisch"
        level_color = "#DC3545"
    elif score >= 50:
        level = "high"
        level_label = "Hoch"
        level_color = "#FD7E14"
    elif score >= 30:
        level = "medium"
        level_label = "Mittel"
        level_color = "#FFC107"
    else:
        level = "low"
        level_label = "Niedrig"
        level_color = "#28A745"

    return {
        "score": min(100, score),
        "level": level,
        "level_label": level_label,
        "level_color": level_color,
        "factors": factors,
    }


# ============================================================================
# Terminaktivität
# ============================================================================


def calculate_appointment_activity(patient_id: int) -> dict[str, Any]:
    """Berechnet Terminaktivität eines Patienten."""
    now = timezone.now()
    year_ago = now - timedelta(days=365)

    appointments = Appointment.objects.using("default").filter(
        patient_id=patient_id, start_time__gte=year_ago
    )

    past = appointments.filter(start_time__lt=now)
    future = appointments.filter(start_time__gte=now)

    completed = past.filter(status="completed").count()
    confirmed = past.filter(status="confirmed").count()
    cancelled = appointments.filter(status="cancelled").count()

    flagged_no_shows = past.filter(is_no_show=True).count()
    fallback_no_shows = past.filter(is_no_show=False, status__in=["scheduled", "confirmed"]).count()
    no_shows = flagged_no_shows + fallback_no_shows

    last_appointment = (
        Appointment.objects.using("default")
        .filter(patient_id=patient_id, start_time__lt=now, status="completed")
        .order_by("-start_time")
        .first()
    )

    next_appointment = (
        Appointment.objects.using("default")
        .filter(patient_id=patient_id, start_time__gte=now, status__in=["scheduled", "confirmed"])
        .order_by("start_time")
        .first()
    )

    days_since_last = None
    days_until_next = None

    if last_appointment:
        days_since_last = (now - last_appointment.start_time).days

    if next_appointment:
        days_until_next = (next_appointment.start_time - now).days

    return {
        "total_past": completed + confirmed,
        "completed": completed,
        "future": future.filter(status__in=["scheduled", "confirmed"]).count(),
        "no_shows": no_shows,
        "cancelled": cancelled,
        "last_appointment": {
            "date": last_appointment.start_time.isoformat() if last_appointment else None,
            "days_ago": days_since_last,
            "type": getattr(last_appointment.type, "name", "Termin") if last_appointment else None,
        },
        "next_appointment": {
            "date": next_appointment.start_time.isoformat() if next_appointment else None,
            "days_until": days_until_next,
            "type": getattr(next_appointment.type, "name", "Termin") if next_appointment else None,
        },
        "completion_rate": round(completed / max(1, completed + no_shows) * 100, 1),
    }


# ============================================================================
# Medikations-Compliance
# ============================================================================


def calculate_medication_compliance(patient_id: int) -> dict[str, Any]:
    """Berechnet Medikations-Compliance Score."""
    medications = _generate_demo_medications(patient_id)

    if not medications:
        return {
            "score": None,
            "label": "Keine Medikation",
            "color": "#6C757D",
            "medications": [],
            "active_count": 0,
        }

    active_meds = [m for m in medications if m.get("active")]

    if not active_meds:
        return {
            "score": None,
            "label": "Keine aktive Medikation",
            "color": "#6C757D",
            "medications": medications,
            "active_count": 0,
        }

    avg_compliance = sum(m.get("compliance", 80) for m in active_meds) / len(active_meds)

    if avg_compliance >= 90:
        label = "Ausgezeichnet"
        color = "#28A745"
    elif avg_compliance >= 75:
        label = "Gut"
        color = "#20C997"
    elif avg_compliance >= 60:
        label = "Mäßig"
        color = "#FFC107"
    else:
        label = "Unzureichend"
        color = "#DC3545"

    return {
        "score": round(avg_compliance, 1),
        "label": label,
        "color": color,
        "medications": medications,
        "active_count": len(active_meds),
    }


# ============================================================================
# Vitaldaten-Trends
# ============================================================================


def calculate_vital_trends(patient_id: int) -> dict[str, Any]:
    """Berechnet Vitaldaten-Trends und aktuelle Werte."""
    vitals = _generate_demo_vitals(patient_id)

    if not vitals or len(vitals) < 2:
        return {"current": None, "trends": {}, "history": vitals}

    current = vitals[-1]
    previous = vitals[-2]

    def calc_trend(key: str, lower_is_better: bool = True) -> dict:
        curr_val = current.get(key)
        prev_val = previous.get(key)

        if curr_val is None or prev_val is None:
            return {"direction": "stable", "icon": "→", "color": "#6C757D"}

        diff = curr_val - prev_val

        if abs(diff) < 0.5:
            return {"direction": "stable", "icon": "→", "color": "#6C757D"}

        if lower_is_better:
            if diff > 0:
                return {"direction": "up", "icon": "↑", "color": "#DC3545"}
            return {"direction": "down", "icon": "↓", "color": "#28A745"}
        else:
            if diff > 0:
                return {"direction": "up", "icon": "↑", "color": "#28A745"}
            return {"direction": "down", "icon": "↓", "color": "#DC3545"}

    trends = {
        "systolic": calc_trend("systolic", lower_is_better=True),
        "diastolic": calc_trend("diastolic", lower_is_better=True),
        "pulse": calc_trend("pulse", lower_is_better=True),
        "bmi": calc_trend("bmi", lower_is_better=True),
        "spo2": calc_trend("spo2", lower_is_better=False),
    }

    def evaluate_vital(_key: str, value: float, ranges: dict) -> dict:
        if value < ranges.get("low", float("-inf")):
            return {"status": "low", "label": "Niedrig", "color": "#FFC107"}
        if value > ranges.get("high", float("inf")):
            return {"status": "high", "label": "Erhöht", "color": "#DC3545"}
        return {"status": "normal", "label": "Normal", "color": "#28A745"}

    evaluations = {
        "systolic": evaluate_vital("systolic", current["systolic"], {"low": 90, "high": 140}),
        "diastolic": evaluate_vital("diastolic", current["diastolic"], {"low": 60, "high": 90}),
        "pulse": evaluate_vital("pulse", current["pulse"], {"low": 50, "high": 100}),
        "bmi": evaluate_vital("bmi", current["bmi"], {"low": 18.5, "high": 25}),
        "temperature": evaluate_vital(
            "temperature", current["temperature"], {"low": 36.0, "high": 37.5}
        ),
        "spo2": evaluate_vital("spo2", current["spo2"], {"low": 95, "high": 100}),
    }

    return {
        "current": current,
        "trends": trends,
        "evaluations": evaluations,
        "history": vitals,
    }


# ============================================================================
# Laborwert-Ampelsystem
# ============================================================================


def calculate_lab_traffic_light(patient_id: int) -> dict[str, Any]:
    """Berechnet Laborwert-Ampelsystem."""
    labs = _generate_demo_labs(patient_id)

    if not labs:
        return {
            "latest_date": None,
            "values": {},
            "summary": {"green": 0, "yellow": 0, "red": 0},
            "history": [],
        }

    latest = labs[0]

    def evaluate_lab(value: float, normal_min: float, normal_max: float) -> dict:
        tolerance = (normal_max - normal_min) * 0.2

        if normal_min <= value <= normal_max:
            return {"status": "green", "label": "Normal", "color": "#28A745"}

        if value < normal_min:
            if value >= normal_min - tolerance:
                return {"status": "yellow", "label": "Leicht erniedrigt", "color": "#FFC107"}
            return {"status": "red", "label": "Kritisch niedrig", "color": "#DC3545"}

        if value <= normal_max + tolerance:
            return {"status": "yellow", "label": "Leicht erhöht", "color": "#FFC107"}
        return {"status": "red", "label": "Kritisch erhöht", "color": "#DC3545"}

    evaluated_values = {}
    summary = {"green": 0, "yellow": 0, "red": 0}

    for key, lab_data in latest["values"].items():
        evaluation = evaluate_lab(lab_data["value"], lab_data["normal_min"], lab_data["normal_max"])
        evaluated_values[key] = {**lab_data, **evaluation}
        summary[evaluation["status"]] += 1

    return {
        "latest_date": latest["date"],
        "values": evaluated_values,
        "summary": summary,
        "history": labs,
    }


# ============================================================================
# Chronische Erkrankungen
# ============================================================================


def get_chronic_conditions(patient_id: int) -> dict[str, Any]:
    """Gibt chronische Erkrankungen des Patienten zurück."""
    diagnoses = _generate_demo_diagnoses(patient_id)
    chronic = [d for d in diagnoses if d.get("chronic")]
    active = [d for d in diagnoses if d.get("active")]

    by_severity = {"high": [], "medium": [], "low": []}
    for d in diagnoses:
        severity = d.get("severity", "low")
        by_severity[severity].append(d)

    return {
        "total": len(diagnoses),
        "chronic_count": len(chronic),
        "active_count": len(active),
        "diagnoses": diagnoses,
        "chronic": chronic,
        "by_severity": by_severity,
    }


# ============================================================================
# Patienten-Stammdaten
# ============================================================================


def get_patient_profile(patient_id: int) -> dict[str, Any] | None:
    """Holt Patientenstammdaten und berechnet abgeleitete Werte."""
    patient = None
    try:
        patient = Patient.objects.using("default").get(id=patient_id)
    except Patient.DoesNotExist:
        patient = None
    except Exception:
        patient = None

    # Last resort: deterministic demo profile for dev data seeded only via appointments.
    if patient is None:
        random.seed(patient_id + 9000)
        first_names = [
            "Alex",
            "Sam",
            "Taylor",
            "Jordan",
            "Robin",
            "Casey",
            "Jamie",
            "Morgan",
            "Chris",
            "Kai",
        ]
        last_names = [
            "Müller",
            "Schmidt",
            "Schneider",
            "Fischer",
            "Weber",
            "Meyer",
            "Wagner",
            "Becker",
            "Hoffmann",
            "Schäfer",
        ]
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)

        birth_year = random.randint(1940, 2015)
        birth_month = random.randint(1, 12)
        birth_day = random.randint(1, 28)
        birth_date = date(birth_year, birth_month, birth_day)

        gender = random.choice(["M", "W", "D"])
        if gender == "M":
            gender_icon = "♂"
        elif gender == "W":
            gender_icon = "♀"
        else:
            gender_icon = "○"

        initials = (f"{first_name[:1]}{last_name[:1]}").upper()
        today = date.today()
        age = (today - birth_date).days // 365
        allergies = _generate_demo_allergies(patient_id)

        return {
            "id": patient_id,
            "patient_id": patient_id,
            "first_name": first_name,
            "last_name": last_name,
            "display_name": f"{last_name}, {first_name}",
            "full_name": f"{first_name} {last_name}",
            "initials": initials,
            "birth_date": birth_date.isoformat(),
            "age": age,
            "gender": gender,
            "gender_icon": gender_icon,
            "phone": None,
            "email": None,
            "allergies": allergies,
            "has_allergies": len(allergies) > 0,
        }

    today = date.today()
    birth_date = getattr(patient, "birth_date", None)
    age = (today - birth_date).days // 365 if birth_date else None

    initials = (f"{(patient.first_name or '')[:1]}{(patient.last_name or '')[:1]}").upper()

    gender_raw = (patient.gender or "").strip()
    gender_lower = gender_raw.lower()
    if gender_raw in ("M", "m") or gender_lower in ("male", "mann", "männlich"):
        gender_icon = "♂"
    elif gender_raw in ("W", "w") or gender_lower in ("female", "frau", "weiblich"):
        gender_icon = "♀"
    else:
        gender_icon = "○"

    allergies = _generate_demo_allergies(patient_id)

    return {
        "id": patient.id,
        "patient_id": patient.id,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "display_name": f"{patient.last_name}, {patient.first_name}",
        "full_name": f"{patient.first_name} {patient.last_name}",
        "initials": initials,
        "birth_date": birth_date.isoformat() if birth_date else None,
        "age": age,
        "gender": patient.gender or "Unbekannt",
        "gender_icon": gender_icon,
        "phone": patient.phone,
        "email": patient.email,
        "allergies": allergies,
        "has_allergies": len(allergies) > 0,
    }


# ============================================================================
# Patienten-Übersicht (alle Patienten)
# ============================================================================


def get_patient_overview_stats() -> dict[str, Any]:
    """Berechnet Übersichtsstatistiken für alle Patienten."""
    try:
        total_patients = int(Patient.objects.using("default").count())
    except Exception:
        total_patients = 0

    now = timezone.now()
    six_months_ago = now - timedelta(days=180)

    active_patient_ids = (
        Appointment.objects.using("default")
        .filter(start_time__gte=six_months_ago, status__in=["completed", "confirmed", "scheduled"])
        .values_list("patient_id", flat=True)
        .distinct()
    )

    active_count = len(set(active_patient_ids))

    today_start = timezone.make_aware(
        datetime.combine(now.date(), datetime.min.time()), timezone.get_current_timezone()
    )
    today_end = today_start + timedelta(days=1)

    today_patients = (
        Appointment.objects.using("default")
        .filter(
            start_time__gte=today_start,
            start_time__lt=today_end,
            status__in=["scheduled", "confirmed"],
        )
        .values_list("patient_id", flat=True)
        .distinct()
        .count()
    )

    month_start = today_start.replace(day=1)

    new_patients_this_month = (
        Appointment.objects.using("default")
        .filter(start_time__gte=month_start, start_time__lt=now)
        .values("patient_id")
        .annotate(first_visit_count=Count("id"))
        .filter(first_visit_count=1)
        .count()
    )

    return {
        "total_patients": total_patients,
        "active_patients": active_count,
        "inactive_patients": max(0, total_patients - active_count),
        "patients_today": today_patients,
        "new_this_month": new_patients_this_month,
        "active_rate": round(active_count / max(1, total_patients) * 100, 1),
    }


# ============================================================================
# Gesamtansicht für einen Patienten
# ============================================================================


def get_all_patient_kpis(patient_id: int) -> dict[str, Any]:
    """Sammelt alle KPIs für einen einzelnen Patienten."""
    logger.debug("kpi.patient.get_all_patient_kpis start (patient_id=%s)", patient_id)
    with timed_block("kpi.patient.get_all_patient_kpis", log=logger, level="debug"):
        profile = get_patient_profile(patient_id)

        if not profile:
            result = {"error": "Patient nicht gefunden", "patient_id": patient_id}
        else:
            status = calculate_patient_status(patient_id)
            risk = calculate_patient_risk_score(patient_id)
            appointments = calculate_appointment_activity(patient_id)
            compliance = calculate_medication_compliance(patient_id)
            vitals = calculate_vital_trends(patient_id)
            labs = calculate_lab_traffic_light(patient_id)
            conditions = get_chronic_conditions(patient_id)
            documents = _generate_demo_documents(patient_id)
            reports = [d for d in documents if d.get("kind") == "Bericht"]
            prescriptions = _generate_demo_prescriptions(patient_id)

            result = {
                "profile": profile,
                "status": {
                    "status": status.status,
                    "label": status.label,
                    "color": status.color,
                    "icon": status.icon,
                },
                "risk": risk,
                "appointments": appointments,
                "compliance": compliance,
                "vitals": vitals,
                "labs": labs,
                "conditions": conditions,
                "documents": documents,
                "reports": reports,
                "prescriptions": prescriptions,
            }
    logger.debug("kpi.patient.get_all_patient_kpis end (patient_id=%s)", patient_id)
    return result
