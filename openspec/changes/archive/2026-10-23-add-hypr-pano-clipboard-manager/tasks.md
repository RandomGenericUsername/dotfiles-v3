## 1. Contracts

- [x] 1.1 Add the `clipboard.update` and `clipboard.state` topics and payload schemas to `contracts/event-contract.json` and the equivalent `event-contract.md` description, keeping them additive on `org.dotfiles.Events1`; verify the JSON/XML parse and both topics appear in the contract's known-topics table
- [x] 1.2 Extend the runtime emit-validation and hub known-topics/control allowlist to accept `clipboard.update` and `clipboard.state` and to control a `clipboard` job (pause/resume/stop); verify `test_dbus_conformance.py`, `test_event_contract_drift.py`, and `test_hub_registry.py` pass with a valid and a rejected payload

## 2. Runtime Domain and Ports

- [x] 2.1 Define clipboard domain models (item type enum, item with hash/type/preview/path/timestamp/favorite, classification result) in the runtime domain layer; verify unit tests cover each classification outcome in design D9
- [x] 2.2 Define `IClipboardSource` (blocking change stream + current content + mimetypes + declared mode) and a history-store port (load, append/dedupe, evict, set favorite, delete) in `ports/`; verify architecture test `tests/architecture/test_layering.py` still passes and ports import no adapters
- [x] 2.3 Define the config contract (per-type retention limits + defaults) as a domain/port type; verify unit tests cover defaults, partial config, and invalid config handling

## 3. Runtime Adapters

- [x] 3.1 Implement the `wl-paste` source adapter: `--watch` protocol stream, mimetype listing, image byte capture to `~/.cache/hypr-pano/`, content hashing, and a startup capability probe that selects protocol vs declared polling mode; verify unit tests with a fake subprocess/stream cover protocol mode, polling fallback, empty clipboard, and watch-process crash
- [x] 3.2 Implement the JSON history-store adapter: atomic temp-file rename, hash dedupe that bumps recency, favorites, per-type eviction (non-favorites first), delete, and orphaned image cleanup; verify unit tests cover each operation and the interrupted-write case
- [x] 3.3 Implement the config-file reader for `~/.config/hypr-pano/config.json` with tolerant parsing and defaults; verify unit tests cover present, absent, partial, and malformed config

## 4. Runtime Application and CLI

- [x] 4.1 Implement `application/clipboard_host.py` and `application/clipboard.py` modeled on the capture stack: lease start/renew/end, publish `clipboard.update` on accepted change, in-memory paused state, and `Control` handling for pause/resume/stop (typed error on unknown action); verify unit tests mirroring `test_capture_controller.py` drive it with a fake clock, fake source, fake store, and fake job client
- [x] 4.2 Add the `dotfiles-runtime clipboard` command composing the host with the D-Bus job client and the degraded local arm when the hub is absent; verify `tests/unit/test_cli_clipboard.py` covers command wiring, hub-present and hub-absent client selection, and a clean stop
- [x] 4.3 Verify the daemon-absent path is loud but non-fatal via a `tests/integration/` bus smoke test that degrades-or-registers without raising; live recovery after a hub restart is delegated to the supervisor (systemd unit restart), matching capture

## 5. AGS GUI

- [x] 5.1 Scaffold `src/gui-tools/hypr-pano/` as a standalone AGS app (`app.tsx` with a stable instance name, `style.css`) following `src/gui-tools/capture-tool/`, using the uncommitted prototype at `src/gui-tools/hypr_pano/` (`ui/window.py`, `ui/item_card.py`, `ui/previews.py`, `clipboard_manager.py`) as the behavioral reference for the port; verify `ags bundle` succeeds and `ags run` launches the instance without affecting the bar
- [x] 5.2 Implement history hydration (read the JSON document on open) and the hub consumer (pure `lib/event-bus-core.ts` core + Gio seam) with subscribe-then-hydrate and stale-`(epoch, seq)` discard for `clipboard.update`, decoding with `recursiveUnpack()` so `{type, hash, path, preview}` arrive as plain values (see `06d90a7`); add a node drift test pinning the core's constants to `contracts/event-contract.*`; verify live cards appear on capture while the overlay is open and on reopen after being closed
- [x] 5.3 Implement `ui/PanoWindow.tsx` as a bottom-anchored layer-shell overlay with search and a horizontal card strip, plus the empty state; verify the overlay anchors at the bottom and search filters the list
- [x] 5.4 Implement item cards and per-type previews/icons (text, image thumbnail, link, code, color swatch, emoji); verify each type renders its distinct preview and icon
- [x] 5.5 Implement selection and copy-back: click and keyboard (arrows, Enter, `Ctrl+1..9`, Delete, favorite toggle), `wl-copy` with the correct representation for text vs `image/png`, and the self-copy suppression handshake; verify a copied image round-trips into a paste target and no duplicate history entry is created
- [x] 5.6 Implement window lifecycle: Escape closes, focus-out hides, hide-after-copy, and the incognito toggle issuing hub `Control("pause"/"resume")` with the state reflected in the window; verify pause blocks new history entries and resume restores them

## 6. Provisioning and Wiring

- [x] 6.1 Extend the `gui_tools` Ansible role to deploy the AGS app to `<install>/config/ags-hypr-pano/` and `config-links` to symlink `~/.config/ags-hypr-pano`; verify a provisioning run creates the directory and resolves the symlink
- [x] 6.2 Install the toggle-with-restart launcher (start-if-down `ags run -d`) and add session autostart for the runtime clipboard job and the AGS instance; if the job runs as a systemd user unit, add its template task plus a restart handler guarded like `runtime_daemon` (`6dd697f`: notify on template change, never in `--check`, only with a live user manager); verify `command -v` resolves the launcher and a fresh login has the job running and the instance available
- [x] 6.3 Add the Hyprland keybind to toggle the overlay and verify it opens the window when running and starts a fresh instance when stopped

## 7. Integration and Sign-off

- [x] 7.1 Run the full runtime test suite (`pytest`) and the contract conformance tests; verify all pass with no layering violations
- [ ] 7.2 VM smoke test the end-to-end flow: login → copy text and an image → toggle overlay → search → paste → favorite → delete → incognito pause blocks capture → resume restores it
- [x] 7.3 Confirm the Python prototype at `src/gui-tools/hypr_pano/` stays untracked (uncommitted reference only), is not staged or committed onto the branch, and that no prototype paths remain referenced by provisioning or configs
