# UX Design Validation — Audio Panel Redesign

**Reviewed artifacts:** `DESIGN.md`, `EXPERIENCE.md`, approved HTML concept, and `openspec/changes/redesign-ags-audio-panel/`  
**Reviewers:** UX rubric and accessibility  
**Review basis:** Original reviewer findings, followed by remediation edits. The revised artifacts have not been independently re-reviewed.

## Synthesis

The original review found no critical issues. It recorded **5 high, 7 medium, and 4 low findings** across the two reviews. The main handoff gaps were named flows, missing design/behavior component patterns, incomplete state and source traceability, accessible routing and slider semantics, and missing input controls in the concept. The UX spines, OpenSpec, and mock have since been updated to address these findings. This is a remediation record, not a fresh verdict: follow-up review is still needed before treating all fixes as verified.

The approved interaction contract remains coherent: preferred output is the default route; app routing can follow it or explicitly override it; device output gain and per-app stream gain are separate; playback/seek are app-scoped; input and microphone activity are represented; and the mock is now the visual reference. The OpenSpec preserves the hexagonal boundary and keeps the system event hub scoped to dotfiles-owned jobs.

## Rubric dimensions

| Dimension | Original verdict | Findings and remediation |
|---|---|---|
| Flow coverage | Thin | **High:** No named journeys with protagonist, outcome, and failure path. `EXPERIENCE.md` now names five flows for preferred output, app routing, app mute/volume, seek, and microphone input, including recovery branches. |
| Token completeness | Adequate | **Medium:** Contrast guidance lacked measurable criteria. `DESIGN.md` now defines contrast targets and load-bearing text, icon, and focus combinations. |
| Component coverage | Broken | **High:** Missing component inventories. `DESIGN.md` now specifies visual components; `EXPERIENCE.md` defines their behaviors, states, and interaction patterns. |
| State coverage | Thin | **Medium:** Cold/empty/error/input-permission states were not adequately covered. `EXPERIENCE.md` now has state patterns and recovery behavior for unavailable devices, action errors, empty discovery, and denied input access. |
| Visual reference coverage | Thin | **Low:** Older HTML mocks were unclassified. Both spines now identify the four historical mocks and designate the new concept as current. |
| Bloat & overspecification | Adequate | **Low:** Core rules duplicated across UX and OpenSpec. The docs now state their roles and cross-link UX intent to testable requirements. Some intentional duplication remains for traceability. |
| Inheritance discipline | Adequate | **Medium:** Experience lacked source provenance; routing feasibility was both assumed and left as an investigation. Sources and requirement-to-flow mapping were added; OpenSpec now makes truthful route-intent representation an explicit design gate with a fallback. |
| Shape fit | Thin | **High:** Canonical handoff sections were absent. `DESIGN.md` and `EXPERIENCE.md` now include the required sections, including Components, Component Patterns, State Patterns, Accessibility Floor, and Key Flows. |

## Accessibility review

| Severity | Original finding | Remediation recorded |
|---|---|---|
| High | App identity was only available through a tooltip. | App names are now visible in each row, alongside media identity. |
| High | Route choice lacked selected-state and keyboard-menu semantics. | The mock and contract now specify selected state, arrow/Home/End navigation, Escape, focus return, and the follow-versus-override distinction. |
| Medium | App rows lacked semantic grouping and stable focus guidance. | Row grouping, visual tab order, capability-aware controls, and focus stability are now in the UX/OpenSpec accessibility requirements. |
| Medium | Slider values lacked meaningful units and seek-time announcements. | The concept exposes percent and elapsed/total values; UX/OpenSpec specify scope-aware accessible names and values. |
| Medium | Input controls were missing from the visual concept. | Input selection, level, and mute controls are now represented in the mock and spec. |
| Low | Constrained work area and text scaling behavior was unclear. | UX now requires reachable controls, visible focus while scrolling, and accessible full labels under constrained sizing. |
| Low | Contrast goals were not measurable. | Contrast targets and required combinations are now stated in the design tokens and accessibility floor. |

## Mechanical notes

- Original reviewer reports are retained as `review-rubric.md` and `review-accessibility.md`.
- Remediation is visible in `DESIGN.md`, `EXPERIENCE.md`, the approved concept, and the OpenSpec proposal/design/spec/tasks.
- These changes are planning artifacts; no implementation code was changed as part of the review gate.
- `openspec` CLI validation was unavailable in this environment. No project test suite was run; the planning validation scripts are documented in the OpenSpec validation directory.
- `uv run` for memlog hit a read-only cache; the repository memlog helper was run directly with Python and recorded the route-unknown and row-lifetime refinements.

## Follow-up

Sally's focused re-review is recorded below. Her review covered the then-current artifacts; it predates the route-unknown and player/stream-lifetime refinements recorded later in this report.

## Sally theme follow-up — 2026-10-02

Sally re-reviewed the revised theme contract. She confirms runtime `colors.css` inheritance is explicit, the mock now visibly says its colors are layout-only, and the action/slider roles match GUI unification and current AGS styles. Earlier flow, component, app-identity, input, and keyboard-accessibility gaps are substantially addressed.

At that review date, the medium finding was unmeasured generated-palette contrast. The token-level contrast calculations have since been run against two cached palettes and meet the targets after the token adjustment recorded below. Sally has not re-reviewed those measurements or the post-review route/player state refinements; rendered GTK/compositor review remains open.

## Architecture feasibility — 2026-10-02

The controlled live test confirmed that an ordinary new app follows the preferred output A → C. It also confirmed WirePlumber moves an explicit target A when A is the current default; reasserting explicit A while C is preferred pins the stream to A through another default change. The test used silent temporary sinks with no active playback streams, restored the original C-Media default, and removed the test graph. This confirms the product flow and the app-owned reassertion strategy; it is not a limitation in the user's routing concept.
## Specification refinement and validation — 2026-10-02

The current consumer map and audio edit review are recorded in `openspec/changes/redesign-ags-audio-panel/validation/current-boundary-review.md`. It confirms the important split: popup/bar read `audio/state.ts`, Settings writes the default speaker through a separate direct AstalWp path, MPRIS owns another session state service, while the event hub is scoped to capture state. The in-progress audio edits add useful observations and possible same-value rendering mitigations, but the 1.5-second stream/name holds and render counters are not a clean target architecture and have not been independently verified against a live GTK reproduction.

The palette token prototype now passes its modeled contrast checks on two cached generated palettes after raising small muted text to 64% foreground opacity and applying the GUI-unification selected-text fallback. This closes the token-calculation gap; it does not close actual GTK/compositor rendering review.

An executable route-intent model passes twelve synthetic transition cases. The revised UX spines and OpenSpec agree that endpoint equality does not establish intent for a pre-existing stream, ordinary new apps follow preferred, explicit overrides stay distinct, and rows survive while either player or stream remains. The core route behavior passed live validation. The remaining adapter work is to audit monitor payloads for default metadata, external target changes, relink, and AGS restart; the rendered GTK palette review also remains open.
