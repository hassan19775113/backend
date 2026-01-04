"""
Views für das Patienten-Dashboard.

Enthält:
- PatientOverviewView: Übersicht aller Patienten
- PatientDashboardView: Detail-Dashboard für einen Patienten
- PatientAPIView: JSON-API für AJAX-Anfragen
"""
from __future__ import annotations

import json

from django.db.models import Q
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from praxi_backend.appointments.models import Appointment
from praxi_backend.medical.models import Patient
from praxi_backend.patients.models import Patient as PatientCache

from .patient_kpis import (
    get_all_patient_kpis,
    get_patient_overview_stats,
    get_patient_profile,
    calculate_patient_status,
    calculate_patient_risk_score,
)
from .patient_charts import get_all_patient_charts


class PatientOverviewView(TemplateView):
    """
    Übersichtsseite mit Patientenliste und Schnellstatistiken.
    """
    template_name = 'dashboard/patients_overview.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistiken
        stats = get_patient_overview_stats()
        context['stats'] = stats
        
        # Patientenliste mit Status
        try:
            patients = Patient.objects.using('medical').all()[:50]
            patient_list = []
            
            for patient in patients:
                status = calculate_patient_status(patient.id)
                risk = calculate_patient_risk_score(patient.id)
                profile = get_patient_profile(patient.id)
                
                patient_list.append({
                    'id': patient.id,
                    'name': f"{patient.last_name}, {patient.first_name}",
                    'age': profile['age'] if profile else None,
                    'gender': patient.gender,
                    'status': {
                        'label': status.label,
                        'color': status.color,
                        'icon': status.icon,
                    },
                    'risk': {
                        'score': risk['score'],
                        'level': risk['level'],
                        'color': risk['level_color'],
                    },
                })
            
            context['patients'] = patient_list
        except Exception as e:
            context['patients'] = []
            context['error'] = str(e)
        
        context['title'] = 'Patienten-Übersicht'
        
        return context


class PatientDashboardView(TemplateView):
    """
    Detail-Dashboard für einen einzelnen Patienten.
    """
    template_name = 'dashboard/patients.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Support both /patients/<id>/ and /patients/?patient_id=<id>
        patient_id = self.kwargs.get('patient_id')
        patient_id_param = self.request.GET.get('patient_id')
        if patient_id_param not in (None, ''):
            try:
                patient_id = int(patient_id_param)
            except (TypeError, ValueError):
                pass
        
        if patient_id:
            # Einzelpatient-Dashboard
            kpis = get_all_patient_kpis(patient_id)
            charts = get_all_patient_charts(patient_id)
            
            if 'error' in kpis:
                context['error'] = kpis['error']
            else:
                context['patient'] = kpis['profile']
                context['status'] = kpis['status']
                context['risk'] = kpis['risk']
                context['appointments'] = kpis['appointments']
                context['compliance'] = kpis['compliance']
                context['vitals'] = kpis['vitals']
                context['labs'] = kpis['labs']
                context['conditions'] = kpis['conditions']
                context['charts'] = charts

                # JSON für JavaScript
                context['charts_json'] = json.dumps(charts)
                context['vitals_json'] = json.dumps(kpis['vitals'])
                context['labs_json'] = json.dumps(kpis['labs'])

                # Template compatibility: top KPI strip expects `kpis.*`.
                appt = kpis.get('appointments') or {}
                last_dt = (appt.get('last_appointment') or {}).get('date')
                next_dt = (appt.get('next_appointment') or {}).get('date')
                no_shows = int(appt.get('no_shows') or 0)
                past_done = int(appt.get('total_past') or 0)
                total_for_rate = max(1, past_done + no_shows)
                context['kpis'] = {
                    'total_appointments': int(appt.get('total_past') or 0)
                    + int(appt.get('future') or 0)
                    + int(appt.get('cancelled') or 0),
                    'last_visit': (last_dt or '')[:10] or None,
                    'next_appointment': (next_dt or '')[:10] or None,
                    'no_show_rate': round(no_shows / total_for_rate * 100, 1),
                }

                # Template expects allergies as separate variable.
                profile = kpis.get('profile') or {}
                context['allergies'] = profile.get('allergies') or []

                # Ensure profile has a patient_id key used in template.
                if profile.get('patient_id') is None:
                    profile['patient_id'] = profile.get('id')

                # Provide status fields directly on patient dict for template.
                status = kpis.get('status') or {}
                profile.setdefault('status', status.get('status'))
                profile.setdefault('status_label', status.get('label'))
                profile.setdefault('insurance_type', None)
                
            
            context['title'] = f"Patient: {kpis.get('profile', {}).get('full_name', 'Unbekannt')}"
        else:
            # Fallback: Zeige ersten Patienten oder Demo
            try:
                first_patient = Patient.objects.using('medical').first()
                if first_patient:
                    patient_id = first_patient.id
                    kpis = get_all_patient_kpis(patient_id)
                    charts = get_all_patient_charts(patient_id)
                    
                    context['patient'] = kpis['profile']
                    context['status'] = kpis['status']
                    context['risk'] = kpis['risk']
                    context['appointments'] = kpis['appointments']
                    context['compliance'] = kpis['compliance']
                    context['vitals'] = kpis['vitals']
                    context['labs'] = kpis['labs']
                    context['conditions'] = kpis['conditions']
                    context['charts'] = charts
                    context['charts_json'] = json.dumps(charts)
                    context['vitals_json'] = json.dumps(kpis['vitals'])
                    context['labs_json'] = json.dumps(kpis['labs'])
                    context['title'] = f"Patient: {kpis['profile']['full_name']}"

                    appt = kpis.get('appointments') or {}
                    last_dt = (appt.get('last_appointment') or {}).get('date')
                    next_dt = (appt.get('next_appointment') or {}).get('date')
                    no_shows = int(appt.get('no_shows') or 0)
                    past_done = int(appt.get('total_past') or 0)
                    total_for_rate = max(1, past_done + no_shows)
                    context['kpis'] = {
                        'total_appointments': int(appt.get('total_past') or 0)
                        + int(appt.get('future') or 0)
                        + int(appt.get('cancelled') or 0),
                        'last_visit': (last_dt or '')[:10] or None,
                        'next_appointment': (next_dt or '')[:10] or None,
                        'no_show_rate': round(no_shows / total_for_rate * 100, 1),
                    }

                    profile = kpis.get('profile') or {}
                    context['allergies'] = profile.get('allergies') or []
                    if profile.get('patient_id') is None:
                        profile['patient_id'] = profile.get('id')
                    status = kpis.get('status') or {}
                    profile.setdefault('status', status.get('status'))
                    profile.setdefault('status_label', status.get('label'))
                    profile.setdefault('insurance_type', None)
                else:
                    context['error'] = 'Keine Patienten vorhanden'
                    context['title'] = 'Patienten-Dashboard'
            except Exception as e:
                context['error'] = f'Fehler beim Laden: {str(e)}'
                context['title'] = 'Patienten-Dashboard'

        context['selected_patient_id'] = patient_id

        # Patientenliste für Dropdown / Seitennavigation.
        patients_payload: list[dict] = []
        try:
            patients = (
                Patient.objects.using('medical')
                .all()
                .order_by('last_name', 'first_name', 'id')
            )[:50]
            patients_payload = [
                {'patient_id': p.id, 'display_name': f"{p.last_name}, {p.first_name}"}
                for p in patients
            ]
        except Exception:
            patients_payload = []

        if not patients_payload:
            ids = list(
                (
                    Appointment.objects.using('default')
                    .order_by()
                    .values_list('patient_id', flat=True)
                    .distinct()
                )[:50]
            )
            ids = [int(pid) for pid in ids if pid is not None]

            if ids:
                name_by_id: dict[int, str] = {}
                try:
                    cached = PatientCache.objects.using('default').filter(patient_id__in=ids)
                    name_by_id = {p.patient_id: f"{p.last_name}, {p.first_name}" for p in cached}
                except Exception:
                    name_by_id = {}

                patients_payload = [
                    {
                        'patient_id': pid,
                        'display_name': name_by_id.get(pid, f"Patient #{pid}"),
                    }
                    for pid in ids
                ]
            else:
                # As a last resort, show whatever is in the cache table.
                try:
                    cached = (
                        PatientCache.objects.using('default')
                        .all()
                        .order_by('last_name', 'first_name', 'id')
                    )[:50]
                    patients_payload = [
                        {'patient_id': p.patient_id, 'display_name': f"{p.last_name}, {p.first_name}"}
                        for p in cached
                    ]
                except Exception:
                    patients_payload = []

        context['patients'] = patients_payload
        context['patient_list'] = [
            {'id': p['patient_id'], 'name': p['display_name']}
            for p in patients_payload
        ]
        
        return context


class PatientAPIView(View):
    """
    JSON-API für Patienten-Dashboard-Daten.
    """
    
    def get(self, request, patient_id: int | None = None):
        if patient_id:
            # Einzelpatient
            kpis = get_all_patient_kpis(patient_id)
            charts = get_all_patient_charts(patient_id)
            
            return JsonResponse({
                'success': 'error' not in kpis,
                'kpis': kpis,
                'charts': charts,
            })
        else:
            # Übersicht
            stats = get_patient_overview_stats()
            
            return JsonResponse({
                'success': True,
                'stats': stats,
            })


class PatientSearchView(View):
    """
    API für Patientensuche.
    """
    
    def get(self, request):
        query = request.GET.get('q', '').strip()
        
        if len(query) < 2:
            return JsonResponse({'results': []})
        
        try:
            patients = Patient.objects.using('medical').filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query)
            )[:10]
            
            results = [
                {
                    'id': p.id,
                    'name': f"{p.last_name}, {p.first_name}",
                    'birth_date': p.birth_date.isoformat(),
                }
                for p in patients
            ]
            
            return JsonResponse({'results': results})
        except Exception as e:
            return JsonResponse({'error': str(e), 'results': []})
