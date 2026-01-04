"""
Scheduling Dashboard Views
"""
import json

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import cache_page

from .scheduling_kpis import get_all_scheduling_kpis
from .scheduling_charts import get_all_scheduling_charts


class SchedulingDashboardView(View):
    """Scheduling KPIs Dashboard View"""
    
    @method_decorator(staff_member_required)
    def get(self, request):
        # KPIs berechnen
        kpis = get_all_scheduling_kpis()
        charts = get_all_scheduling_charts()
        
        context = {
            'title': 'Scheduling KPIs',
            'kpis': kpis,
            'charts_json': json.dumps(charts),
            'heatmap_matrix': json.dumps(kpis['peak_load']['matrix']),
            'funnel_data': json.dumps(charts['status_funnel']),
        }
        
        return render(request, 'dashboard/scheduling.html', context)


class SchedulingAPIView(View):
    """API Endpoint für Scheduling Dashboard-Daten"""
    
    @method_decorator(staff_member_required)
    @method_decorator(cache_page(60))
    def get(self, request):
        kpis = get_all_scheduling_kpis()
        charts = get_all_scheduling_charts()
        
        return JsonResponse({
            'kpis': kpis,
            'charts': charts,
        })
