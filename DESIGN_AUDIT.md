# GraphABI design audit

Date: 2026-08-01
Scope: project README, repository assets, generated compatibility report, public Pages site, and organization profile
Review standard: can a developer recognize GraphABI from one screenshot and understand the semantic-break thesis within ten seconds?

## Executive assessment

The existing project communicates its technical claim accurately, but it does not yet have a recognizable visual identity. It looks like a careful developer tool assembled from familiar dark-theme conventions: navy panels, purple accents, rounded cards, status pills, and a static node diagram. Those choices are competent and readable, but interchangeable. Nothing makes the image unmistakably GraphABI when the wordmark is removed.

The strongest existing design decision is the product contrast itself: structural compatibility passes while semantic compatibility fails. The redesign should not add a second visual metaphor. It should turn that contrast into one coherent system: a visible semantic pulse moving along an edge, stopping at the first incompatible assumption, and exposing a witness and downstream blast radius.

## What is already working

- The README states the schema-pass/semantic-fail problem early and uses real CLI output.
- The demo report asset reflects the actual deterministic demonstration rather than an invented customer scenario.
- The generated report is self-contained, server-rendered, escaped, and usable without a CDN, font service, or build pipeline.
- Statuses are written as text as well as color, so the basic meaning is not color-only.
- The Pages site is lightweight, responsive at a basic level, and has no third-party runtime dependencies.
- The organization profile is concise and correctly represents one project rather than a fictional company.
- Purple is already associated with GraphABI, which provides continuity for a more disciplined identity.

These qualities are constraints to preserve, not reasons to preserve the current presentation.

## Identity and logo

### Current decision

GraphABI is represented by a text heading or a generic three-node graph mark. The social preview uses ordinary connected dots and cards.

### Problem

Connected dots describe every graph tool. The current mark communicates topology, not the product's unique job. It does not remain distinctive at 16 px, and its meaning disappears without surrounding copy. There is no canonical lockup, monochrome mark, favicon, avatar, spacing rule, or small-size behavior.

### Correction

Use one broken edge as the identity. Two connected nodes establish flow; a precise interruption establishes semantic incompatibility. The gap and failure cut—not a graph cluster—must be the memorable silhouette. Create one geometry across favicon, avatar, wordmark, graph scenes, report markers, and motion.

## Visual primitive

### Current decision

The website, README asset, and report all show nodes and edges, but they render them as static diagrams. Decorative gradients and panels carry more visual weight than the graph state.

### Problem

There is no repeated behavior that belongs to GraphABI. A screenshot communicates a dashboard-like result, while motion communicates nothing because there is effectively no motion system. The product's reasoning sequence—flow, check, break, trace, explain, fix—is not visible.

### Correction

Make the Semantic Pulse the only expressive primitive. A violet pulse represents information in flight. It resolves green when a contract passes, stops red at a semantic break, and resolves amber when evidence is unknown. Animation should end at an explanatory witness, not loop as ambient decoration.

## Color

### Current decision

The surfaces use several close but inconsistent navy values. The website, report, and SVG assets each define different pass, fail, warning, border, and accent colors.

### Problem

Color has no stable semantic contract across surfaces. The current green and red are softer in the report than in project assets. Purple alternates between decoration and meaning. Generic blue gradients weaken the graph-engineering focus.

### Correction

Adopt one dark-first palette everywhere: background `#0B0F14`, surface `#121820`, primary `#8B5CF6`, semantic pulse `#A78BFA`, pass `#22C55E`, fail `#EF4444`, unknown `#F59E0B`, and edge `#556070`. Purple means active semantic flow, never arbitrary decoration. Status color must always be paired with a label, symbol, line pattern, or explanatory text.

## Typography

### Current decision

All surfaces use reasonable system fonts, but each invents its own sizes, weights, tracking, and monospace treatment.

### Problem

Hierarchy varies between marketing, documentation, and report contexts. Large headings feel like ordinary landing-page typography rather than technical instrumentation. Dense report content becomes difficult to scan because labels, evidence, identifiers, and explanations are not clearly differentiated.

### Correction

Use a restrained system sans stack for narrative and a system monospace stack for contracts, traces, commands, values, and identifiers. Use fewer sizes, tighter heading tracking, strong numerical alignment, and consistent eyebrow labels. Typography should make evidence legible; it should not compete with the graph.

## Motion

### Current decision

The current Pages site and README visual are static. The report declares reduced-motion handling but has no meaningful reasoning animation to reduce.

### Problem

The central transition—schema remains green while meaning breaks—is only explained in prose. Generic CSS movement would add noise without improving understanding.

### Correction

Create a deterministic narrative timeline: nodes appear, edges connect, a pulse traverses compatible edges, the candidate changes, the schema indicator remains green, the semantic pulse reaches the verifier edge and stops, the graph freezes, the affected downstream path is marked, and the witness appears. Use `easeOutQuint` and 220–500 ms transitions. Never bounce, float, parallax, or animate indefinitely. Reduced-motion mode must present the final state immediately.

## Website information architecture

### Current decision

The current homepage is a short single-page overview with a hero, a result card, a static graph, and an install command.

### Problem

It is accurate but underspecified. It does not progressively demonstrate the hidden bug, the contract, the recorded-trace mechanism, the report, or the architecture. The hero relies on generic gradient atmosphere. There is no executable-feeling focal moment, and the site does not establish a recognizable rhythm after the first screen.

### Correction

Sequence the homepage as one investigation: hero break, the bug normal schema checks miss, replayable graph, six-step method, YAML contract, real terminal result, framework-independent architecture, report witness, roadmap, and GitHub call to action. Every section should reuse graph rails, pulse markers, interrupted edges, and witness structures. Remove decoration that does not advance the investigation.

## Hero

### Current decision

The current hero leads with a conventional headline and supporting copy beside or above a result card.

### Problem

The first screen tells rather than demonstrates. It could belong to many validation or observability tools. The eye is not guided through cause, break, and consequence.

### Correction

Make the animated edge the hero. Keep the copy direct: “Your schema passed. Your agent still broke.” The graph must enact that claim once, then hold on the broken edge and witness. A keyboard-accessible replay control lets the sequence be studied without turning it into a perpetual animation.

## README

### Current decision

The README is comprehensive and honest, with five badges, a static report image, long explanatory sections, an ASCII architecture diagram, and full command references.

### Problem

The first screen is text-heavy and visually resembles a mature Python library rather than a new category. The badge row competes with the thesis. The static report asset is useful but not memorable. The architecture illustration and main demo use unrelated visual treatments. Several paragraphs defer the real proof below the fold.

### Correction

Use a compact logo lockup, one category line, the schema-pass/agent-break headline, a deterministic demo GIF, and the one command above the fold. Keep only real CI, Python, license, and alpha badges in a secondary position. Follow with exact output, a compact schema-versus-semantics comparison, contract YAML, animated-system architecture, report visual, limitations, roadmap, and contribution entry points. Preserve technical depth through links rather than front-loading every detail.

## Organization profile

### Current decision

The profile is concise prose with repository, website, contributing, and security links.

### Problem

It has no visual memory and repeats ordinary project metadata. It does not show the broken-edge concept, so the organization page feels disconnected from the repository and site.

### Correction

Use the same lockup and compact graph asset, one mission sentence, and four actions: repository, website, contributing, and security. Do not add company language, subproject grids, or ecosystem claims.

## Generated report

### Current decision

The report uses dark panels, summary metrics, a static inline SVG graph, tables, witness details, and a small status palette.

### Problem

It visually presents the conclusion before replaying the causal sequence. The graph is secondary to summary cards. Edges lack an active semantic pulse. The first break, witness, and repair location are separated rather than treated as one investigation. Colors and spacing do not match the website. The fixed-width graph can feel cramped on narrow screens.

### Correction

Lead with an incident-like compatibility header, then replay the recorded path. Freeze at the first breaking edge and reveal the witness card. Keep the complete evidence in accessible disclosure elements. Use the same graph geometry, colors, status badges, spacing, and motion rules as the website. Preserve full offline operation and deterministic server rendering.

## Components and layout

### Current decision

Rounded cards are the dominant container on every surface.

### Problem

Cards create visual fragmentation and do not reinforce flow. Repeating the same rounded rectangle for metrics, graphs, code, and prose erases information hierarchy. Shadows and gradients add a generic premium veneer without product meaning.

### Correction

Use graph rails and shared baselines to connect sections. Reserve bordered surfaces for evidence, code, traces, and witnesses. Nodes use compact technical geometry; witness panels use an unmistakable broken-edge header. Prefer one-pixel borders and local status glow only at active or broken edges. Remove decorative blobs and broad gradient haze.

## Accessibility and responsive behavior

### Current decision

The site uses semantic HTML and the report includes SVG titles and descriptions. Reduced motion is acknowledged. The palette is generally high contrast.

### Problem

The experience has not been organized around keyboard replay, live animation status, focus states, or a meaningful reduced-motion outcome. SVG labels and dense tables can overflow on mobile. Status distinction still leans too heavily on hue in some diagrams. There is no documented contrast or touch-target standard.

### Correction

Provide visible focus rings, 44 px interactive targets, accessible names, a replay button, an `aria-live` narrative, and text/symbol redundancy for every status. On narrow screens, stack nodes vertically or enable labelled horizontal scroll rather than shrinking text below legibility. Reduced-motion mode must skip the sequence and reveal the same evidence. Target WCAG AA contrast at minimum.

## Performance and implementation

### Current decision

The site and report are dependency-free at runtime, use inline/local assets, and avoid frontend frameworks.

### Problem

There is no explicit asset budget or motion performance rule. A future redesign could easily introduce heavy video, fonts, or libraries to achieve polish.

### Correction

Keep the website static and the report self-contained. Use SVG, CSS transforms, and minimal progressive JavaScript. Do not ship web fonts, frameworks, analytics, external scripts, or background video. Keep the core page usable without JavaScript. Treat performance, offline report integrity, and no hidden network calls as brand qualities.

## Content and positioning

### Current decision

GraphABI is repeatedly described as “semantic compatibility testing for AI-agent graphs.”

### Problem

“Testing” frames the project as another test runner and “AI evaluation” adjacency can obscure the edge-level ABI concept. Some current phrasing emphasizes tools before the category.

### Correction

Lead with “Semantic Compatibility Infrastructure.” State the concrete consequence next: “Your schema passed. Your agent still broke. GraphABI tells you exactly where.” Use “test” only for specific commands or validation mechanics. Never claim arbitrary semantic understanding.

## Asset system

### Current decision

The repository contains one report SVG and one social preview in SVG and PNG formats.

### Problem

There is no canonical source hierarchy, naming convention, generation path, or relationship between repository, site, report, favicon, social preview, and avatar assets.

### Correction

Create a single `docs/assets/brand/` source family containing the logo lockups, mark, favicon, hero graph, architecture illustration, report preview, social preview, OpenGraph image, organization avatar, and deterministic demo GIF. Mirror only necessary deployment assets into the Pages repository. Document generation and validation so contributors do not hand-edit divergent variants.

## Decision inventory

| Existing decision | Disposition | Reason |
|---|---|---|
| Honest schema-pass/semantic-fail claim | Keep | It is the category-defining contrast. |
| Real deterministic demo output | Keep | It grounds the identity in proof. |
| Self-contained report | Keep | Offline trust and portability are product qualities. |
| Local/system fonts | Keep and standardize | Fast, private, and technically appropriate. |
| Dark-first presentation | Keep and normalize | Fits trace inspection and existing recognition. |
| Purple accent | Keep with strict meaning | It becomes the semantic pulse, not decoration. |
| Generic connected-node mark | Replace | It does not identify the broken-edge product. |
| Static graphs | Replace | They fail to express propagation and stopping. |
| Broad gradient atmosphere | Delete | It does not reinforce semantic flow. |
| Card-dominant layout | Reduce | Evidence needs containers; everything else needs continuity. |
| Divergent status palettes | Replace | Status meaning must be stable across surfaces. |
| Large README badge row | Reduce | The thesis and demonstration must lead. |
| Generic “testing” category language | Replace | The category is semantic compatibility infrastructure. |
| Runtime frontend dependencies | Continue avoiding | They are unnecessary for this visual system. |

## Audit conclusion

The redesign should not make GraphABI look more fashionable. It should make the product mechanism visible and repeatable. The test for every future decision is simple: does it help a developer see meaning flow, see where it breaks, trace the affected path, understand the witness, or locate the fix? If not, it does not belong in the GraphABI visual system.
