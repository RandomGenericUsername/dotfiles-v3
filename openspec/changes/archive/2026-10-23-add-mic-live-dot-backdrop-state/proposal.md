## Why

The microphone live dot is a literal green status signal. Its dark separation
ring improves visibility on a light bar backdrop and looks like a black blob
on a dark backdrop. The current unstaged implementation infers backdrop tone
from `current/icons/meta.json:contrast.decisions`, but those decisions mean
that icon colors were retargeted; they do not identify a light or dark
backdrop. The metadata is also attached to a reusable content-addressed icon
entry, so it is not authoritative per active wallpaper.

## What Changes

- The runtime publishes an explicit per-monitor backdrop appearance in
  active runtime state, derived from that monitor's wallpaper top-strip
  sample.
- The AGS bar reads this state and applies the live-dot ring according to the
  backdrop appearance, with a safe fallback when the appearance is unknown.
- The value follows the wallpaper lifecycle and is refreshed by the existing
  wallpaper apply/reconcile path; it is independent of contrast-guard policy
  and retarget decisions.
- The mic indicator's ring styling is scoped so the bar change does not
  accidentally alter the audio popup's live dot.

## Non-Goals

- No separate dark/light microphone SVG variants; microphone mute state
  continues selecting `mic-on`/`mic-off` as today.
- No GTK dark-theme detection. The signal represents the wallpaper behind
  the bar.
- No changes to the contrast guard's WCAG threshold, token selection, or
  cache keys.
