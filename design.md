---
name: Servidor
colors:
  # ── Surface / Background Hierarchy ──
  surface: '#0f1419'
  surface-dim: '#0f1419'
  surface-bright: '#353940'
  surface-container-lowest: '#0a0e14'
  surface-container-low: '#181c22'
  surface-container: '#1c2026'
  surface-container-high: '#262a30'
  surface-container-highest: '#31353b'

  # ── Text / On-Surface ──
  on-surface: '#dfe2ea'
  on-surface-variant: '#bfc7d4'
  inverse-surface: '#dfe2ea'
  inverse-on-surface: '#2d3137'

  # ── Borders / Outlines ──
  outline: '#89919d'
  outline-variant: '#404752'
  surface-tint: '#9ecaff'
  surface-variant: '#31353b'

  # ── Primary (Cyan-Blue) ──
  primary: '#9ecaff'
  on-primary: '#003258'
  primary-container: '#2096f3'
  on-primary-container: '#002c4f'
  inverse-primary: '#0061a3'
  primary-fixed: '#d1e4ff'
  primary-fixed-dim: '#9ecaff'
  on-primary-fixed: '#001d36'
  on-primary-fixed-variant: '#00497d'

  # ── Secondary (Violet) ──
  secondary: '#cbbeff'
  on-secondary: '#330098'
  secondary-container: '#4b26b7'
  on-secondary-container: '#baa9ff'
  secondary-fixed: '#e7deff'
  secondary-fixed-dim: '#cbbeff'
  on-secondary-fixed: '#1d0061'
  on-secondary-fixed-variant: '#4b26b7'

  # ── Tertiary (Amber/Warning) ──
  tertiary: '#ffb77b'
  on-tertiary: '#4d2700'
  tertiary-container: '#db7900'
  on-tertiary-container: '#452200'
  tertiary-fixed: '#ffdcc2'
  tertiary-fixed-dim: '#ffb77b'
  on-tertiary-fixed: '#2e1500'
  on-tertiary-fixed-variant: '#6d3900'

  # ── Error (Coral-Red for Critical/Danger) ──
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'

  # ── Background ──
  background: '#0f1419'
  on-background: '#dfe2ea'

typography:
  hero-metric:
    fontFamily: jetbrainsMono
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  page-title:
    fontFamily: inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  section-header:
    fontFamily: inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: 0.05em
  body-base:
    fontFamily: inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  data-mono:
    fontFamily: jetbrainsMono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
  label-caps:
    fontFamily: inter
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.08em

rounded:
  sm: 0.125rem    # 2px
  DEFAULT: 0.25rem # 4px
  md: 0.375rem    # 6px
  lg: 0.5rem      # 8px
  xl: 0.75rem     # 12px
  full: 9999px

spacing:
  base_unit: 4px
  container-padding: 24px
  gutter: 16px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 32px
---

# Servidor Design System

> Extracted from Stitch project `5247979867984193199` — "Servidor Patient Safety Dashboard"
> Design system asset: `assets/06c51be98be2460b976e9f9c9f1117b1`

## Brand & Style

The design system is engineered for "Calm Authority" — a mission-control aesthetic tailored for high-stakes healthcare environments. It prioritizes information density without cognitive fatigue, utilizing a dark-mode-first approach to reduce eye strain during long shifts.

The visual style is a hybrid of **Corporate/Modern** and **Minimalism**, stripping away decorative elements to focus on data integrity and situational awareness. It employs progressive disclosure to hide secondary details until necessary, ensuring the most critical patient safety metrics remain the focal point. The interface should feel like a precision instrument: reliable, quiet, and responsive.

## Colors

This design system uses a specialized dark palette to maintain high legibility and hierarchical depth.

- **Background Strategy:** A tiered system of cool grays. The `base` is used for the overall application canvas, while `surface` and `elevated` define nested content areas and modals.
- **Data Signaling:** Color is used exclusively for functional signaling. `Safe` (emerald), `Warning` (amber), and `Critical` (coral) follow standard medical conventions. `Active` and `Primary` accents use a professional cyan to denote selection and focus without causing visual alarm.
- **Contrast:** High contrast is maintained for primary text, while `muted` text is reserved for labels and timestamps to prevent visual clutter in data-heavy views.

### Semantic Status Colors (for CSS implementation)

These are NOT in the Stitch material tokens but must be defined as custom properties:

```css
/* Safe / Healthy / Resolved */
--status-safe: #27ae7a;
--status-safe-bg: rgba(39, 174, 122, 0.12);

/* Warning / Degraded (maps to tertiary) */
--status-warning: #ffb77b;
--status-warning-bg: rgba(255, 183, 123, 0.12);

/* Critical / Danger (maps to error) */
--status-critical: #d64545;
--status-critical-bg: rgba(214, 69, 69, 0.12);

/* Active / Processing (maps to primary-container) */
--status-active: #2096f3;
--status-active-bg: rgba(32, 150, 243, 0.12);
```

## Typography

Typography is used to differentiate between narrative content and technical data.

- **Interface Text:** All standard UI elements (navigation, labels, body text) use **Inter**. Its neutral character ensures it stays out of the way of the data.
- **Metrics & Logs:** All numerical values, timestamps, and log entries use **JetBrains Mono**. The monospaced nature allows for vertical alignment of digits in tables and dashboards, making it easier to scan for changes in magnitude.
- **Hierarchy:** Use the `hero-metric` for critical status numbers (e.g., active alerts). `Section-header` and `label-caps` provide clear structural anchors for complex forms and dashboards.

## Layout & Spacing

The layout utilizes a **Fixed Grid** philosophy for desktop dashboards to ensure that critical widgets remain in predictable locations.

- **Grid:** A 12-column grid system with 16px gutters. Dashboard widgets should span multiples of 3 or 4 columns.
- **Rhythm:** A 4px baseline grid governs all spacing. Vertical stacks use 8px or 16px increments to maintain a compact, "information-dense" feel.
- **Responsiveness:** On mobile, the 12-column grid collapses into a single-column vertical stack. On tablet, the sidebar transitions to a collapsed icon-only state to maximize the data display area.
- **Margins:** Outer page margins are locked at 24px to provide "breathing room" against the screen edge.

### Sidebar

- Width: `240px` (expanded), `64px` (collapsed/icon-only)
- Background: `surface-container-lowest` (#0a0e14)
- Right border: 1px solid `outline-variant` (#404752)
- Nav item height: 40px
- Active item: `primary-container` (#2096f3) as left border (3px), `surface-container` background
- Hover: `surface-container-high` background

## Elevation & Depth

Depth is communicated through **Tonal Layering** and **Low-Contrast Outlines** rather than traditional shadows.

- **Stacking Logic:** Higher elevation is represented by lighter surface colors. The `base` background is the lowest level. `Surface` is for cards/widgets, and `Elevated` is for popovers or active selection states.
- **Borders:** Every container must have a 1px border. Use `outline-variant` (#404752) borders for passive containers and `outline` (#89919d) borders for interactive elements like inputs and buttons.
- **Shadows:** Avoid shadows for layout elements. Only use a minimal, neutral 10% black shadow with a 4px blur for floating modals to separate them from the interface content.

## Shapes

To maintain the "Mission Control" and "Technical" aesthetic, the design system uses **Soft** geometry.

- **Radius:** Standard components (buttons, inputs, cards) use a 0.25rem (4px) radius. This provides just enough softness to feel modern while maintaining the rigid, structural feel of a dashboard.
- **Exceptions:** Status badges and tags may use a pill shape (fully rounded) to distinguish them from interactive buttons. High-level dashboard containers should remain at 4px to align with the grid system.

## Components

- **Buttons:** Use a flat aesthetic with 1px borders. Primary buttons use the `primary-container` (#2096f3) with white text. Secondary/outline buttons use `surface-container` background and `outline-variant` border.
- **Status Chips:** Small, condensed labels using `label-caps`. The background should be a 15% opacity version of the status color (Safe/Warning/Critical) with a solid color text and border.
- **Input Fields:** Dark backgrounds (`surface-container-lowest`) with `outline-variant` borders. On focus, the border transitions to `primary-container` (#2096f3) with a 1px outer glow.
- **Cards/Widgets:** Use the `surface-container` (#1c2026) background. Headers should be separated by a 1px `outline-variant` border. Use 16px for internal padding.
- **Data Tables:** Row-based layout with no vertical borders. Use `outline-variant` horizontal dividers. Use a subtle `surface-container-high` background on hover.
- **Logs:** Monospaced text in `data-mono`. Use `on-surface-variant` (#bfc7d4) for timestamps and `on-surface` (#dfe2ea) for the log message.

---

## Screens Inventory

| Screen | Title | Size |
|---|---|---|
| `3df8979fb8b5412094dc353e280251e4` | Dashboard Shell - Clean | 2560×2048 |
| `2ad41b9771a9461685382701ef5d2617` | Dashboard Shell (original) | 2560×2048 |
| `19afd746ba2541e89114a36f1b521286` | Agent Reasoning Timeline | 2560×2336 |
| `93aff0e86c4e4b23ad3b731d07f0b067` | Scenario Cards | 2560×2048 |
| `c1dc948d3bd24cb69c7814455a639e2e` | Blast Radius Analysis | 2560×2048 |
| `11544157198722980504` | Reference image | 1830×1454 |

---

## Language Guide (Plain Language for UI)

| Technical term | Plain label for UI |
|---|---|
| vitals-ingestion-svc | Vitals Monitoring |
| medication-alerts-svc | Medication Safety |
| lab-routing-svc | Lab Results |
| patient-portal-svc | Patient Portal |
| memory_pressure | Memory Overload |
| cpu_spike | Processing Overload |
| network_partition | Network Disconnected |
| rolling_restart | Graceful Service Restart |
| scale_out | Add More Capacity |
| Blast radius | Patients Affected |
| Remediation plan | Recovery Plan |
| Trust matrix | Safety Gate |
