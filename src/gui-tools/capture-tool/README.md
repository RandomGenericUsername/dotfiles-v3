# Capture tool

The Hyprland screenshot/recording tool: an AGS/GTK4 GUI over a thin backend
CLI. AGS owns the desktop UI and state wiring; the backend owns the capture
itself. The recorder backend is selected behind an abstraction, so
`gpu-screen-recorder` and `wf-recorder` are swappable without redesigning the
UI.

## Current structure

```text
capture-tool/
├── app.tsx             # AGS entry point: the composition root (builds adapters)
├── domain/             # PURE: no GTK, no GLib, no I/O
│   ├── settings.ts     #   config vocabulary, defaults, merge, validation
│   └── ui-state.ts     #   UI-state shape, first-run defaults, merge, GIF map
├── ports/              # interfaces ONLY: no implementation, no I/O
│   ├── settings-store.ts   #   load()/save() the capture config
│   ├── ui-state-store.ts   #   load()/save() the last-used UI state
│   ├── capture-launcher.ts #   launch(argv)
│   ├── backend-probe.ts    #   backend(): Promise<string>
│   └── capture-ports.ts    #   the aggregate the view is constructed with
├── adapters/           # ALL I/O lives here
│   ├── glib-settings-store.ts   # GLib.file_*/mkdir_with_parents, the Environment
│   ├── glib-ui-state-store.ts   # the same, for capture-ui.json
│   ├── exec-capture-launcher.ts # execAsync + the hide-then-wait-150ms delay
│   └── exec-backend-probe.ts    # execAsync(["capture-tool","backend"]) + parse
├── ui/classic/          # today's layout: the dialog, as it renders
│   ├── ClassicWindow.tsx  #   the shell — window, mode switch, key controller
│   ├── ScreenshotPage.tsx #   the screenshot view
│   ├── RecordingPage.tsx  #   the recording view (GIF-conditional rows)
│   └── SettingsPage.tsx   #   the three settings groups
├── ui/shared/           # the builder kit BOTH layouts import
│   ├── rows.ts          #   settingsLabel/Item/Group, path/toggle/pill rows
│   ├── groups.ts        #   select/applyGroup/clearChildren
│   └── icons.ts         #   captureIcon/withIcon over the icon registry
├── lib/icon-registry.ts# palette-aware icon lookup for this instance
├── types.ts            # shared types (frozen by the parity gate)
├── style.css           # the stylesheet (frozen by the parity gate)
├── bin/capture-tool    # the backend CLI
└── tests/              # the Python suites
```

`domain/` and `ports/` are pure by rule, not by convention:
`scripts/capture-hexagonal-gate.py` check 1 fails on any `ags/*` or `gi://*`
import there, because the point of these layers is that the
merge/validation/defaults logic and the seams are testable without GTK. The
inverse is check 2: only `adapters/` (and the composition root) may reference
`execAsync`, `GLib.file_*` or `GLib.mkdir_with_parents`, so a view that reached
for the filesystem directly would fail the gate.

One consequence worth knowing before editing `glib-ui-state-store.ts`:
`mergeUiState` is pure and dereferences `persisted.screenshot` directly, so it
**throws** on a `null` persisted object. That is deliberate — whole-object null
tolerance belongs to the adapter that owns "the file was missing or
unparseable", and it substitutes `{}` instead of forwarding `null`. The
degradation rules are unchanged: a missing state file is first run and silent; a
corrupt one logs loudly and still yields the settings-derived defaults.

The GUI does not contain the capture logic: it builds a request and hands it to
the backend over the CLI. So `CaptureWindow` spawns `capture-tool` through the
`CaptureLauncher` port rather than going through a controller layer — the planned
`CaptureController`/`ScreenshotController`/`RecordingController`/`TargetResolver`
indirection described in §25 of the project plan was **never built**, and the
`screenshot`/`recording` view modules alongside it were unimplemented
scaffolding. All six were deleted rather than relocated: see
`openspec/changes/refactor-capture-tool-hexagonal/` for the proposal, and
`design.md` in that directory for the layer-by-layer design, the gates, and the
decisions. That change restructures the GUI into hexagonal layers with **zero
behaviour change** and is in progress: `domain/`, `ui/shared/`, `ports/` and
`adapters/` have landed. What remains is the pure request→argv translator
(`domain/cli-args.ts`), the classic-layout split and the final composition-root
cleanup — so the tree above is still transitional.

`ui/shared/` exists for a reason beyond tidiness. The row builders, the
selected-state helpers and the icon resolver are already generic and already
callback-shaped, so they were lifted out *before* a second layout did — that is
what stops a future layout growing its own divergent row builders instead of
importing these. The two `Gtk.Switch` and `Gtk.Image` comments in `rows.ts` and
`icons.ts` are load-bearing: they record two live bugs (`Gtk.Picture` +
`set_size_request` inflating every icon tile to screen scale, and a hand-rolled
track+knob that looked identical in both states because a `GtkBox` ignores a
child's main-axis alignment). They travel with the code, per the spec.

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

