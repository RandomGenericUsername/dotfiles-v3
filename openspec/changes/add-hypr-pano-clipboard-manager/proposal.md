## Why

Hyprland has no clipboard history manager. The existing local prototype at `src/gui-tools/hypr_pano/` replicates gnome-shell-pano but is an untracked Python/GTK experimental MVP whose clipboard watcher is broken (`wl-paste --watch` fails, per its `HANDOFF.md`), whose UI stack (PyGObject + gtk4-layer-shell) diverges from every other GUI tool in this repo (AGS v3/TSX), and which runs its monitor inside the GUI process.

Phase 5 has now shipped the missing infrastructure: a session hub (`org.dotfiles.Events`), leased jobs with a `Control` channel (`org.dotfiles.Job1`), and a push-only domain-event contract. A clipboard manager is the same shape as the already-migrated capture host — a resident watcher that pushes state and accepts pause/resume — so it should be built on that spine rather than as a second, hand-rolled daemon.

## What Changes

- **New runtime job** `dotfiles-runtime clipboard`: resident foreground host mirroring `application/capture_host.py` — registers a `clipboard` lifetime job with the hub, renews its lease, emits clipboard domain events, and serves `org.dotfiles.Job1.Control` for incognito (`pause`/`resume`/`stop`).
- **Event-driven clipboard detection**: a `wl-paste --watch` source driven by the compositor's `wlr-data-control` protocol (no idle CPU). The monitor blocks on the watch pipe and wakes only on a real change. A hash-compare polling loop exists **only** as a declared degraded mode when the data-control protocol is unavailable; the healthy path never polls.
- **New event topics** added additively to the event contract (`org.dotfiles.Events1`): `clipboard.update` (payload `{type, hash, path, preview}`) on each captured item — images referenced by path/hash, never sent as binary — and `clipboard.state` (`{state, job_id}`) on every start/pause/resume/stop so the UI reflects real incognito state and routes `Control`.
- **JSON history store** under `$XDG_STATE_HOME/hypr-pano/`: content-hash dedupe (re-copy bumps recency), favorites flag, images cached under `~/.cache/hypr-pano/`, atomic writes, per-type trimming. No SQLite.
- **Smart type detection**: text, image, link (`text/uri-list`), code snippet, hex color, emoji — each rendered with a distinct card icon.
- **New AGS GUI** `src/gui-tools/hypr-pano/` (standalone instance, capture-tool pattern): Pano-style bottom layer-shell overlay, search, per-type previews, favorites, and full keyboard navigation (arrows, Enter, `Ctrl+1..9`, Delete) plus click-to-copy via `wl-copy`.
- **Incognito**: hub `Control` from the window toggle (and available to a bar indicator later).
- **Config file** `~/.config/hypr-pano/config.json` is the only settings surface (per-type retention limits, favorites handling); there is no settings GUI in v1.
- **Wiring**: Hyprland keybind (`SUPER+V`) to toggle the window; provisioning deploys the AGS app and autostarts the runtime clipboard job (systemd user unit).
- **Replaces the `cliphist` stopgap**: the dormant `wl-paste … cliphist store` autostart lines are removed, `cliphist` is dropped from the package manifest, and the new resident watcher becomes the single clipboard-history mechanism.
- **Fresh start**: no migration of the prototype's SQLite history; the untracked Python prototype is retained only as an uncommitted reference copy in the working tree (`src/gui-tools/hypr_pano/`) to guide the port, and is not carried onto this branch.

## Capabilities

### New Capabilities

- `clipboard-manager`: the runtime clipboard watcher job (detection source, history store, config contract, hub event/control behavior) and its AGS overlay UI (layout, keyboard/mouse interaction, incognito, type-aware presentation).

### Modified Capabilities

*(None — the event-contract files are governed outside the OpenSpec capability inventory; the additive `clipboard.update` topic and the new GUI-tool instance are captured as requirements of `clipboard-manager` and in Impact.)*

## Impact

- **Contracts**: `contracts/event-contract.{md,json,xml}` gain the `clipboard.update` topic and payload schema (additive; no version bump); conformance checks updated.
- **Runtime (`src/runtime`)**: new ports (`IClipboardSource`, history-store port), adapters (`wl_paste_source`, `json_history_store`, config reader), `application/clipboard_host.py`, CLI command `clipboard` with hub-present and degraded (no-hub) arms, plus unit/architecture tests mirroring capture.
- **GUI**: new `src/gui-tools/hypr-pano/` (AGS app entry, `ui/PanoWindow.tsx`, cards/previews, stylesheet); the untracked prototype `src/gui-tools/hypr_pano/` is discarded.
- **Provisioning**: `gui_tools` role deploys the AGS app to `<install>/config/ags-hypr-pano/`; `config-links` symlinks `~/.config/ags-hypr-pano`; a new `runtime_clipboard` role installs and enables the `dotfiles-runtime-clipboard.service` user unit (ordered after the hub, restart-on-template-change); `cli_tools` installs the `hypr-pano-ui` launcher; Hyprland keybind + autostart updated (the `cliphist` autostart lines removed, `cliphist` dropped from `packages.yaml`); `verify` role updated.
- **Dependencies**: `wl-clipboard` is already provisioned; requires AGS v3 and the Phase 5 hub daemon (degraded mode when the hub is absent, loud but non-fatal).
- **Out of scope for v1**: history migration, settings GUI, bar incognito indicator, storing binary/file-list payloads beyond `text/uri-list` links, cross-device sync.
