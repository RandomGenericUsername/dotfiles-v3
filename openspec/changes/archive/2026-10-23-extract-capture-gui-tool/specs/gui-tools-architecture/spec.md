## ADDED Requirements

### Requirement: Self-contained GUI tool layout
The repository SHALL maintain the capture tool under `src/gui-tools/capture-tool/` containing the backend controller (`bin/capture-tool`), the AGS app entry (`app.tsx`), the stylesheet (`style.css`), the dialog (`ui/CaptureWindow.tsx`), and the carried-over scaffolding (`ui/RecordingView.tsx`, `ui/ScreenshotView.tsx`, `types.ts`, `controllers/*`) verbatim.

#### Scenario: Tool directory layout
- **WHEN** inspecting `src/gui-tools/capture-tool/`
- **THEN** `bin/capture-tool` is executable and `app.tsx`, `style.css`, `ui/CaptureWindow.tsx` exist alongside the verbatim scaffolding files

#### Scenario: Legacy source locations are gone
- **WHEN** inspecting the repo tree
- **THEN** `scripts/capture-tool` and `dotfiles/config/ags/capture/` do not exist

### Requirement: Dedicated AGS instance identity
The capture app SHALL declare `instanceName: "capture"` in code, and the desktop keybind SHALL invoke a provisioned start-if-down launcher (`capture-ui`) that addresses the instance explicitly. The launcher toggles a running window, and starts a fresh `ags run -d ~/.config/ags-capture` when no instance is on the bus, so provisioning's quit (which forces a re-bundle) never leaves the keybind a silent no-op.

#### Scenario: Toggle opens the dialog
- **WHEN** pressing `SUPER+PRINT` with the capture instance running
- **THEN** the capture dialog visibility toggles without affecting bar windows

#### Scenario: Keybind restarts a quit instance
- **WHEN** pressing `SUPER+PRINT` after the capture instance has been quit (e.g. by a provisioning run that updated its sources)
- **THEN** the launcher starts a fresh `ags run -d ~/.config/ags-capture` and the dialog opens

#### Scenario: Two instances are listed
- **WHEN** running `ags list` on a provisioned machine
- **THEN** both `ags` (bar) and `capture` instances are reported

### Requirement: Autostart launches both instances
Hyprland autostart SHALL launch the bar app and, staggered after it, the capture app via `ags run -d` against the symlinked config dir with a log file.

#### Scenario: Fresh login brings up both apps
- **WHEN** a Hyprland session starts
- **THEN** the bar is visible and `ags list` shows the `capture` instance without `/run/user/*/ags.js` collision errors

### Requirement: Capture provisioning contract
The `gui_tools` Ansible role SHALL deploy the capture app sources to `<install>/config/ags-capture/`, `config-links` SHALL symlink `~/.config/ags-capture` there, and `cli_tools` SHALL install `bin/capture-tool` (backend, mode `0755`) and the `capture-ui` launcher (keybind entrypoint, mode `0755`).

#### Scenario: Provisioning deploys the standalone app
- **WHEN** bootstrap runs the `gui_tools` role
- **THEN** `<install>/config/ags-capture/app.tsx` exists and `~/.config/ags-capture` resolves to it

#### Scenario: Backend remains on PATH
- **WHEN** running `command -v capture-tool` after provisioning
- **THEN** the backend resolves and `capture-tool status` returns valid JSON

#### Scenario: UI launcher is installed
- **WHEN** running `command -v capture-ui` after provisioning
- **THEN** the launcher resolves and is executable (the keybind's entrypoint)

### Requirement: Bar is capture-window-free but recording-aware
The bar app SHALL NOT register `capture-window`, and its recording controls SHALL continue driving the backend (`status` poll, `pause|resume|stop`) with no dependency on the capture instance.

#### Scenario: Recording timer survives the split
- **WHEN** a recording starts via the capture dialog and the capture instance is later quit
- **THEN** the bar still shows elapsed time and pause/stop keep working

### Requirement: Stylesheet ownership follows the window
The capture app's stylesheet SHALL carry the full `window#capture-window` / `.capture-*` rules, and both apps SHALL apply the shared `colors.css` so `@color_*` tokens resolve in each process.

#### Scenario: Dialog renders themed
- **WHEN** the capture dialog opens on a provisioned machine
- **THEN** it renders with theme colors (no unstyled fallback) matching the pre-split appearance
