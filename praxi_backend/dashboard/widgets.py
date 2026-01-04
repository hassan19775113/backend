"""
Widget-Definitionen für das Admin-Dashboard
"""
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class KPICard:
    """KPI-Card Widget"""
    title: str
    value: Any
    icon: str
    color: str
    trend: Optional[dict] = None
    subtitle: Optional[str] = None
    link: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'title': self.title,
            'value': self.value,
            'icon': self.icon,
            'color': self.color,
            'trend': self.trend,
            'subtitle': self.subtitle,
            'link': self.link,
        }


@dataclass
class StatusBadge:
    """Status Badge Widget"""
    label: str
    count: int
    color: str
    icon: str
    
    def to_dict(self) -> dict:
        return {
            'label': self.label,
            'count': self.count,
            'color': self.color,
            'icon': self.icon,
        }


@dataclass
class ProgressBar:
    """Progress Bar Widget für Auslastung"""
    label: str
    value: float
    max_value: float = 100.0
    color: str = '#1A73E8'
    
    @property
    def percent(self) -> float:
        if self.max_value == 0:
            return 0
        return min(100, (self.value / self.max_value) * 100)
    
    def to_dict(self) -> dict:
        return {
            'label': self.label,
            'value': self.value,
            'max_value': self.max_value,
            'percent': round(self.percent, 1),
            'color': self.color,
        }

def build_kpi_cards(kpis: dict) -> list[dict]:
    """Erstellt KPI-Cards aus den berechneten KPIs.
    Icons wurden von Emojis auf schlanke Fluent-like SVGs umgestellt.
    Die SVG-Strings werden in den Templates mit `|safe` gerendert.
    """
    cards = []
    
    # Users (People / Group)
    people_svg = """
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false">
      <path d="M16 11c1.7 0 3-1.3 3-3s-1.3-3-3-3-3 1.3-3 3 1.3 3 3 3zM7 11c1.7 0 3-1.3 3-3S8.7 5 7 5 4 6.3 4 8s1.3 3 3 3zm0 2c-2.3 0-7 1.2-7 3.5V20h14v-3.5C14 14.2 9.3 13 7 13zm9 0c-.3 0-.7 0-1 .1 1.1.9 1.8 2 1.8 3.4V20h6v-3.5C22 14.2 17.3 13 16 13z"/>
    </svg>
    """

    # Doctor / Clinician
    doctor_svg = """
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false">
      <path d="M12 12a4 4 0 100-8 4 4 0 000 8zm-6 8v-1c0-2.8 3.6-4 6-4s6 1.2 6 4v1H6z"/>
    </svg>
    """

    # Hospital / Patient
    hospital_svg = """
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false">
      <path d="M3 11h18v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-9zM7 7h10v4H7V7zM12 2l4 3h-3v2h-2V5H8l4-3z"/>
    </svg>
    """

    # Calendar
    calendar_svg = """
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false">
      <path d="M7 10h5v5H7v-5zm0 7h5v2H7v-2zM3 5h2V3h2v2h8V3h2v2h2a1 1 0 0 1 1 1v3H2V6a1 1 0 0 1 1-1z"/>
    </svg>
    """

    # Bar chart (week)
    barchart_svg = """
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false">
      <path d="M3 3h2v18H3V3zm5 6h2v12H8V9zm5-4h2v16h-2V5zm5 8h2v8h-2v-8z"/>
    </svg>
    """

    # Line / Trend chart (month)
    linechart_svg = """
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false">
      <path d="M3 17h2v4H3v-4zm5-6h2v10H8V11zm5-4h2v14h-2V7zm5 8h2v6h-2v-6z"/>
    </svg>
    """

    # Scalpel / Operation
    scalpel_svg = """
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false">
      <path d="M2 21l6-6 9-9 2 2-9 9-6 6H2zM20 4l.7-.7 1.4 1.4L21.4 5.4 20 4z"/>
    </svg>
    """

    # Stopwatch / Duration
    timer_svg = """
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false">
      <path d="M12 2s1.5 2.5 1.5 4.5S12 9 12 9s-1.5-2.5-1.5-4.5S12 2 12 2zM6 13a6 6 0 0012 0c0-3.3-3-6-6-6s-6 2.7-6 6z"/>
    </svg>
    """

    # Clock (peak hour)
    clock_svg = """
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false">
      <path d="M12 1a11 11 0 100 22 11 11 0 000-22zm1 11.5V6h-2v6h5v-2h-3z"/>
    </svg>
    """

    # Day calendar (peak day)
    day_svg = """
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false">
      <path d="M3 5h18v14H3zM7 3h2v2H7V3zm8 0h2v2h-2V3z"/>
    </svg>
    """

    # Door / Room
    door_svg = """
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false">
      <path d="M3 3h18v18H3V3zm4 4h2v10H7V7z"/>
    </svg>
    """

    # Build cards (using the SVG strings above)
    cards.append(KPICard(
        title='Benutzer',
        value=kpis['users']['total_users'],
        icon=people_svg,
        color='#1A73E8',
        subtitle=f"{kpis['users']['total_doctors']} Ärzte",
        link='/praxiadmin/core/user/',
    ).to_dict())
    
    cards.append(KPICard(
        title='Ärzte',
        value=kpis['users']['total_doctors'],
        icon=doctor_svg,
        color='#34A853',
        link='/praxiadmin/core/user/?role__name=doctor',
    ).to_dict())
    
    cards.append(KPICard(
        title='Patienten',
        value=kpis['patients'],
        icon=hospital_svg,
        color='#FBBC05',
        link='/praxiadmin/dashboard/patients/',
    ).to_dict())
    
    cards.append(KPICard(
        title='Termine heute',
        value=kpis['appointments']['today'],
        icon=calendar_svg,
        color='#EA4335',
        trend=kpis['appointments']['trend'],
        subtitle=f"{kpis['appointments']['week']} diese Woche",
        link='/praxiadmin/dashboard/appointments/',
    ).to_dict())
    
    cards.append(KPICard(
        title='Termine Woche',
        value=kpis['appointments']['week'],
        icon=barchart_svg,
        color='#9C27B0',
        trend=kpis['appointments']['trend'],
    ).to_dict())
    
    cards.append(KPICard(
        title='Termine Monat',
        value=kpis['appointments']['month'],
        icon=linechart_svg,
        color='#00BCD4',
    ).to_dict())
    
    cards.append(KPICard(
        title='OPs heute',
        value=kpis['operations']['today'],
        icon=scalpel_svg,
        color='#FF5722',
        trend=kpis['operations']['trend'],
        subtitle=f"{kpis['operations']['week']} diese Woche",
        link='/praxiadmin/appointments/operation/',
    ).to_dict())
    
    cards.append(KPICard(
        title='OPs Woche',
        value=kpis['operations']['week'],
        icon=hospital_svg,
        color='#795548',
        trend=kpis['operations']['trend'],
    ).to_dict())
    
    cards.append(KPICard(
        title='⌀ Terminlänge',
        value=f"{kpis['appointments']['avg_duration_mins']} min",
        icon=timer_svg,
        color='#607D8B',
    ).to_dict())
    
    peak_hours = kpis['peak_hours']
    cards.append(KPICard(
        title='Peak-Stunde',
        value=f"{peak_hours['peak_hour']}:00",
        icon=clock_svg,
        color='#3F51B5',
        subtitle=f"{peak_hours['peak_count']} Termine",
    ).to_dict())
    
    peak_days = kpis['peak_days']
    cards.append(KPICard(
        title='Peak-Tag',
        value=peak_days['peak_day'],
        icon=day_svg,
        color='#009688',
        subtitle=f"{peak_days['peak_count']} Termine",
    ).to_dict())
    
    cards.append(KPICard(
        title='Räume',
        value=kpis['resources']['total_rooms'],
        icon=door_svg,
        color='#8BC34A',
        subtitle=f"{kpis['resources']['total_devices']} Geräte",
        link='/praxiadmin/appointments/resource/',
    ).to_dict())
    
    return cards
def build_status_badges(kpis: dict) -> list[dict]:
    """Erstellt Status-Badges für Termin-Status."""
    status_config = {
        'scheduled': {'label': 'Geplant', 'color': '#FBBC05', 'icon': '📋'},
        'confirmed': {'label': 'Bestätigt', 'color': '#1A73E8', 'icon': '✅'},
        'completed': {'label': 'Abgeschlossen', 'color': '#34A853', 'icon': '✔️'},
        'cancelled': {'label': 'Storniert', 'color': '#EA4335', 'icon': '❌'},
    }
    
    badges = []
    status_counts = kpis['appointments'].get('status_counts', {})
    
    for status, config in status_config.items():
        count = status_counts.get(status, 0)
        badges.append(StatusBadge(
            label=config['label'],
            count=count,
            color=config['color'],
            icon=config['icon'],
        ).to_dict())
    
    return badges


def build_utilization_bars(kpis: dict) -> dict:
    """Erstellt Progress Bars für Auslastung."""
    doctor_bars = []
    for doc in kpis.get('doctor_utilization', []):
        doctor_bars.append(ProgressBar(
            label=doc['name'],
            value=doc['utilization'],
            color=doc['color'],
        ).to_dict())
    
    room_bars = []
    for room in kpis.get('room_utilization', []):
        room_bars.append(ProgressBar(
            label=room['name'],
            value=room['utilization'],
            color=room['color'],
        ).to_dict())
    
    return {
        'doctors': doctor_bars,
        'rooms': room_bars,
    }
