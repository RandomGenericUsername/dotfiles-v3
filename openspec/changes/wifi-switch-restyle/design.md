# Design: restyle the power switch to the mock

## Rules (from `state-1-connected` / `state-3-off`)

- Track: `min-width 42px, min-height 24px, border-radius 12px`; off =
  `alpha(@color_foreground, 0.2)`; on = the mock blue (start from
  `@color_13`; if it renders off-hue on the owner's wallpaper, use the
  palette's approved blue slot and record the choice here).
- Knob (`slider`): 20px white circle, `translateX(18px)` equivalent via
  GTK checked-slider margin/position rules, `0 1px 4px rgba(0,0,0,0.3)`
  shadow, 0.2s transition.
- Insensitive (pre-`wifiReady`): opacity ~0.45, default cursor — must read
  as "loading", never as "off".
- Tokens only (`colors.css`); the one literal allowed is the knob shadow
  black (already the pattern in this file).

## Verification

- Parity gate → 0. Screenshots vs all three anchors at both wallpaper
  extremes (light/dark): ON=blue, OFF=grey, pre-ready=dimmed.
- Toggle-behavior regression: one click = one NM Set (guard untouched,
  but prove it — the last change touching switches must re-prove it).
