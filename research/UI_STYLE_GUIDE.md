# MedContent AI Platform - UI/UX Style Guide

This document provides comprehensive instructions for implementing the UI design system used in the MedContent AI Platform. The design follows a **"Clinical Clean"** philosophy: professional, trust-based, and suitable for medical/pharmaceutical applications.

---

## Table of Contents
1. [Design Philosophy](#design-philosophy)
2. [Color System](#color-system)
3. [Typography](#typography)
4. [Spacing System](#spacing-system)
5. [Border Radius](#border-radius)
6. [Shadows](#shadows)
7. [Buttons](#buttons)
8. [Form Elements](#form-elements)
9. [Cards](#cards)
10. [Navigation](#navigation)
11. [Layout Patterns](#layout-patterns)
12. [Status & Feedback](#status--feedback)
13. [Animations](#animations)
14. [Responsive Design](#responsive-design)
15. [Component Reference](#component-reference)

---

## Design Philosophy

### Core Principles
1. **Clinical Clean**: Light backgrounds, professional appearance, suitable for medical/pharma
2. **Trust-Based**: Green for verified/compliant, blue for primary actions, clear visual hierarchy
3. **Minimal & Focused**: Avoid clutter, use whitespace generously
4. **Accessible**: High contrast text, clear interactive states, screen-reader friendly

### Visual Language
- **Light Mode by Default**: White and warm gray backgrounds
- **Rounded Corners**: Soft, approachable feel (not harsh rectangles)
- **Subtle Shadows**: Clinical shadows that suggest depth without drama
- **Gradient Accents**: Brand blue gradients for CTAs and highlights

---

## Color System

### Brand Blue (Primary)
The primary brand color used for CTAs, links, and interactive elements.

| Token | Hex | Usage |
|-------|-----|-------|
| `brand-50` | `#d7e9ff` | Light backgrounds, hover states |
| `brand-100` | `#86c9f5` | Light accents |
| `brand-200` | `#00aff0` | Light blue |
| `brand-300` | `#0096f0` | Medium blue |
| `brand-400` | `#007af0` | Bright blue |
| `brand-500` | `#0070bf` | **Primary brand blue** |
| `brand-600` | `#005fa3` | Darker (hover) |
| `brand-700` | `#004d87` | Deep |
| `brand-800` | `#003c6b` | Deeper |
| `brand-900` | `#002b4f` | Darkest |

**Primary Gradient:**
```css
background: linear-gradient(135deg, #0070bf 0%, #007af0 50%, #00aff0 100%);
```

### Neutrals (Warm Stone)
Warm gray palette for backgrounds, text, and borders.

| Token | Hex | Usage |
|-------|-----|-------|
| `neutral-25` | `#FCFCFB` | Lightest |
| `neutral-50` | `#FAFAF9` | Primary background |
| `neutral-100` | `#F5F5F4` | Secondary background |
| `neutral-150` | `#EEEEEC` | Tertiary background |
| `neutral-200` | `#E7E5E4` | Borders |
| `neutral-300` | `#D6D3D1` | Heavy borders |
| `neutral-400` | `#A8A29E` | Dim text |
| `neutral-500` | `#78716C` | Muted text |
| `neutral-600` | `#57534E` | Secondary text |
| `neutral-700` | `#44403C` | Heavy text |
| `neutral-800` | `#292524` | Dark text |
| `neutral-900` | `#1C1917` | Primary text |

### Semantic Colors

#### Trust Green (Success/Verified)
```
50:  #F0FDF4   100: #DCFCE7   200: #BBF7D0   300: #86EFAC
400: #4ADE80   500: #22C55E   600: #16A34A   700: #15803D
```

#### Attention Amber (Warning/Pending)
```
50:  #FFFBEB   100: #FEF3C7   200: #FDE68A   300: #FCD34D
400: #FBBF24   500: #F59E0B   600: #D97706   700: #B45309
```

#### Alert Red (Error/Critical)
```
50:  #FEF2F2   100: #FEE2E2   200: #FECACA   300: #FCA5A5
400: #F87171   500: #EF4444   600: #DC2626   700: #B91C1C
```

#### Process Purple (AI/System Actions)
```
50:  #FAF5FF   100: #F3E8FF   200: #E9D5FF   300: #D8B4FE
400: #C084FC   500: #A855F7   600: #9333EA   700: #7C3AED
```

### CSS Variables Reference
```css
:root {
  /* Backgrounds */
  --bg-primary: #FAFAF9;
  --bg-secondary: #F5F5F4;
  --bg-tertiary: #EEEEEC;
  --bg-elevated: #FFFFFF;
  --bg-hover: #F0F0EE;

  /* Surfaces */
  --surface-card: #FFFFFF;
  --surface-card-hover: #FAFAF9;
  --surface-border: #E7E5E4;

  /* Text */
  --text-primary: #1C1917;
  --text-secondary: #57534E;
  --text-muted: #78716C;
  --text-dim: #A8A29E;

  /* Accent */
  --accent-primary: #0070bf;
  --accent-primary-hover: #007af0;
  --accent-glow: rgba(0, 112, 191, 0.2);

  /* Status */
  --success: #16A34A;
  --success-bg: #F0FDF4;
  --warning: #D97706;
  --warning-bg: #FFFBEB;
  --error: #DC2626;
  --error-bg: #FEF2F2;
  --info: #0070bf;
  --info-bg: #d7e9ff;
}
```

---

## Typography

### Font Families
```css
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', monospace;
```

**Required Google Fonts import:**
```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
```

### Font Sizes
| Token | Size | Usage |
|-------|------|-------|
| `--text-xs` | 0.75rem (12px) | Labels, badges |
| `--text-sm` | 0.875rem (14px) | Body small, captions |
| `--text-base` | 1rem (16px) | Body default |
| `--text-lg` | 1.125rem (18px) | Subheadings |
| `--text-xl` | 1.25rem (20px) | Card titles |
| `--text-2xl` | 1.5rem (24px) | Section titles |
| `--text-3xl` | 1.875rem (30px) | Page titles |
| `--text-4xl` | 2.25rem (36px) | Hero subheadings |
| `--text-5xl` | 3rem (48px) | Hero titles |
| `--text-6xl` | 3.75rem (60px) | Large display |
| `--text-7xl` | 4.5rem (72px) | Hero display |

### Font Weights
- **300**: Light (rarely used)
- **400**: Regular (body text)
- **500**: Medium (labels, navigation)
- **600**: Semibold (headings, buttons)
- **700**: Bold (hero titles, emphasis)

### Line Heights
- Body text: `1.6`
- Headings: `1.1` to `1.2`
- Compact UI: `1.4`

### Letter Spacing
- Headings: `-0.02em` (tighter)
- Uppercase labels: `0.1em` (wider)

---

## Spacing System

Use consistent spacing multiples based on 4px (0.25rem).

| Token | Value | Usage |
|-------|-------|-------|
| `--space-1` | 0.25rem (4px) | Tight gaps |
| `--space-2` | 0.5rem (8px) | Small gaps, inline spacing |
| `--space-3` | 0.75rem (12px) | Compact padding |
| `--space-4` | 1rem (16px) | Default padding |
| `--space-5` | 1.25rem (20px) | Medium padding |
| `--space-6` | 1.5rem (24px) | Section padding |
| `--space-8` | 2rem (32px) | Large gaps |
| `--space-10` | 2.5rem (40px) | Section margins |
| `--space-12` | 3rem (48px) | Large section margins |
| `--space-16` | 4rem (64px) | Page sections |
| `--space-20` | 5rem (80px) | Major sections |
| `--space-24` | 6rem (96px) | Hero padding |

---

## Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | 0.375rem (6px) | Small elements, badges |
| `--radius-md` | 0.5rem (8px) | Inputs, small cards |
| `--radius-lg` | 0.75rem (12px) | Cards, buttons |
| `--radius-xl` | 1rem (16px) | Large cards, modals |
| `--radius-2xl` | 1.5rem (24px) | Feature cards |
| `--radius-full` | 9999px | Pills, avatars, tabs |

**Pattern**: Use `--radius-full` for pill-shaped buttons and navigation tabs.

---

## Shadows

| Token | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(28, 25, 23, 0.04)` | Subtle depth |
| `--shadow-md` | `0 4px 6px -1px rgba(28, 25, 23, 0.06), 0 2px 4px -1px rgba(28, 25, 23, 0.04)` | Cards |
| `--shadow-lg` | `0 10px 15px -3px rgba(28, 25, 23, 0.06), 0 4px 6px -2px rgba(28, 25, 23, 0.03)` | Elevated elements |
| `--shadow-xl` | `0 20px 25px -5px rgba(28, 25, 23, 0.08), 0 10px 10px -5px rgba(28, 25, 23, 0.04)` | Modals |
| `--shadow-brand` | `0 4px 14px -3px rgba(0, 112, 191, 0.25)` | Primary buttons |
| `--shadow-glow` | `0 0 20px rgba(0, 112, 191, 0.2)` | Focus states |

**Note**: Shadows use warm gray tones (not pure black) for a softer, clinical look.

---

## Buttons

### Primary Button
```css
.btn--primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  font-family: var(--font-sans);
  font-size: 1rem;
  font-weight: 600;
  color: white;
  background: linear-gradient(135deg, #0070bf 0%, #007af0 50%, #00aff0 100%);
  border: none;
  border-radius: 9999px;  /* Pill shape */
  box-shadow: 0 4px 14px -3px rgba(0, 112, 191, 0.25);
  cursor: pointer;
  transition: all 200ms ease;
}

.btn--primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px -4px rgba(0, 112, 191, 0.35);
}
```

### Secondary Button
```css
.btn--secondary {
  /* Same base as primary */
  color: var(--text-primary);
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  box-shadow: none;
}

.btn--secondary:hover {
  background: var(--bg-hover);
  border-color: #86c9f5;
}
```

### Button Sizes
```css
/* Default */
padding: 0.75rem 1.5rem;
font-size: 1rem;

/* Large */
padding: 1rem 2rem;
font-size: 1.125rem;

/* Icon-only */
width: 40px;
height: 40px;
padding: 0;
border-radius: 0.75rem;
```

---

## Form Elements

### Text Input
```css
.form-input {
  width: 100%;
  padding: 0.75rem 1rem;
  font-family: var(--font-sans);
  font-size: 1rem;
  color: var(--text-primary);
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 0.75rem;
  outline: none;
  transition: all 200ms ease;
}

.form-input:focus {
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 3px rgba(0, 112, 191, 0.2);
}

.form-input::placeholder {
  color: var(--text-muted);
}
```

### Select Dropdown
```css
.form-select {
  /* Same as input */
  appearance: none;
  background-image: url("data:image/svg+xml,..."); /* Chevron icon */
  background-repeat: no-repeat;
  background-position: right 1rem center;
  padding-right: 2.5rem;
}
```

### Form Group Pattern
```html
<div class="form-group">
  <label for="field">Field Label</label>
  <input type="text" id="field" class="form-input" placeholder="Enter value...">
</div>
```

```css
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-group label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-secondary);
}
```

---

## Cards

### Base Card
```css
.card {
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 1rem;
  padding: 1.5rem;
  transition: all 200ms ease;
}

.card:hover {
  background: var(--surface-card-hover);
  border-color: #86c9f5;
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
```

### Card Header Pattern
```css
.card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.card__icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0070bf, #007af0);
  border-radius: 0.75rem;
  color: white;
}

.card__title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
}

.card__desc {
  font-size: 0.875rem;
  color: var(--text-secondary);
  line-height: 1.6;
}
```

### Feature Card (with gradient background)
```css
.card--feature {
  background: linear-gradient(135deg, #d7e9ff 0%, #E0F2FE 100%);
  border-color: #86c9f5;
}
```

---

## Navigation

### Top Navigation Bar
```css
.nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--surface-border);
}

.nav__inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1.5rem;
}
```

### Navigation Links
```css
.nav__link {
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-secondary);
  text-decoration: none;
  border-radius: 9999px;
  transition: all 200ms ease;
}

.nav__link:hover {
  color: var(--text-primary);
  background: var(--surface-card);
}

.nav__link--active {
  color: var(--text-primary);
  background: var(--surface-card);
}
```

### Tab Navigation
```css
.tabs {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem;
  background: var(--surface-card);
  border-radius: 9999px;
  border: 1px solid var(--surface-border);
}

.tabs__tab {
  padding: 0.5rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  border-radius: 9999px;
  cursor: pointer;
  transition: all 200ms ease;
}

.tabs__tab--active {
  color: var(--text-primary);
  background: var(--bg-elevated);
}
```

---

## Layout Patterns

### Container Widths
```css
--max-width: 1200px;         /* Default content */
--max-width-narrow: 800px;   /* Text-heavy content */
--max-width-wide: 1400px;    /* Full-width layouts */
```

### Grid Layouts
```css
/* Auto-fit responsive grid */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5rem;
}

/* Fixed 2-column */
.grid--2 {
  grid-template-columns: repeat(2, 1fr);
}

/* Fixed 3-column */
.grid--3 {
  grid-template-columns: repeat(3, 1fr);
}
```

### Sidebar + Content Pattern
```css
.layout-sidebar {
  display: flex;
  min-height: 100vh;
}

.layout-sidebar__sidebar {
  width: 320px;
  min-width: 280px;
  max-width: 400px;
  background: var(--surface-card);
  border-right: 1px solid var(--surface-border);
}

.layout-sidebar__content {
  flex: 1;
  overflow: auto;
}
```

---

## Status & Feedback

### Status Badges
```css
.badge {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.75rem;
  font-size: 0.75rem;
  font-weight: 500;
  border-radius: 9999px;
}

.badge--success {
  color: #16A34A;
  background: #F0FDF4;
}

.badge--warning {
  color: #D97706;
  background: #FFFBEB;
}

.badge--error {
  color: #DC2626;
  background: #FEF2F2;
}

.badge--info {
  color: #0070bf;
  background: #d7e9ff;
}

.badge--neutral {
  color: var(--text-muted);
  background: var(--bg-tertiary);
}
```

### Loading States
```css
/* Skeleton loader */
.skeleton {
  background: linear-gradient(90deg, #F5F5F4 25%, #E7E5E4 50%, #F5F5F4 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
  border-radius: 0.5rem;
}

@keyframes skeleton-loading {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Spinner */
.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--surface-border);
  border-top-color: var(--accent-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

### Toast Notifications
```css
.toast {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 1.5rem;
  background: var(--surface-card);
  border: 1px solid var(--surface-border);
  border-radius: 0.75rem;
  box-shadow: var(--shadow-lg);
}

.toast--success { border-left: 4px solid #16A34A; }
.toast--warning { border-left: 4px solid #D97706; }
.toast--error { border-left: 4px solid #DC2626; }
```

---

## Animations

### Transition Tokens
```css
--transition-fast: 150ms ease;
--transition-base: 200ms ease;
--transition-slow: 300ms ease;
```

### Standard Animations
```css
/* Fade in */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* Slide up (for modals, dropdowns) */
@keyframes slideUp {
  from { transform: translateY(10px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

/* Pulse (for live indicators) */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* Bounce (for scroll indicators) */
@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(4px); }
}
```

### Hover Effects
- **Buttons**: `transform: translateY(-1px)` + enhanced shadow
- **Cards**: `transform: translateY(-2px)` + border color change
- **Links**: Color transition only

---

## Responsive Design

### Breakpoints
```css
/* Mobile first approach */
@media (max-width: 640px) { /* Mobile */ }
@media (max-width: 768px) { /* Tablet portrait */ }
@media (max-width: 1024px) { /* Tablet landscape */ }
@media (max-width: 1280px) { /* Small desktop */ }
```

### Mobile Adjustments
1. **Navigation**: Collapse to hamburger menu
2. **Grids**: Stack to single column below 640px
3. **Padding**: Reduce from `--space-6` to `--space-4`
4. **Font sizes**: Use `clamp()` for responsive scaling
5. **Sidebars**: Hide or overlay on mobile

---

## Component Reference

### Icon Usage
- Use Lucide React icons (`lucide-react` package)
- Default size: 20px (navigation), 24px (buttons), 48px (feature cards)
- Icon color inherits from text color

### Avatar Pattern
```css
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 0.75rem;
  background: var(--surface-card);
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar--ai {
  background: linear-gradient(135deg, #0070bf, #007af0);
  color: white;
}
```

### Empty State Pattern
```css
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  text-align: center;
}

.empty-state__icon {
  width: 64px;
  height: 64px;
  margin-bottom: 1rem;
  color: var(--text-muted);
}

.empty-state__title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
}

.empty-state__desc {
  font-size: 0.875rem;
  color: var(--text-secondary);
  max-width: 400px;
}
```

---

## Implementation Checklist

- [ ] Import Inter and JetBrains Mono fonts
- [ ] Set up CSS variables for colors, spacing, typography
- [ ] Use Tailwind CSS with custom config (or vanilla CSS with variables)
- [ ] Implement pill-shaped buttons with gradient for primary CTAs
- [ ] Use warm gray neutrals (not pure gray)
- [ ] Add subtle shadows (not harsh drop shadows)
- [ ] Include focus states with blue glow
- [ ] Test all interactive states (hover, active, focus, disabled)
- [ ] Verify color contrast meets WCAG AA standards
- [ ] Test responsive layouts at all breakpoints

---

## Quick Start CSS

Minimal CSS to get started:

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --brand-500: #0070bf;
  --brand-600: #005fa3;
  --neutral-50: #FAFAF9;
  --neutral-200: #E7E5E4;
  --neutral-500: #78716C;
  --neutral-900: #1C1917;
  --success: #16A34A;
  --warning: #D97706;
  --error: #DC2626;
}

body {
  font-family: 'Inter', sans-serif;
  background: var(--neutral-50);
  color: var(--neutral-900);
  line-height: 1.6;
}

.btn-primary {
  background: linear-gradient(135deg, #0070bf, #007af0);
  color: white;
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 9999px;
  font-weight: 600;
  cursor: pointer;
}

.card {
  background: white;
  border: 1px solid var(--neutral-200);
  border-radius: 1rem;
  padding: 1.5rem;
}
```

---

## Contact & Resources

- **Figma**: [Request access to design files]
- **Component Library**: See `frontend/src/components/`
- **Full CSS**: See `frontend/src/styles/scriptiva.css`
- **Tailwind Config**: See `frontend/tailwind.config.js`
