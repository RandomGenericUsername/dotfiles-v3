## Why

The capture UI (`dotfiles/config/ags/capture/`) and its Python backend (`scripts/capture-tool`) belong together as one GUI tool, but they live in two different hierarchies: the dialog is embedded in the bar's AGS app (`dotfiles/config/ags/app.tsx`) while its backend sits in the generic `scripts/` bucket. The `refactor/reorganize-scripts-and-gui-tools` attempt proved the failure mode to avoid: it removed `CaptureWindow` from the main app without launching any replacement, so `ags toggle capture-window` addressed a window that no longer existed and `SUPER+PRINT` went dead.

## What Changes

- Create `src/gui-tools/capture-tool/` as the single home for the capture tool: `bin/capture-tool` (backend, verbatim), `ui/CaptureWindow.tsx` (dialog, verbatim), plus the currently-unwired scaffolding (`ui/RecordingView.tsx`, `ui/ScreenshotView.tsx`, `types.ts`, `controllers/*`) kept as-is for a future controller refactor.
- Give it its own AGS app entry (`app.tsx` with `instanceName: "capture"`, standalone `style.css` carrying the moved `window#capture-window` / `.capture-*` rules).
- Remove `CaptureWindow` from the bar app; the bar keeps `RecordingIndicator` (backend-coupled via `capture-tool status`, unaffected by the split).
- Provision the app to a new spine dir `<install>/config/ags-capture/` via a new `gui_tools` Ansible role; symlink `~/.config/ags-capture` via `config-links`; autostart a second `ags run -d` (staggered); keybind becomes `ags toggle capture-window -i capture`.

## Capabilities

### New Capabilities

- `gui-tools-architecture`: layout + lifecycle contract for standalone GUI tools under `src/gui-tools/<tool>/` (in-code instance name, autostart slot, toggle protocol, stylesheet split, provisioning split).

### Modified Capabilities

*(None — the bar's behavior and the backend CLI are unchanged.)*

## Impact

- Highest-risk of the four splits — implements LAST, after the three mechanical moves (all on master). Requires VM smoke test of `SUPER+PRINT`, pause/resume timer, and monitor hotplug.
- Codebase: `src/gui-tools/capture-tool/` created; `dotfiles/config/ags/capture/` removed; `dotfiles/config/ags/app.tsx` + `style.css` slimmed.
- Provisioning: new `gui_tools` role + playbook slot; `compositor_configs` drops 8 capture entries; `config-links` gains the `ags-capture` symlink; `verify` swaps assertions; `cli_tools` untouched (backend path moves with the source tree, `dest` unchanged).
