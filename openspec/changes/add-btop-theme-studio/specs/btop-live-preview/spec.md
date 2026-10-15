# Spec Delta

## Purpose

`btop-live-preview` renders the studio's preview from the real btop binary running on a pseudo-terminal, so the preview is always btop's actual output — layout, braille graphs, and colours — and never a re-implementation that can drift.

## ADDED Requirements

### Requirement: Preview is the real btop binary

The preview SHALL be produced by running the actual `btop` binary on a pty, pointed at the candidate theme, and SHALL NOT be a re-implementation of btop's drawing.

#### Scenario: candidate theme is what btop renders
- **WHEN** a candidate theme is previewed
- **THEN** the rendered frame is btop's own output for that theme, including its layout and graph symbols

### Requirement: Live update via reload and delta capture

The preview SHALL update as the user edits by reloading a warm btop process (`SIGUSR2`) and capturing only the redraw delta, so a change is reflected without restarting btop, and an edit SHALL render in well under one second on the target host.

#### Scenario: edit reflects without restart
- **WHEN** the user changes a theme key
- **THEN** the preview updates from the same running btop process via a reload, without a fresh process start

#### Scenario: preset change restarts
- **WHEN** the selected preset changes
- **THEN** btop is restarted with that preset, since a preset cannot be switched by reload

### Requirement: Faithful screen reconstruction

The captured pty output SHALL be reconstructed with a terminal emulator that handles partial redraws and truecolour, so the reconstructed frame matches what btop drew.

#### Scenario: partial redraws do not smear
- **WHEN** btop repaints only part of the screen
- **THEN** the reconstructed frame contains each cell exactly once, with no duplicated or stale rows

### Requirement: Column-accurate rendering

The rendered frame SHALL be displayed with a monospace font that covers braille and box-drawing glyphs at a single cell width, so columns do not drift.

#### Scenario: braille graphs align
- **WHEN** the frame contains braille graph glyphs
- **THEN** the columns before and after the graphs remain aligned

### Requirement: Preview never mutates installed state

The preview SHALL write the candidate theme only to a throwaway location and SHALL NOT modify the installed theme, the generated theme, or the repo.

#### Scenario: preview is side-effect free
- **WHEN** the preview renders any theme
- **THEN** the installed theme, the runtime `current/` pointer, and the repo are unchanged
