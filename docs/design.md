---
name: Obsidian Telemetry
colors:
  surface: '#101416'
  surface-dim: '#101416'
  surface-bright: '#363a3c'
  surface-container-lowest: '#0b0f11'
  surface-container-low: '#181c1e'
  surface-container: '#1c2022'
  surface-container-high: '#262b2d'
  surface-container-highest: '#313538'
  on-surface: '#e0e3e5'
  on-surface-variant: '#b9cbbf'
  inverse-surface: '#e0e3e5'
  inverse-on-surface: '#2d3133'
  outline: '#84958a'
  outline-variant: '#3b4a41'
  surface-tint: '#00e29f'
  primary: '#adffd5'
  on-primary: '#003825'
  primary-container: '#05eea8'
  on-primary-container: '#006746'
  inverse-primary: '#006c4a'
  secondary: '#b9c9d3'
  on-secondary: '#23323b'
  secondary-container: '#3c4b54'
  on-secondary-container: '#abbbc5'
  tertiary: '#dcf0ff'
  on-tertiary: '#00354a'
  tertiary-container: '#9ad9ff'
  on-tertiary-container: '#006083'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#45ffb9'
  primary-fixed-dim: '#00e29f'
  on-primary-fixed: '#002114'
  on-primary-fixed-variant: '#005237'
  secondary-fixed: '#d5e5f0'
  secondary-fixed-dim: '#b9c9d3'
  on-secondary-fixed: '#0e1d25'
  on-secondary-fixed-variant: '#3a4951'
  tertiary-fixed: '#c4e7ff'
  tertiary-fixed-dim: '#7bd0ff'
  on-tertiary-fixed: '#001e2c'
  on-tertiary-fixed-variant: '#004c69'
  background: '#101416'
  on-background: '#e0e3e5'
  surface-variant: '#313538'
typography:
  display-lg:
    fontFamily: Space Grotesk
    fontSize: 56px
    fontWeight: '700'
    lineHeight: 64px
    letterSpacing: -0.04em
  display-lg-mobile:
    fontFamily: Space Grotesk
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.03em
  headline-lg:
    fontFamily: Space Grotesk
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Space Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-sm:
    fontFamily: Space Grotesk
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: JetBrains Mono
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-md:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  body-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0.01em
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  label-xs:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '700'
    lineHeight: 14px
    letterSpacing: 0.08em
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-desktop: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1.25rem
  space-xl: 2rem
---

## Brand & Style

This design system embodies an avant-garde quantitative telemetry terminal. Built for mission-critical analytics, high-throughput financial monitoring, and deep data surveillance, it abandons standard consumer SaaS conventions in favor of tactical precision, hard geometric structure, and dense information architecture.

### Personality & Tone
- **Instrumental & Exact:** Interfaces behave like aerospace telemetry or algorithmic execution terminals rather than marketing dashboards.
- **Hypersonic Contrast:** Deep void-black canvases juxtaposed against an electric mint signal line.
- **Unforgiving Precision:** Monospaced data arrays, explicit bounding coordinates, and zero-radius geometry command absolute authority and zero decorative fluff.

### Visual Style Movement
The visual aesthetic fuses **Technical Brutalism** with **Experimental Telemetry**. It utilizes pure right-angle viewports, razor-thin structural dividers, monospace quantitative tables, and targeted laser-focused luminescent highlights.

## Colors

The palette operates under a strict dark regime governed by high-contrast functional roles.

- **Signal Primary (`#05EEA8`):** The electric mint beacon. Reserved exclusively for primary active vectors, verified states, cursor crosshairs, and dominant rate-of-change indicators.
- **Chassis Secondary (`#1B2A32`):** Low-key cyan-tinted slate used for secondary interactive surfaces, panel headers, and segmented switch containers.
- **Telemetry Tertiary (`#38BDF8`):** Cryogenic sky blue dedicated to system diagnostic data, secondary metric series, and structural metadata.
- **Base Neutral (`#080C0E`):** A cold abyssal void underpinning all layouts. Paired with elevated container tiers at `#0D1418` and `#141E24`.

### Functional Status Tokens
- **Positive / Yield:** `#05EEA8` (Matches primary signal)
- **Negative / Fault:** `#FF3B5C` (Acid crimson)
- **Warning / Divergence:** `#FFB224` (Industrial amber)
- **Informational / Sync:** `#38BDF8` (Cryo blue)

Every color token is applied functionally to convey state and density; decorative washes or arbitrary gradients are strictly prohibited.

## Typography

The typographic hierarchy establishes a deliberate dichotomy between structural display anchors and rigorous data readout channels:

- **Display & Section Headers (`Space Grotesk`):** Provides sharp, structural, modernist architecture for views, primary module names, and core analytical KPI banners.
- **Body, Metrics, & Interface Controls (`JetBrains Mono`):** Enforces horizontal and vertical monospace rhythm across all telemetry tables, parameter switches, timestamps, and log entries.

All numerical representations must enable tabular figures (`font-variant-numeric: tabular-nums`) to maintain unwavering visual columns during live socket updates. Label tokens should be styled in uppercase to reinforce physical panel markings.

## Layout & Spacing

This design system uses a strict modular dashboard grid optimized for high-density visual comprehension.

### Layout Model
- **Dense Grid Architecture:** Built around a 12-column layout on desktop viewports and a single or dual-column collapsed stack on mobile displays.
- **Gutter & Boundary Discipline:** 1rem default gutters scale to 1.5rem on viewports above 1440px. Gutters double as structural wireframes where 1px boundary lines align seamlessly through grid coordinates.
- **Density Scaling:** Vertical padding inside components is tightened (`space-xs` and `space-sm`) to maximize visible real estate above the fold.

### Responsive Breakpoints
- **Mobile (< 768px):** Single column stream; charts convert to simplified range streams; analytical tables switch to card-based key-value pairs.
- **Tablet (768px - 1199px):** 6-column grid; auxiliary data panes collapse into sliding drawer sheets.
- **Desktop (1200px+):** Full 12-column layout featuring persistent multi-column telemetry rails and split analytical viewports.

## Elevation & Depth

Visual hierarchy is constructed purely through **Tonal Tiers** and **Sub-pixel Structural Borders**, completely rejecting ambient blur drop-shadows.

### Structural Depth Architecture
- **Layer 0 (Canvas Base):** `#080C0E` — The underlying terminal substrate.
- **Layer 1 (Card & Module Backgrounds):** `#0D1418` — Houses modular telemetry panels, charts, and primary workspace blocks.
- **Layer 2 (Recessed Wells & Inputs):** `#05080A` — Inset areas for field inputs, filter beds, and secondary code blocks.
- **Layer 3 (Floating Overlays & Popovers):** `#141E24` — Highest surface tier reserved for dropdowns, contextual parameter tooltips, and modal alerts.

### Border & Edge Treatment
Depth separation relies on razor-sharp `1px solid rgba(255, 255, 255, 0.08)` borders on default surfaces. In elevated or hovered states, boundaries transition to `1px solid rgba(5, 238, 168, 0.40)`.

### Phosphor Glow Effect
Interactive states and critical alerts utilize a constrained phosphor bloom: a crisp `0 0 12px rgba(5, 238, 168, 0.25)` glow, reinforcing the tactile feel of an illuminated CRT terminal.

## Shapes

The shape system enforces pure, unyielding angularity. With `roundedness: 0`, every UI element across the system operates with hard 90-degree corners.

- **Zero-Radius Primitives:** All cards, buttons, tags, input bars, modal viewports, and table rows are constructed with `border-radius: 0px`.
- **Architectural Accents:** Corners of key interactive modules may feature decorative 45-degree chamfers or terminal crosshair notches (`+` markers at intersection vertices) to evoke quantitative flight hardware.

## Components

### Buttons
- **Primary Action:** Solid `#05EEA8` fill with `#080C0E` text in `JetBrains Mono` (Bold/Caps). Sharp 0px corners. Hover state introduces a phosphor edge glow (`0 0 16px rgba(5, 238, 168, 0.40)`).
- **Secondary Action:** Transparent fill with a `1px solid rgba(255, 255, 255, 0.15)` border and `#FFFFFF` text. Hover state shifts border to `#05EEA8` with a tinted background wash (`rgba(5, 238, 168, 0.06)`).
- **Destructive Action:** Sharp outline with `1px solid #FF3B5C`, transitioning to full `#FF3B5C` fill with `#080C0E` text upon armed confirmation.

### Data Chips & Telemetry Tags
- Compact height (20px), zero-radius borders, `label-xs` typography in monospace uppercase.
- Status indicators feature a leading 4px square LED pip (e.g., green for healthy pulse, red for anomaly).

### Inputs & Search Bars
- Background set to recessed well tone (`#05080A`), framed by `1px solid rgba(255, 255, 255, 0.1)`.
- Caret styled as an electric mint solid block (`#05EEA8`).
- Active focus invokes a `1px solid #05EEA8` boundary with zero outline offset.

### Metric Cards & Analytical Panels
- Composed of `#0D1418` fill wrapped in a `1px solid rgba(255, 255, 255, 0.08)` hairline border.
- Headers are divided from body content by an internal horizontal 1px rule.
- Header bars display monospace tracking codes (`ID // 08-REV`) aligned flush right in `label-xs`.

### Checkboxes & Toggle Controls
- **Checkboxes:** 14px sharp squares. Checked state features a full `#05EEA8` fill with an inset `#080C0E` center block or checkmark.
- **Toggles:** Segmented two-position horizontal blocks. Active state illuminates in high-contrast mint with zero sliding animation delays.

### Data Tables & Stream Lists
- Dense cell padding (`space-xs` vertical, `space-sm` horizontal).
- Alternate row striping using `#080C0E` and `#0A0F12`.
- Hovering a row triggers a continuous `1px solid #05EEA8` left accent spine.