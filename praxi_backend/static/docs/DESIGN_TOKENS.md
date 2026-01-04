# PraxiApp Design Tokens
## Microsoft Fluent UI Style – Medical Web Product

Ein professionelles, vertrauenswürdiges und modernes Design-System für medizinische Anwendungen.

---

## 📋 Token-Übersicht

### 1. Farbpalette

#### Primary Colors
| Token | Wert | Verwendung |
|-------|------|------------|
| `--color-primary` | `#0F6CBD` | Hauptaktionsfarbe, Links, Buttons |
| `--color-primary-hover` | `#115EA3` | Hover-Zustand |
| `--color-primary-pressed` | `#0E4A80` | Aktiv/Pressed-Zustand |
| `--color-primary-light` | `#E8F3FC` | Hintergründe, Badges |
| `--color-primary-light-hover` | `#D4E9F8` | Hover auf hellem Primary |

#### Neutral Palette
| Token | Wert | Verwendung |
|-------|------|------------|
| `--color-neutral-0` | `#FFFFFF` | Reinweiß |
| `--color-neutral-10` | `#F8F8F8` | Hover-Hintergrund |
| `--color-neutral-20` | `#F3F2F1` | Alternativer Hintergrund |
| `--color-neutral-30` | `#EDEBE9` | Subtile Borders |
| `--color-neutral-40` | `#E1DFDD` | Standard-Borders |
| `--color-neutral-50` | `#C8C6C4` | Disabled Text, starke Borders |
| `--color-neutral-60` | `#A19F9D` | Sekundärer Text |
| `--color-neutral-70` | `#605E5C` | Icons, Labels |
| `--color-neutral-80` | `#3B3A39` | Dunkler Text |
| `--color-neutral-90` | `#323130` | Primärer Text |
| `--color-neutral-100` | `#201F1E` | Dunkelster Text |

#### Accent Colors
| Token | Wert | Verwendung |
|-------|------|------------|
| `--color-accent-teal` | `#00B7C3` | Abgeschlossen, Info-Akzent |
| `--color-accent-teal-light` | `#E0F7F9` | Teal-Hintergrund |
| `--color-accent-green` | `#107C10` | Erfolg, Bestätigung |
| `--color-accent-green-light` | `#DFF6DD` | Erfolg-Hintergrund |
| `--color-accent-red` | `#D13438` | Fehler, Dringend |
| `--color-accent-red-light` | `#FDE7E9` | Fehler-Hintergrund |
| `--color-accent-yellow` | `#FCE100` | Warnung |
| `--color-accent-yellow-light` | `#FFF9CC` | Warnung-Hintergrund |
| `--color-accent-orange` | `#FF8C00` | Aufmerksamkeit |
| `--color-accent-orange-light` | `#FFF4E5` | Orange-Hintergrund |

#### Semantic Colors
| Token | Wert | Verwendung |
|-------|------|------------|
| `--color-success` | `#107C10` | Erfolgsmeldungen |
| `--color-success-background` | `#DFF6DD` | Erfolg-Banner |
| `--color-warning` | `#FCE100` | Warnungen |
| `--color-warning-background` | `#FFF9CC` | Warnung-Banner |
| `--color-error` | `#D13438` | Fehlermeldungen |
| `--color-error-background` | `#FDE7E9` | Fehler-Banner |
| `--color-info` | `#0F6CBD` | Informationen |
| `--color-info-background` | `#E8F3FC` | Info-Banner |

#### Surface & Background
| Token | Wert | Verwendung |
|-------|------|------------|
| `--color-surface` | `#FFFFFF` | Karten, Panels |
| `--color-surface-alt` | `#F3F2F1` | Alternative Flächen |
| `--color-surface-hover` | `#F8F8F8` | Hover-Zustand |
| `--color-background` | `#FFFFFF` | Seitenhintergrund |
| `--color-background-canvas` | `#F3F2F1` | Canvas-Hintergrund |

#### Border & Divider
| Token | Wert | Verwendung |
|-------|------|------------|
| `--color-border` | `#E1DFDD` | Standard-Border |
| `--color-border-strong` | `#C8C6C4` | Betonte Borders |
| `--color-border-subtle` | `#EDEBE9` | Subtile Borders |
| `--color-divider` | `#E1DFDD` | Trennlinien |

#### Text Colors
| Token | Wert | Verwendung |
|-------|------|------------|
| `--color-text-primary` | `#323130` | Haupttext |
| `--color-text-secondary` | `#605E5C` | Sekundärer Text |
| `--color-text-tertiary` | `#A19F9D` | Tertiärer Text |
| `--color-text-disabled` | `#C8C6C4` | Deaktivierter Text |
| `--color-text-inverse` | `#FFFFFF` | Text auf dunklem Hintergrund |
| `--color-text-link` | `#0F6CBD` | Links |
| `--color-text-link-hover` | `#115EA3` | Link-Hover |

#### Medical-Specific Colors
| Token | Wert | Verwendung |
|-------|------|------------|
| `--color-medical-urgent` | `#D13438` | Notfall, Dringend |
| `--color-medical-attention` | `#FF8C00` | Aufmerksamkeit erforderlich |
| `--color-medical-normal` | `#107C10` | Normal, OK |
| `--color-medical-scheduled` | `#0F6CBD` | Geplant |
| `--color-medical-completed` | `#00B7C3` | Abgeschlossen |

---

### 2. Typografie

#### Font Families
| Token | Wert |
|-------|------|
| `--font-family-primary` | `"Segoe UI", "Inter", "Roboto", -apple-system, BlinkMacSystemFont, sans-serif` |
| `--font-family-mono` | `"Cascadia Code", "Fira Code", "Consolas", monospace` |

#### Font Weights
| Token | Wert |
|-------|------|
| `--font-weight-regular` | `400` |
| `--font-weight-medium` | `500` |
| `--font-weight-semibold` | `600` |
| `--font-weight-bold` | `700` |

#### Typography Scale
| Stil | Size | Weight | Line-Height | Letter-Spacing |
|------|------|--------|-------------|----------------|
| **Heading 1** | 28px | 600 | 1.2 | -0.02em |
| **Heading 2** | 24px | 600 | 1.25 | -0.01em |
| **Heading 3** | 20px | 600 | 1.3 | 0 |
| **Heading 4** | 16px | 600 | 1.35 | 0 |
| **Subtitle** | 16px | 500 | 1.4 | 0 |
| **Body** | 14px | 400 | 1.5 | 0 |
| **Body Secondary** | 14px | 400 | 1.5 | 0 |
| **Body Strong** | 14px | 600 | 1.5 | 0 |
| **Caption** | 12px | 400 | 1.4 | 0 |
| **Caption Strong** | 12px | 600 | 1.4 | 0 |
| **Overline** | 10px | 600 | 1.3 | 0.08em |

---

### 3. Spacing

#### Base Scale
| Token | Wert | Verwendung |
|-------|------|------------|
| `--spacing-0` | 0px | Kein Abstand |
| `--spacing-1` | 4px | Minimaler Abstand |
| `--spacing-2` | 8px | Kleiner Abstand |
| `--spacing-3` | 12px | Zwischen-Abstand |
| `--spacing-4` | 16px | Standard-Abstand |
| `--spacing-5` | 20px | Mittlerer Abstand |
| `--spacing-6` | 24px | Größerer Abstand |
| `--spacing-8` | 32px | Großer Abstand |
| `--spacing-10` | 40px | Sehr groß |
| `--spacing-12` | 48px | Section-Abstand |
| `--spacing-16` | 64px | Page-Abstand |

#### Semantic Scale
| Token | Wert |
|-------|------|
| `--spacing-xs` | 4px |
| `--spacing-sm` | 8px |
| `--spacing-md` | 16px |
| `--spacing-lg` | 24px |
| `--spacing-xl` | 32px |
| `--spacing-2xl` | 48px |
| `--spacing-3xl` | 64px |

---

### 4. Border Radius

| Token | Wert | Verwendung |
|-------|------|------------|
| `--radius-none` | 0 | Keine Rundung |
| `--radius-xs` | 2px | Minimal |
| `--radius-sm` | 4px | Buttons, Inputs |
| `--radius-md` | 6px | Dropdowns, Tooltips |
| `--radius-lg` | 8px | Cards, Modals |
| `--radius-xl` | 12px | Große Container |
| `--radius-2xl` | 16px | Hero-Elemente |
| `--radius-full` | 9999px | Kreise, Pills |

#### Component-Specific
| Token | Wert |
|-------|------|
| `--radius-button` | 4px |
| `--radius-input` | 4px |
| `--radius-card` | 8px |
| `--radius-modal` | 8px |
| `--radius-tooltip` | 4px |
| `--radius-badge` | 4px |
| `--radius-avatar` | 9999px |
| `--radius-chip` | 9999px |

---

### 5. Shadows

#### Basic Shadows
| Token | Wert | Verwendung |
|-------|------|------------|
| `--shadow-none` | none | Kein Schatten |
| `--shadow-xs` | `0 1px 2px rgba(0,0,0,0.04)` | Subtil |
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.06)` | Leicht |
| `--shadow-md` | `0 2px 4px rgba(0,0,0,0.08)` | Medium |
| `--shadow-lg` | `0 4px 8px rgba(0,0,0,0.10)` | Groß |
| `--shadow-xl` | `0 8px 16px rgba(0,0,0,0.12)` | Sehr groß |
| `--shadow-2xl` | `0 16px 32px rgba(0,0,0,0.14)` | Maximal |

#### Fluent UI Elevation
| Token | Verwendung |
|-------|------------|
| `--shadow-elevation-2` | Subtile Erhöhung (Cards) |
| `--shadow-elevation-4` | Hover-Zustand |
| `--shadow-elevation-8` | Dropdowns, Popovers |
| `--shadow-elevation-16` | Dialoge |
| `--shadow-elevation-64` | Modals |

---

### 6. Transitions

#### Duration
| Token | Wert |
|-------|------|
| `--duration-instant` | 0ms |
| `--duration-fast` | 100ms |
| `--duration-normal` | 200ms |
| `--duration-slow` | 300ms |
| `--duration-slower` | 400ms |

#### Easing
| Token | Wert |
|-------|------|
| `--easing-standard` | `cubic-bezier(0.4, 0, 0.2, 1)` |
| `--easing-decelerate` | `cubic-bezier(0, 0, 0.2, 1)` |
| `--easing-accelerate` | `cubic-bezier(0.4, 0, 1, 1)` |
| `--easing-bounce` | `cubic-bezier(0.68, -0.55, 0.265, 1.55)` |

---

### 7. Z-Index

| Token | Wert | Verwendung |
|-------|------|------------|
| `--z-index-base` | 0 | Basis |
| `--z-index-dropdown` | 1000 | Dropdowns |
| `--z-index-sticky` | 1100 | Sticky Header |
| `--z-index-fixed` | 1200 | Fixed Elements |
| `--z-index-modal-backdrop` | 1300 | Modal Backdrop |
| `--z-index-modal` | 1400 | Modals |
| `--z-index-popover` | 1500 | Popovers |
| `--z-index-tooltip` | 1600 | Tooltips |
| `--z-index-toast` | 1700 | Toast Notifications |

---

### 8. Sizing

#### Icon Sizes
| Token | Wert |
|-------|------|
| `--icon-size-xs` | 12px |
| `--icon-size-sm` | 16px |
| `--icon-size-md` | 20px |
| `--icon-size-lg` | 24px |
| `--icon-size-xl` | 32px |

#### Button Heights
| Token | Wert |
|-------|------|
| `--button-height-sm` | 28px |
| `--button-height-md` | 36px |
| `--button-height-lg` | 44px |

#### Input Heights
| Token | Wert |
|-------|------|
| `--input-height-sm` | 28px |
| `--input-height-md` | 36px |
| `--input-height-lg` | 44px |

---

## 🎨 Verwendung

```css
/* Import */
@import url('design-tokens.css');

/* Beispiel: Button */
.button-primary {
  background-color: var(--color-primary);
  color: var(--color-text-inverse);
  border-radius: var(--radius-button);
  padding: var(--spacing-button-padding-y) var(--spacing-button-padding-x);
  font-weight: var(--font-weight-semibold);
  transition: var(--transition-colors);
  box-shadow: var(--shadow-sm);
}

.button-primary:hover {
  background-color: var(--color-primary-hover);
  box-shadow: var(--shadow-md);
}

/* Beispiel: Card */
.card {
  background-color: var(--color-surface);
  border: var(--border-default);
  border-radius: var(--radius-card);
  padding: var(--spacing-card-padding);
  box-shadow: var(--shadow-card);
}

.card:hover {
  box-shadow: var(--shadow-card-hover);
}
```

---

## 📁 Dateien

- **CSS Tokens**: `praxi_backend/static/css/design-tokens.css`
- **Dokumentation**: `praxi_backend/static/docs/DESIGN_TOKENS.md`

---

*Erstellt für PraxiApp – Microsoft Fluent UI Design System für medizinische Anwendungen*
