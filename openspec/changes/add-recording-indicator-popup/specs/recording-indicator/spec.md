## Purpose

The bar recording indicator as a single coherent surface: a restyled inline cluster plus a click-to-popup control card, both driven by the existing `capture.state` subscription.

## ADDED Requirements

### Requirement: Restyled inline cluster

The cluster SHALL show a pulsing record dot, a tabular-nums timer, and ghost icon buttons (pause/resume, stop) with hover states; in `paused` state the dot and frame turn amber. The cluster SHALL render nothing when idle.

#### Scenario: Recording cluster
- **WHEN** `capture.state` reports `recording` with elapsed 37s
- **THEN** the bar shows a pulsing red dot, `00:37`, pause and stop buttons — matching `bar-indicator.html`

#### Scenario: Paused cluster
- **WHEN** `capture.state` reports `paused`
- **THEN** the dot is amber without pulse, the timer is frozen, and the pause button shows the resume (play) icon with a "Resume recording" tooltip

#### Scenario: Idle invisibility (preserved)
- **WHEN** `capture.state` reports `idle` (or the hub restarts before re-hydration)
- **THEN** no icon, label, or placeholder is rendered

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
