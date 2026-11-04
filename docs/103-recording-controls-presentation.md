# 103 — Recording controls: ownership, presentation modes and coupling

Status: delivered 2026-11-04. This is the durable architecture record for the
recording-controls work; the implementation evidence lives in the capture
`SPIKE-003` / `SPIKE-004` tickets.

## Decision

The capture tool owns the recording controls. The top bar does **not** render a
second cluster; it only provides a measured slot and asks the capture instance
to draw the cluster there.

This is option B from `SPIKE-002` / `SPIKE-003`.

## Ownership

| Concern | Owner |
|---|---|
| Top-bar slot measurement, visibility subscription, request client | `ags-bar` |
| Cluster window, monitor resolution, timer, popover, Pause/Resume/Stop | `ags-capture-tool` |
| Recording state authority | `capture.state` hub topic |
| Control actions | capture → `hub.control(jobId, action)` |
| Request contract | `ags-platform/ports/capture-cluster.ts` |
| Shared visual component | `ags-capture-tool/ui/shared/recording-cluster.tsx` |

The shared component is internal to the capture app. It is used by both
capture-owned surfaces and is not imported by the bar.

## Flow

```text
ags-bar
  subscribes to capture.state for visibility
  measures its own slot (monitor-local logical pixels)
  ags request capture-cluster '<json>' -i capture
        |
        v
ags-capture-tool
  validates the request
  controller resolves the monitor and creates a layer-shell window
  renders RecordingCluster at the slot
  owns timer / popover / Pause / Resume / Stop
        |
        v
  hub.control(jobId, action)   (never through the bar)
```

The bar may also forward the global `popup-close` request to capture's
`popover-close`. There is no capture-to-bar controller callback.

## Presentation modes

One setting: `recording_controls`.

| Mode | Top-bar slot | Capture native bar | Compact controls |
|---|---|---|---|
| `top-bar` | active while recording | suppressed | allowed |
| `hover` | hidden | reveal on pointer entry | forced full inline |
| `always` | hidden | always visible | allowed |

Exactly one automatic surface is active per mode. `hover` forces full inline
Pause/Stop because a compact popover would require hover → click → click.

`bar_compact_controls` remains a separate layout preference; it controls
popover vs inline **where the chosen surface allows it**.

## Settings and migration

- New key: `recording_controls` (`top-bar` / `hover` / `always`).
- Legacy key: `bar.recording_hud`.
- Migration: `hidden → top-bar`, `hover → hover`, `always → always`.
- The capture settings store writes the migrated key forward on first load, so
  the bar (which reads the top-level key through the Preferences port) cannot
  default to `top-bar` while capture is still on a legacy value.
- Unknown values degrade to `top-bar`.
- `hidden` is removed from the UI; there is always exactly one control surface.

## Failure and lifecycle

- `capture.state` is authoritative; the bar's observed hint only bootstraps.
- Hide destroys the cluster window. There is no mapped transparent cluster.
- Bar restart resets its local sequence; capture treats `seq === 1` as a new bar
  generation.
- A 15 s bar keepalive update recovers a capture restart without a bar state
  change.
- The cluster is `OVERLAY` / `IGNORE` / `Keymode.NONE`.
- Multi-monitor: one cluster per reporting bar; slot coordinates are
  monitor-local logical pixels. Negative monitor origins remain in the payload’s
  monitor fields, never in the slot x/y.
- In `top-bar` mode the capture S4 HUD is suppressed and a launcher/keybind does
  not re-enable it.

## Why the coupling is accepted

The bar must know the request contract and slot semantics; capture must know the
bar’s monitor-local slot. That is the cost of keeping one state/rendering owner
instead of reintroducing a second timer/control implementation in the bar.

The coupling is bounded by:
- one versioned JSON request and one response string;
- one shared `capture.state` domain topic;
- one existing capture-tool config (read through the Preferences port);
- no new hub topic and no event-contract change.

If the presentation rule proves permanent, moving it to an
`ags-platform/ports/recording-presentation.ts` port is the natural next step;
the first delivery keeps it in capture with a tiny bar projection to avoid an
extra platform release.

## Released artifacts

- `ags-platform v0.5.0` — `capture-cluster` request contract
- `ags-bar v0.3.0` — slot + request client + `recording_controls` gate
- `ags-capture-tool v0.3.1` — shared cluster, unified modes, on-disk migration
- `dotfiles-provision v0.1.33` — platform pin mirror
- `dotfiles-v3` PIN-0140 — tuple + app tags

Live install verified by `dotfiles-provision verify` (exit 0).
