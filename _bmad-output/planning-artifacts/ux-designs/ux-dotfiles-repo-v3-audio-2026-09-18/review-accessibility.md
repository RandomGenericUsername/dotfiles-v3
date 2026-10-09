# Audio panel accessibility review

Scope: accessibility-focused review of the approved HTML concept, UX design/contract, and OpenSpec requirements. This is a design review, not an implementation audit. HTML prototype limitations are called out separately from requirements that should be clarified for the AGS/GTK implementation.

## Findings

### A1 — High: App identity is only available through the app badge tooltip

**Locations:** [mockup](mockups/audio-panel-redesign-concept.html:197) and [mockup](mockups/audio-panel-redesign-concept.html:230); [DESIGN.md](DESIGN.md:46); [EXPERIENCE.md](EXPERIENCE.md:51); [spec](../../../../openspec/changes/redesign-ags-audio-panel/specs/ags-audio-panel/spec.md:92)

The visual app badge has a `title`, but no app name is visibly printed in either row; the visible text is track/artist metadata. The spec and UX contract require app identity to remain available with media identity. Tooltip-only identity is unavailable to touch users, can be hard to discover, and may not be exposed consistently by GTK accessibility. Show the app name in the row (or otherwise provide a persistent visible label); keep accessible names for the artwork and controls scoped to that app.

### A2 — High: Route selectors lack a specified accessible selection model and keyboard menu behavior

**Locations:** [mockup](mockups/audio-panel-redesign-concept.html:168), [mockup](mockups/audio-panel-redesign-concept.html:200), [DESIGN.md](DESIGN.md:59), [EXPERIENCE.md](EXPERIENCE.md:68-70), [spec](../../../../openspec/changes/redesign-ags-audio-panel/specs/ags-audio-panel/spec.md:19-25)

The HTML buttons expose `aria-expanded`, but do not identify controlled menus, menu semantics, or the selected option to assistive technology. The contract requires focusability and accessible names but does not say how keyboard users open/select/escape from a route menu, how focus is restored, or how the selected “Follow preferred” versus explicit route is announced. Define a native GTK choice control where possible, or specify equivalent accessible role, expanded/selected state, keyboard navigation, Escape, and focus-return behavior. Ensure the current device and follow/override intent are included in the selector's accessible name/value.

### A3 — Medium: Playback controls can become a long, repetitive focus sequence without row grouping

**Locations:** [mockup](mockups/audio-panel-redesign-concept.html:193-223), [DESIGN.md](DESIGN.md:44-51), [EXPERIENCE.md](EXPERIENCE.md:66-72), [spec](../../../../openspec/changes/redesign-ags-audio-panel/specs/ags-audio-panel/spec.md:116-139)

Rows contain route, previous, play/pause, next, seek, mute, and volume controls. The specification does not define a semantic group/accessible row label or a focus-order strategy when many apps are present. In GTK, expose each row as a labelled group (app plus current media) and keep the tab order aligned with the visual order; avoid adding controls for unavailable capabilities. Confirm focus remains on the same logical app/control when rows update or reorder, as stable geometry alone does not guarantee focus stability.

### A4 — Medium: Slider values need semantic units and seek time announcements

**Locations:** [mockup](mockups/audio-panel-redesign-concept.html:180-187), [mockup](mockups/audio-panel-redesign-concept.html:210-221), [EXPERIENCE.md](EXPERIENCE.md:68-71), [spec](../../../../openspec/changes/redesign-ags-audio-panel/specs/ags-audio-panel/spec.md:40-53)

The mock exposes accessible labels for volume sliders and visible percentages, but a seek slider is labelled with the track title while its range value is a percentage; the visible elapsed/total time is a separate unassociated text node. The contract says numeric values are available but does not define meaningful spoken values for seek or distinguish sink level from stream level for assistive technology. In GTK, give each slider a name containing scope (device/app) and an accessible value formatted as percent or elapsed/total time; associate visible value text where practical and announce mute state independently of level.

### A5 — Medium: Input controls are absent from the approved interaction model

**Locations:** [DESIGN.md](DESIGN.md:53-55), [EXPERIENCE.md](EXPERIENCE.md:18-24), [mockup](mockups/audio-panel-redesign-concept.html:260-275), [spec](../../../../openspec/changes/redesign-ags-audio-panel/specs/ags-audio-panel/spec.md:141-158)

The design and spec say the popup controls preferred input and input level/mute, but the mock shows only a microphone name and a “Devices” link; it has no input selector behavior, input level slider, or mute action. This leaves the input control's keyboard access, names, state, and focus order unreviewable. Add the actual input controls to the concept, or explicitly mark them as omitted from this visual slice and supply their control design before implementation.

### A6 — Low: Narrow-window and zoom behavior is not specified beyond scrolling

**Locations:** [DESIGN.md](DESIGN.md:31), [EXPERIENCE.md](EXPERIENCE.md:63, 72), [mockup](mockups/audio-panel-redesign-concept.html:34-48, 139-145)

The browser mock adapts its surrounding page below 760 px and scrolls its content, but that is not evidence that the anchored GTK popup fits a small monitor, high text scaling, or magnifier use. The UX contract promises truncation and scrolling without specifying a minimum popup width, what may wrap, or ensuring route names and slider values remain discoverable. Define GTK behavior at constrained work-area sizes and large text scale: keep controls reachable without clipping, preserve scroll/focus visibility, and expose truncated labels in an accessible description.

### A7 — Low: Contrast-safe colors are a principle, not a verifiable token requirement

**Locations:** [DESIGN.md](DESIGN.md:57-59), [EXPERIENCE.md](EXPERIENCE.md:66-72), [mockup](mockups/audio-panel-redesign-concept.html:8-22, 49-53, 121-123)

The UX contract correctly rejects color-only mute state, but small dim hints and status text in the mock rely on low-emphasis colors and there are no contrast thresholds or palette-state checks in the contract. Since mock colors are explicitly illustrative, this is not a finding against the approved palette. Require final generated-theme tokens to meet the project's contrast target for small text, inactive/selected routes, focus indicators, and muted/live states; retain text/icon/state shape cues in addition to color.

## Scope notes

- The mock's native HTML range inputs and buttons are keyboard operable, but do not prove GTK focus order, AT names, scale value formatting, or popup focus handling. The UX contract's high-level accessibility requirements are sound; findings A2-A5 identify the missing interaction details.
- The mock contains no motion that needs a reduced-motion accommodation. Reduced-motion behavior is therefore not a current blocker; keep transitions optional/brief and honor GTK/system animation preferences if implementation adds them.
- No color-only mute cue is specified: the concept changes the speaker glyph and the UX contract explicitly requires mute state not rely on color alone. Verify final icon and accessible state reflect live mute and level.
