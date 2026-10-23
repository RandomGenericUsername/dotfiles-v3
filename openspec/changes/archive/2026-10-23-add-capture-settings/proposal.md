## Why

The capture tool has no settings surface: output directories, filename patterns, default format/output/quality choices, cursor inclusion, and notification behavior are all hardcoded or first-run constants. The approved mockup (`spikes/capture-tool-ui/settings.html`) defines the target — a General / Screenshot / Recording settings page in the shell's visual language — and the project plan (§38) reserves exactly these rows. With the main window, indicator, and notifications landed, settings is the last mockup surface without an implementation.

## What Changes

- **Settings view in the capture window**: a gear button in the panel footer opens a settings view (replacing the mode views) with the mockup's three groups — General (screenshot folder, recording folder, filename pattern, notifications toggle), Screenshot (default format, default output, cursor toggle), Recording (default frame rate, quality, audio, cursor toggle, backend readout). A back affordance + `Escape` returns to the mode view.
- **Config file contract**: `$XDG_CONFIG_HOME/capture-tool/config.json` (GUI reads/writes; backend reads) with first-run defaults in code and `mkdir_with_parents` creation — no provisioning surface, no hub involvement. Precedence: explicit CLI args > config file > hardcoded defaults; initial UI selections: last-used state (Change 1 A5) > settings defaults > hardcoded.
- **Backend support**: output directories + `strftime` filename pattern drive default save paths; `--cursor` flag threads through (screenshot + recording backends; exact recorder flags verified on-machine); the notifications toggle gates `Notify` emission; backend readout reports the detected recorder (`Automatic (gpu-screen-recorder)`) — display-only, never user-selectable (plan: backend stays hidden).

## Capabilities

### New Capabilities

- `capture-settings`: the settings view (layout, navigation, controls), the config-file contract (schema, defaults, precedence), backend consumption (dirs, pattern, cursor, notification gating, backend readout), and tests.

### Modified Capabilities

*(None — existing CLI flags keep working; config only supplies defaults that explicit args override.)*

## Impact

- **GUI** (`src/gui-tools/capture-tool/`): settings view component(s), footer gear entry point, view-switching with `Escape` hierarchy (settings→mode view→hide window), config read/write, stylesheet additions from the mockup recipe.
- **Runtime/backend** (`bin/capture-tool` + runtime capture modules): config-file loading with safe fallbacks, `--cursor` plumb-through, pattern-based default paths, notification gating; unit tests mirroring existing capture tests.
- **Provisioning**: none — no new packages, no new spine dirs, no autostart changes. (Redeploy of changed sources flows through the normal `gui-tools`/`cli_tools` placement.)
- **Out of scope**: settings sync across machines, per-monitor defaults, codec expert settings, notification history/DoND (Change 3 v1 scope stands).
