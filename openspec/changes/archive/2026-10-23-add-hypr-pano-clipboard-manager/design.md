## Context

See `proposal.md` for motivation. The constraints that shape this design:

- Phase 5 already provides the session hub (`org.dotfiles.Events1`), leased jobs with a `Control` channel (`org.dotfiles.Job1`), and a push-only, JSON-only domain-event contract (`contracts/event-contract.md`). The capture tool (`src/gui-tools/capture-tool` + `application/capture_host.py`) is the reference implementation of a resident job with a reactive UI.
- The repository's GUI convention is standalone AGS v3/TSX tools under `src/gui-tools/<tool>/`, each with its own instance, stylesheet, and toggle launcher. The Python prototype at `src/gui-tools/hypr_pano/` is untracked and does not follow it. A read-only reference copy of that prototype is present in the working tree at the same path solely to guide the port (card layout, search, click-to-copy, image handling); it is not committed and no behavior is inherited from it verbatim.
- Wayland offers no general "selection changed" subscription to ordinary clients; global clipboard observation requires the compositor's `wlr-data-control` protocol, which `wl-paste --watch` wraps.
- The event contract forbids opaque binary and unbounded payloads, so image bytes cannot ride the bus.
- `wl-clipboard` is already provisioned. A dormant `cliphist` stopgap (two `wl-paste --watch cliphist store` autostart lines, no UI) exists and is replaced rather than run alongside, so only one watcher owns the clipboard.

## Goals / Non-Goals

**Goals:**
- A clipboard watcher that is event-driven on the healthy path, survives GUI restarts, and is independently testable (no bus, no Wayland, no real time in unit tests).
- A history store and config contract that are simple, local, and loss-tolerant.
- An AGS overlay that is a thin consumer: it hydrates and subscribes, never polls, and never owns clipboard state.
- Incognito that is a single hub-controlled state shared by the daemon and the UI.

**Non-Goals:**
- Migrating or reading the prototype's SQLite history.
- A settings GUI or live config reload.
- Binary/file-list payloads beyond link URIs; secret detection/redaction.
- Cross-machine sync; cloud history.
- A bar incognito indicator (the `Control` contract leaves room for one later).

## Decisions

### D1 — Clipboard watcher is a runtime job, not an AGS module or a bespoke daemon

Chosen: `dotfiles-runtime clipboard`, modeled on `CaptureHost`, registered with the hub. Alternatives: (a) a GJS module inside the AGS shell — rejected because history would stop whenever the shell reloads, and `Control`/events would have to be reimplemented; (b) an independent daemon outside the hub — rejected because it re-solves leasing, hydration, and control that Phase 5 already provides.

Rationale: it inherits crash-safe lease expiry, a typed control channel for incognito, and the `subscribe → hydrate → (epoch, seq)` discipline that the bar and other tools already follow. The watcher also runs before/independently of the UI, so history accumulates from login.

### D2 — Detection via `wl-paste --watch`; polling is a declared degraded mode only

Chosen: block on the `wl-paste --watch` stream so the process sleeps until the compositor signals a selection change. Alternatives: periodic hash polling as the primary mechanism — rejected as wasteful and contrary to the "state is pushed" rule; GTK/clipboard-manager APIs — rejected because they cannot observe global selections on Wayland.

The HANDOFF failure ("data-control protocol" error) is treated as an environment capability problem, not an architecture one: the source probes the protocol path at startup and, if unavailable, enters a declared polling mode (or fails loud if configured strict). The healthy path never polls.

### D3 — Extend the existing event interface additively with `clipboard.update`

Chosen: a new topic `clipboard.update` on `org.dotfiles.Events1`, payload `{type, hash, path, preview}`. Alternatives: a versioned `Clipboard1` interface — rejected because the addition is purely additive (no removals, retypes, or new required fields); binary on the bus — rejected by contract limits and payload discipline.

Images are referenced by path + hash; the UI reads bytes from disk when rendering. Preview text is bounded to respect payload size limits. The contract currently models every payload field as required (its conformance test pins `required` to the payload key set), so `path` and `preview` are always present and carry an empty string when not applicable to the item type.

A companion topic `clipboard.state` (`{state: idle|running|paused, job_id}`) is emitted on every transition, mirroring `capture.state`. It gives the overlay the daemon's real incognito state and the hub-allocated `job_id` to route `Control` through — so the toggle reflects the daemon rather than local optimism, and a pause issued elsewhere is observable.

### D4 — History as a single atomically-rewritten JSON document

Chosen: `$XDG_STATE_HOME/hypr-pano/history.json`, images under `~/.cache/hypr-pano/`. Alternatives: SQLite via the `sqlite3` CLI from GJS/Python — rejected as an extra subprocess and dependency for a small dataset; per-item files — rejected because ordering/dedupe/favorites become a directory walk.

Rationale: history is small (bounded by per-type limits), reads are whole-document, and the daemon is the single writer. Atomic rename means a crash mid-write leaves the prior document intact. Contention is avoided because the GUI only reads.

Exception (favorite/delete): the overlay's favorite and delete actions are user-initiated and rare, and the contract has no history-mutation method (adding one would grow the wire surface). The GUI writes those two mutations with the same atomic temp-file+rename, and the daemon store re-reads the document on every operation (no in-memory cache), so the only exposure is a capture write and a user mutation landing in the same instant; the last writer wins and the loss is bounded to a single history entry. A future change can add a proper mutation channel if this proves bothersome in practice.

### D5 — Per-type retention from a file-only config with tolerant defaults

Chosen: `~/.config/hypr-pano/config.json` defining per-type limits. Alternatives: a GUI settings dialog — deferred by requirement; DBus settings methods — rejected as surface area without a consumer.

Rationale: limits are static policy; a file is greppable, diffable, and provisionable. Parse errors fall back to defaults and are reported, never fatal.

### D6 — Copy-back suppresses re-capture via hash dedupe plus a self-write guard

Chosen: when the UI copies an item, it writes to the clipboard through `wl-copy`, which the watcher will observe. The watcher dedupes by content hash (existing item's recency is bumped rather than a duplicate appended) and briefly suppresses items whose hash matches a just-observed copy-back. Alternatives: a private "suppress next event" flag set through the hub — rejected as cross-process coordination complexity.

### D7 — GUI owns no state; it hydrates and subscribes

Chosen: on open, the overlay reads the history document and subscribes to `clipboard.update`; the paused/running state comes from hub job state (or the emitters of state events). Live updates arrive as signals. Alternatives: polling the history file — rejected by the push-only rule; keeping an in-memory copy that outlives the window — rejected because it diverges from daemon truth on hub restarts. The overlay never captures; the only writes it performs are the two user-initiated history mutations described in D4.

The consumer reuses the bar's proven split rather than hand-rolling a transport: a pure `event-bus-core` module (contract constants, subscribe-before-read hydration, `(epoch, seq)` filtering; no GJS imports, pinned to `contracts/event-contract.*` by a node drift test) plus a thin Gio seam. The Gio seam MUST decode signal and hydration payloads with `recursiveUnpack()`, not `deepUnpack()`: `DomainEvent` carries `a{sv}`, and `deepUnpack()` leaves each value as a `GLib.Variant` so `payload.<field>` comparisons silently fail (fixed for the bar in `06d90a7`). `Control` is issued through the hub's `Control` method with the job id from hydration — never by shelling the tool.

Layer-shell keyboard/focus: the overlay maps with `Keymode.ON_DEMAND` (matching the capture tool and ICME) and calls `present()` on map; `EXCLUSIVE` was rejected because it grabbed the keyboard and made the overlay interfere with the capture tool when both were open. It installs its `Gtk.EventControllerKey` in the **capture** phase so navigation keys are seen before the focused `SearchEntry` consumes arrows/Enter/digits. Focus-out auto-hide is deliberately NOT used: layer surfaces do not report `is-active` reliably under pointer motion, and reacting to it hid the overlay the moment the pointer moved. Dismissal is Escape, hide-after-copy, or the toggle.

### D8 — Incognito is one hub-controlled state

Chosen: the window's incognito toggle issues `Control("pause"/"resume")` through the hub; the daemon owns the state and refuses to capture while paused. Alternatives: a UI-local flag disconnected from the daemon — rejected because it would still capture, defeating the feature; direct signalling to the daemon — rejected because `Control` is the single sanctioned path.

### D9 — Type classification precedence

Chosen precedence: image (any `image/*`) → link (`text/uri-list` or single URL) → color (full-string hex) → emoji (emoji-only) → code (heuristic: multiple code markers) → text (default). Rationale: deterministic and testable; image-first matches the browser dual-representation case.

### D10 — Deployment mirrors the capture tool

Chosen: `gui_tools` role deploys the AGS app to `<install>/config/ags-hypr-pano/`, `config-links` symlinks `~/.config/ags-hypr-pano`, a launcher handles toggle-with-restart, and session autostart starts the runtime job plus the AGS instance. Rationale: identical lifecycle to the capture tool, so operators and the bar need no new mental model.

If the clipboard job runs as a systemd user unit, its template task MUST notify a restart handler guarded exactly like `runtime_daemon` (`6dd697f`): restart only when the unit template actually changed, never in `--check`, and only when a live user manager is present. A bare `state: started` does not re-exec an already-running job, so a template fix would otherwise stay unapplied until the next login.

## Risks / Trade-offs

- [`wl-paste --watch` availability varies by session] → probe at startup; run declared polling fallback; report the mode; never fail silently.
- [Copy-back is re-observed as a new copy] → hash dedupe (recency bump, no duplicate) plus a short self-write suppression window.
- [Image cache grows unbounded] → image retention limit plus orphan cleanup of files no longer referenced by history.
- [History file torn by an interrupted write] → write to a temp file and atomically rename; GUI tolerates a missing/corrupt document by showing the empty state.
- [Malformed config silently changes retention] → tolerant parse with defaults and a reported warning; defaults are conservative.
- [Hub absent at login] → loud degraded mode (no events, no remote pause), local capture continues; recovers when the hub and job re-register.
- [Burst copying trips the hub publish rate limit] → typed `RateLimited` is non-fatal; the store already holds the item, so only the live update may be dropped and the UI recovers on next hydration.
- [Secrets copied to the clipboard land in history] → mitigated by incognito (manual); automated secret filtering is explicitly out of scope for v1.

## Migration Plan

1. Land the runtime job and event topic first; verify capture and events with the hub while no UI exists.
2. Land the AGS tool; verify toggle, search, copy-back, and live updates against the running job.
3. Enable provisioning autostart and the keybind last, after a VM smoke test of login → copy → toggle → paste.
4. Rollback: disable the autostart entries and keybind and stop the job; the history JSON is inert and can be deleted without affecting other tools. The prototype Python directory is untracked and is not part of this branch.

## Open Questions

- Whether a bar incognito indicator is wanted in a later change (the `Control`/state contract already permits it).
- Whether secret/pattern-based filtering deserves its own change once real usage is observed.
