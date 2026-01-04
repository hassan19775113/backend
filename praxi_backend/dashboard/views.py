"""
Dashboard Views
"""
import json

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import cache_page

from .kpis import get_all_kpis
from .charts import get_all_charts
from .widgets import build_kpi_cards, build_status_badges, build_utilization_bars


class DashboardView(View):
    """Haupt-Dashboard View"""
    
    @method_decorator(staff_member_required)
    def get(self, request):
        # KPIs berechnen
        kpis = get_all_kpis()
        charts = get_all_charts()
        
        # Widgets aufbauen
        kpi_cards = build_kpi_cards(kpis)
        status_badges = build_status_badges(kpis)
        utilization_bars = build_utilization_bars(kpis)
        
        context = {
            'title': 'PraxiApp Dashboard',
            'kpis': kpis,
            'kpi_cards': kpi_cards,
            'status_badges': status_badges,
            'utilization_bars': utilization_bars,
            'charts_json': json.dumps(charts),
            'heatmap_matrix': json.dumps(charts['hourly_heatmap']['matrix']),
        }
        
        return render(request, 'dashboard/index.html', context)


class DashboardAPIView(View):
    """API Endpoint für Dashboard-Daten (für AJAX-Refresh)"""
    
    @method_decorator(staff_member_required)
    @method_decorator(cache_page(60))  # 1 Minute Cache
    def get(self, request):
        kpis = get_all_kpis()
        charts = get_all_charts()
        
        kpi_cards = build_kpi_cards(kpis)
        status_badges = build_status_badges(kpis)
        utilization_bars = build_utilization_bars(kpis)
        
        return JsonResponse({
            'kpis': kpis,
            'kpi_cards': kpi_cards,
            'status_badges': status_badges,
            'utilization_bars': utilization_bars,
            'charts': charts,
        })
