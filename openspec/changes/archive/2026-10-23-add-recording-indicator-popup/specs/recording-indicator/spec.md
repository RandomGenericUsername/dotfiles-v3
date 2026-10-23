## Purpose

The bar recording indicator as a single coherent surface: a restyled inline cluster plus a click-to-popup control card, both driven by the existing `capture.state` subscription.

## ADDED Requirements

### Requirement: Restyled inline cluster

The cluster SHALL show a pulsing REC dot (the one fixed `#e0605f` affordance — everything else is a `@color_*` token), a tabular-nums timer, and ghost icon buttons (pause/resume, stop) with hover states; in `paused` state the dot and frame use the palette caution slot (`@color_03`) without pulse. The cluster SHALL render nothing when idle.

#### Scenario: Recording cluster
- **WHEN** `capture.state` reports `recording` with elapsed 37s
- **THEN** the bar shows a pulsing red dot, `00:37`, pause and stop buttons — matching `bar-indicator.html`

#### Scenario: Paused cluster
- **WHEN** `capture.state` reports `paused`
- **THEN** the dot is amber without pulse, the timer is frozen, and the pause button shows the resume (play) icon with a "Resume recording" tooltip

#### Scenario: Idle invisibility (preserved)
- **WHEN** `capture.state` reports `idle` (or the hub restarts before re-hydration)
- **THEN** no icon, label, or placeholder is rendered

### Requirement: Two bar feedback modes

The bar SHALL support two recording feedback modes, selected by the capture
tool's `bar_compact_controls` setting (read from the capture config, watched so
a change applies without restarting the bar):

- **compact** (`true`): the bar shows only the pulsing dot + elapsed time; the
  popup carries pause/resume/stop and SHALL NOT repeat the elapsed time, which
  the bar already shows.
- **full** (`false`, default): the bar carries the pause/resume/stop buttons
  itself and clicking it SHALL open no popup, because the controls are already
  visible.

#### Scenario: Compact mode hides the inline buttons
- **WHEN** `bar_compact_controls` is true and a recording is running
- **THEN** the bar shows the dot and timer only, and clicking them opens the popup with Pause/Resume and Stop

#### Scenario: Full mode duplicates nothing
- **WHEN** `bar_compact_controls` is false and a recording is running
- **THEN** the bar shows the dot, timer and the pause/resume/stop buttons, and clicking the indicator opens no popup

#### Scenario: Switching mode is live
- **WHEN** the setting is toggled in the capture settings view while a recording is running
- **THEN** the bar re-renders in the new mode without a restart, and an open popup closes when leaving compact mode

### Requirement: Click-to-popup card

Clicking the cluster SHALL open a card with a large timer and Pause/Resume + Stop rows; the card SHALL mirror the cluster's state and time exactly, close on `Escape`/outside-click/Stop, and use the amber frame in paused state.

#### Scenario: Popup mirrors cluster
- **WHEN** the popup is open during a recording at 00:37
- **THEN** it shows the red dot, "Recording", `00:37`, and Pause + Stop rows — matching `bar-indicator.html`

#### Scenario: Popup actions route like the cluster
- **WHEN** the user clicks Pause in the popup
- **THEN** the same `Control(job_id, "pause")` fires as the cluster button and both surfaces transition to paused

### Requirement: Single state source

Cluster and popup SHALL share one `capture.state` subscription and one interpolated elapsed value; no second subscription or timer loop SHALL be introduced.

#### Scenario: No drift
- **WHEN** the popup is open across a pause/resume transition
- **THEN** both surfaces update within the same render cycle with identical values
