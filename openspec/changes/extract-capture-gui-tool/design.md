## Context

Today one AGS v3 process (instance `ags`, started by `autostart.lua` via bare `ags run` rooted at `~/.config/ags` → spine `<install>/config/ags`) owns both `Bar` and `CaptureWindow` (`dotfiles/config/ags/app.tsx`). The dialog (`capture/CaptureWindow.tsx`, 197 lines, fully inline — shells to `capture-tool start|screenshot`, hides itself for 150ms before firing) shares the process with the bar only through the window registry: the keybind `ags toggle capture-window` and `app.get_window("capture-window")` both resolve inside that single instance.

The bar's recording controls (`bar/widgets/recording.tsx`, embedded via `tray.tsx`) never touch the window: they poll `capture-tool status` JSON every 500ms and invoke `pause|resume|stop`. The backend (`scripts/capture-tool`, 342-line Python, argparse surface `start|screenshot|stop|pause|resume|status`, state in `$XDG_STATE_HOME/capture-tool/state.json`) is therefore the shared truth, and the split is safe at the logic layer. What must be re-established is the *runtime* layer: process ownership, toggle routing, provisioning, and styles.

Verified against the installed AGS 3.1.0: the instance name is set in code (`app.start({ instanceName })`, defaults to `"ags"` — `ags run` takes no instance flag); `ags toggle|request|quit` all accept `-i/--instance`; `ags list` shows live instances. Two concurrent `ags run` invocations collide on `/run/user/$UID/ags.js` (upstream issue #815) unless staggered.

## Goals / Non-Goals

**Goals:**
- Capture dialog runs as its own persistent AGS instance (`capture`), toggleable via `SUPER+PRINT` with cold-start-free latency and preserved tab state.
- Bar behavior identical (recording timer, pause/resume/stop untouched).
- Backend CLI surface unchanged (`start`, `stop`, `pause`, `resume`, `screenshot`, `status`).
- All 8 current capture sources plus the backend move as a unit; the unwired scaffolding (`RecordingView`, `ScreenshotView`, `types.ts`, `controllers/*`) is kept verbatim for a future controller refactor (owner decision — not rewired now).

**Non-Goals:**
- No controller-layer refactor (the README's planned `CaptureController` wiring stays aspirational; `CaptureWindow` keeps shelling out directly).
- No changes to the recorder backends (`gpu-screen-recorder` / `wf-recorder` selection) or screenshot plumbing.
- No `RecordingIndicator` move — it stays in the bar by design.

## Decisions

### Decision 1: Two persistent daemons (A), not on-demand (B)
Keep a resident capture instance alongside the bar. Alternative B (spawn-on-keybind, quit-on-close) was rejected: GJS cold start (~0.5–1s) on every `SUPER+PRINT`, tab/target state resets each open (selection lives in `CaptureWindow` closure vars), and `hide-then-shoot` (150ms hide before region screenshot, plus 3/5/10s delays) would need a fork-before-quit rework. A preserves instant toggle and costs one idle GJS runtime.

### Decision 2: In-code instance name + `-i` toggle routing
Capture `app.tsx` sets `instanceName: "capture"` (v3 has no `run`-time flag for this). Keybind becomes `ags toggle capture-window -i capture`. Alternatives (wrapper script `capture-ui toggle`) rejected: direct CLI keeps the keybind readable and matches `ags list`/`ags quit -i` ergonomics. Restart loop for dev: `ags quit -i capture && ags run -d ~/.config/ags-capture`, independent of the bar.

**Reversal (2026-09-11) — the wrapper is now adopted.** The rejection above assumed the instance is always running (autostart) and that provisioning never quits it. The gui_tools role now quits all three AGS instances after placing updated sources (AGS bundles TS at startup and serves the old bundle otherwise), and the bar/icme have restart paths (runtime-seed's AgsReloader; the icme start-if-down launcher). A bare `ags toggle -i capture` has neither, so a mid-session re-bootstrap left `SUPER+PRINT` dead until the next login. The keybind now calls a provisioned `capture-ui` launcher (`cli_tools` template, mirroring `icon-color-mapping-editor.j2`): toggle if running, quit-and-restart if a zombie, fresh `ags run` if down. The direct-CLI ergonomics argument is superseded by restart-safety under provisioning.

### Decision 3: Separate spine dir `ags-capture/` + XDG symlink
Provisioned layout is `<install>/config/ags-capture/` (own `app.tsx`, `style.css`, `ui/`, `controllers/`, `types.ts`), launched via `ags run -d ~/.config/ags-capture`, with `~/.config/ags-capture` symlinked by `config-links` mirroring the bar. Alternative (nesting under `ags/capture/` with a second entry point) rejected: one directory would host two apps with different lifecycles, and the bar's per-file template entries already treat `ags/capture/` as bar-owned.

### Decision 4: New `gui_tools` role, not `compositor_configs` extension
A dedicated role owns the capture app files (per-file copies in the established pattern), slotted into the bootstrap chain after `compositor_configs`; `config-links` gains the symlink; `verify` swaps the 8 old `ags/capture/*` assertions for the new `ags-capture/*` set. Alternative (extending `compositor_configs`) rejected: that role's contract is "skeletons for the bar/compositor apps" and its structural test pins exact file counts — a second app deserves its own contract and its own test surface.

### Decision 5: Stylesheet split along window ownership
The `window#capture-window` + `.capture-*` block (`dotfiles/config/ags/style.css:18-96`) moves to the capture app's `style.css`. Both mains keep `app.apply_css(.../colors.css)` so `@color_*` tokens resolve in both processes. `CaptureWindow.tsx` imports no shared TS (no `icon-registry` use), so no code-sharing seam is needed.

### Decision 6: Keep the unwired scaffolding verbatim
`RecordingView`, `ScreenshotView`, `types.ts`, and the four controllers move as-is (owner decision). They are imported by nothing — verified via full import-graph audit — but stay for a future controller refactor. Known wart carried over deliberately: `CaptureTarget`/`ScreenshotFormat`/etc. are defined both in `types.ts` and inline in `CaptureWindow.tsx`; reconciling them belongs to that future refactor, not this move.

## Risks / Trade-offs

- **[Risk] Toggle targets a window the new instance doesn't register** → Mitigation: v3 requires windows be toggleable through the instance (same JSX `<window name=>` pattern the bar already uses); verify `ags toggle capture-window -i capture` in the VM before merging.
- **[Risk] Concurrent autostart collides on `/run/user/$UID/ags.js`** → Mitigation: stagger the second `ags run` (sleep) in `autostart.lua`; confirm both instances in `ags list` after reboot.
- **[Risk] Monitor hotplug double-handling** → Mitigation: both mains iterate `get_monitors()` (bar `EXCLUSIVE/TOP`, capture `OVERLAY/CENTER` — no layer conflict); test dock/undock in VM.
- **[Risk] Stale `ags/capture` husks on existing machines** → Mitigation: `gui_tools`/`compositor_configs` remove-or-ignore policy for the old spine paths (same-machine reprovision converges; document in tasks).
- **[Risk] Chain-order breakage (new role)** → Mitigation: slot after `compositor_configs`, before `verify`; dry-run + container apply-verify tests.

## Migration Plan

1. Land source move + bar slimming + keybind + autostart on a feature branch (VM-tested).
2. Provisioning roles (`gui_tools`, `config-links`, `verify`, `compositor_configs`) in the same branch — app and deploy move atomically so no intermediate state has a dangling toggle.
3. Rollback: revert keybind + autostart + bar `app.tsx`; files stay. Single revert commit.

## Open Questions

- None structural. Verification-only items (toggle registration, hotplug, `ags list` with two instances) are tasks, not unknowns.
