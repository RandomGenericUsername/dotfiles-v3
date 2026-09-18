# Tasks: add-gtk4-event-reload

**Delegation contract.** All work happens in the worktree
`../dotfiles-repo-v3-gtk4-event-reload` on branch `feat/gtk4-event-reload`.
Each `## N` section is dispatched as ONE agent. An agent MUST read
`proposal.md`, `design.md`, and `specs/gtk4-event-reload/spec.md` before
starting, MUST work only in this worktree, MUST tick each `- [ ]` → `- [x]` in
this file as it completes it, and MUST make one conventional commit per
section. Do not start a dependent section before its prerequisites are ticked.
No OpenSpec CLI is installed; this file is the tracker (mirrors the format of
`openspec/changes/add-icon-contrast-guard/tasks.md`).

Dependency order: 1 → 2 → 3 → 4 → 5 → 6. (Sections 1 and 2 are independent
and may run in parallel. Section 4 hosts the subscriber, so it requires
section 3 — do NOT run 4 before 3.)

## 0. Setup — Orchestrator (done)

- [x] 0.1 `git worktree add ../dotfiles-repo-v3-gtk4-event-reload -b feat/gtk4-event-reload` (from `master` @ `773074f`)
- [x] 0.2 Immediate stale-install fix on `master`: `uv tool install --force --no-cache <main-repo>/src/runtime`; verified `from runtime.adapters.gtk4_app_reloader import Gtk4AppReloader` succeeds and installed `main.py` references it (3 refs)
- [x] 0.3 Author change artifacts (`proposal.md`, `design.md`, `tasks.md`, `specs/gtk4-event-reload/spec.md`, `.openspec.yaml`)

## 1. Contract: additive `trigger` on `wallpaper.state` — Agent A

- [x] 1.1 `contracts/event-contract.json` — `topics["wallpaper.state"].payload` gains `"trigger": "s"`; add `"enum": { "trigger": ["set","regenerate","reconcile","reactive"] }`; update `cadence`/`notes` to state `trigger` is optional/additive and which operation maps to which value
- [x] 1.2 `contracts/event-contract.xml` + `contracts/event-contract.md` — mirror the JSON change (keep the three artifacts in lockstep; the drift/conformance tests compare them)
- [x] 1.3 `src/runtime/src/runtime/adapters/emit_validation.py` (_TOPIC_SCHEMAS, ~line 165) — add optional `trigger` `{"type":"string","enum":[...]}`; do NOT add it to `required` (old publishers stay valid)
- [x] 1.4 `src/runtime/src/runtime/cli/main.py::_publish_wallpaper_state` (line 446) — new `trigger: str` parameter, emitted in the payload; update the two existing call sites here: wallpaper set → `"set"`, icons regenerate → `"regenerate"`. The standalone `reconcile` (`"reconcile"`) and daemon reactive converge (`"reactive"`) call sites are added in section 4.2/4.3 — do NOT add them now
- [x] 1.5 GJS pinned literals: `src/gui-tools/wallpaper-selector/lib/event-bus-core.ts` and `src/gui-tools/icon-color-mapping-editor/lib/event-bus-core.ts` — add optional `trigger` to the wallpaper-state payload type (no behavior change)
- [x] 1.6 Tests: runtime embedded-schema tests accept payloads with and without `trigger`, and reject an invalid enum value; both `tests/event-contract-drift.mjs` pass
- [x] 1.7 Commit: `feat(contract): add additive trigger discriminator to wallpaper.state`

## 2. Restart primitive hardening — Agent B

- [x] 2.1 `src/runtime/src/runtime/adapters/gtk4_app_reloader.py::_restart` — after SIGTERM, poll `os.kill(pid, 0)` until `ProcessLookupError` using the existing `_LIVENESS_POLLS`/`_LIVENESS_POLL_INTERVAL` budget; on timeout send SIGKILL and poll again; only then `Popen(argv, start_new_session=True)`
- [x] 2.2 Extract the wait-for-death step into a small testable helper (e.g. `_wait_for_exit(pid) -> bool`); keep `_discover_gtk4_apps`, `TARGET_APPS`, `DEFAULT_SKIP_APPS` unchanged
- [x] 2.3 Module docstring — record the restart-safety contract: allowlist-only, per-target state rationale (`power-options-gtk`: daemon frontend, apply-on-change; `hyprmod`: persists to `hyprland.conf`), SIGTERM = graceful close, SIGKILL only after grace, `skip_apps` opt-out, vacuous success on no targets
- [x] 2.4 Tests `tests/unit/test_gtk4_app_reloader.py` — wait-before-relaunch ordering (fake pid-alive probe), SIGKILL escalation on timeout, still-alive-after-both → `False`, no-targets → `True`; keep existing restart/skip tests green
- [x] 2.5 Commit: `fix(runtime): wait for GTK4 app exit before relaunch (GApplication race)`

## 3. Consumer binding: `gtk4_app_subscriber.py` — Agent C

Prereqs: sections 1 and 2 ticked.

- [x] 3.1 New `src/runtime/src/runtime/adapters/gtk4_app_subscriber.py` — mirror `bar_subscriber.py`: jeepney blocking transport, register match rules before `GetTopicState` hydration, `(epoch, seq)` lexicographic discard, `JobsCleared`/`NameOwnerChanged` re-hydration, payload size/depth validation; contract constants read from `contracts/event-contract.json` at import time (never import `runtime.domain`/`runtime.ports`)
- [x] 3.2 Dispatch logic — on `DomainEvent` topic `wallpaper.state`: only `state == "done"`; skip `trigger == "regenerate"` (log); restart allowlisted apps for `set`/`reconcile`/`reactive` via the hardened primitive; tolerate a missing `trigger` field conservatively (treat as palette-affecting only if `state=="done"`; document the choice)
- [x] 3.3 Reuse `_discover_gtk4_apps` + hardened restart (import from `gtk4_app_reloader`); no duplicated /proc logic
- [x] 3.4 Tests `tests/unit/test_gtk4_app_subscriber.py` (mirror `test_bar_subscriber.py`): hydration baseline, stale `(epoch,seq)` dropped, `JobsCleared` re-hydration without replay, oversized/deep payload dropped, trigger gate table (`regenerate` skipped; `set`/`reconcile`/`reactive` restart), missing-trigger behavior, no-targets no-op
- [x] 3.5 Commit: `feat(runtime): add gtk4_app_subscriber hub consumer binding`

## 4. Daemon hosting + publish coverage — Agent D

Prereqs: sections 1 and 3 ticked (1.4 call-site wiring is completed here).

- [x] 4.1 `src/runtime/src/runtime/cli/main.py::daemon_run` (line ~2074) — start the subscriber read loop in a background thread (own `open_dbus_connection`); ensure clean shutdown on daemon stop; never crash the daemon on subscriber errors (log + continue)
- [x] 4.2 Standalone `reconcile` command — publish `wallpaper.state done/error` with `trigger="reconcile"` around the use case (mirror `_run_wallpaper_set`'s publish discipline: informational only, never fail the command on publish failure)
- [x] 4.3 Daemon reactive converge (`_run_reactive_converge`) — after converge, publish `done` with `trigger="reactive"` (same non-fatal discipline)
- [x] 4.4 Tests: daemon starts/stops the subscriber thread cleanly; a published `set` done causes exactly one restart invocation against fakes; `regenerate` causes none; subscriber failure does not stop the daemon
- [x] 4.5 Commit: `feat(runtime): host gtk4 subscriber in daemon and publish reconcile/reactive triggers`

## 5. Chain rewiring + escape hatch — Agent A

Prereqs: sections 1 and 3 ticked.

- [x] 5.1 `_build_reloaders` (`main.py:380-411`) — remove `Gtk4AppReloader()` and its import; update the docstring's pinned consumer order (Hyprland, AGS, Hyprpaper, terminal, kitty)
- [x] 5.2 Update composition tests: `tests/unit/test_cli_reconcile.py:168-180` and `tests/unit/test_cli_wallpaper_set.py:366-414` — assert `Gtk4AppReloader` is absent and the remaining five are present in order
- [x] 5.3 New CLI command `dotfiles-runtime gtk4 restart` — discover + hardened restart; exit non-zero if any restart fails; works with no hub/daemon; add to the command surface/help and the command registration tests
- [x] 5.4 Grep-clean: no stale `Gtk4AppReloader` references in reload-chain wiring or docs claiming it is in the chain
- [x] 5.5 Commit: `refactor(runtime): move GTK4 reload out of swap chain; add gtk4 restart`

## 6. Docs + full verification — Agent B (or C)

Prereqs: all prior sections ticked.

- [ ] 6.1 Docs — update the reload/consumer prose (`docs/`, and the runtime architecture-in-spine notes) to state: event-driven GTK4 restart, `trigger` semantics, `done` = synchronous chain then subscribers act, degraded mode + escape hatch, allowlist/safety contract
- [ ] 6.2 Full suite green: `uv run --directory src/runtime pytest -q`; `ruff check` + `ruff format --check` + `mypy --strict` clean on touched runtime modules; GJS drift tests green (`wallpaper-selector`, `icme`)
- [ ] 6.3 Manual E2E from the worktree (requires the user): `uv tool install --force --no-cache <worktree>/src/runtime`; restart `dotfiles-runtime-daemon.service`; with `power-options-gtk` + `hyprmod` open — (a) change wallpaper → both close/reopen with new palette; (b) contrast toggle → no restart; (c) stop daemon → `dotfiles-runtime gtk4 restart` works; (d) no apps open → no-op. Record outcomes in this file
- [ ] 6.4 Commit: `docs(runtime): document event-driven GTK4 app reload`

## 7. Archive + merge — Orchestrator (after user sign-off)

- [ ] 7.1 Move `openspec/changes/add-gtk4-event-reload/` to `openspec/changes/archive/2026-09-18-add-gtk4-event-reload/`
- [ ] 7.2 Merge `feat/gtk4-event-reload` → `master`; remove the worktree
