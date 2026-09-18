## Why

The contrast guard is now per-wallpaper optional (see
`icon-contrast-opt-out`), but there is no surface to exercise the choice:
today the user must accept whatever the last derivation did. The wallpaper
selector (SUPER+W) is where wallpapers are previewed, hovered, and applied —
so the opt-out belongs there, next to the wallpaper it affects.

## What Changes

- An "Auto high-contrast icons" checkbox in the wallpaper selector,
  reflecting and editing the per-wallpaper preference for the focused
  wallpaper (L2 variant-gallery header for the drilled wallpaper; hover
  affordance on L1 cards surfaces the same control without drilling).
- Behavior contract (decided):
  - Hovered/focused wallpaper IS the live one + toggle flipped ⇒ call
    `dotfiles-runtime icons regenerate` with the matching policy (current
    palette, icons only, AGS reload on converge) — no wallpaper re-set.
  - Applying a wallpaper or variant (L1 quick-Apply, L2 Apply pill) honors
    the checkbox state for that wallpaper (persisted before/at apply so
    `wallpaper set` in `auto` mode resolves identically even if the flag
    is not threaded).
  - While `wallpaper.state` is `applying` (incl. the new `visible`
    intermediate — see `wallpaper-set-visible-first`), Apply controls are
    disabled; the grid, search, drill-down, and the checkbox itself stay
    interactive (checkbox flips during busy only queue the preference,
    never trigger a set/regenerate until `done`/`error`).
- UX mockups (`mock.html`, static, styled from the tool's own `style.css`)
  are part of this change and precede implementation — Sally (UX) owns them.

## Non-goals

- No new runtime mechanics in this change (store, flag, and `icons
  regenerate` all come from `icon-contrast-opt-out`; this change is GUI +
  wiring only).
- No bulk/global toggle (no "apply to all wallpapers" — per-wallpaper only,
  default ON covers the rest).
- No redesign of the selector's grid/drill-down flow beyond the checkbox
  placement and busy-state treatment.
