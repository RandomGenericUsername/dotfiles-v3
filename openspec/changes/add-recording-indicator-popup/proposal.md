## Why

While recording, the bar shows only a timer with pause/stop buttons (`dotfiles/config/ags/bar/widgets/recording.tsx`). The approved mockup (`spikes/capture-tool-ui/bar-indicator.html`) keeps that inline cluster but adds a click-to-popup card with a large tabular timer and explicit Pause/Resume + Stop rows — the glanceable state the project plan (§13) calls for: "Clicking the indicator should expose recording controls." The inline cluster restyle (pulsing dot, paused-amber) and the popup ship together so the indicator reads as one coherent surface. This change lands after `add-capture-ui-restyle` (it consumes the `capture-tool` icon group).

## What Changes

- **Inline cluster restyle**: pulsing record dot (CSS animation; static red fallback where GTK CSS animation is unavailable), tabular-nums timer, icon buttons with hover states, amber dot/border in `paused` state; cluster renders nothing when idle (already true — preserved as an explicit requirement).
- **Click-to-popup card**: anchored under the cluster, large `MM:SS` timer, Pause/Resume + Stop rows with `capture-tool` icons, amber-accented frame in paused state; opens on cluster click, closes on `Escape`/outside click/stop.
- **State source unchanged**: the existing `capture.state` hub subscription (with local elapsed interpolation and hub-restart reset) drives both cluster and popup; control actions route through the same `Control(job_id, …)` path.

## Capabilities

### New Capabilities

- `recording-indicator`: the bar recording cluster + popup card (visual states, interaction, state sourcing).

### Modified Capabilities

*(None — `recording.tsx` internals are rewritten but its contract — hidden-when-idle, hub-driven, `Control`-routed — is preserved and pinned by the spec.)*

## Impact

- **Bar** (`dotfiles/config/ags/`): `recording.tsx` rework + stylesheet additions in the bar `style.css` (popup surface, dot pulse, paused-amber); icons already available from Change 1.
- **Contracts**: none — no event-contract changes; the existing `capture.state` payload (`state`, `elapsed_seconds`, `job_id`) is sufficient.
- **Provisioning**: none beyond the normal app redeploy (bar sources are already provisioned; the AgsReloader picks up palette-driven styles automatically).
- **Out of scope**: notifications (Change 3), capture window changes (Change 1), recording lifecycle/backend changes.
