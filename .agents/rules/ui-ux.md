---
trigger: "glob:frontend/src/**/*"
description: "Design system tokens, accessibility, canvas animations, and component styling for ContextForge"
priority: 2
applies_to: ["frontend/src/**/*.jsx", "frontend/src/**/*.js", "frontend/src/**/*.css"]
---

# UI/UX Rules — ContextForge

These rules apply to all frontend files. They enforce the design system defined in `PRD.md §5`, WCAG 2.1 AA accessibility, and animation quality standards.

---

## Design Token Usage

### Rule UI-001: All colours must use CSS custom property tokens
No hardcoded hex values, RGB values, or named colours may appear in component styles. All colour references must use the CSS custom properties defined in the global stylesheet:

```css
/* CORRECT */
.agent-card { background: var(--color-surface); border-color: var(--color-border); }
.score-number { color: var(--color-accent-signal); }

/* FORBIDDEN */
.agent-card { background: #0C1524; }  /* hardcoded hex */
.score-number { color: blue; }        /* named colour */
```

The complete token list is defined in `PRD.md §5.2`. If a new colour is needed, it must be added to the token system in the global CSS file first, then referenced via `var()`.

### Rule UI-002: All font sizes must use CSS custom property scale tokens
Font sizes must reference the typographic scale tokens:

```css
/* CORRECT */
.section-title { font-size: var(--text-h2); font-weight: 600; line-height: 1.3; }
.body-copy { font-size: var(--text-body); font-weight: 400; line-height: 1.6; }

/* FORBIDDEN */
.section-title { font-size: 24px; }  /* hardcoded size */
.body-copy { font-size: 1em; }       /* relative without scale anchor */
```

### Rule UI-003: Typography families must only use the three defined font stacks
```css
/* CORRECT */
--font-display: 'Space Grotesk', system-ui, sans-serif;
--font-body: 'Inter', system-ui, sans-serif;
--font-mono: 'JetBrains Mono', 'Courier New', monospace;

/* FORBIDDEN: any other Google Font or system font substitution without updating PRD */
```

---

## Accessibility (WCAG 2.1 AA)

### Rule UI-004: All interactive elements must be keyboard-reachable and have visible focus states
Every button, link, input, and interactive element must:
- Be reachable via `Tab` key
- Have a visible focus indicator that meets 3:1 contrast ratio against its surroundings
- Not rely solely on colour to convey state (e.g., agent status chips must show both a colour change AND a text label change)

```css
/* Required focus style pattern */
:focus-visible {
  outline: 2px solid var(--color-accent-signal);
  outline-offset: 2px;
  border-radius: 2px;
}
/* Never remove focus outlines with outline: none without a replacement */
```

### Rule UI-005: All images and canvas elements must have text alternatives
- `<img>` elements: always have a descriptive `alt` attribute. Decorative images use `alt=""`.
- Canvas elements used for animation: must have `aria-label` and `role="img"` or `aria-hidden="true"` if purely decorative.

```jsx
// Particle background (decorative — hidden from screen readers)
<canvas ref={canvasRef} aria-hidden="true" className="particle-canvas" />

// Neural net canvas (provides status — must be labelled)
<canvas
  ref={neuralRef}
  role="img"
  aria-label={`${agentName} agent — ${status}`}
  className="neural-canvas"
/>
```

### Rule UI-006: Colour contrast ratios must meet WCAG 2.1 AA minimums
- Normal text (< 18px): minimum 4.5:1 contrast ratio
- Large text (>= 18px or >= 14px bold): minimum 3:1 contrast ratio
- UI components (borders, icons): minimum 3:1 against background

**Pre-verified token pairs (do not mix other combinations without contrast check):**
| Text token | Background token | Ratio |
|-----------|-----------------|-------|
| `--color-text-primary` on `--color-void` | `#E8F0FE` on `#050A14` | 16.8:1 ✓ |
| `--color-text-primary` on `--color-surface` | `#E8F0FE` on `#0C1524` | 14.2:1 ✓ |
| `--color-text-secondary` on `--color-void` | `#7B9CC7` on `#050A14` | 5.1:1 ✓ |
| `--color-success` on `--color-surface` | `#00D68F` on `#0C1524` | 7.3:1 ✓ |
| `--color-error` on `--color-surface` | `#FF4D4F` on `#0C1524` | 5.8:1 ✓ |
| `--color-warning` on `--color-surface` | `#FFB020` on `#0C1524` | 6.1:1 ✓ |

**Forbidden combination:** `--color-text-muted` (`#3D5A80`) on `--color-void` — ratio is 2.8:1, below AA. Use only for non-text UI elements.

### Rule UI-007: Agent status must never be communicated by colour alone
The AgentCard status chip must always show both a colour change AND a text label:
- Pending: grey background, label "Waiting"
- Running: blue pulsing background, label "Thinking..."
- Complete: green background, label "Done"
- Failed: red background, label "Failed"

WCAG Success Criterion 1.4.1 prohibits relying solely on colour.

### Rule UI-008: All form inputs must have associated visible labels
The ChatBox textarea must have an associated `<label>` element (even if visually hidden via `sr-only`):
```jsx
<label htmlFor="idea-input" className="sr-only">
  Describe your business idea
</label>
<textarea
  id="idea-input"
  placeholder="Describe your business idea — as a sentence, a voice note, or a document."
  aria-label="Business idea input"
/>
```

### Rule UI-009: Dynamic content updates must use ARIA live regions
When agent status changes, the heatmap populates, or the BRD sections render, these updates must be announced to screen readers via `aria-live`:

```jsx
// Agent status announcements
<div aria-live="polite" aria-atomic="false" className="sr-only" id="status-announcer">
  {latestStatusMessage}  {/* e.g., "VC agent complete. Lean Founder agent now thinking." */}
</div>
```

---

## Layout & Responsive Design

### Rule UI-010: No layout shift after initial render
Components that receive async data must render a fixed-size skeleton at the same dimensions as the loaded state. No element may change its height or width after data loads, as this causes Cumulative Layout Shift (CLS) violations.

```jsx
// CORRECT: skeleton at same height as loaded card
{status === 'loading'
  ? <div className="agent-card-skeleton" style={{ height: '160px' }} />
  : <AgentCard agent={agent} status={status} />
}
```

### Rule UI-011: Responsive breakpoints are fixed at three values
```css
/* Mobile first base: 0–767px */
/* Tablet: 768px–1023px */
@media (min-width: 768px) { }
/* Desktop: 1024px+ */
@media (min-width: 1024px) { }
```

No other breakpoints may be added without updating this rule. Do not use pixel values between these.

### Rule UI-012: AgentGrid must use CSS Grid, not Flexbox
The 6-agent grid must be implemented with CSS Grid to guarantee correct cell alignment regardless of content length:
```css
.agent-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);  /* 3 columns desktop */
  gap: 16px;
}
@media (max-width: 767px) {
  .agent-grid { grid-template-columns: 1fr; }  /* 1 column mobile */
}
@media (min-width: 768px) and (max-width: 1023px) {
  .agent-grid { grid-template-columns: repeat(2, 1fr); }  /* 2 columns tablet */
}
```

---

## Animation Rules

### Rule UI-013: Respect `prefers-reduced-motion`
All CSS animations and canvas animations must check the `prefers-reduced-motion` media query. If the user has requested reduced motion, all animations must be either disabled or reduced to a simple opacity change:

```css
@media (prefers-reduced-motion: reduce) {
  .agent-card { animation: none !important; transition: opacity 200ms ease; }
  .heatmap-bar { transition: none; }
  .score-ring { animation: none; }
}
```

For canvas animations (particle field, neural net), the `useParticleCanvas` hook must check:
```javascript
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
if (prefersReducedMotion) {
  // Render one static frame only; do not start animation loop
  return;
}
```

### Rule UI-014: Animation performance — no CSS properties that trigger layout
CSS transitions and animations must only use `transform` and `opacity`. Never animate `width`, `height`, `top`, `left`, `margin`, or `padding` as they trigger browser layout recalculation:

```css
/* CORRECT: GPU-composited properties only */
.agent-card { transition: opacity 300ms ease, transform 300ms ease; }
.agent-card.running { transform: scale(1.02); opacity: 1; }

/* FORBIDDEN: layout-triggering animation */
.heatmap-bar { transition: width 800ms ease; }  /* causes layout recalc */
/* Alternative: use transform: scaleX() with transform-origin: left */
.heatmap-bar-fill { transform-origin: left center; transition: transform 800ms cubic-bezier(0.34,1.56,0.64,1); }
```

### Rule UI-015: Canvas must be sized via `devicePixelRatio` for crisp rendering on HiDPI
```javascript
function resizeCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  return ctx;
}
```

This must be called on canvas mount and on every `resize` event (debounced to 100ms).

### Rule UI-016: The particle background canvas must never block scroll or pointer events
```css
.particle-canvas {
  position: fixed;
  top: 0; left: 0;
  width: 100%; height: 100%;
  pointer-events: none;  /* REQUIRED: never capture user interaction */
  z-index: -1;
}
```

---

## Component Styling Conventions

### Rule UI-017: No inline styles except for dynamic canvas/animation values
Inline `style` props in React must only be used for values that genuinely cannot be expressed in CSS (e.g., dynamic canvas dimensions computed at runtime, SVG stroke-dasharray values for score rings). All other styling must use CSS class names.

```jsx
// CORRECT: dynamic value cannot be in static CSS
<circle style={{ strokeDasharray: `${circumference} ${circumference}`, strokeDashoffset: offset }} />

// FORBIDDEN: static style that belongs in CSS
<div style={{ display: 'flex', gap: '16px' }}>  {/* put this in a CSS class */}
```

### Rule UI-018: Heatmap risk level colour must be applied via data attribute, not inline style
```jsx
// CORRECT: CSS handles the colour via attribute selector
<div className="heatmap-section" data-risk={section.risk_level}>
  ...
</div>

/* In CSS: */
.heatmap-section[data-risk="high"] .risk-bar { background: var(--color-risk-high); }
.heatmap-section[data-risk="medium"] .risk-bar { background: var(--color-risk-medium); }
.heatmap-section[data-risk="low"] .risk-bar { background: var(--color-risk-low); }
```

### Rule UI-019: Agent accent colours must be applied via data attribute on agent cards
```jsx
<div className="agent-card" data-agent={agent.name}>
// CSS:
.agent-card[data-agent="vc"] { --agent-accent: var(--color-agent-vc); }
.agent-card[data-agent="lean"] { --agent-accent: var(--color-agent-lean); }
/* etc. */
.agent-card .status-border { border-color: var(--agent-accent); }
```
