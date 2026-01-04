# PraxiApp Layout‑Patterns (Fluent‑UI Stil)

Diese Blueprints beschreiben wiederverwendbare Seiten‑Layouts für die wichtigsten PraxiApp‑Seitentypen.

**Basis (Shell + Komponenten):**
- Shell: `.app-header`, `.sidebar`, `.main-content` aus `praxi_backend/static/css/components.css`
- Komponenten: Buttons, Cards/Panels, Tables, Forms, KPI‑Widgets, Modals, Breadcrumbs (ebenfalls `components.css`)
- Tokens: `praxi_backend/static/css/design-tokens.css`

> Hinweis: Es existiert zusätzlich ein älteres Dashboard‑System mit `.prx-*` Klassen (`base_dashboard.css`). Die folgenden Patterns sind für das **Fluent‑UI Token/Component‑System** gedacht und können schrittweise migriert werden.

---

## Globale Regeln (Raster, Abstände, Panels)

### Standard‑Spacing (Faustregeln)
- **App Shell**
  - Header: `48px` Höhe (bestehend)
  - Sidebar: `240px` Breite (bestehend) / collapsed `56px`
  - Page Padding: `var(--spacing-6)` (24px) in `.main-content`

- **Inhalte**
  - Vertikaler Abstand zwischen großen Blöcken: `var(--spacing-6)` (24px)
  - Zwischen UI‑Controls (Filterzeile): `var(--spacing-2)`–`var(--spacing-3)`
  - In Cards/Panels: `var(--spacing-4)` (16px) bis `var(--spacing-6)` (24px)

### Standard‑Raster
- KPI‑Bereich: `.kpi-grid` (auto‑fit, min 200px)
- 2‑Spalten Content + Aside: `minmax(0, 1fr) 320px` (Filterpanel rechts)
- Tabellen: immer in `.table-container` (horizontal scroll + Border)

### Panel‑Regeln
- Filter/Right‑Rail: `.panel.panel--bordered.panel--shadowed`
- „Karten“ für wichtige Blöcke: `.card` (Header/Body/Footer)

### Responsive Grundregeln
- **≤ 1024px**: Right‑Rail (Filterpanel) unter den Content stacken
- **≤ 768px**:
  - Filterzeilen umbrechen (Controls auf 2–3 Zeilen)
  - Tabellen mit `.table--responsive` (Head ausblenden, `data-label` anzeigen)
  - Sidebar: in der Regel „drawer“/collapsed (Pattern: `.sidebar--collapsed` oder eigenes Off‑Canvas)

---

## 0) App‑Shell (für alle Seiten)

### Layout‑Struktur
- Header oben
- Sidebar links
- Content rechts

### HTML‑Skeleton
```html
<header class="app-header">
  <div class="app-header__brand">
    <img class="app-header__logo" src="/static/img/logo.svg" alt="PraxiApp" />
    <h1 class="app-header__title">PraxiApp</h1>
  </div>

  <div class="app-header__nav">
    <!-- optional: globale Links/Actions -->
  </div>

  <button class="app-header__user" type="button" aria-label="Benutzermenü">
    <div class="app-header__avatar" aria-hidden="true">DR</div>
    <div class="app-header__user-info">
      <div class="app-header__user-name">Dr. Beispiel</div>
      <div class="app-header__user-role">doctor</div>
    </div>
  </button>
</header>

<aside class="sidebar" aria-label="Hauptnavigation">
  <section class="sidebar__section">
    <h2 class="sidebar__section-title">Dashboards</h2>
    <ul class="sidebar__nav">
      <li><a class="sidebar__link sidebar__link--active" href="/dashboard/">Übersicht</a></li>
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
      <li><a class="sidebar__link" href="/core/users/">User</a></li>
    </ul>
  </section>

  <section class="sidebar__section">
    <h2 class="sidebar__section-title">Medical</h2>
    <ul class="sidebar__nav">
      <li><a class="sidebar__link" href="/medical/patients/">Patienten</a></li>
    </ul>
  </section>
</aside>

<main class="main-content">
  <!-- page content -->
</main>
```

---

## 1) Haupt‑Dashboard (Praxis‑Übersicht)

### Layout‑Struktur
- Shell: Header + Sidebar
- Content:
  1) Page Header (Titel + Aktionen)
  2) KPI‑Grid oben
  3) Middle Area: Tabellen/Charts links (Main)
  4) Optional: Filter rechts (Aside)

### Komponenten‑Einsatz
- `.page-header` + `.page-header__actions` (Actions rechts)
- KPI: `.kpi-grid` + `.kpi-widget`
- Main: `.card` für Charts/Tabellenblöcke
- Filter: `.panel.panel--bordered.panel--shadowed` (Right‑Rail)

### Abstände
- Zwischen KPI‑Grid und Middle Area: `var(--spacing-6)`
- In Cards/Panels: 16–24px (`--spacing-4` / `--spacing-6`)

### Responsive Verhalten
- ≤ 1024px: Right‑Rail unter Main
- ≤ 768px: KPI‑Grid wird 1‑Spaltig, Tabellen `.table--responsive`

### HTML‑Skeleton
```html
<div class="page-header">
  <h2 class="page-header__title">Praxis‑Übersicht</h2>
  <p class="page-header__subtitle">Heute: 29.12.2025</p>
  <div class="page-header__actions">
    <button class="btn btn--primary">Neuer Termin</button>
    <button class="btn btn--secondary">Export</button>
  </div>
</div>

<section class="kpi-grid" aria-label="KPIs">
  <article class="kpi-widget">
    <header class="kpi-widget__header">
      <h3 class="kpi-widget__title">Termine heute</h3>
      <div class="kpi-widget__icon kpi-widget__icon--primary" aria-hidden="true">📅</div>
    </header>
    <p class="kpi-widget__value">42</p>
    <div class="kpi-widget__footer">+3 vs. gestern</div>
  </article>
  <!-- weitere KPIs -->
</section>

<div class="content-grid content-grid--with-aside">
  <section class="content-grid__main">
    <article class="card">
      <header class="card__header">
        <h3 class="card__title">Termine</h3>
        <div class="card__actions">
          <button class="btn btn--ghost btn--sm">Mehr</button>
        </div>
      </header>
      <div class="card__body">
        <div class="table-container">
          <table class="table table--responsive">
            <!-- ... -->
          </table>
        </div>
      </div>
    </article>

    <article class="card" style="margin-top: var(--spacing-6);">
      <header class="card__header">
        <h3 class="card__title">Auslastung (Chart)</h3>
      </header>
      <div class="card__body">
        <!-- Chart Canvas/SVG -->
      </div>
    </article>
  </section>

  <aside class="content-grid__aside">
    <div class="panel panel--bordered panel--shadowed">
      <h3 class="panel__title">Filter</h3>
      <form class="form form--inline">
        <div class="form-group">
          <label class="form-label" for="f1">Arzt</label>
          <select class="input select" id="f1"><option>Alle</option></select>
        </div>
        <div class="form-group">
          <label class="form-label" for="f2">Status</label>
          <select class="input select" id="f2"><option>Alle</option></select>
        </div>
        <div class="form-actions form-actions--left">
          <button class="btn btn--secondary" type="button">Reset</button>
          <button class="btn btn--primary" type="submit">Anwenden</button>
        </div>
      </form>
    </div>
  </aside>
</div>
```

---

## 2) Scheduling‑Dashboard

### Layout‑Struktur
- Shell: Header + Sidebar
- Content:
  1) Filterzeile oben (inline form)
  2) Timeline/Übersicht (groß, mittig)
  3) Tabellen: unten oder rechts (je nach Screen)

### Komponenten‑Einsatz
- Filterzeile: `.form.form--inline` + `.input`/`.select` + Buttons
- Timeline Container: `.card.card--flat` oder `.panel.panel--bordered`
- Tabellen: `.table-container` + `.table` (optional `.table--compact`)

### Abstände
- Filterzeile → Timeline: `var(--spacing-4)`–`var(--spacing-6)`

### Responsive Verhalten
- ≤ 768px: Filterzeile wraps; Timeline scrollt horizontal (`overflow-x: auto`); Tabelle `.table--responsive`

### HTML‑Skeleton
```html
<div class="page-header">
  <h2 class="page-header__title">Terminplanung</h2>
  <p class="page-header__subtitle">Slots, Auslastung, Konflikte</p>
</div>

<form class="form form--inline" aria-label="Scheduling Filter">
  <div class="form-group">
    <label class="form-label" for="d">Datum</label>
    <input class="input" id="d" type="date" />
  </div>
  <div class="form-group">
    <label class="form-label" for="doc">Arzt</label>
    <select class="input select" id="doc"><option>Alle</option></select>
  </div>
  <div class="form-group">
    <label class="form-label" for="dur">Dauer</label>
    <select class="input select" id="dur"><option>30 min</option></select>
  </div>
  <div class="form-actions form-actions--left">
    <button class="btn btn--secondary" type="button">Zurücksetzen</button>
    <button class="btn btn--primary" type="submit">Aktualisieren</button>
  </div>
</form>

<article class="card" style="margin-top: var(--spacing-6);">
  <header class="card__header">
    <h3 class="card__title">Timeline</h3>
  </header>
  <div class="card__body" style="overflow-x: auto;">
    <!-- Timeline (SVG/Canvas/Div‑Grid) -->
  </div>
</article>

<article class="card" style="margin-top: var(--spacing-6);">
  <header class="card__header">
    <h3 class="card__title">Konflikte / Vorschläge</h3>
  </header>
  <div class="card__body">
    <div class="table-container">
      <table class="table table--responsive table--compact">
        <!-- ... -->
      </table>
    </div>
  </div>
</article>
```

---

## 3) User‑Management

### Layout‑Struktur
- Shell
- Top: Breadcrumb + Titel
- Middle: Tabelle
- Right‑Rail: Filter‑Panel

### Komponenten‑Einsatz
- Breadcrumb: `.breadcrumb` (+ `breadcrumb__item`, `breadcrumb__separator`)
- Header: `.page-header`
- Tabelle: `.table-container` + `.table`
- Filter: `.panel.panel--bordered.panel--shadowed`

### Abstände
- Breadcrumb → Titel: `var(--spacing-2)`–`var(--spacing-3)`
- Tabelle/Filter Rail Gap: `var(--spacing-6)`

### Responsive Verhalten
- ≤ 1024px: Filter Rail unter Tabelle
- ≤ 768px: Tabelle `.table--responsive`

### HTML‑Skeleton
```html
<nav class="breadcrumb" aria-label="Breadcrumb">
  <a class="breadcrumb__item" href="/">Home</a>
  <span class="breadcrumb__separator">/</span>
  <span class="breadcrumb__item breadcrumb__item--current">User</span>
</nav>

<div class="page-header">
  <h2 class="page-header__title">User‑Management</h2>
  <p class="page-header__subtitle">Rollen, Aktivität, Zugriff</p>
  <div class="page-header__actions">
    <button class="btn btn--primary">User anlegen</button>
  </div>
</div>

<div class="content-grid content-grid--with-aside">
  <section class="content-grid__main">
    <div class="table-container">
      <table class="table table--responsive">
        <!-- columns: Username, Role, Active, Last login, Actions -->
      </table>
    </div>
  </section>

  <aside class="content-grid__aside">
    <div class="panel panel--bordered panel--shadowed">
      <h3 class="panel__title">Filter</h3>
      <form class="form">
        <div class="form-group">
          <label class="form-label" for="q">Suche</label>
          <input class="input" id="q" placeholder="Name, Mail…" />
        </div>
        <div class="form-group">
          <label class="form-label" for="role">Rolle</label>
          <select class="input select" id="role"><option>Alle</option></select>
        </div>
        <div class="form-actions form-actions--space-between">
          <button class="btn btn--secondary" type="button">Reset</button>
          <button class="btn btn--primary" type="submit">Anwenden</button>
        </div>
      </form>
    </div>
  </aside>
</div>
```

---

## 4) Patienten‑/Ärzte‑Listen

### Layout‑Struktur
- Shell
- Page Header (Titel + ggf. Quick Actions)
- Filter (oben oder rechts)
- Tabelle als Hauptinhalt

### Komponenten‑Einsatz
- Filter oben: `.form--inline` (Fluent‑typisch „command bar“‑ähnlich, aber ruhig)
- Tabelle: `.table` + `.table__cell--truncate`, `.table__cell--nowrap`
- Hover: ist bereits ruhig (`--color-neutral-20`)

### Abstände
- Filter → Tabelle: `var(--spacing-4)`

### Responsive Verhalten
- ≤ 768px: Filter umbrechen, Tabelle `.table--responsive`

### HTML‑Skeleton
```html
<div class="page-header">
  <h2 class="page-header__title">Patienten</h2>
  <p class="page-header__subtitle">Suche, Filter, aktuelle Fälle</p>
  <div class="page-header__actions">
    <button class="btn btn--primary">Neuer Patient</button>
  </div>
</div>

<form class="form form--inline" aria-label="Listen Filter">
  <div class="form-group">
    <label class="form-label" for="search">Suche</label>
    <input class="input" id="search" placeholder="Name / ID" />
  </div>
  <div class="form-group">
    <label class="form-label" for="status">Status</label>
    <select class="input select" id="status"><option>Alle</option></select>
  </div>
  <div class="form-actions form-actions--left">
    <button class="btn btn--secondary" type="button">Reset</button>
    <button class="btn btn--primary" type="submit">Filtern</button>
  </div>
</form>

<div class="table-container" style="margin-top: var(--spacing-4);">
  <table class="table table--responsive">
    <!-- klare Spalten: Name, Geburtsdatum, Arzt, Letzter Besuch, Status -->
  </table>
</div>
```

---

## 5) OP‑Dashboard

### Layout‑Struktur
- Shell
- Top: KPI‑Cards (Auslastung, Durchlaufzeit, Wartend, etc.)
- Middle: OP‑Liste (Tabelle)
- Optional: Chart (rechts oder unterhalb)

### Komponenten‑Einsatz
- KPI: `.kpi-grid` + `.kpi-widget`
- OP‑Liste: `.card` + `.table`
- Optional Chart: `.card` (eigenständiger Block)

### Abstände
- KPI → Liste: `var(--spacing-6)`

### Responsive Verhalten
- ≤ 1024px: Chart unter Liste
- ≤ 768px: Tabelle `.table--responsive`

### HTML‑Skeleton
```html
<div class="page-header">
  <h2 class="page-header__title">OP‑Dashboard</h2>
  <p class="page-header__subtitle">Status, Durchlaufzeiten, Engpässe</p>
</div>

<section class="kpi-grid" aria-label="OP KPIs">
  <article class="kpi-widget">
    <header class="kpi-widget__header">
      <h3 class="kpi-widget__title">Wartend</h3>
      <div class="kpi-widget__icon kpi-widget__icon--warning" aria-hidden="true">⏳</div>
    </header>
    <p class="kpi-widget__value">6</p>
  </article>
  <!-- weitere KPIs -->
</section>

<div class="content-grid content-grid--with-aside" style="margin-top: var(--spacing-6);">
  <section class="content-grid__main">
    <article class="card">
      <header class="card__header">
        <h3 class="card__title">Heutige OPs</h3>
      </header>
      <div class="card__body">
        <div class="table-container">
          <table class="table table--responsive">
            <!-- patient_id, start_time, room, surgeon, status -->
          </table>
        </div>
      </div>
    </article>
  </section>

  <aside class="content-grid__aside">
    <article class="card">
      <header class="card__header"><h3 class="card__title">Trend</h3></header>
      <div class="card__body">
        <!-- Chart -->
      </div>
    </article>
  </aside>
</div>
```
