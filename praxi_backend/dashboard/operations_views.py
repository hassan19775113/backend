"""
Views für das Operations-Dashboard.

Enthält:
- OperationsDashboardView: Hauptansicht des Operations-Dashboards
- OperationsAPIView: JSON-API für AJAX-Anfragen
"""
from __future__ import annotations

import json

from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from .operations_kpis import get_all_operations_kpis, get_realtime_operations_kpis
from .operations_charts import get_all_operations_charts


class OperationsDashboardView(TemplateView):
    """
    Hauptansicht für das Operations-Dashboard.
    
    Zeigt:
    - KPI-Cards (Auslastung, Durchsatz, No-Show, etc.)
    - Patientenfluss-Visualisierung
    - Ressourcen-Heatmaps
    - Engpass-Analysen
    - Leistungsübersicht
    """
    template_name = 'dashboard/operations.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Zeitraum aus Query-Parameter
        days = int(self.request.GET.get('days', 30))
        view_mode = self.request.GET.get('mode', 'overview')  # overview, realtime, resources
        
        # KPIs berechnen
        if view_mode == 'realtime':
            kpis = get_realtime_operations_kpis()
        else:
            kpis = get_all_operations_kpis(days=days)
        
        # Charts generieren
        charts = get_all_operations_charts(days=days, kpis=kpis)
        
        # Context aufbauen
        context['title'] = 'Operations-Dashboard'
        context['period'] = kpis['period']
        context['selected_days'] = days
        context['view_mode'] = view_mode
        
        # KPIs
        context['utilization'] = kpis['utilization']
        context['throughput'] = kpis['throughput']
        context['no_show'] = kpis['no_show']
        context['cancellation'] = kpis['cancellation']
        context['resources'] = kpis['resources']
        context['bottleneck'] = kpis['bottleneck']
        context['hourly'] = kpis['hourly']
        context['status_distribution'] = kpis['status_distribution']
        context['patient_flow'] = kpis['patient_flow']
        context['flow_times'] = kpis['flow_times']
        context['punctuality'] = kpis['punctuality']
        context['documentation'] = kpis['documentation']
        context['services'] = kpis['services']
        
        # Charts als JSON
        context['charts'] = charts
        context['charts_json'] = json.dumps(charts)
        
        # Ressourcen-Listen für Filter
        context['rooms'] = kpis['resources']['rooms']
        context['devices'] = kpis['resources']['devices']
        
        return context


class OperationsAPIView(View):
    """
    JSON-API für Operations-Dashboard-Daten.
    
    Unterstützt:
    - GET /api/operations-dashboard/?days=30 - Alle KPIs
    - GET /api/operations-dashboard/?mode=realtime - Echtzeit-Daten
    """
    
    def get(self, request):
        days = int(request.GET.get('days', 30))
        mode = request.GET.get('mode', 'standard')
        include_charts = request.GET.get('charts', 'true').lower() == 'true'
        
        # KPIs berechnen
        if mode == 'realtime':
            kpis = get_realtime_operations_kpis()
        else:
            kpis = get_all_operations_kpis(days=days)
        
        response_data = {
            'success': True,
            'mode': mode,
            'kpis': kpis,
        }
        
        # Charts optional
        if include_charts:
            charts = get_all_operations_charts(days=days, kpis=kpis)
            response_data['charts'] = charts
        
        return JsonResponse(response_data)


class OperationsResourceView(TemplateView):
    """
    Detailansicht für einzelne Ressourcen.
    """
    template_name = 'dashboard/operations_resource.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        resource_id = self.kwargs.get('resource_id')
        days = int(self.request.GET.get('days', 30))
        
        # TODO: Detaillierte Ressourcen-KPIs implementieren
        context['resource_id'] = resource_id
        context['selected_days'] = days
        context['title'] = 'Ressourcen-Details'
        
        return context
