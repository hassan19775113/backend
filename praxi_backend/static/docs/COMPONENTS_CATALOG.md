# PraxiApp Komponenten-Katalog
## Fluent UI Design System für medizinische Praxissoftware

Vollständige Dokumentation aller UI-Komponenten mit Beispielen, Varianten und Designregeln.

---

## 📁 Dateien

| Datei | Beschreibung |
|-------|-------------|
| `design-tokens.css` | CSS-Variablen und Tokens |
| `components.css` | Alle Komponenten-Styles |

---

## 1. Buttons

### Zweck
Aktionen auslösen, Formulare absenden, Navigation initiieren.

### Varianten

| Variante | Klasse | Verwendung |
|----------|--------|------------|
| **Primary** | `.btn--primary` | Hauptaktionen (Speichern, Anlegen) |
| **Secondary** | `.btn--secondary` | Sekundäre Aktionen (Abbrechen) |
| **Ghost** | `.btn--ghost` | Tertiäre Aktionen, Links |
| **Destructive** | `.btn--destructive` | Löschaktionen, gefährliche Aktionen |

### Größen

| Größe | Klasse | Höhe |
|-------|--------|------|
| Small | `.btn--sm` | 28px |
| Medium | (default) | 36px |
| Large | `.btn--lg` | 44px |

### States

| State | Beschreibung |
|-------|-------------|
| Normal | Standard-Darstellung |
| Hover | Leicht dunklere Farbe, verstärkter Schatten |
| Active | Dunkelste Variante, reduzierter Schatten |
| Disabled | 50% Opacity, `cursor: not-allowed` |
| Focus | 2px Primary-Outline mit 2px Offset |

### Designregeln

- **Typografie**: Segoe UI, 14px, Semibold (600)
- **Spacing**: 8px vertikal, 16px horizontal
- **Radius**: 4px
- **Transition**: 150ms für Farben

### HTML-Beispiel

```html
<!-- Primary Button -->
<button class="btn btn--primary">
  <svg class="btn__icon"><!-- Icon --></svg>
  Termin anlegen
</button>

<!-- Secondary Button -->
<button class="btn btn--secondary">Abbrechen</button>

<!-- Ghost Button -->
<button class="btn btn--ghost">Details anzeigen</button>

<!-- Destructive Button -->
<button class="btn btn--destructive">Löschen</button>

<!-- Disabled -->
<button class="btn btn--primary" disabled>Gesperrt</button>

<!-- Button Group -->
<div class="btn-group">
  <button class="btn btn--primary">Speichern</button>
  <button class="btn btn--secondary">Abbrechen</button>
</div>

<!-- Icon-Only Button -->
<button class="btn btn--secondary btn--icon">
  <svg class="btn__icon"><!-- Icon --></svg>
</button>
```

---

## 2. Navigation

### 2.1 Header (App Bar)

#### Zweck
Globale Navigation, App-Branding, Benutzerinformationen.

#### Struktur
- Links: Logo + App-Titel
- Mitte: Optional Suche oder Tabs
- Rechts: User-Info, Benachrichtigungen

#### Designregeln

| Eigenschaft | Wert |
|-------------|------|
| Höhe | 48px |
| Hintergrund | `--color-surface` (#FFFFFF) |
| Border | 1px bottom, `--color-border` |
| Position | Sticky, top: 0 |
| Z-Index | 1100 |

```html
<header class="app-header">
  <div class="app-header__brand">
    <img src="logo.svg" alt="PraxiApp" class="app-header__logo">
    <h1 class="app-header__title">PraxiApp</h1>
  </div>
  
  <nav class="app-header__nav">
    <!-- Notifications, Actions -->
  </nav>
  
  <div class="app-header__user">
    <div class="app-header__avatar">MK</div>
    <div class="app-header__user-info">
      <span class="app-header__user-name">Max König</span>
      <span class="app-header__user-role">Administrator</span>
    </div>
  </div>
</header>
```

### 2.2 Sidebar

#### Zweck
Hauptnavigation der Anwendung, strukturiert nach Bereichen.

#### Sektionen (gemäß PraxiApp)

| Sektion | Links |
|---------|-------|
| **Dashboards** | Übersicht, Termine-Dashboard, OP-Dashboard |
| **Termine** | Kalender, Termine, OP-Planung |
| **Core** | Benutzer, Rollen, Audit-Log |
| **Medical** | Patienten, Krankenakten |

#### States

| State | Styling |
|-------|---------|
| Normal | Text: `--color-text-secondary`, BG: transparent |
| Hover | BG: `--color-neutral-20`, Text: primary |
| Active | BG: `--color-primary-light`, Text: `--color-primary`, Border-left: 3px primary |

#### Designregeln

| Eigenschaft | Wert |
|-------------|------|
| Breite | 240px (collapsed: 56px) |
| Hintergrund | `--color-surface` |
| Border | 1px right |
| Link-Padding | 8px 16px |
| Icon-Größe | 20px |

```html
<aside class="sidebar">
  <div class="sidebar__section">
    <h2 class="sidebar__section-title">Dashboards</h2>
    <nav class="sidebar__nav">
      <a href="#" class="sidebar__link sidebar__link--active">
        <svg class="sidebar__link-icon"><!-- Icon --></svg>
        <span class="sidebar__link-text">Übersicht</span>
      </a>
      <a href="#" class="sidebar__link">
        <svg class="sidebar__link-icon"><!-- Icon --></svg>
        <span class="sidebar__link-text">Termine-Dashboard</span>
      </a>
    </nav>
  </div>
  
  <div class="sidebar__section">
    <h2 class="sidebar__section-title">Termine</h2>
    <nav class="sidebar__nav">
      <a href="#" class="sidebar__link">
        <svg class="sidebar__link-icon"><!-- Icon --></svg>
        <span class="sidebar__link-text">Kalender</span>
        <span class="sidebar__link-badge">3</span>
      </a>
    </nav>
  </div>
</aside>
```

---

## 3. Cards / Panels

### Zweck
Inhaltsgruppierung, Datenvisualisierung, Formularbereiche.

### Varianten

| Variante | Klasse | Beschreibung |
|----------|--------|-------------|
| Default | `.card` | Standard-Karte |
| Elevated | `.card--elevated` | Verstärkter Schatten |
| Flat | `.card--flat` | Ohne Schatten |
| Interactive | `.card--interactive` | Klickbar mit Hover-Effekt |

### Struktur

```
┌─────────────────────────────────┐
│ Header (Titel + Actions)        │
├─────────────────────────────────┤
│                                 │
│ Body (Inhalt)                   │
│                                 │
├─────────────────────────────────┤
│ Footer (Buttons, Meta)          │
└─────────────────────────────────┘
```

### Designregeln

| Eigenschaft | Wert |
|-------------|------|
| Hintergrund | `--color-surface` (#FFFFFF) |
| Border | 1px `--color-border` |
| Radius | 8px |
| Padding (Body) | 16px (sm: 12px, lg: 24px) |
| Shadow | `--shadow-card` (elevation-2) |
| Shadow Hover | `--shadow-card-hover` (elevation-4) |

```html
<div class="card">
  <div class="card__header">
    <div>
      <h3 class="card__title">Patienteninformation</h3>
      <p class="card__subtitle">Letzte Aktualisierung: Heute, 14:30</p>
    </div>
    <div class="card__actions">
      <button class="btn btn--ghost btn--sm">Bearbeiten</button>
    </div>
  </div>
  
  <div class="card__body">
    <!-- Karteninhalt -->
  </div>
  
  <div class="card__footer">
    <button class="btn btn--secondary btn--sm">Abbrechen</button>
    <button class="btn btn--primary btn--sm">Speichern</button>
  </div>
</div>
```

---

## 4. Tabellen

### Zweck
Strukturierte Darstellung von Listen und Daten.

### Varianten

| Variante | Klasse | Beschreibung |
|----------|--------|-------------|
| Default | `.table` | Standard-Tabelle |
| Striped | `.table--striped` | Alternierende Zeilenfarben |
| Compact | `.table--compact` | Reduziertes Padding |
| Borderless | `.table--borderless` | Ohne Linien |
| Responsive | `.table--responsive` | Card-Layout auf Mobile |

### Designregeln

| Element | Styling |
|---------|---------|
| **Header** | BG: `--color-neutral-20`, Text: `--color-neutral-70`, 12px uppercase |
| **Zeilen** | Border-bottom: 1px `--color-border-subtle` |
| **Hover** | BG: `--color-neutral-20` |
| **Selected** | BG: `--color-primary-light` |
| **Padding** | 12px horizontal, 12px vertikal |

### Status-Badges in Tabellen

```html
<span class="table__status table__status--success">Bestätigt</span>
<span class="table__status table__status--warning">Ausstehend</span>
<span class="table__status table__status--error">Abgesagt</span>
<span class="table__status table__status--info">Geplant</span>
```

### HTML-Beispiel

```html
<div class="table-container">
  <table class="table table--striped">
    <thead>
      <tr>
        <th class="th--sortable th--sorted">Patient ↓</th>
        <th>Termin</th>
        <th>Arzt</th>
        <th>Status</th>
        <th class="table__cell--center">Aktionen</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Max Mustermann</td>
        <td>29.12.2025, 10:00</td>
        <td>Dr. Schmidt</td>
        <td><span class="table__status table__status--success">Bestätigt</span></td>
        <td class="table__actions">
          <button class="btn btn--ghost btn--sm btn--icon">✏️</button>
          <button class="btn btn--ghost btn--sm btn--icon">🗑️</button>
        </td>
      </tr>
    </tbody>
  </table>
</div>
```

### Responsive Tabelle

```html
<table class="table table--responsive">
  <tbody>
    <tr>
      <td data-label="Patient">Max Mustermann</td>
      <td data-label="Termin">29.12.2025, 10:00</td>
      <td data-label="Status">Bestätigt</td>
    </tr>
  </tbody>
</table>
```

---

## 5. Formulare

### Zweck
Dateneingabe, Filterung, Benutzerinteraktion.

### Komponenten

| Komponente | Klasse |
|------------|--------|
| Input | `.input` |
| Select | `.input.select` |
| Textarea | `.input.textarea` |
| Checkbox | `.checkbox` |
| Radio | `.radio` |
| Toggle | `.toggle` |

### Input States

| State | Styling |
|-------|---------|
| Normal | BG: `--color-neutral-10`, Border: `--color-border` |
| Hover | BG: `--color-neutral-20`, Border: `--color-border-strong` |
| Focus | BG: `--color-surface`, Border: `--color-primary`, Box-shadow |
| Error | Border: `--color-error` |
| Disabled | BG: `--color-disabled-background`, Opacity 0.5 |

### Designregeln

| Eigenschaft | Wert |
|-------------|------|
| Höhe | 36px (sm: 28px, lg: 44px) |
| Padding | 8px 12px |
| Radius | 4px |
| Font | 14px Regular |
| Label | 14px Medium, `--color-text-primary` |

### HTML-Beispiel

```html
<form class="form">
  <div class="form__row form__row--2">
    <div class="form-group">
      <label class="form-label form-label--required">Vorname</label>
      <input type="text" class="input" placeholder="Vorname eingeben">
    </div>
    
    <div class="form-group">
      <label class="form-label form-label--required">Nachname</label>
      <input type="text" class="input" placeholder="Nachname eingeben">
    </div>
  </div>
  
  <div class="form-group">
    <label class="form-label">E-Mail</label>
    <div class="input-group">
      <svg class="input-group__icon"><!-- Mail Icon --></svg>
      <input type="email" class="input input--with-icon-left" placeholder="email@beispiel.de">
    </div>
    <span class="form-helper">Wir senden eine Bestätigung an diese Adresse.</span>
  </div>
  
  <div class="form-group">
    <label class="form-label">Arzt</label>
    <select class="input select">
      <option>Bitte wählen...</option>
      <option>Dr. Schmidt</option>
      <option>Dr. Müller</option>
    </select>
  </div>
  
  <div class="form-group">
    <label class="form-label">Notizen</label>
    <textarea class="input textarea" rows="4" placeholder="Zusätzliche Informationen..."></textarea>
  </div>
  
  <div class="form-group">
    <label class="checkbox">
      <input type="checkbox" class="checkbox__input">
      <span>Erinnerung per SMS senden</span>
    </label>
  </div>
  
  <div class="form-group">
    <label class="toggle">
      <input type="checkbox" class="toggle__input">
      <span class="toggle__track">
        <span class="toggle__thumb"></span>
      </span>
      <span>Aktiv</span>
    </label>
  </div>
  
  <div class="form-actions">
    <button type="button" class="btn btn--secondary">Abbrechen</button>
    <button type="submit" class="btn btn--primary">Speichern</button>
  </div>
</form>
```

### Fehlerdarstellung

```html
<div class="form-group">
  <label class="form-label form-label--required">E-Mail</label>
  <input type="email" class="input input--error" value="ungültig">
  <span class="form-helper form-helper--error">Bitte geben Sie eine gültige E-Mail-Adresse ein.</span>
</div>
```

---

## 6. KPI-Widgets

### Zweck
Darstellung von Kennzahlen, Statistiken und Metriken auf Dashboards.

### Varianten

| Variante | Klasse | Beschreibung |
|----------|--------|-------------|
| Default | `.kpi-widget` | Standard-Widget |
| Compact | `.kpi-widget--compact` | Horizontale Anordnung |
| Clickable | `.kpi-widget--clickable` | Mit Hover-Effekt |

### Struktur

```
┌─────────────────────────────────┐
│ [Icon]              TITEL       │
│                                 │
│        1.234                    │  ← Wert (groß, bold)
│        ↑ 12%                    │  ← Änderung (optional)
│                                 │
│ Verglichen mit Vormonat         │  ← Footer (optional)
└─────────────────────────────────┘
```

### Designregeln

| Eigenschaft | Wert |
|-------------|------|
| Hintergrund | `--color-surface` |
| Border | 1px `--color-border` |
| Radius | 8px |
| Padding | 16px |
| Titel | 12px Medium, uppercase, `--color-text-secondary` |
| Wert | 24px Bold, `--color-text-primary` |

### Icon-Varianten

| Variante | Icon-BG | Icon-Farbe |
|----------|---------|------------|
| Primary | `--color-primary-light` | `--color-primary` |
| Success | `--color-success-background` | `--color-success` |
| Warning | `--color-warning-background` | `--color-accent-yellow-dark` |
| Error | `--color-error-background` | `--color-error` |
| Teal | `--color-accent-teal-light` | `--color-accent-teal` |

### HTML-Beispiel

```html
<div class="kpi-grid">
  <!-- Standard KPI -->
  <div class="kpi-widget">
    <div class="kpi-widget__header">
      <h4 class="kpi-widget__title">Termine heute</h4>
      <div class="kpi-widget__icon kpi-widget__icon--primary">
        📅
      </div>
    </div>
    <p class="kpi-widget__value">24</p>
    <span class="kpi-widget__change kpi-widget__change--positive">
      ↑ 12% vs. Vorwoche
    </span>
  </div>
  
  <!-- Mit Footer -->
  <div class="kpi-widget">
    <div class="kpi-widget__header">
      <h4 class="kpi-widget__title">Auslastung</h4>
      <div class="kpi-widget__icon kpi-widget__icon--success">
        📊
      </div>
    </div>
    <p class="kpi-widget__value">87%</p>
    <p class="kpi-widget__footer">Durchschnitt der letzten 7 Tage</p>
  </div>
  
  <!-- Negative Entwicklung -->
  <div class="kpi-widget">
    <div class="kpi-widget__header">
      <h4 class="kpi-widget__title">Absagen</h4>
      <div class="kpi-widget__icon kpi-widget__icon--error">
        ❌
      </div>
    </div>
    <p class="kpi-widget__value">3</p>
    <span class="kpi-widget__change kpi-widget__change--negative">
      ↑ 50% mehr als üblich
    </span>
  </div>
  
  <!-- Compact Variante -->
  <div class="kpi-widget kpi-widget--compact">
    <div class="kpi-widget__icon kpi-widget__icon--teal">
      👥
    </div>
    <div class="kpi-widget__content">
      <h4 class="kpi-widget__title">Patienten</h4>
      <p class="kpi-widget__value">1.234</p>
    </div>
  </div>
</div>
```

---

## 7. Modale

### Zweck
Fokussierte Interaktionen, Bestätigungen, Formulare, Details.

### Größen

| Größe | Klasse | Max-Width |
|-------|--------|-----------|
| Small | `.modal--sm` | 360px |
| Default | (none) | 480px |
| Large | `.modal--lg` | 640px |
| XL | `.modal--xl` | 800px |
| Fullscreen | `.modal--fullscreen` | 100% |

### Struktur

```
┌────────────────────────────────────┐
│ Titel                         [X] │  ← Header
├────────────────────────────────────┤
│                                    │
│ Inhalt                             │  ← Body (scrollbar)
│                                    │
├────────────────────────────────────┤
│                   [Abbrechen] [OK] │  ← Footer
└────────────────────────────────────┘
```

### Designregeln

| Eigenschaft | Wert |
|-------------|------|
| Hintergrund | `--color-surface` |
| Backdrop | `rgba(0, 0, 0, 0.4)` |
| Radius | 8px |
| Shadow | `--shadow-modal` (elevation-64) |
| Header Padding | 16px 24px |
| Body Padding | 24px |
| Footer Padding | 16px 24px |
| Footer BG | `--color-surface-alt` |

### Animation

- **Öffnen**: Scale 0.95 → 1, translateY 10px → 0, 200ms
- **Backdrop**: Opacity 0 → 1, 200ms

### HTML-Beispiel

```html
<!-- Backdrop -->
<div class="modal-backdrop modal-backdrop--visible">
  <!-- Standard Modal -->
  <div class="modal">
    <div class="modal__header">
      <h2 class="modal__title">Termin bearbeiten</h2>
      <button class="modal__close" aria-label="Schließen">×</button>
    </div>
    
    <div class="modal__body">
      <form class="form">
        <!-- Formularinhalt -->
      </form>
    </div>
    
    <div class="modal__footer">
      <button class="btn btn--secondary">Abbrechen</button>
      <button class="btn btn--primary">Speichern</button>
    </div>
  </div>
</div>

<!-- Bestätigungs-Dialog -->
<div class="modal-backdrop modal-backdrop--visible">
  <div class="modal modal--sm modal--confirm">
    <div class="modal__body">
      <div class="modal__icon modal__icon--danger">⚠️</div>
      <h2 class="modal__title">Termin löschen?</h2>
      <p class="modal__message">
        Diese Aktion kann nicht rückgängig gemacht werden.
        Der Patient wird per E-Mail benachrichtigt.
      </p>
    </div>
    
    <div class="modal__footer">
      <button class="btn btn--secondary">Abbrechen</button>
      <button class="btn btn--destructive">Löschen</button>
    </div>
  </div>
</div>
```

---

## 8. Zusätzliche Komponenten

### Badges

```html
<span class="badge badge--default">Standard</span>
<span class="badge badge--primary">Neu</span>
<span class="badge badge--success">Aktiv</span>
<span class="badge badge--warning">Ausstehend</span>
<span class="badge badge--error">Abgesagt</span>
<span class="badge badge--info">Information</span>
```

### Alerts

```html
<div class="alert alert--info">
  <svg class="alert__icon">ℹ️</svg>
  <div class="alert__content">
    <h4 class="alert__title">Hinweis</h4>
    <p class="alert__message">Es gibt neue Termine für heute.</p>
  </div>
</div>

<div class="alert alert--success">...</div>
<div class="alert alert--warning">...</div>
<div class="alert alert--error">...</div>
```

### Tabs

```html
<div class="tabs">
  <ul class="tabs__list">
    <li><button class="tabs__tab tabs__tab--active">Übersicht</button></li>
    <li><button class="tabs__tab">Termine</button></li>
    <li><button class="tabs__tab">Dokumente</button></li>
  </ul>
</div>
<div class="tabs__panel">
  <!-- Tab-Inhalt -->
</div>
```

### Progress Bar

```html
<div class="progress">
  <div class="progress__bar" style="width: 75%"></div>
</div>

<div class="progress progress--success">
  <div class="progress__bar" style="width: 100%"></div>
</div>
```

### Empty State

```html
<div class="empty-state">
  <div class="empty-state__icon">📭</div>
  <h3 class="empty-state__title">Keine Termine gefunden</h3>
  <p class="empty-state__description">
    Es gibt keine Termine für den ausgewählten Zeitraum.
  </p>
  <button class="btn btn--primary">Termin anlegen</button>
</div>
```

### Skeleton Loading

```html
<div class="card">
  <div class="card__body">
    <div class="skeleton skeleton--title"></div>
    <div class="skeleton skeleton--text" style="margin-top: 8px;"></div>
    <div class="skeleton skeleton--text" style="margin-top: 4px; width: 80%;"></div>
  </div>
</div>
```

---

## 🎨 Farb-Schnellreferenz

### Primär
| Token | Hex | Verwendung |
|-------|-----|------------|
| `--color-primary` | #0F6CBD | Buttons, Links, Active |
| `--color-primary-hover` | #115EA3 | Hover-Zustände |
| `--color-primary-light` | #E8F3FC | Hintergründe, Badges |

### Semantic
| Token | Hex | Verwendung |
|-------|-----|------------|
| `--color-success` | #107C10 | Erfolg, Bestätigt |
| `--color-warning` | #FCE100 | Warnung, Ausstehend |
| `--color-error` | #D13438 | Fehler, Abgesagt |
| `--color-info` | #0F6CBD | Information |

### Medical-Specific
| Token | Hex | Verwendung |
|-------|-----|------------|
| `--color-medical-urgent` | #D13438 | Notfall |
| `--color-medical-attention` | #FF8C00 | Aufmerksamkeit |
| `--color-medical-normal` | #107C10 | Normal/OK |
| `--color-medical-scheduled` | #0F6CBD | Geplant |
| `--color-medical-completed` | #00B7C3 | Abgeschlossen |

---

## 📐 Spacing-Schnellreferenz

| Token | Wert | Verwendung |
|-------|------|------------|
| `--spacing-1` | 4px | Inline-Elemente, Icons |
| `--spacing-2` | 8px | Button-Gaps, kleine Abstände |
| `--spacing-3` | 12px | Input-Padding, Card-Header |
| `--spacing-4` | 16px | Card-Body, Standard-Gap |
| `--spacing-6` | 24px | Section-Padding, große Gaps |
| `--spacing-8` | 32px | Page-Sections |

---

## 🔗 Integration

```html
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PraxiApp</title>
  <link rel="stylesheet" href="/static/css/design-tokens.css">
  <link rel="stylesheet" href="/static/css/components.css">
</head>
<body>
  <!-- App-Struktur -->
  <header class="app-header">...</header>
  <aside class="sidebar">...</aside>
  <main class="main-content">...</main>
</body>
</html>
```

---

*PraxiApp Design System v1.0.0 – Microsoft Fluent UI Style für medizinische Anwendungen*
