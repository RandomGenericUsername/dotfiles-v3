# Capture tool

The Hyprland screenshot/recording tool: an AGS/GTK4 GUI over a thin backend
CLI. AGS owns the desktop UI and state wiring; the backend owns the capture
itself. The recorder backend is selected behind an abstraction, so
`gpu-screen-recorder` and `wf-recorder` are swappable without redesigning the
UI.

## Current structure

```text
capture-tool/
├── app.tsx             # AGS entry point: registers the window
├── ui/CaptureWindow.tsx# the dialog — window, panels, settings
├── lib/icon-registry.ts# palette-aware icon lookup for this instance
├── types.ts            # shared types (frozen by the parity gate)
├── style.css           # the stylesheet (frozen by the parity gate)
├── bin/capture-tool    # the backend CLI
└── tests/              # the Python suites
```

The GUI does not contain the capture logic: it builds a request and hands it to
the backend over the CLI. So `CaptureWindow` shells out to `capture-tool`
directly rather than going through a controller layer — the planned
`CaptureController`/`ScreenshotController`/`RecordingController`/`TargetResolver`
indirection described in §25 of the project plan was **never built**, and the
`screenshot`/`recording` view modules alongside it were unimplemented
scaffolding. All six were deleted rather than relocated: see
`openspec/changes/refactor-capture-tool-hexagonal/` for the proposal, and
`design.md` in that directory for the layer-by-layer design, the gates, and the
decisions. That change restructures the GUI into hexagonal layers
(`domain/` pure, `ports/`, `adapters/`) with **zero behaviour change**; the
structure above is accurate until it lands.

The capture GUI was split out of the shared bar app into this directory
verbatim (see `openspec/changes/extract-capture-gui-tool/`). `style.css` and
`types.ts` are unchanged by both changes — the parity gate enforces it.

## Dependency notes

The provisioning manifest already includes core screenshot utilities (`grim`, `slurp`, `wl-clipboard`).
The recording setup also requires media/audio dependencies and a recorder backend, which are now added to `dotfiles/provisioning/packages.yaml`.

## Gates

Two developer-run gates cover this directory (there is no working CI for
either — `design.md` §7.1 in the hexagonal change explains why):

- `make capture-typecheck` — `tsc --noEmit`, zero errors in our files. Needed
  because `ags bundle` transpiles without type checking, so a wrong signature
  otherwise reaches production silently. Requires the desktop stack.
- `make capture-hexagonal-gate` — layer purity, the single request→argv
  translator, absence of the dead scaffolding, per-file provisioning
  registration, and the class vocabulary of the classic layout. Red until the
  refactor lands.

## Recording host (Phase 5)

`start` no longer owns the recorder itself. It resolves the target/backend and
spawns `dotfiles-runtime capture`, which owns the recorder child, registers a
`capture` lifetime job with the running daemon, publishes `capture.state`
through the hub, and serves `org.dotfiles.Job1.Control`. Pause/resume/stop are
driven by the bar through the hub's `Control` (never by shelling this script),
so the legacy `stop`/`pause`/`resume`/`status` subcommands and the
`$XDG_STATE_HOME/capture-tool/state.json` file have been retired. `screenshot`
is unchanged.

