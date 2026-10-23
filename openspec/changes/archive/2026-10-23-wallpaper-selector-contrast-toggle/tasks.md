## 1. Mockups (Sally, UX) — BEFORE code

- [x] 1.1 `mock.html` (static, `ws-*` classes + palette slots from the
  tool's `style.css`): (1) L1 card hover with contrast shortcut glyph,
  (2) L2 crumb header checkbox ON and OFF states, (3) busy state (Apply
  insensitive, checkbox live + "saved — will apply when ready" note),
  (4) status-line copy per transition
- [x] 1.2 User sign-off on mockups (placement D1 + copy); record decision
  in this file before §2 starts
  - **Amendment 2026-09-18 (post-live-review sign-off):** the L1 hover
    swatch is a TOGGLE (indicator AND control, `onSwatchToggled`), not a
    drill-to-L2 shortcut. Approved after host-side iteration; mock + spec
    D1 updated to match. Supersedes the original "drills to L2" decision.

## 2. GUI implementation

- [x] 2.1 `lib/`: `setContrastPref(hash, enabled)` helper (CLI accessor
  only — never writes state files directly); pref lookup wired into
  card/variant render (cheap map read at render time, rescan refresh)
- [x] 2.2 L2 crumb-header checkbox (primary) + L1 hover shortcut (drills to
  L2); live-target flip ⇒ `icons regenerate --contrast on|off`; non-live
  flip ⇒ persist only; apply paths persist-then-set in `auto`
- [x] 2.3 Busy treatment: event-driven busy (`applying`/`visible`) disables
  Apply controls; checkbox stays live with deferred-regenerate semantics +
  status copy; grid/search/drill untouched
- [x] 2.4 `node tests/model.mjs`-style coverage for any model additions +
  existing GUI test suite green; `ags bundle` clean

## 3. Verification

- [ ] 3.1 Manual against backend from `icon-contrast-opt-out`: live toggle
  repaints bar without flicker; set-with-variant honors box; busy
  double-apply impossible; reboot preserves checkbox state
- [ ] 3.2 Cross-link evidence to change A's §3.3 (busy gate proof)
