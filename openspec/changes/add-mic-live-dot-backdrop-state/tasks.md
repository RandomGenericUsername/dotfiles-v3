## 1. Backdrop appearance contract and derivation

- [ ] 1.1 Verify AGS GDK connector names match runtime monitor keys.
- [ ] 1.2 Add a pure luminance-to-appearance classifier and reuse the runtime
  top-strip sampler. Keep unknown/failure distinct from dark.
- [ ] 1.3 Extend `MonitorWallpaperConfig` and the strict `current.json`
  schema with an optional nullable per-monitor appearance field; update
  load/save validation and serialization while keeping existing
  schema-version-2 files valid.
- [ ] 1.4 Populate the appearance on full wallpaper apply/reconcile and seed;
  clear it in the visible-first intermediate state; preserve it through
  unrelated state updates and define regeneration behavior.
- [ ] 1.5 Update shared-data contract documentation and state contract tests.

## 2. AGS consumption and styling

- [ ] 2.1 Add a pure AGS reader for the active-state value and a GLib file
  reader using the existing XDG state root.
- [ ] 2.2 Select the mic live-dot ring from explicit appearance (`light` on,
  `dark` off, unknown defaults on), not from icon contrast decisions.
- [ ] 2.3 Scope the ring CSS to the bar mic dot and preserve popup styling.
- [ ] 2.4 Add focused pure-reader tests for light, dark, legacy/missing,
  malformed, and invalid appearance values.

## 3. Verification

- [ ] 3.1 Validate current-state schema compatibility for old files and
  round-trip behavior for each new appearance value.
- [ ] 3.2 Validate apply, visible-first intermediate, recovery/reconcile, and
  icons-regenerate flows keep appearance synchronized with the active
  wallpaper.
- [ ] 3.3 Verify bar behavior on light and dark backdrops and confirm the
  audio popup dot retains its intended styling.
