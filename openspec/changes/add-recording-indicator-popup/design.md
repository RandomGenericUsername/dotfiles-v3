# Design: add-recording-indicator-popup

Reference UI: `spikes/capture-tool-ui/bar-indicator.html`.

## 1. Cluster restyle

Keep the current DOM order (dot + timer + pause/resume + stop) and the `visible={state ≠ idle}` contract. Visual upgrades:
- `.rec-dot`: 9px record-red circle with a 1.6s pulse ring (GTK CSS `@keyframes` where supported; else static dot). Paused → `var(--warn)` amber, no pulse.
- `.rec-timer`: tabular-nums, bold, min-width so the cluster doesn't jitter as digits change.
- `.rec-btn`: 26px ghost buttons; hover surface; `.stop:hover` tints record-red. Icons from `capture-tool` group (`pause`/`play`/`stop` at 16px) via the same `iconPath(state…)` pattern already in the widget.

## 2. Popup card

New `Astal.Window` (or overlay anchored to the bar end — follow the bar's existing popup/overlay pattern if one exists, e.g. the power-profile popover precedent in `style.css`):
- 216px card, panel translucency + hairline border + radius (same surface recipe as the capture panel).
- Row 1: dot + "Recording" / "Recording paused" (amber frame variant when paused).
- Big timer: 30px bold tabular, same interpolated elapsed value as the cluster (single source: the existing `elapsed` state).
- Actions grid: Pause/Resume + Stop with icons; Stop hover tints record-red (matches mockup `.danger`).
- Open on cluster click; close on `Escape`, outside click, or after Stop (state → idle hides cluster and popup).
- Popup and cluster MUST show the same state and time at every render (shared `state`/`elapsed` signals, no second subscription).

## 3. Non-goals

No new hub topics, no polling, no changes to `bin/capture-tool`. Paused-time freeze behavior (timer halts while paused) already exists via the interpolation guard — keep it.
