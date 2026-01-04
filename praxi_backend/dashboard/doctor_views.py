"""
Views für das Ärzte-Dashboard.

Enthält:
- DoctorDashboardView: Übersicht aller Ärzte
- DoctorDetailView: Detail-Dashboard für einen Arzt
- DoctorAPIView: JSON-API für AJAX-Anfragen
"""
from __future__ import annotations

import json

from datetime import date, datetime, timedelta

from django.http import JsonResponse
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from praxi_backend.core.models import User
from praxi_backend.appointments.models import Appointment, DoctorHours, Operation

from .doctor_kpis import (
    get_active_doctors,
    get_all_doctor_kpis,
    get_doctor_comparison_data,
    get_doctor_profile,
)
from .doctor_charts import get_all_doctor_charts


class DoctorDashboardView(TemplateView):
    """
    Übersichts-Dashboard für alle Ärzte.
    """
    template_name = 'dashboard/doctors.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # NOTE: The template `dashboard/doctors.html` uses query params (?doctor_id=...&period=...)
        # and expects specific context keys (stats, doctors_list, doctors_overview, doctor_kpis, ...).
        # The previous implementation produced different keys, which made the page appear empty.

        def _int_or_none(value: str | None) -> int | None:
            if value is None:
                return None
            value = str(value).strip()
            if not value:
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        def _period_to_days(period: str | None, fallback_days: int = 30) -> tuple[str, int, str]:
            period = (period or '').strip().lower()
            if period not in {'week', 'month', 'quarter'}:
                period = 'week'
            if period == 'week':
                return period, 7, 'Woche'
            if period == 'month':
                return period, 30, 'Monat'
            return period, 90, 'Quartal'

        selected_doctor_id = _int_or_none(self.request.GET.get('doctor_id'))
        if selected_doctor_id is None:
            selected_doctor_id = _int_or_none(self.kwargs.get('doctor_id'))

        # Keep compatibility with the JSON API (days=...) while the UI uses period=...
        days_override = _int_or_none(self.request.GET.get('days'))
        period, days, period_label = _period_to_days(self.request.GET.get('period'))
        if days_override is not None and days_override > 0:
            days = days_override

        doctors = get_active_doctors()
        doctor_ids = [d.id for d in doctors]

        def _full_name(u: User) -> str:
            name = u.get_full_name().strip() if hasattr(u, 'get_full_name') else ''
            return name or getattr(u, 'username', str(u.id))

        def _initials(u: User) -> str:
            first = (getattr(u, 'first_name', '') or '').strip()
            last = (getattr(u, 'last_name', '') or '').strip()
            if first or last:
                return (first[:1] + last[:1]).upper()
            username = (getattr(u, 'username', '') or '').strip()
            return (username[:2] or 'DR').upper()

        # Doctor list for the selector (template expects `doctors_list`)
        doctors_list_payload = [
            {
                'id': d.id,
                'full_name': _full_name(d),
                'name': get_doctor_profile(d).get('name') if d is not None else _full_name(d),
                'color': getattr(d, 'calendar_color', None) or '#1E90FF',
            }
            for d in doctors
        ]
        context['doctors_list'] = doctors_list_payload
        # Keep backward compatible key used elsewhere.
        context['doctor_list'] = doctors_list_payload

        # Global stats for the header KPI cards
        tz = timezone.get_current_timezone()
        end_dt = timezone.now()
        start_dt = end_dt - timedelta(days=days)

        # Appointments (range, all doctors)
        appt_qs = Appointment.objects.using('default').filter(
            doctor_id__in=doctor_ids,
            start_time__gte=start_dt,
            start_time__lte=end_dt,
        )

        # Operations (range, any role in team)
        op_qs = Operation.objects.using('default').filter(
            start_time__gte=start_dt,
            start_time__lte=end_dt,
        ).filter(
            Q(primary_surgeon_id__in=doctor_ids)
            | Q(assistant_id__in=doctor_ids)
            | Q(anesthesist_id__in=doctor_ids)
        )

        comparison = get_doctor_comparison_data(days=days)
        avg_utilization = comparison.get('aggregates', {}).get('avg_utilization', 0)

        context['stats'] = {
            'active_doctors': len(doctors),
            'total_appointments': appt_qs.count(),
            'total_operations': op_qs.count(),
            'avg_utilization': avg_utilization,
        }

        context['selected_doctor_id'] = selected_doctor_id
        context['period'] = period
        context['period_label'] = period_label

        # Detail view (selected doctor)
        if selected_doctor_id is not None:
            kpis = get_all_doctor_kpis(selected_doctor_id, days=days)
            if 'error' in kpis:
                context['error'] = kpis['error']
                context['doctor'] = None
            else:
                doctor_obj = (
                    User.objects.using('default')
                    .filter(id=selected_doctor_id, role__name='doctor')
                    .first()
                )

                profile = kpis.get('profile', {})
                color = profile.get('calendar_color') or (getattr(doctor_obj, 'calendar_color', None) if doctor_obj else None) or '#1E90FF'

                context['doctor'] = {
                    'id': selected_doctor_id,
                    'title': 'Dr.',
                    'full_name': _full_name(doctor_obj) if doctor_obj else profile.get('name', 'Unbekannt'),
                    'initials': _initials(doctor_obj) if doctor_obj else 'DR',
                    'specialty': getattr(doctor_obj, 'specialty', None) or 'Allgemeinmedizin',
                    'email': getattr(doctor_obj, 'email', '') if doctor_obj else '',
                    'phone': getattr(doctor_obj, 'phone', None) if doctor_obj else None,
                    'color': color,
                    'is_active': bool(getattr(doctor_obj, 'is_active', True)) if doctor_obj else True,
                }

                # Operations for this doctor (any involvement)
                op_count = Operation.objects.using('default').filter(
                    start_time__gte=start_dt,
                    start_time__lte=end_dt,
                ).filter(
                    Q(primary_surgeon_id=selected_doctor_id)
                    | Q(assistant_id=selected_doctor_id)
                    | Q(anesthesist_id=selected_doctor_id)
                ).count()

                volume = kpis.get('volume', {})
                util = kpis.get('utilization', {})
                no_show = kpis.get('no_show', {})
                duration = kpis.get('duration', {})

                context['doctor_kpis'] = {
                    'appointments': volume.get('total', 0),
                    'completed': volume.get('completed', 0),
                    'completion_rate': volume.get('completion_rate', 0),
                    'operations': op_count,
                    'utilization': util.get('utilization', 0),
                    'no_shows': no_show.get('no_show_count', 0),
                    'no_show_rate': no_show.get('no_show_rate', 0),
                    'avg_duration': duration.get('avg_actual', 0) or duration.get('avg_planned', 0),
                }

                # Weekly schedule (DoctorHours) for the profile card
                weekdays = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
                hours_rows = list(
                    DoctorHours.objects.using('default')
                    .filter(doctor_id=selected_doctor_id, active=True)
                    .order_by('weekday', 'start_time', 'id')
                )
                by_day: dict[int, list] = {i: [] for i in range(7)}
                for h in hours_rows:
                    by_day[h.weekday].append(h)

                schedule = []
                for i in range(7):
                    rows = by_day.get(i) or []
                    if not rows:
                        schedule.append({'name': weekdays[i], 'active': False, 'start': None, 'end': None})
                        continue
                    start_t = min(r.start_time for r in rows)
                    end_t = max(r.end_time for r in rows)
                    schedule.append(
                        {
                            'name': weekdays[i],
                            'active': True,
                            'start': start_t.strftime('%H:%M'),
                            'end': end_t.strftime('%H:%M'),
                        }
                    )
                context['schedule'] = schedule

                # Upcoming appointments
                now_local = timezone.localtime(timezone.now(), tz)
                upcoming = list(
                    Appointment.objects.using('default')
                    .filter(doctor_id=selected_doctor_id, start_time__gte=now_local)
                    .select_related('type')
                    .order_by('start_time', 'id')[:25]
                )

                def _status_badge(status: str) -> tuple[str, str]:
                    status = (status or '').lower()
                    mapping = {
                        'scheduled': ('info', 'Geplant'),
                        'confirmed': ('success', 'Bestätigt'),
                        'completed': ('neutral', 'Abgeschlossen'),
                        'cancelled': ('danger', 'Storniert'),
                    }
                    return mapping.get(status, ('info', status or '—'))

                upcoming_payload = []
                for appt in upcoming:
                    status_class, status_label = _status_badge(getattr(appt, 'status', ''))
                    type_obj = getattr(appt, 'type', None)
                    upcoming_payload.append(
                        {
                            'patient_initials': f"P{str(getattr(appt, 'patient_id', '') or '')[:1]}" or 'P',
                            'patient_name': f"Patient #{appt.patient_id}",
                            'type_name': getattr(type_obj, 'name', None) or 'Termin',
                            'type_color': getattr(type_obj, 'color', None) or '#0078D4',
                            'status_class': status_class,
                            'status_label': status_label,
                            'date': timezone.localtime(appt.start_time, tz).isoformat(),
                        }
                    )
                context['upcoming_appointments'] = upcoming_payload

                # Minimal chart payloads expected by doctors.html
                # Appointments per day (line)
                daily = (
                    Appointment.objects.using('default')
                    .filter(doctor_id=selected_doctor_id, start_time__gte=start_dt, start_time__lte=end_dt)
                    .annotate(day=TruncDate('start_time'))
                    .values('day')
                    .annotate(count=Count('id'))
                    .order_by('day')
                )
                labels = [d['day'].strftime('%Y-%m-%d') for d in daily]
                data = [d['count'] for d in daily]

                # Status distribution (doughnut)
                status_rows = (
                    Appointment.objects.using('default')
                    .filter(doctor_id=selected_doctor_id, start_time__gte=start_dt, start_time__lte=end_dt)
                    .values('status')
                    .annotate(count=Count('id'))
                    .order_by('status')
                )
                s_labels = [r['status'] for r in status_rows]
                s_data = [r['count'] for r in status_rows]

                charts_min = {
                    'appointments_per_day': {
                        'labels': labels,
                        'datasets': [{'label': 'Termine', 'data': data}],
                    },
                    'status_distribution': {
                        'labels': s_labels,
                        'datasets': [{'label': 'Status', 'data': s_data}],
                    },
                }
                context['charts_json'] = json.dumps(charts_min)

                context['title'] = f"Ärzte-Dashboard: {context['doctor']['full_name']}"
                context['is_detail'] = True
        else:
            # Overview: build table rows for all doctors
            comparison_rows = comparison.get('doctors', [])
            comparison_by_id = {row.get('doctor_id'): row for row in comparison_rows}

            # Operation counts per doctor (any role) via grouped queries
            operation_counts: dict[int, int] = {d.id: 0 for d in doctors}
            base_ops = Operation.objects.using('default').filter(
                start_time__gte=start_dt,
                start_time__lte=end_dt,
            )
            for field in ('primary_surgeon_id', 'assistant_id', 'anesthesist_id'):
                rows = (
                    base_ops.filter(**{f"{field}__in": doctor_ids})
                    .values(field)
                    .annotate(c=Count('id'))
                )
                for r in rows:
                    doctor_id = r.get(field)
                    if doctor_id is not None:
                        operation_counts[int(doctor_id)] = operation_counts.get(int(doctor_id), 0) + int(r.get('c') or 0)

            doctors_overview = []
            for d in doctors:
                row = comparison_by_id.get(d.id, {})
                doctors_overview.append(
                    {
                        'id': d.id,
                        'full_name': _full_name(d),
                        'initials': _initials(d),
                        'specialty': getattr(d, 'specialty', None) or 'Allgemein',
                        'appointments': row.get('appointments', 0),
                        'operations': operation_counts.get(d.id, 0),
                        'utilization': row.get('utilization', 0),
                        'no_show_rate': row.get('no_show_rate', 0),
                        'color': getattr(d, 'calendar_color', None) or '#1E90FF',
                    }
                )

            context['doctors_overview'] = doctors_overview

            # Minimal utilization chart expected by the template
            context['charts_json'] = json.dumps(
                {
                    'utilization_by_doctor': {
                        'labels': [row['full_name'] for row in doctors_overview],
                        'datasets': [
                            {
                                'label': 'Auslastung (%)',
                                'data': [row['utilization'] for row in doctors_overview],
                            }
                        ],
                    }
                }
            )

            context['title'] = 'Ärzte-Dashboard'
            context['is_detail'] = False

        return context


class DoctorAPIView(View):
    """
    JSON-API für Ärzte-Dashboard-Daten.
    """
    
    def get(self, request, doctor_id: int | None = None):
        days = int(request.GET.get('days', 30))
        
        if doctor_id:
            # Einzelarzt
            kpis = get_all_doctor_kpis(doctor_id, days=days)
            charts = get_all_doctor_charts(doctor_id=doctor_id, days=days)
            
            return JsonResponse({
                'success': 'error' not in kpis,
                'kpis': kpis,
                'charts': charts,
            })
        else:
            # Übersicht
            comparison = get_doctor_comparison_data(days=days)
            charts = get_all_doctor_charts(days=days)
            
            return JsonResponse({
                'success': True,
                'comparison': comparison,
                'charts': charts,
            })


class DoctorCompareView(TemplateView):
    """
    Vergleichsansicht für zwei Ärzte.
    """
    template_name = 'dashboard/doctors_compare.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        doctor1_id = self.request.GET.get('doctor1')
        doctor2_id = self.request.GET.get('doctor2')
        days = int(self.request.GET.get('days', 30))
        
        if doctor1_id and doctor2_id:
            kpis1 = get_all_doctor_kpis(int(doctor1_id), days=days)
            kpis2 = get_all_doctor_kpis(int(doctor2_id), days=days)
            
            context['doctor1'] = kpis1
            context['doctor2'] = kpis2
            context['comparison_mode'] = True
        else:
            context['comparison_mode'] = False
        
        context['doctor_list'] = [
            {
                'id': d.id,
                'name': get_doctor_profile(d)['name'],
            }
            for d in get_active_doctors()
        ]
        
        context['title'] = 'Ärzte-Vergleich'
        context['selected_days'] = days
        
        return context
