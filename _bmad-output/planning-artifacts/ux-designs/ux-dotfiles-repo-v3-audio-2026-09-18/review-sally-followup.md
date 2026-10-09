# Sally follow-up UX review — audio panel theme and handoff

**Reviewer:** Sally (BMad UX Designer)  
**Date:** 2026-10-02  
**Scope:** Re-review of runtime theme inheritance, contrast/selection, browser concept, and prior UX/accessibility findings. Planning artifacts only; no implementation validation.

## Verdict

**The design contract is now coherent on runtime inheritance and semantic color roles.** `colors.action` is aligned with GUI-unification at `@color_06`; slider fill remains on the existing AGS `@color_13` token. Selection text now has a conditional contrast rule, and the browser mock visibly identifies its colors as layout-only. The earlier flow, component, app-identity, input-control, and keyboard-operation gaps are substantially addressed.

**One review concern remains:** contrast has not been demonstrated against generated wallpaper palettes. The prose now says what to do if foreground-on-selection fails, but the artifacts provide no measured palette matrix or theme-aware rendering to show that required text, selected-state, and focus contrast passes. The frontmatter `{colors.selection}` token is still written as a fixed foreground pairing; implementation should treat the conditional rule in Colors as authoritative and choose/compute the effective on-selection color accordingly.

## Remaining finding

### Medium — Contrast is specified but not evidenced across runtime palettes

`DESIGN.md` Colors and `EXPERIENCE.md` Accessibility Floor require 4.5:1 small-text contrast and 3:1 control/focus contrast. `DESIGN.md` now says existing `@color_foreground` over `@color_10` is retained only when it meets 4.5:1 across generated palettes, with the GUI-unification on-selection rule or a computed generator token as fallback. The OpenSpec capability explicitly requires the wallpaper-generated `colors.css` palette and covers palette changes. The concept itself now has a visible notice that its fixed sample palette is for layout only.

These are coherent requirements, but no contrast results are recorded for the live palette or representative generated palettes, and the fixed-color concept cannot provide that evidence. The GUI-unification spec explicitly calls for contrast to hold across dark and light-ish palettes. Translucent panel/card surfaces, selected text/fill, and the `@color_10` focus ring remain unverified.

**Recommendation:** Before implementation sign-off, record small-text and non-text/focus contrast for at least two representative generated palettes, including the actual composite panel/card surfaces and `@color_10` selection. Ensure implementation derives the effective selected text color using the specified contrast rule instead of assuming the fixed `{colors.selection}` pairing always passes.

## Resolved since prior follow-up

- The HTML mock now visibly states its fixed colors are layout-only and names the runtime AGS token source.
- OpenSpec explicitly requires wallpaper-generated palette inheritance and defines palette-change behavior.
- `colors.action` now maps to GUI-unification's `@color_06`; slider fill remains `@color_13`, matching existing AGS slider styles.
- The selection foreground rule now incorporates the GUI-unification contrast rule and a computed-token fallback.
- Named user flows, component contracts, app identity, input controls, route keyboard operation, meaningful slider values, and constrained sizing remain covered.

## Artifact locations reviewed

- [DESIGN.md](DESIGN.md): token map and conditional selected-text contrast rule.
- [EXPERIENCE.md](EXPERIENCE.md): accessibility thresholds, component behavior, named flows, and traceability.
- [Approved concept HTML](mockups/audio-panel-redesign-concept.html): visible layout-only theme notice and fixed sample colors.
- [GUI-unification UX spec](../../gui-unification-ux-spec.md): action role and on-selection contrast rule.
- [OpenSpec capability](../../../../openspec/changes/redesign-ags-audio-panel/specs/ags-audio-panel/spec.md): runtime palette requirement and scenarios.
- [AGS runtime palette loading](../../../../dotfiles/config/ags/app.tsx): applies generated `colors.css` at startup.
- [AGS shared styles](../../../../dotfiles/config/ags/style.css): current slider, selection, and primary-action precedents.

## Review boundary

This focused review confirms the written design intent, not actual rendered contrast. Palette measurements or a theme-aware render are still needed to close the remaining finding.
