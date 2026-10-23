## Purpose

Backend support for the recording view's richest rows: audio source selection, finite duration with auto-stop, and GIF as a dedicated conversion pipeline rather than a recorder passthrough.

## ADDED Requirements

### Requirement: Audio source selection

`capture-tool start` SHALL accept `--audio {none,system,mic}` (default `none`) and route the choice into the recorder backend's PipeWire device selection. `none` SHALL NOT open any audio device. An unavailable selected device SHALL fail loudly with a typed error the UI can categorize (never silent fallback).

#### Scenario: System audio records
- **WHEN** starting with `--audio system` on a machine with a monitor source
- **THEN** the output file contains a synchronized audio track

#### Scenario: None opens nothing
- **WHEN** starting with `--audio none`
- **THEN** no PipeWire/audio device is opened for the session

#### Scenario: Missing device is loud
- **WHEN** the selected source (e.g. `mic`) has no available device
- **THEN** the command fails with a typed audio-unavailable error before recording starts

### Requirement: Finite duration with auto-stop

`capture-tool start` SHALL accept `--duration <seconds>` (`0` = infinite, default `0`); on reaching a finite duration the controller SHALL stop the recorder, finalize the file, and report completion exactly as if the user had stopped it manually.

#### Scenario: Auto-stop finalizes
- **WHEN** recording with `--duration 10`
- **THEN** after ~10s the recorder stops and a valid, playable file is produced

### Requirement: GIF special pipeline

With `--format gif`, the backend SHALL capture at the selected GIF frame rate (10/15/20/30) and scale (`--size original|75|50`), then convert to GIF (FFmpeg pipeline); it SHALL NEVER open audio hardware in GIF mode regardless of `--audio`. GIF failures (e.g. oversized region) SHALL surface typed errors.

#### Scenario: GIF ignores audio
- **WHEN** recording `--format gif --audio system`
- **THEN** the session opens no audio device and still produces a valid GIF

#### Scenario: GIF size scales
- **WHEN** recording `--format gif --size 50`
- **THEN** the output dimensions are half the capture geometry in each axis
