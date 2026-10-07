## ADDED Requirements

### Requirement: A window's own helpers SHALL resolve that window, not a window by name

`hideCaptureWindow()` and `syncWindowSize()` in `ui/classic/ClassicWindow.tsx`
SHALL operate on the `Astal.Window` returned by their own factory. They SHALL NOT
call `app.get_window(...)` or otherwise consult the global window registry.

Rationale, measured on this host with two real `ClassicWindow` instances: every
window is named `capture-window`, and AGS resolves a name with
`windows.find((w) => w.name === name)` (`/usr/share/ags/js/lib/gtk4/app.ts:156-158`)
over `Gtk.Application.get_windows()` — a list that is not registration order and
is re-ordered as windows are mapped and unmapped. The observed resolutions for
the same two windows were `B` on a fresh instance and `A` after A had mapped and
unmapped. A name lookup therefore does not identify *this* window, and both
helpers are per-window actions reached from widgets inside a window.

#### Scenario: A capture hides the window whose button was pressed
- **WHEN** two `ClassicWindow`s exist, both are visible, and the capture button on window **A** is pressed
- **THEN** window A becomes hidden and window B's `visible` is unchanged

#### Scenario: The wrong window is not hidden
- **WHEN** the same sequence runs while `app.windows` holds both windows
- **THEN** no window other than A is hidden — the pre-fix behaviour, reproduced live, was `A=true B=false`

#### Scenario: A view switch resizes the window that switched
- **WHEN** two `ClassicWindow`s exist and the settings view is opened on window **A**
- **THEN** A's default size grows to the settings view's height and B's default size is unchanged

#### Scenario: The registry is not consulted
- **WHEN** `ui/classic/ClassicWindow.tsx` is read
- **THEN** it contains no `app.get_window(` call and no `import ... from "ags/gtk4/app"`

### Requirement: The self-reference SHALL be per-window, not per-module

`ClassicWindow` SHALL declare its own reference to its window inside the factory
body. A module-level binding SHALL NOT be used.

Rationale, measured: `app.tsx` builds one window per monitor. A module-level
`let captureWindow` is overwritten by the second construction, the first window's
helpers then act on the second window, and the defect this change removes returns
verbatim. This was not hypothetical — the first version of this change did it and
was caught by the live harness, producing output identical to the pre-fix control.

#### Scenario: One window does not capture another's identity
- **WHEN** `ClassicWindow` is called twice and both `$` handlers have run
- **THEN** each window's `hideCaptureWindow()` hides only itself

#### Scenario: The declaration is pinned inside the factory
- **WHEN** `ui/classic/ClassicWindow.tsx` is read with comment lines stripped
- **THEN** `let captureWindow` appears after `export function ClassicWindow(`, and exactly once

### Requirement: The window name SHALL stay the single literal `capture-window` across all three consumers

The window's `name`, the `window#capture-window` selector in `style.css`, and
`WINDOW="capture-window"` in
`src/provisioning/ansible/roles/cli_tools/templates/capture-ui.j2` SHALL remain
in agreement.

Rationale: the name is consumed outside this module by a GTK id selector (which
matches `Gtk.Widget:name`, not a CSS class) and by a **provisioned** launcher that
the `SUPER+PRINT` keybind executes (`dotfiles/config/hypr/keybindings.lua:42-46`).
The launcher is the start-if-down script: if `ags toggle` fails it quits the
instance and starts a fresh one, so a name mismatch makes the keybind open nothing
while `ags list` still reports `capture` as running. Neither failure is visible
to a test today.

#### Scenario: The three consumers agree
- **WHEN** the window name, the `style.css` id selector and `capture-ui.j2`'s `WINDOW=` are compared
- **THEN** all three are the string `capture-window`

#### Scenario: A rename that misses the launcher fails the suite
- **WHEN** the window is renamed without changing `capture-ui.j2`
- **THEN** `tests/ts/window-identity.test.ts` fails, naming both strings

#### Scenario: A rename that misses the stylesheet fails the suite
- **WHEN** the window is renamed without changing the `window#capture-window` rule
- **THEN** `tests/ts/window-identity.test.ts` fails

#### Scenario: The launcher still toggles by variable
- **WHEN** `capture-ui.j2` is read
- **THEN** it contains `ags toggle "$WINDOW" -i "$INSTANCE"` and a `WINDOW="…"` declaration

### Requirement: This change SHALL NOT require a provisioning run

No file under `src/provisioning/**` SHALL be modified, and
`~/.local/bin/capture-ui` SHALL continue to work against the deployed build
without re-provisioning.

Rationale: `capture-ui.j2` is a Jinja template installed by the `cli_tools` role,
so any edit to it only reaches the operator's machine on the next provision run.
Choosing an approach that needs none keeps the fix operator-independent.

#### Scenario: No provisioning template changed
- **WHEN** the diff for this change is inspected
- **THEN** no path under `src/provisioning/` appears

#### Scenario: The existing keybind path is untouched
- **WHEN** `dotfiles/config/hypr/keybindings.lua` is read
- **THEN** the capture binding still executes `capture-ui` and does not name a window

### Requirement: Monitor hotplug and focused-monitor launch SHALL remain explicitly out of scope

This change SHALL NOT claim to fix either of the following, and neither SHALL be
described as fixed elsewhere without its own evidence:

1. `ags toggle capture-window` reaches exactly one window, so on a multi-monitor
   host the panel opens on the same monitor every time regardless of focus.
2. `app.tsx` reads `app.get_monitors()` once in `main()` and registers no
   monitor-changed handler, so a monitor attached after login gets no window.

#### Scenario: The exclusions are recorded
- **WHEN** this change's `proposal.md` and `design.md` are read
- **THEN** each of the two items is listed under Non-goals with the reason it is
  not addressed here