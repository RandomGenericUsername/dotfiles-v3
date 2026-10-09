# Spine Pair Review — AGS Audio Panel Redesign

## Overall verdict

The approved interaction model is clearly captured and the OpenSpec is strongly aligned on preferred-output routing, distinct device/app gain, per-app metadata and controls, and the removal of aggregate transport. The spine pair is not yet a reliable complete handoff: it lacks named key-flow coverage and component patterns, leaves important states and visual tokens underspecified, and the Experience spine omits source traceability. No critical findings; address the high findings before implementation uses these documents as the sole UX contract.

## 1. Flow coverage — thin

Checked the approved mock and requirements described in the UX and OpenSpec. The Experience interaction subsections have numbered actions, but they are not Key Flows with a named protagonist, explicit climax, or applicable failure paths. Input/microphone activity and device-unavailable recovery are not developed as user journeys. The old memlog records earlier flow decisions, but those are superseded by the approved concept.

### Findings
- **high** The Experience spine has no named Key Flows for the locked preferred-output, per-app routing, media control, or input journeys; numbered interaction steps alone do not identify protagonist/climax/failure paths (EXPERIENCE.md:27-54). *Fix:* Add short named flows with Juan David, the intended outcome beat, and relevant failure branches.

## 2. Token completeness — adequate

DESIGN.md defines no frontmatter visual tokens and uses no `{path.to.token}` references, so there are no unresolved token references or malformed token values. It delegates final colors to the generated wallpaper palette and GUI-unification spec (DESIGN.md:57-59). It does not state contrast targets for key text/control combinations, nor concrete typography, spacing, or focus tokens.

### Findings
- **medium** Contrast-safe is an instruction without a target or identified load-bearing combinations (DESIGN.md:57-59; EXPERIENCE.md:66-72). *Fix:* State the applicable contrast threshold and identify text, icon, and focus combinations, or point to an exact inherited standard.

## 3. Component coverage — broken

The component vocabulary includes the popup, preferred-output selector, output-level slider/mute, app row, artwork/app badge, route selector, transport buttons, seek and app-volume sliders, input controls, microphone-activity rows, and bar indicators. Neither spine has the required component specification/pattern section. OpenSpec tasks and requirements cover the functional behaviors more fully, but do not substitute for the missing visual and behavioral component tables.

### Findings
- **high** No `Components` section exists in DESIGN.md and no `Component Patterns` section exists in EXPERIENCE.md, leaving named controls without shared visual anatomy or behavior rules (DESIGN.md:14-74; EXPERIENCE.md:16-72). *Fix:* Add matching component inventories with states, keyboard/activation behavior, and ownership of device-level versus app-level effects.

## 4. State coverage — thin

The Experience spine covers missing artwork/metadata, no-MPRIS streams, unavailable devices, truncation, focus visibility, and large-list scrolling (EXPERIENCE.md:56-72). It does not define cold-load/initial discovery, empty output/app/input/activity sections, action failure feedback, or microphone-permission-denied states. The OpenSpec adds local action errors and hot-unplug recovery, but these are not expressed as user-facing state patterns (OpenSpec design.md:51-53, 61-68).

### Findings
- **medium** Several applicable states have implementation-level mention or no UX treatment, especially device/action errors, empty lists, and microphone access denial (EXPERIENCE.md:16-25, 56-72; OpenSpec design.md:51-53, 61-68). *Fix:* Add a compact state matrix per surface, including what remains usable and the recovery path.

## 5. Visual reference coverage — thin

`mockups/audio-panel-redesign-concept.html` is linked from both spines and correctly identified as the approved hierarchy/interaction reference (DESIGN.md:7-11, 14-16; EXPERIENCE.md:5, 85). Other HTML references present are `key-bar-indicators.html`, `key-audio-transport.html`, `key-audio-popup.html`, and `key-alternatives.html`; none is linked inline with a description. The memlog calls these earlier artifacts historical/superseded, but the spines do not name each as historical. The SVGs under `mockups/assets/` are supporting artwork rather than independent screen references.

### Findings
- **low** Four older HTML mockups remain unclassified by name in the spines, so a downstream reader can mistake them for active reference material (mockups/key-bar-indicators.html, key-audio-transport.html, key-audio-popup.html, key-alternatives.html; DESIGN.md:16). *Fix:* Add a brief historical-reference note listing them, or move them out of the active mockups set.

## 6. Bloat & overspecification — adequate

The docs are compact, decision-focused, and avoid pixel-level implementation prescriptions. The same core choices are repeated across the mock, the two spines, and OpenSpec, which is useful for acceptance but makes later updates susceptible to drift. Exact dimensions are appropriately described as tunable (DESIGN.md:31). No material bloat found.

### Findings
- **low** The same locked behavior is restated across UX and OpenSpec, increasing maintenance points (EXPERIENCE.md:74-81; OpenSpec specs/ags-audio-panel/spec.md:5-42). *Fix:* Keep UX as the interaction contract and OpenSpec as testable requirements, with links between corresponding sections.

## 7. Inheritance discipline — adequate

All four DESIGN.md source paths resolve in the repository, and its approved mock reference resolves. OpenSpec cites the same approved concept and is consistent with the locked decisions: preferred-follow versus explicit routing, device versus app gain, app-scoped transport, metadata/artwork fallback, whole-popup scope, and event-source separation (OpenSpec proposal.md:5-16, 28-33; design.md:3-11; specs/ags-audio-panel/spec.md:5-212). The Experience frontmatter has no `sources` list, however, and requirement names are not mapped back to the source records; the only explicit pointer is the approved mock. The required glossary/component-name comparison cannot be completed because neither a glossary nor component inventories exist.

### Findings
- **medium** Experience does not declare its source set, so a consumer cannot trace the contract’s inherited decisions or distinguish source evidence from owner-approved requirements (EXPERIENCE.md:1-6, 74-85). *Fix:* Add `sources` and explicit UX requirement/decision names, with the approved mock and relevant technical evidence identified separately.
- **medium** Routing behavior is specified as guaranteed while the tasks still require confirming whether PipeWire exposes enough intent to distinguish follow-preferred from explicit routing (OpenSpec design.md:49-53; tasks.md:5-8). *Fix:* Make that investigation a stated design gate and record the supported behavior/fallback before treating the route model as implementable.

## 8. Shape fit — thin

DESIGN.md has a clear style statement and some layout, colors, and do/don't guidance, but skips most canonical design sections, including Typography, Elevation & Depth, Shapes, and Components. EXPERIENCE.md has information architecture, interaction, state/fallback, and accessibility content, but lacks explicit Foundation, Voice and Tone, Component Patterns, State Patterns, Interaction Primitives, Accessibility Floor, and Key Flows headings. A standalone responsive section is not needed for this single desktop popup; documenting compact/scrolling behavior inline is reasonable.

### Findings
- **high** The spine pair omits several canonical handoff sections without stating inheritance or why those defaults do not apply; notably component behavior and key flows are absent (DESIGN.md:14-74; EXPERIENCE.md:8-85). *Fix:* Restore required sections or explicitly mark inherited/non-applicable sections and link their source of truth.

## Mechanical notes

- DESIGN.md sources resolve: `mockups/audio-panel-redesign-concept.html`, `_bmad-output/planning-artifacts/ags-audio-mpris-transport-dispatch-contract-2026-09-21.md`, `_bmad-output/planning-artifacts/gui-unification-ux-spec.md`, and `docs/linux-wayland-pipewire-ags-audio-control.md`.
- EXPERIENCE.md has no `sources` frontmatter; its approved-reference path resolves.
- The OpenSpec proposal, design, tasks, and capability spec agree with the owner-locked UI/functional decisions. The implementation feasibility of follow-preferred intent remains explicitly a task to investigate.
- No Mermaid diagrams occur in the reviewed spine pair or OpenSpec.
