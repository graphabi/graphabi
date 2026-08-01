# GraphABI design system

Version: 0.1
Status: active
Updated: 2026-08-01

## Brand core

**Category:** Semantic Compatibility Infrastructure
**Promise:** Your schema passed. Your agent still broke. GraphABI tells you exactly where.
**Mechanism:** GraphABI records semantic flow across graph edges, checks the assumptions a consumer relies on, stops at the first incompatibility, traces the affected path, and presents a concrete witness and repair location.

GraphABI is not represented by artificial intelligence imagery, abstract computation, or generic observability charts. Its identity is one interrupted relationship: meaning reached an edge but could not cross it safely.

## The Semantic Pulse

The Semantic Pulse is the universal visual and motion primitive. It is a small packet of meaning moving along graph edges.

Its reasoning sequence is always:

1. **Flow**: a violet pulse moves from producer to consumer.
2. **Check**: the consumer edge evaluates its explicit contract.
3. **Break**: a red interruption stops incompatible meaning.
4. **Trace**: the affected downstream route becomes visible without implying execution continued.
5. **Explain**: a witness reveals the observed value and violated expectation.
6. **Fix**: the nearest repair edge is identified.

The pulse is explanatory, not ambient. It runs once, resolves to a stable result, and stops. It may be replayed through an explicit control.

## Field and instrument

Two graph languages exist, and they are never mixed on the same surface.

**The instrument** is every product surface: the replay, the playground, the report, the architecture pipeline. It is precise, deterministic, and it comes to rest. It asserts a result. Everything above about the Semantic Pulse governs it.

**The field** is the ambient substrate behind the page. It is a live force-directed graph whose topology rewires itself and across which pulses travel, most arriving and some stopping at a cut. It never resolves and never repeats. It represents the world before GraphABI: meaning moving through a graph, breaking quietly, with nobody watching.

The field is bound by three rules:

- it is decorative, `aria-hidden`, and carries no information that is absent elsewhere;
- it never asserts a verdict about anything the product has actually checked;
- it stays below every product surface in contrast, so it can never compete with evidence.

The tension between the two is the argument: unbounded semantic flow on one side, a stopped and explained artifact on the other. A surface is one or the other, never both.

### Pulse states

| State | Color | Behavior | Meaning |
|---|---:|---|---|
| In flight | `#A78BFA` | Moves toward the consumer | Semantic information is being observed. |
| Compatible | `#22C55E` | Reaches the node; edge resolves solid | The explicit contract passed. |
| Breaking | `#EF4444` | Stops at the gap; graph freezes | The consumer's semantic assumption was violated. |
| Unknown | `#F59E0B` | Stops with a dotted unresolved tail | The available evidence cannot prove compatibility. |
| Inactive | `#556070` | Static, low emphasis | No result is being asserted. |

PASS, BREAKING, and UNKNOWN must always be expressed with text and/or a symbol in addition to color.

## Logo system

### Concept

The logo is one broken edge. A producer node is connected to a consumer rail, but the connection is interrupted by a precise diagonal cut. The cut is the identity; the nodes are context.

The mark must never become a generic multi-node graph. It must not use brains, robots, circuits, neural networks, hexagons, atoms, cubes, shields, sparks, or checkmarks.

### Geometry

- Canonical mark view box: `0 0 64 64`.
- Node diameter: 10 units.
- Edge center line: y = 32.
- Left node center: x = 9.
- Right node center: x = 55.
- Edge gap: x = 29–35.
- Break glyph: two short diagonal strokes centered on the gap, visually forming an interruption rather than a decorative X.
- Stroke cap and join: round.
- Primary stroke: 4 units at 64 px; optically increased at 16 px.
- Clear space: at least one node diameter on all sides.

The left flow segment uses Semantic Pulse violet. The stopped segment and interruption use fail red in color contexts. Monochrome variants use the current text color and preserve the gap.

### Lockups

- `logo.svg`: default horizontal mark plus GraphABI wordmark for dark backgrounds.
- `logo-dark.svg`: light wordmark on the dark GraphABI field.
- `logo-light.svg`: dark wordmark for light backgrounds.
- `logo-monochrome.svg`: one-color lockup using `currentColor`-equivalent geometry.
- `logo-mark.svg`: mark only.
- `icon.svg`: compact mark with extra optical weight.
- `favicon.svg`: 16 px safe mark, no wordmark.
- `organization-avatar.svg`: centered mark on the GraphABI background.

### Minimum sizes

- Mark: 16 px.
- Horizontal lockup: 112 px wide.
- Avatar mark should occupy 58–66% of the canvas.

At 16 px the break remains at least two device pixels wide. Do not render the wordmark below 112 px.

### Incorrect use

Do not close the gap, animate the logo continuously, add shadows to the mark, place it on noisy imagery, recolor status segments arbitrarily, stretch the geometry, place the cut on multiple edges, or turn the mark into a general graph diagram.

## Color system

### Core palette

| Token | Value | Use |
|---|---:|---|
| `color-bg` | `#0B0F14` | Primary dark canvas. |
| `color-surface` | `#121820` | Evidence panels, code, and raised graph regions. |
| `color-surface-strong` | `#18212C` | Active or nested surfaces. |
| `color-primary` | `#8B5CF6` | Brand action and selected control. |
| `color-pulse` | `#A78BFA` | Semantic information in flight. |
| `color-pass` | `#22C55E` | Deterministic compatibility pass. |
| `color-fail` | `#EF4444` | Breaking semantic incompatibility. |
| `color-unknown` | `#F59E0B` | Unknown or insufficient evidence. |
| `color-pass-text` / `color-fail-text` / `color-unknown-text` | theme-specific | Status colors set as text. |
| `color-edge` | `#556070` | Inactive graph edges. |
| `color-text` | `#F8FAFC` | Primary text on dark backgrounds. |
| `color-muted` | `#94A3B8` | Supporting copy and metadata. |
| `color-subtle` | `#64748B` | Tertiary metadata when contrast permits. |
| `color-border` | `#273241` | Surface and divider borders. |
| `color-light-bg` | `#F8FAFC` | Light-context canvas. |
| `color-light-text` | `#0B0F14` | Light-context text and logo. |

### Color rules

- Purple means active semantic flow or a primary action. It is not a decorative wash.
- Green is only a proven pass. Never use it for “probably compatible.”
- Red identifies an actual breaking violation, not generic emphasis.
- Amber covers both UNKNOWN and INSUFFICIENT_EVIDENCE; the written label distinguishes them.
- Inactive graph structure is never brighter than active evidence.
- Large-area status backgrounds use low-alpha tints; full-strength colors are reserved for strokes, symbols, labels, and focus moments.
- Status colors are split by role. The base token drives strokes, rails, node borders, and the break mark, which are non-text UI and only have to clear 3:1. The `-text` token drives anything set as text and has to clear 4.5:1 against every surface it can land on, including the status tints. A single value cannot satisfy both, and the break mark keeps full strength.

## Typography

No web fonts are loaded. System typography is a performance and privacy decision.

### Families

```css
--font-sans: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont,
  "Segoe UI", sans-serif;
--font-mono: "SFMono-Regular", "Cascadia Code", "Roboto Mono",
  ui-monospace, monospace;
```

Inter is used only when already installed. The layout must remain correct with the system fallback.

### Scale

| Role | Size / line height | Weight | Notes |
|---|---|---:|---|
| Display | `clamp(2.65rem, 7vw, 5.75rem) / 0.96` | 650 | Tight tracking, max 12 words. |
| Page title | `clamp(2rem, 4vw, 3.5rem) / 1.02` | 650 | Reports and documentation. |
| Section title | `clamp(1.6rem, 3vw, 2.5rem) / 1.1` | 620 | One idea per section. |
| Component title | `1.125rem / 1.35` | 600 | Witnesses and graph modules. |
| Body large | `1.125rem / 1.7` | 400 | Introductory explanation. |
| Body | `1rem / 1.65` | 400 | General copy. |
| Label | `0.75rem / 1.3` | 650 | Uppercase, `0.09em` tracking. |
| Code | `0.875rem / 1.65` | 450 | Commands, YAML, and evidence. |

Headlines use sentence case. All-caps is reserved for compact system labels such as PASS and BREAKING.

## Spacing and geometry

- Base unit: 4 px.
- Content spacing scale: 4, 8, 12, 16, 24, 32, 48, 64, 96, 128 px.
- Maximum narrative width: 720 px.
- Maximum page width: 1200 px.
- Minimum page gutter: 20 px mobile, 32 px tablet, 48 px desktop.
- Surface radius: 12 px.
- Compact controls and badges: 8 px.
- Nodes: 10–12 px corner radius, never fully pill-shaped.
- Border: 1 px `color-border`.
- Status line: 2 px; active pulse track: 3 px.

Avoid excessive rounding. Evidence should feel precise and inspectable, not soft or toy-like.

## Component language

### Graph node

A node contains a concise node ID and optional role. It has five states:

- dormant: dim border and label;
- active: violet border with a small leading pulse marker;
- passed: green edge arrival and restrained green status tick;
- affected: red-tinted border with a downstream label, but no implication that the node itself violated the contract;
- terminal: square terminal notch or explicit `terminal` label.

Nodes do not bob, glow continuously, or change physical position during evaluation.

### Graph edge

An edge is a status-bearing interface, not a connector. It comprises an inactive rail, an optional semantic pulse, a status marker, and an edge/contract label when space permits.

- PASS: continuous green resolved rail.
- BREAKING: red leading rail terminating at the logo cut; the downstream route is red-dashed to communicate blast radius, not successful propagation.
- UNKNOWN: amber dotted rail with an unresolved marker.
- Inactive: neutral gray rail.

### Broken-edge marker

The logo cut is reused at the first incompatible edge. It is the only high-saturation red focal point in a graph scene. Multiple breaking findings may be listed, but the replay freezes at the first breaking edge.

### Status badge

Badges contain a symbol plus label:

- `✓ PASS`
- `× BREAKING`
- `! WARNING`
- `? UNKNOWN`
- `… INSUFFICIENT EVIDENCE`

Use compact rectangular badges with 8 px radius. Status is never communicated by an unlabeled dot.

### Witness card

The witness is the explanatory payoff. Its header begins with a small broken-edge mark and the contract ID. Its body compares expectation and observation in adjacent or stacked columns. It must include run ID, edge, relevant metadata, reason schema validation did not catch the issue, affected path, and nearest repair location. Full trace detail belongs in an accessible disclosure below the minimal witness.

### Code and terminal

Code surfaces use the same graph rail as a left border. YAML contract conditions use violet, requirements use green, and observed conflicts use red only when annotated outside the code tokenization. Terminal output is real and never embellished with invented timing or customer data.

### Buttons and links

Primary action: violet background, light text, no gradient.

Secondary action: transparent surface, border, light text.
Text link: light text with a violet underline on hover/focus.

All interactive targets are at least 44 × 44 px. Focus uses a 2 px `#A78BFA` ring with 3 px offset.

## Motion language

### Easing and duration

```css
--ease-out-quint: cubic-bezier(0.22, 1, 0.36, 1);
--duration-fast: 220ms;
--duration-standard: 320ms;
--duration-slow: 500ms;
```

Transitions below 220 ms feel like UI response rather than narrative. No narrative transition exceeds 500 ms. Pauses between causal steps may last longer so the result can be read.

### Canonical replay timeline

1. **0–320 ms:** graph nodes resolve into view in topology order.
2. **320–820 ms:** neutral edges connect.
3. **820–2,200 ms:** baseline pulse traverses all edges; each resolves green.
4. **2,200–2,700 ms:** candidate-change label appears; schema indicator remains green.
5. **2,700–3,900 ms:** candidate pulse leaves researcher and reaches the verifier contract.
6. **3,900–4,220 ms:** the edge interrupts red and the pulse stops.
7. **4,220–4,720 ms:** downstream blast radius resolves as red dashed rails.
8. **4,720–5,220 ms:** the witness panel enters once and receives focus only when replay was user-initiated.
9. **After 5,220 ms:** the interface is static. Nothing loops.

Exact pauses can vary by surface, but the causal order cannot.

### Animation properties

Animate `transform`, `opacity`, stroke color, and stroke dash offset. Avoid layout-triggering motion. The pulse travels on the edge center line and stops before the gap. On product surfaces use no bounce, elastic easing, floating elements, random particle systems, scrolling parallax, or ambient loops.

The ambient field is the single exception, and only under the rules in "Field and instrument". It is a continuous simulation rather than a particle system: nodes are held by repulsion and edge springs, and every mark on screen belongs to a node or an edge. Decorative motion that is not a graph is still prohibited.

### Reduced motion

When `prefers-reduced-motion: reduce` is active:

- skip the replay timeline;
- render the final graph state immediately;
- reveal the witness without sliding;
- remove moving dash patterns and pulses;
- retain status color, labels, break marker, affected route, and all explanatory content;
- keep the replay control available only if it performs an immediate state reset without animation, or label it unavailable.

Motion never contains information that is absent from the final static state.

## Information architecture

### Website

1. Hero: category, promise, one-command action, canonical replay.
2. The bug normal checks miss: same shape, changed meaning.
3. Interactive graph: replay and inspect first breaking edge.
4. How it works: flow → check → break → trace → explain → fix.
5. YAML contract: consumer-driven invariant.
6. Terminal demo: actual command and output.
7. Architecture: adapters → trace model → contracts → impact → reports.
8. Real report: witness, blast radius, and repair point.
9. Roadmap: honest implemented/next distinction.
10. GitHub CTA: repository, documentation, contribution.

### README

The first screen contains lockup, category, promise, hero GIF, and `uvx graphabi demo` or the documented install-and-run equivalent. Technical proof follows before feature breadth. The README links to detailed docs rather than duplicating all architecture and contributor policy.

### Generated report

1. Run and compatibility verdict.
2. Replayable affected graph.
3. First breaking edge and witness.
4. Structural comparison.
5. All semantic findings.
6. Downstream paths and repair location.
7. Unknown and insufficient-evidence results.
8. Full trace disclosures.
9. Limitations and reproduction command.

### Organization profile

One project only: logo, one-sentence mission, compact graph visual, repository, website, contributing, security.

## Responsive behavior

- Desktop graphs may flow horizontally.
- At widths below 720 px, canonical linear graphs become vertical so labels remain readable.
- Complex report graphs may use an explicitly labelled horizontal scroll region; never shrink below a 13 px graph label.
- Witness comparisons switch from two columns to one.
- Header actions wrap without hiding the primary demo action.
- Decorative secondary metadata may disappear; evidence and status may not.
- The hero promise must remain fully visible at 320 px width without horizontal page overflow.

## Accessibility requirements

- Meet WCAG 2.2 AA contrast for text and interactive controls.
- Use one `<h1>` and a logical heading outline.
- Provide a skip link on the website and report.
- SVGs use `<title>` and `<desc>`; decorative SVGs are hidden.
- Replay controls are native buttons with an accessible name and visible focus.
- Use an `aria-live="polite"` region for replay narration; do not announce every animation frame.
- Do not move keyboard focus during autoplay.
- Expandable trace evidence uses native `<details>`/`<summary>`.
- Tables retain headers and horizontal overflow wrappers on narrow screens.
- Every image has useful alternative text or an empty alt when adjacent text fully duplicates it.
- HTML-looking trace values remain escaped in reports.

## Voice and content

GraphABI sounds precise, direct, and skeptical.

Preferred:

- “Your schema passed. Your agent still broke.”
- “First breaking edge: researcher → verifier.”
- “The candidate asserted `verified=true` without an opened supporting source.”
- “UNKNOWN: the trace does not contain enough evidence to prove this contract.”
- “GraphABI enforces explicit assumptions; it does not understand arbitrary meaning.”

Avoid:

- “AI-powered,” “revolutionary,” “magic,” “intelligent,” or “enterprise-grade.”
- Claims that a schema proves semantics.
- Claims that UNKNOWN is a pass.
- Generic phrases such as “unlock insights,” “observability at scale,” or “build with confidence.”
- Fictional adoption, performance, or ecosystem claims.

## Asset matrix

Canonical sources live under `docs/assets/brand/`.

| Asset | Format | Purpose |
|---|---|---|
| Logo lockups | SVG | README, site, report header, documentation. |
| Logo mark and icon | SVG | Compact navigation and package identity. |
| Favicon | SVG | Browser tab at 16 px. |
| Hero graph | SVG + HTML/CSS/JS implementation | Canonical Semantic Pulse scene. |
| Demo animation | GIF | GitHub-compatible README replay. |
| Architecture | SVG | Framework-independent flow. |
| Report preview | SVG | README and site report section. |
| Social preview | SVG + 1280×640 PNG | GitHub repository social preview. |
| OpenGraph | SVG + 1200×630 PNG | Website link unfurl. |
| Organization avatar | SVG + 512×512 PNG | Organization identity. |

Raster derivatives are generated from the canonical SVG or deterministic animation source. They must not be edited independently.

## Performance budget

- No runtime framework, analytics, web font, CDN, video, or network request.
- Initial website transfer target: under 250 KB excluding the optional README GIF.
- JavaScript target: under 32 KB uncompressed, of which the ambient field may use 18 KB.
- CSS target: under 64 KB uncompressed.
- Largest Contentful Paint target: under 2.5 seconds on a throttled mobile profile.
- Cumulative Layout Shift target: below 0.05.
- No frame over 20 ms at 1440, 1920, or 390 with 4x CPU throttling.

The uncompressed sub-budgets were raised from 12 KB and 30 KB when the field
and the two rebuilt diagram components landed. The number that governs is the
transfer budget: the whole page is 29 KB gzipped, and a canvas simulation was
chosen over a WebGL library precisely to keep it there. Raise these again only
against a measured Lighthouse and frame-timing result, never speculatively.
- All motion uses compositor-friendly properties where practical.
- Report remains one self-contained HTML file plus its JSON sibling.

## Governance

Any public-facing component or asset must use the tokens and causal motion sequence in this document. A new visual element must answer at least one of these questions:

- Where is meaning flowing?
- What contract is checking it?
- Where did it break?
- What is affected downstream?
- What evidence explains the result?
- Where should the developer repair it?

If it answers none of them, remove it.
