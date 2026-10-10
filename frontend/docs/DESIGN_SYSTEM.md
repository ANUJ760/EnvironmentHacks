# EcoTwin Design System & UI Specifications

## 1. Visual Direction & Aesthetic
- Comfortable, richly detailed 2D/top-down city viewer inspired by urban simulation classics.
- Soft neutral surfaces, crisp borders, forest-green accents, and focused map viewport.
- Uncluttered desktop layout: full-height top bar, collapsible 280px left rail, full central map canvas, collapsible 320px right inspector, and contextual dialogs.

## 2. Color Tokens & Contrast
| Token | Hex Value | Semantic Role |
|---|---|---|
| `background` | `#F6F8F4` | App base canvas / viewport background |
| `ink` / text | `#172A24` | Primary high-contrast typography (13.5:1 ratio) |
| `primary` | `#0C8055` | Primary CTA, active selections, brand symbol |
| `primary-hover` | `#096342` | Darker active hover state |
| `forest` | `#173F33` | Deep brand tone for primary action bars |
| `accent` | `#2F9E81` | Secondary environmental highlights |
| `border` | `#D8E5DD` | Subtle structural division lines |
| `warning` | `#B56B1F` | Non-destructive cautions & draft badges |

## 3. Typography & Spacing
- **Font Stack**: System UI (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`).
- **Code / Identifiers**: System monospace (`ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas`).
- **Target Sizes**: Minimum 44×44 CSS px touch targets for toolbar buttons and controls.
- **Responsiveness**: Fluid layout with responsive breakpoints for desktop (1440px), tablet (900px), and mobile (375px).

## 4. Accessibility Targets (WCAG 2.2 AA)
- Minimum 4.5:1 contrast for regular text; 3:1 for large text and interactive components.
- Complete keyboard accessibility: Tab navigation, Enter/Space activation, Esc modal dismissal.
- Full DOM/SVG fallback view (`SvgMapFallback`) and feature directory (`AccessibleFeatureList`) for non-canvas users and screen readers.
- `prefers-reduced-motion` compliance.
