# PraxiApp Komponenten‑Designsystem (Fluent‑UI Stil)

Status: **Source of truth für Komponenten‑Regeln** (HTML‑Struktur + CSS‑Klassen), basierend auf:
- Tokens: `praxi_backend/static/css/design-tokens.css`
- Komponenten: `praxi_backend/static/css/components.css`

Ziel: Ruhige, professionelle UI für medizinische Praxissoftware (lange Nutzungsdauer, hohe Lesbarkeit, klare Interaktion).

---

## CSS‑Architektur (empfohlen)

**Layering (von allgemein nach spezifisch):**
1. **Tokens**: `design-tokens.css` (Farben, Typografie, Spacing, Radius, Shadows, Z‑Index)
2. **Components**: `components.css` (BEM‑artige Klassen pro Bauteil)
3. **Theme/Overrides** (optional): `theme.css` (z. B. Gradients, Glass‑Effekte, semantische Mappings)
4. **Pages**: `pages/*.css` (nur Layout/Seiten‑Spezifika, keine neuen Tokens)

**Regeln:**
- Komponenten verwenden **nur Tokens** (keine Hardcoded Farben/Abstände), außer wo explizit dokumentiert.
- States erfolgen bevorzugt über **`:hover`, `:active`, `:focus-visible`, `:disabled`**.
- Interaktive Elemente müssen **Focus‑Visible** haben (Tastatur‑Nutzung, Barrierefreiheit).

---

## 1) Buttons

### Zweck
Primäre Interaktionspunkte (Speichern, Anlegen, Navigationsaktionen, gefährliche Aktionen wie Löschen).

### Varianten
- **Primary**: Hauptaktion pro View
- **Secondary**: Alternative Aktion
- **Ghost**: Niedrige Prominenz (Toolbar, Inline)
- **Destructive**: Irreversible Aktion

Zusätzlich vorhanden:
- Größen: `btn--sm`, `btn` (md), `btn--lg`
- Icon‑Button: `btn--icon`
- Gruppen: `btn-group`, `btn-group--attached`

### States
Gilt für alle Varianten (`.btn`):
- **Normal**: Standard
- **Hover**: sanfte Hintergrund/Border‑Änderung (Fluent‑typisch “quiet”)
- **Active/Pressed**: dunkler/“pressed”
- **Disabled**: reduzierte Deckkraft, nicht klickbar
- **Focus**: `:focus-visible` Outline

### Typografie
- Font: `--font-family-primary`
- Size: `--body-size` (md), `--caption-size` (sm), `--subtitle-size` (lg)
- Weight: `--font-weight-semibold`

### Spacing
- Gap Icon/Text: `--spacing-2`
- Padding: `--spacing-button-padding-y` / `--spacing-button-padding-x`
- Height: `--button-height-*`

### Farben (Tokens)
- Primary: `--color-primary`, `--color-primary-hover`, `--color-primary-pressed`, `--color-text-inverse`
- Secondary: `--color-surface`, `--color-border-strong`, `--color-text-primary`, Hover `--color-neutral-20`
- Ghost: Text `--color-primary`, Hover `--color-primary-light`
- Destructive: `--color-error`, `--color-accent-red-dark`, Backgrounds `--color-error-background`

### Beispiel‑HTML
```html
<div class="btn-group">
  <button class="btn btn--primary">Speichern</button>
  <button class="btn btn--secondary">Abbrechen</button>
  <button class="btn btn--ghost">Details</button>
  <button class="btn btn--destructive">Löschen</button>
</div>
```

### CSS‑Struktur (Klassen)
- Basis: `.btn`, `.btn:focus-visible`, `.btn:disabled`
- Varianten: `.btn--primary`, `.btn--secondary`, `.btn--ghost`, `.btn--destructive`
- Größen: `.btn--sm`, `.btn--lg`

---

## 2) Navigation

### Zweck
Kontext‑Rahmen der App: schneller Wechsel zwischen Domänen (Dashboards, Termine, Core, Medical) und User‑Kontext.

### 2.1 Header (App‑Titel + User‑Info)

#### Varianten
- Standard: `.app-header`
- Brand‑Block: `.app-header__brand`
- User‑Block: `.app-header__user`

#### States
- User‑Block hover: `background-color: var(--color-neutral-20)`
- Fokus: per `:focus-visible` auf interaktiven Elementen (z. B. User‑Button)

#### Typografie
- Titel: `--subtitle-size`, `--font-weight-semibold`
- User Name: `--body-size`, `--font-weight-medium`
- User Role: `--caption-size`

#### Spacing
- Header Höhe: 48px (`height: 48px`)
- Horizontal Padding: `--spacing-4`

#### Farben (Tokens)
- Background: `--color-surface`
- Border: `--color-border`
- Schatten: `--shadow-sm`

#### Beispiel‑HTML
```html
<header class="app-header">
  <div class="app-header__brand">
    <img class="app-header__logo" src="/static/img/logo.svg" alt="PraxiApp" />
    <h1 class="app-header__title">PraxiApp</h1>
  </div>

  <nav class="app-header__nav" aria-label="Header Navigation">
    <a class="btn btn--ghost" href="/dashboard/">Dashboard</a>
    <a class="btn btn--ghost" href="/appointments/">Termine</a>
  </nav>

  <button class="app-header__user" type="button" aria-label="Benutzermenü öffnen">
    <div class="app-header__avatar" aria-hidden="true">DR</div>
    <div class="app-header__user-info">
      <div class="app-header__user-name">Dr. Beispiel</div>
      <div class="app-header__user-role">doctor</div>
    </div>
  </button>
</header>
```

### 2.2 Sidebar (Links + Sektionen)

#### Zweck
Schneller Modul‑Wechsel. Aktiver Link ist primär; Hover ist neutral‑20.

#### Struktur & Sektionen
- Sektion: `.sidebar__section`
- Titel: `.sidebar__section-title`
- Linkliste: `.sidebar__nav`
- Link: `.sidebar__link` (+ `--active`)

Empfohlene Sektionen:
- **Dashboards**
- **Termine**
- **Core**
- **Medical**

#### Varianten
- Default: `.sidebar`
- Collapsed: `.sidebar sidebar--collapsed`

#### States
- Normal: neutral text
- Hover: `background-color: var(--color-neutral-20)`
- Active: `background-color: var(--color-primary-light)`, `border-left-color: var(--color-primary)`
- Focus: `:focus-visible` auf den Links

#### Typografie
- Section title: Overline‑Tokens (`--overline-*`)
- Link: `--body-size`

#### Spacing
- Sidebar width: 240px (collapsed 56px)
- Link padding: `--spacing-2` / `--spacing-4`

#### Farben (Tokens)
- Background: `--color-surface`
- Divider: `--color-divider`
- Active: `--color-primary-light`, Text `--color-primary`
- Hover: `--color-neutral-20`

#### Beispiel‑HTML
```html
<aside class="sidebar" aria-label="Hauptnavigation">
  <section class="sidebar__section">
    <h2 class="sidebar__section-title">Dashboards</h2>
    <ul class="sidebar__nav">
      <li><a class="sidebar__link sidebar__link--active" href="/dashboard/">Übersicht</a></li>
      <li><a class="sidebar__link" href="/dashboard/operations/">OP</a></li>
    </ul>
  </section>

  <section class="sidebar__section">
    <h2 class="sidebar__section-title">Termine</h2>
    <ul class="sidebar__nav">
      <li><a class="sidebar__link" href="/appointments/">Kalender</a></li>
      <li><a class="sidebar__link" href="/operations/">Operationen</a></li>
    </ul>
  </section>

  <section class="sidebar__section">
    <h2 class="sidebar__section-title">Core</h2>
    <ul class="sidebar__nav">
      <li><a class="sidebar__link" href="/core/users/">Benutzer</a></li>
      <li><a class="sidebar__link" href="/core/audit/">Audit</a></li>
    </ul>
  </section>

  <section class="sidebar__section">
    <h2 class="sidebar__section-title">Medical</h2>
    <ul class="sidebar__nav">
      <li><a class="sidebar__link" href="/medical/patients/">Patienten</a></li>
    </ul>
  </section>
</aside>
```

---

## 3) Cards / Panels

### Zweck
Information in ruhigen Containern bündeln: Patienten‑Karte, Termin‑Details, Einstellungen, Filter.

### Varianten
- **Card**: `.card` (+ Header/Body/Footer)
- **Elevated**: `.card--elevated`
- **Flat**: `.card--flat`
- **Interactive**: `.card--interactive`
- **Panel**: `.panel` (+ `panel--bordered`, `panel--shadowed`)

### States (Card)
- Normal: Border + Shadow
- Hover (interactive): stärkere Elevation
- Active (interactive): transform reset
- Focus (wenn klickbar): via `:focus-visible` am inneren Link/Button

### Typografie
- Title: `--heading-4-size` / `--heading-4-weight`
- Subtitle: `--caption-size`

### Spacing
- Card Header: `--spacing-4`
- Body: `--spacing-4` (16px)
- Body LG: `--spacing-6` (24px)
- Panel: `--spacing-6` (24px)

### Farben (Tokens)
- Background: `--color-surface` (weiß)
- Border: `--color-border`
- Shadow: `--shadow-card` / `--shadow-card-hover`

### Beispiel‑HTML
```html
<article class="card">
  <header class="card__header">
    <div>
      <h3 class="card__title">Patient</h3>
      <p class="card__subtitle">Letzter Besuch: 12.12.2025</p>
    </div>
    <div class="card__actions">
      <button class="btn btn--secondary btn--sm">Bearbeiten</button>
    </div>
  </header>

  <div class="card__body">
    <!-- Inhalt -->
  </div>

  <footer class="card__footer">
    <button class="btn btn--ghost">Mehr</button>
    <button class="btn btn--primary">Termin erstellen</button>
  </footer>
</article>
```

---

## 4) Tabellen

### Zweck
Daten‑dichte Darstellung (Termine, Operationen, Ressourcen). Klar strukturierte Zeilen, ruhiger Hover.

### Varianten
- Default: `.table`
- Striped: `.table table--striped`
- Compact: `.table table--compact`
- Borderless: `.table table--borderless`
- Responsive: `.table table--responsive` (mobile “cardified” via `data-label`)

### States
- Hover Row: `background-color: var(--color-neutral-20)`
- Selected Row: `background-color: var(--color-primary-light)`
- Sortable Header hover: `background-color: var(--color-neutral-30)`

### Typografie
- Body: `--body-size`
- Header: `--caption-size`, uppercase, `--font-weight-semibold`

### Spacing
- Cells: `--spacing-3` / `--spacing-4`
- Compact cells: `--spacing-2` / `--spacing-3`

### Farben (Tokens)
- Header background: `--color-neutral-20`
- Header text: `--color-neutral-70`
- Lines: `--color-border` / `--color-border-subtle`

### Beispiel‑HTML
```html
<div class="table-container">
  <table class="table table--responsive">
    <thead>
      <tr>
        <th>Patient</th>
        <th>Datum</th>
        <th>Status</th>
        <th class="table__cell--numeric">Dauer</th>
        <th class="table__cell--center">Aktionen</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td data-label="Patient">Max Mustermann</td>
        <td data-label="Datum">29.12.2025</td>
        <td data-label="Status"><span class="table__status table__status--info">Geplant</span></td>
        <td data-label="Dauer" class="table__cell--numeric">30 min</td>
        <td data-label="Aktionen" class="table__cell--center">
          <div class="table__actions">
            <button class="btn btn--ghost btn--sm">Öffnen</button>
          </div>
        </td>
      </tr>
    </tbody>
  </table>
</div>
```

---

## 5) Formulare

### Zweck
Sichere Dateneingabe (Patienten‑/Termin‑/OP‑Daten). Viel Weißraum, eindeutige Labels, ruhige States.

### Varianten
- Layout: `.form`, `.form--inline`, `.form__row`, `.form__row--2`, `.form__row--3`
- Controls: `.input`, `.textarea`, `.select`, `.checkbox`, `.radio`, `.toggle`
- Validation: `.input--error`, `.form-helper--error`

### States
- Normal: neutral Hintergrund + Border
- Hover: leichtes Highlight, Border stärker
- Focus: Border `--color-primary` + Focus‑Ring (box‑shadow)
- Disabled: `--color-disabled-background` + `--color-text-disabled`
- Error: `--color-error`

### Typografie
- Label: `--body-size`, `--font-weight-medium`
- Helper: `--caption-size`

### Spacing
- Group gap: `--spacing-1`
- Form gap: `--spacing-4`
- Input padding: `--spacing-input-padding-x/y`

### Farben (Tokens)
- Input background: **`--color-neutral-30` (Sollwert laut Spezifikation)**
- Focus border: `--color-primary`

### Beispiel‑HTML
```html
<form class="form">
  <div class="form-group">
    <label class="form-label form-label--required" for="patient">Patient</label>
    <input class="input" id="patient" name="patient" placeholder="Name / ID" />
    <div class="form-helper">Mindestens 3 Zeichen.</div>
  </div>

  <div class="form__row form__row--2">
    <div class="form-group">
      <label class="form-label" for="date">Datum</label>
      <input class="input" id="date" name="date" type="date" />
    </div>
    <div class="form-group">
      <label class="form-label" for="time">Uhrzeit</label>
      <input class="input" id="time" name="time" type="time" />
    </div>
  </div>

  <div class="form-actions">
    <button class="btn btn--secondary" type="button">Abbrechen</button>
    <button class="btn btn--primary" type="submit">Speichern</button>
  </div>
</form>
```

---

## 6) KPI‑Widgets

### Zweck
Schneller Überblick (heute Termine, Auslastung, OP‑KPIs). Minimalistisch: Titel + Wert + optional Icon/Trend.

### Varianten
- Grid: `.kpi-grid`
- Default: `.kpi-widget`
- Clickable: `.kpi-widget--clickable`
- Compact: `.kpi-widget--compact`
- Icon variants: `kpi-widget__icon--primary|success|warning|error|teal`

### States
- Hover: nur Shadow‑Anhebung (keine lauten Farben)

### Typografie
- Title: `--caption-size`, uppercase, `--font-weight-medium`
- Value: `--heading-2-size`, `--font-weight-bold`

### Spacing
- Padding: `--spacing-4` (16px)
- Grid gap: `--spacing-4`

### Farben (Tokens)
- Surface: `--color-surface`
- Border: `--color-border`
- Icon background: `--color-primary-light` / `--color-success-background` / ...

### Beispiel‑HTML
```html
<section class="kpi-grid" aria-label="KPIs">
  <article class="kpi-widget kpi-widget--clickable">
    <header class="kpi-widget__header">
      <h3 class="kpi-widget__title">Termine heute</h3>
      <div class="kpi-widget__icon kpi-widget__icon--primary" aria-hidden="true">📅</div>
    </header>
    <p class="kpi-widget__value">42</p>
    <div class="kpi-widget__footer">+3 vs. gestern</div>
  </article>
</section>
```

---

## 7) Modale

### Zweck
Fokussierte Tasks (Bestätigung, Bearbeitung) ohne Kontextverlust.

### Varianten
- Default: `.modal`
- Größen: `.modal--sm|--lg|--xl`
- Fullscreen: `.modal--fullscreen`
- Confirm: `.modal--confirm`

### States
- Backdrop visible: `.modal-backdrop--visible`
- Close hover: neutral‑20
- Focus: `:focus-visible` auf Close/Button

### Typografie
- Title: `--heading-3-size`
- Body: `--body-size`

### Spacing
- Backdrop padding: `--spacing-4`
- Header/Footer padding: `--spacing-4` / `--spacing-6`
- Body padding: `--spacing-6`

### Farben (Tokens)
- Modal surface: `--color-surface`
- Backdrop: `rgba(0,0,0,0.4)`
- Divider: `--color-divider`
- Shadow: `--shadow-modal`

### Beispiel‑HTML
```html
<div class="modal-backdrop modal-backdrop--visible" role="presentation">
  <div class="modal" role="dialog" aria-modal="true" aria-labelledby="m-title">
    <header class="modal__header">
      <h2 id="m-title" class="modal__title">Termin bearbeiten</h2>
      <button class="modal__close" type="button" aria-label="Schließen">✕</button>
    </header>

    <div class="modal__body">
      <!-- Formular / Inhalt -->
    </div>

    <footer class="modal__footer">
      <button class="btn btn--secondary">Abbrechen</button>
      <button class="btn btn--primary">Speichern</button>
    </footer>
  </div>
</div>
```

---

## Kurze Designregeln (medizinischer Kontext)

- **Reduktion**: Pro Screen genau *eine* Primary Action.
- **Kontrast & Lesbarkeit**: Tabellen/Forms bleiben ruhig; Statusfarben nur als Akzent.
- **Fehlerzustände**: niemals nur Farbe – immer Text/Helper (z. B. `.form-helper--error`).
- **Focus**: sichtbar und konsistent (`:focus-visible`).
- **Weißraum**: lieber mehr Spacing als mehr Linien.
