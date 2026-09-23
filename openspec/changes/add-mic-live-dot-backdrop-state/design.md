## Context

`DerivationPipeline.ensure_icons` already samples the wallpaper's top strip
and chooses a palette backdrop for icon contrast. `current/icons/meta.json`
only records contrast metadata when overrides are emitted, and icon entries
are content-addressed/reusable across wallpapers. It is therefore the wrong
place for active wallpaper appearance.

AGS creates one `Bar(monitor)` window per GDK monitor. `IconRegistry.resolve`
selects the current rendered SVG by filename; the widget selects `mic-on` or
`mic-off` from microphone mute state. Neither currently selects a light/dark
variant. The AGS icon registry already knows the XDG state directory, while
the runtime owns `current.json` and its strict schema.

## Decisions

### D1. Publish backdrop appearance as active runtime state

Add a nullable, explicit `bar_backdrop` value to each active monitor entry,
not to cache metadata. Its values are `light`, `dark`, or `null` (unknown).
This matches the runtime's per-monitor wallpaper source hashes and AGS's
one-bar-window-per-monitor model. Keep the field additive and optional so
existing schema-version-2 state without it remains readable. Update the
current-state JSON schema, `MonitorWallpaperConfig`, and repository
projection/validation together.

For each monitor, derive appearance from the top-strip luminance of that
monitor's active wallpaper source, using the same sampler. Classify average
WCAG relative luminance `>= 0.5` as `light`, below `0.5` as `dark`. Keep
sampling at the runtime I/O boundary and classification pure.
Do not add image decoding to AGS. A missing wallpaper, unsupported image, or
failed sample produces `null`; consumers use the conservative ring-on
fallback. This mirrors the current source-wallpaper sampling model;
compositing/crop fit is out of scope.

### D2. Keep it independent of the contrast guard

Compute/persist the appearance even when automatic icon contrast is disabled,
when the sampled icon colors already pass, or when icon derivation degrades.
`contrast.decisions` remains solely an explanation of icon retargeting.
Do not add wallpaper-dependent appearance to `current/icons/meta.json`.

### D3. Align state with the visible-first wallpaper lifecycle

The visible-swap phase changes the active wallpaper before full derivation.
Its temporary state must not carry the previous wallpaper's appearance:
write `null` (or an equivalent explicit unknown) until phase-two derivation
publishes the new value. Full apply/reconcile then persist the computed
appearance with the active wallpaper. Seed and legacy-state paths must have a
defined unknown fallback. Any state rewrite that preserves the wallpaper
must preserve its appearance unless it recomputes it.

### D4. Bar consumes durable state

At AGS startup, read and validate `current.json` once through a small pure
reader plus the existing GLib file-I/O boundary. Resolve the bar's GDK monitor
connector to the matching runtime monitor key. `light` adds the ring class;
`dark` omits it; missing connector/state or invalid values preserve current
behavior by showing the ring. Existing AGS reloads after wallpaper
set/reconcile ensure the next bar instance reads committed state. Do not
infer appearance from contrast decisions.

The current icon contrast guard still derives one shared icon set; backdrop
appearance for the ring is per-monitor because AGS renders one bar per monitor
and runtime state already records each monitor's wallpaper source. The
per-monitor sample follows the current source-wallpaper top-strip model.

### D5. Scope ring styling to the bar

Keep the green dot presentation consistent, but give the bar indicator's
conditional ring a distinct style hook. Preserve the audio popup's existing
ring behavior unless explicitly decided otherwise.

## Risks

- The runtime's current-state schema is strict and rejects unknown fields;
  schema, serializer, deserializer, validators, and all `DesktopState`
  construction paths must move together.
- Visible-first writes a temporary wallpaper-only state; stale appearance
  would visibly mis-style the dot after a partial failure.
- AGS connector names must match runtime monitor keys. If they do not, the
  safe fallback is ring-on; verify the mapping during implementation.
- Source-image sampling does not model compositor crop/fit or translucent
  bar styling; the initial signal intentionally follows the runtime's existing
  top-strip approximation.
