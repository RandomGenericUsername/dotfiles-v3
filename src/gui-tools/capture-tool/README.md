# capture-tool — Python backend

This directory now holds **only the Python backend** for the Hyprland
screenshot/recording tool: `bin/capture-tool`, the CLI the AGS GUI shells out to,
plus its Python pytest suites under `tests/`.

The AGS/GTK4 **GUI** used to live here too. It moved into the `ags-apps` monorepo
unit (`capture-tool/`) and is deployed WHOLE by the `ags_apps` role as the live
`<install>/config/ags-capture` symlink (mirroring the bar / hypr-pano /
notifications consumption). The `gui_tools` role no longer enumerates the GUI per
file; the `capture` AGS-instance entry and the provisioned `capture-ui` launcher
(`cli_tools`) still start it from `~/.config/ags-capture`, which resolves through
that symlink. See `openspec/changes/` and the `ags-apps` repo for the GUI.

## What stays here

```text
capture-tool/
├── bin/capture-tool        # the backend CLI (installed by the cli_tools role
│                           #   into the user bin dir as `capture-tool`)
└── tests/                  # the Python pytest suites for the backend
    ├── test_capture_tool_cli.py
    ├── test_capture_settings.py
    └── test_notify.py
```

The backend owns the capture itself: it resolves the target, selects the recorder
backend (`gpu-screen-recorder` / `wf-recorder`), reads/writes the app config
(`$XDG_CONFIG_HOME/capture-tool/config.json`), emits `org.freedesktop.Notifications`
outcome cards, and hands the exact recorder argv to `dotfiles-runtime capture`
(the resident runtime host owns the recorder and serves hub Control). See
`bin/capture-tool` for the module docstrings.

## Recording host (Phase 5)

`start` does not own the recorder itself. It resolves the target/backend and
spawns `dotfiles-runtime capture`, which owns the recorder child, registers a
`capture` lifetime job with the running daemon, publishes `capture.state` through
the hub, and serves `org.dotfiles.Job1.Control`. Pause/resume/stop are driven by
the bar through the hub's `Control` (never by shelling this script), so the legacy
`stop`/`pause`/`resume`/`status` subcommands and the
`$XDG_STATE_HOME/capture-tool/state.json` file have been retired. `screenshot` is
unchanged.

## Gates

The GUI's gates (`make capture-typecheck`, `make capture-test`,
`make capture-hexagonal-gate`) were retired with the GUI and now live in the
`ags-apps` repo. `make deploy-coverage` asserts the consumption shape here,
including that this backend **survives** — a whole-directory delete would silently
drop it.
