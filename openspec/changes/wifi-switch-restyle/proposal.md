# Proposal: restyle the power switch to the mock

## Why

Functionally the toggle is now stable (guarded `WifiSwitch`, explicit
values, `wifiReady` gating — landed and verified flicker-free). Visually it
is still the unstyled native switch rendering in the wrong accent (tan/orange
`@color_13` on the owner's wallpaper instead of the mock's blue). Owner:
"ugly as fuck". This change is pure CSS — zero logic risk by construction.

## What Changes

- `style.css` `.settings-switch` family only: restyle the **native
  `Gtk.Switch`** (no custom widget — AGS has no prebuilt beyond GTK's) to
  the mock: 42×24 track, radius 12, off-track translucent foreground,
  on-track blue family (`@color_13`→ verify against palette; if the token
  reads orange on some wallpapers, pin the mock-approved blue slot and
  document why), white 20px knob with slide transition + shadow,
  complete `:checked`/`slider`/`slider:checked` rules (the current file is
  missing knob-checked styling), `insensitive` state for the `wifiReady`
  gate (dimmed, default cursor).
- Applies everywhere the primitive renders: popup header
  (`state-1-connected`), settings header, speed-test auto-run row
  (`state-2-stc-expanded`).

## Non-goals

- No TSX changes (if a TSX change is needed, this proposal is wrong —
  stop and re-scope).
- No behavior/timing changes to the guard.

## Mock anchors

- `state-1-connected` (ON), `state-3-off` (OFF), `state-2-stc-expanded`
  (small auto-run switch)
