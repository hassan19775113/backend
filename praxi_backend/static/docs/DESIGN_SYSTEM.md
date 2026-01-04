# PraxiApp Design System v3.0

## Calm Medical UI - Outlook-Inspired

Ein vollständiges UI-Design-System für medizinische Web-Applikationen im Microsoft Outlook-Stil.

---

## Design-Philosophie

| Prinzip | Beschreibung |
|---------|-------------|
| **Calm Medical UI** | Steril, freundlich, nicht überladen |
| **Outlook-Inspired** | Helle Panels, klare Navigation, moderne Komponenten |
| **Functional Clarity** | Fokus auf Lesbarkeit und Interaktion |
| **Trust & Safety** | Farben vermitteln Professionalität und Zuverlässigkeit |

---

## Farbsystem

### Primärfarben (Outlook Blue)

| Token | Hex | Verwendung |
|-------|-----|------------|
| `--prx-primary-50` | `#F0F7FF` | Hintergrund sehr hell |
| `--prx-primary-100` | `#E1EFFF` | Ausgewählte Elemente |
| `--prx-primary-200` | `#C3DFFF` | Hover-Zustände |
| `--prx-primary-500` | `#0078D4` | **Hauptfarbe** - Buttons, Links, Header |
| `--prx-primary-600` | `#106EBE` | Hover-Zustand primär |
| `--prx-primary-700` | `#005A9E` | Aktive Links |

### Sekundärfarben (Soft Teal)

| Token | Hex | Verwendung |
|-------|-----|------------|
| `--prx-secondary-100` | `#CCF0F3` | Hintergrund hell |
| `--prx-secondary-400` | `#4FB3BF` | **Hauptfarbe** - Akzente, Object Tools |
| `--prx-secondary-600` | `#2E7A83` | Hover-Zustand |

### Akzentfarben (Mint Green)

| Token | Hex | Verwendung |
|-------|-----|------------|
| `--prx-accent-100` | `#D5F2E8` | Hintergrund hell |
| `--prx-accent-300` | `#7BC6B0` | **Hauptfarbe** - Highlights, Tags |
| `--prx-accent-500` | `#3D9A82` | Hover-Zustand |

### Neutrale Farben

| Token | Hex | Verwendung |
|-------|-----|------------|
| `--prx-neutral-0` | `#FFFFFF` | Reines Weiß, Card-Hintergrund |
| `--prx-neutral-100` | `#F5F7FA` | **Seiten-Hintergrund** |
| `--prx-neutral-250` | `#E1E4E8` | **Rahmen / Borders** |
| `--prx-neutral-500` | `#6B7280` | Beschreibungstext |
| `--prx-neutral-800` | `#2E2E2E` | **Haupttext** |
| `--prx-neutral-900` | `#1F2937` | Überschriften |

### Status-Farben

| Status | Haupt-Hex | Hell-Hex | Verwendung |
|--------|-----------|----------|------------|
| Success | `#22C55E` | `#F0FDF4` | Erfolgsmeldungen, Positiv |
| Warning | `#F4A259` | `#FFFBEB` | Warnungen (Soft Orange) |
| Danger | `#D9534F` | `#FEF2F2` | Fehler, Medical Red |
| Info | `#0EA5E9` | `#F0F9FF` | Informationen, Sky Blue |

### Interaktionsfarben

| Token | Hex | Verwendung |
|-------|-----|------------|
| `--prx-hover-bg` | `#E6F0FA` | Hover-Hintergrund (Tabellen, Listen) |
| `--prx-selected-bg` | `#E1EFFF` | Ausgewählte Zeilen |
| `--prx-focus-ring` | `rgba(0, 120, 212, 0.25)` | Focus-Ring um Inputs |

---

## Typografie

### Font-Familie

```css
font-family: 'Segoe UI', 'Inter', -apple-system, BlinkMacSystemFont, 'Roboto', sans-serif;
```

### Schriftgrößen

| Token | Größe | Verwendung |
|-------|-------|------------|
| `--prx-text-xs` | 11px | Captions, Labels |
| `--prx-text-sm` | 13px | Kleine Texte, Buttons |
| `--prx-text-base` | 14px | **Body-Text** |
| `--prx-text-lg` | 16px | Größerer Text |
| `--prx-text-xl` | 18px | H5, Modal-Titel |
| `--prx-text-2xl` | 20px | H4 |
| `--prx-text-3xl` | 24px | H3 |
| `--prx-text-4xl` | 30px | H1-H2, KPI-Werte |

### Schriftgewichte

| Token | Gewicht | Verwendung |
|-------|---------|------------|
| `--prx-font-normal` | 400 | Body-Text |
| `--prx-font-medium` | 500 | Labels, Links |
| `--prx-font-semibold` | 600 | Überschriften |
| `--prx-font-bold` | 700 | KPI-Werte |

---

## Abstände (8px Basis)

| Token | Wert | Verwendung |
|-------|------|------------|
| `--prx-space-1` | 4px | Minimaler Abstand |
| `--prx-space-2` | 8px | Klein |
| `--prx-space-3` | 12px | Standard |
| `--prx-space-4` | 16px | Mittel |
| `--prx-space-6` | 24px | **Standard-Gap** |
| `--prx-space-8` | 32px | Groß |

---

## Schatten

| Token | Beschreibung |
|-------|-------------|
| `--prx-shadow-xs` | Minimaler Schatten |
| `--prx-shadow-sm` | Kleine Schatten für Cards |
| `--prx-shadow-md` | Standard-Hover-Schatten |
| `--prx-shadow-lg` | Modale, Popover |
| `--prx-shadow-glow` | Blauer Glow-Effekt |

---

## Border-Radius

| Token | Wert | Verwendung |
|-------|------|------------|
| `--prx-radius-sm` | 4px | Kleine Buttons |
| `--prx-radius-md` | 6px | **Standard** - Buttons, Inputs |
| `--prx-radius-lg` | 8px | **Cards, Module** |
| `--prx-radius-xl` | 12px | Modale |
| `--prx-radius-full` | 9999px | Badges, Pills |

---

## Komponenten

### Header

```css
.prx-header {
    background: "#e3e3e3"/*linear-gradient(135deg, #0078D4 0%, #106EBE 100%);*/
    box-shadow: 0 2px 8px rgba(0, 120, 212, 0.15);
}
```

### Sidebar (Navigation)

- Heller Hintergrund (`#FFFFFF`)
- Linke Akzentlinie für aktive Links (`#0078D4`)
- Hover: `#E6F0FA` Hintergrund
- Aktiv: `#E1EFFF` Hintergrund mit blauer Linie

### Cards

```css
.prx-card {
    background: #FFFFFF;
    border: 1px solid #E1E4E8;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}
```

### KPI-Widgets

- Obere Farbakzent-Linie (4px)
- Icon mit Farbhintergrund
- Große Zahlen (30px, bold)
- Trend-Badge (pill-shaped)

### Buttons

| Typ | Hintergrund | Text | Border |
|-----|-------------|------|--------|
| Primary | `#0078D4` | Weiß | - |
| Secondary | Weiß | `#0078D4` | `#0078D4` |
| Ghost | Transparent | `#6B7280` | - |
| Success | `#22C55E` | Weiß | - |
| Danger | `#D9534F` | Weiß | - |

### Tabellen

- Header: `#F5F7FA` Hintergrund, uppercase, 11px
- Zeilen: Weiß, Hover: `#E6F0FA`
- Rahmen: `#F0F2F5` zwischen Zeilen
- Links: `#0078D4`, medium weight

### Formulare

- Inputs: `#D1D5DB` Border, 8px Padding
- Focus: `#0078D4` Border + 3px Focus-Ring
- Labels: `#374151`, 500 weight

### Badges

- Pill-shaped (`border-radius: 9999px`)
- Helle Hintergrundfarbe + dunkle Textfarbe
- Klein: 11px Font, 4px 8px Padding

---

## Layout (12-Spalten-Grid)

```css
.prx-grid {
    display: grid;
    gap: 24px; /* --prx-space-6 */
}

.prx-grid-4 { grid-template-columns: repeat(4, 1fr); }
.prx-grid-3 { grid-template-columns: repeat(3, 1fr); }
.prx-grid-2 { grid-template-columns: repeat(2, 1fr); }
```

### Responsive Breakpoints

| Breakpoint | Verhalten |
|------------|-----------|
| < 768px | Sidebar versteckt, 1-Spalten-Grid |
| < 1200px | 4-Spalten → 2-Spalten |

---

## Transitions

| Token | Wert | Verwendung |
|-------|------|------------|
| `--prx-transition-fast` | 150ms ease | Hover-Effekte |
| `--prx-transition-normal` | 200ms ease | Standard |
| `--prx-transition-slow` | 300ms ease | Komplexe Animationen |

---

## Dark Mode

**Nicht unterstützt.** Das Design-System erzwingt immer den Light Mode:

```css
:root {
    color-scheme: light only !important;
}
```

Dies stellt sicher, dass die medizinische UI immer hell, sauber und professionell erscheint.

---

## Datei-Struktur

```
praxi_backend/static/
├── css/
│   └── praxiapp-design-system.css    # Haupt-Design-System
└── admin/
    └── css/
        └── praxiapp-admin.css        # Django Admin Styling
```

---

## Verwendung

### Dashboard-Templates

```html
<link rel="stylesheet" href="{% static 'css/praxiapp-design-system.css' %}?v=3.0">
```

### Admin-Templates (automatisch in base_site.html)

```html
<link rel="stylesheet" href="{% static 'admin/css/praxiapp-admin.css' %}?v=3.0">
```

---

## Chart.js Farben

```javascript
const PRX_COLORS = {
    primary: '#0078D4',      // Outlook Blue
    secondary: '#4FB3BF',    // Soft Teal
    accent: '#7BC6B0',       // Mint Green
    warning: '#F4A259',      // Soft Orange
    danger: '#D9534F',       // Medical Red
    success: '#22C55E',      // Green
    info: '#0EA5E9',         // Sky Blue
    
    palette: [
        '#0078D4', '#4FB3BF', '#7BC6B0', '#F4A259',
        '#0EA5E9', '#22C55E', '#D9534F', '#6B7280'
    ]
};
```

---

## Best Practices

1. **Weißraum** - Großzügige Abstände für Klarheit
2. **Kontraste** - Sanfte Kontraste, nicht aggressiv
3. **Icons** - Einfache, klare Icons ohne Überladung
4. **Fokus** - Deutlich sichtbare Focus-States
5. **Hover** - Sanfte Hover-Effekte (`#E6F0FA`)
6. **Loading** - Keine aggressiven Spinner/Animationen
7. **Fehler** - Dezente, aber deutliche Fehlermeldungen

---

*Version 3.0 - Calm Medical UI - © 2025 PraxiApp*
