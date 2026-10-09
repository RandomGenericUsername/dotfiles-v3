## Why

The audio panel redesign is merged into master (`61f4ca50`) and works, but it
landed without three things the design of record still assumes.

1. **The spec contradicts the code.** `specs/ags-audio-panel/spec.md` — now on
   master — still requires the device-level output level/mute control. Owner
   decision 2026-10-07 removed it: the preferred-output *selector* stays, but
   each app owns its level. Master therefore specifies a control that does not
   exist.
2. **The mock is out of date.** `mockups/audio-panel-redesign-concept.html`
   still shows that control, and predates the implemented panel in smaller ways.
   `DESIGN.md`/`EXPERIENCE.md` were edited after Sally's focused review and were
   never re-reviewed; the mock is the approved reference, so the divergence
   matters.
3. **The panel's play/pause button does not match the mock.** The mock shows a
   round filled container around it. The owner has supplied new `play.svg` /
   `pause.svg` art and wants it used **here only**, added as new entries through
   the icon pipeline — the existing `media-transport` icons must keep serving
   `previous`/`next`, the bar, and every other surface unchanged.

## What Changes

- Amend the `ags-audio-panel` spec so the device-level output level/mute control
  is removed and app-scoped levels are the only levels the panel sets.
- Update the approved mock to the implemented panel: drop the device-level
  volume line, keep the preferred-output selector and `Follow preferred`.
- Add a new icon group for the panel's play/pause button, with the mock's round
  filled container, used from exactly one call site.
- Reconcile `DESIGN.md` / `EXPERIENCE.md` with the above and record that they
  postdate Sally's review.

## Non-goals

- Re-designing the panel. This brings the spec, the mock and one control in line
  with what is already implemented and accepted.
- Changing `previous`/`next`, the bar indicators, or any other audio surface's
  icons.
- Reopening the prefered-output model itself; the selector stays.

## Impact

- `openspec/changes/redesign-ags-audio-panel/specs/ags-audio-panel/spec.md`
  (and master's promoted copy, if the capability is promoted first)
- `_bmad-output/planning-artifacts/ux-designs/ux-dotfiles-repo-v3-audio-2026-09-18/`
  (`mockups/audio-panel-redesign-concept.html`, `DESIGN.md`, `EXPERIENCE.md`)
- `dotfiles/assets/icon-templates/`, `dotfiles/config/ags/icons.json`,
  `dotfiles/config/ags/audio/AudioPopup.tsx`, `audio-panel.css`
- Provisioning: the new templates and generated icon outputs, plus their
  pinning tests
