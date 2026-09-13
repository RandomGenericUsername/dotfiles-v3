# P5‑3: Watch & Reactive Reconcile

Status: done (one landed slice)

Baseline commit: `2681e97` (dirty tree carried the P5‑1‑2b‑ii hub/emit work; NOT
reverted, built on top; nothing committed by this story).

Epic: Phase 5 epic 5‑3 — Watch & reactive reconcile (see
`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase5.md`; spine
`ARCHITECTURE-SPINE.md` status `final`, AD‑33/AD‑35/AD‑36/AD‑39/AD‑40/AD‑41/AD‑42/AD‑43).

## Story

As the daemon operator, I want the supervised daemon to watch **only** the
enumerated AD‑39 spine roots via inotify, coalesce bursts into one trigger,
recover from overflow/registration loss without polling, and run the existing
synchronous use cases on a changed input set — writing exactly one
`trigger="reactive"` audit line and persisting a last-converged input-hash
backstop — so continuous reconciliation is real, looping-safe, and
observe-only by default.

## Context / scope

The transport is separated from the decision logic so the whole feature is
testable without live inotify:

- **Transport** — `adapters/inotify_watch_source.py` (ctypes over libc, the
  only inotify module) + `ports/watch_source.py` (`IWatchSource`).
- **Decision** — `application/watch.py` (`WatchAccumulator` +
  `WatchCoordinator`: coalesce, overflow, registration-loss rebuild) and
  `application/converge.py` (`ReactiveConvergeUseCase`: backstop + composite
  + single audit line).
- **Watched set** — `adapters/watch_roots.py` (explicit AD‑39 allowlist;
  never `derive.find_*`).
- **Backstop / hash** — `adapters/converge_backstop.py` (under `state_root`) +
  `adapters/converge_inputs.py` (bounded to the watch depth).
- **Wiring** — `cli/main.py` (`_run_reactive_converge`, `_build_watch_source`,
  `_run_daemon_run`, `daemon run --activate`).
- **Relocation** — `adapters/desired_state_reader.py` now takes an explicit
  intent path; `resolve_desired_path(config_home)` yields
  `$XDG_CONFIG_HOME/dotfiles/desired.json`; the CLI resolves it and every
  call site (plan/reconcile/converge/reactive) was updated.

Inner history suppression is a `CacheSeeder(suppress_history=True)` flag set by
the composition root when it builds the composite's use cases; the composite
owns the single reactive line.

## Acceptance Criteria (all met)

1. **Inotify over the AD‑39 roots only** — `enumerate_watch_roots` is the
   explicit spine allowlist (CSG templates depth 2, `weg/effects.yaml` file,
   `icon-templates` depth 4, `icon-mappings` depth 2, relocated
   `desired.json`); consumer-pointer destinations and all of `state_root` are
   excluded. The adapter handles `IN_CREATE`/`IN_MODIFY`/`IN_DELETE`/
   `IN_MOVED_FROM`/`IN_MOVED_TO`/`IN_Q_OVERFLOW`/`IN_IGNORED`/`IN_MOVE_SELF`/
   `IN_DELETE_SELF`, extends watches to newly created in-depth directories,
   watches a file root via its immediate parent filtered to the exact
   filename, and surfaces an unwatchable root. ✅
2. **Coalesce + overflow + recovery** — `WatchCoordinator` fires exactly one
   trigger per burst (quiet window = `read_event` returning `None`); overflow
   forces `full_rescan` without rebuilding (watches survive); registration
   loss calls `source.rebuild()` and forces `full_rescan`. **No polling**: the
   source blocks on the inotify fd (+ stop pipe) and never stats/rescans on a
   timer. ✅
3. **Reactive composite + exactly one line** — active converge runs
   `CheckInputs → RegenerateStale → Reconcile → declarative`, then — only when
   the reactive prune is **opted in** (see "Reactive prune policy (Gate‑2 N1
   resolution)") — a real AD‑30‑bounded prune pass, then appends exactly one
   `trigger="reactive"` line and persists the backstop. Inner writes are
   suppressed. Daemon prune (`_run_prune`) appends exactly one
   `trigger="prune"` line with counts when opted in. **Default (opt‑in off):
   no deletion, no `prune` line**; the AD‑30 would‑be removal count is computed
   read‑only and logged at INFO. Observe-only appends no history. ✅
4. **Converge-on-start backstop** — `LastConvergedBackstop` persists under
   `state_root` (never a watched root); inputs are the four derivation inputs
   **plus** the intent document, hashed over exactly the watched set and
   bounded to the watch depth. Unchanged ⇒ no-op; absent/corrupt/symlinked ⇒
   treated as changed. Unseeded ⇒ benign no-op (the daemon never seeds). ✅
5. **desired.json relocation** — reader + watcher use
   `$XDG_CONFIG_HOME/dotfiles/desired.json`; absent ⇒ `None` (no-op);
   corrupt ⇒ `ValueError` (the reactive declarative step logs and skips it as
   a recoverable step); symlink ⇒ rejected (no-follow). ✅
6. **Safety invariants** — the daemon/converge holds **no lock across a
   use-case call** (every use case owns `.seed.lock`/`.history.lock`
   internally, sequentially; the composite imports no mutex); the backstop is
   an output location the watcher never watches. ✅
7. **Tests** — fake-source driven: coalescing, overflow re-scan,
   registration-loss recovery, reactive trigger line (exactly one),
   backstop no-op/change, desired relocation, no-polling invariant, plus a
   live (Linux-only) inotify smoke test. ✅
8. **Repo guard** — `test_history_writer_triggers.py` AST-scans every
   `append_history(trigger=…)` call site and fails on any value outside
   `HISTORY_TRIGGERS`, and asserts the `reactive` and `prune` writers exist. ✅

## Tasks / Subtasks

- [x] `domain/watch.py` — pure `WatchEventKind` + `WatchEvent`, content-change
      and registration-loss sets.
- [x] `ports/watch_source.py` — `IWatchSource` ABC (`start`/`close`/`rebuild`/
      `read_event`).
- [x] `adapters/watch_roots.py` — AD‑39 enumerated spine allowlist with bounded
      depths; no repo resolution.
- [x] `adapters/inotify_watch_source.py` — ctypes inotify transport; masks,
      recursive bounded installation, new-dir extension, file-parent filter,
      overflow/ignored/self events, stop-pipe-aware blocking read, rebuild,
      idempotent close.
- [x] `application/watch.py` — accumulator + coordinator (coalesce, overflow,
      registration-loss rebuild, recoverable handler failures).
- [x] `adapters/converge_inputs.py` — total, depth-bounded watch-set hasher with
      stable sentinels.
- [x] `adapters/converge_backstop.py` — atomic read/write under `state_root`,
      symlink refusal, corrupt ⇒ changed; record shape machine-defined by
      `contracts/schemas/last-converged.schema.json` (AD‑44, follow-up) and
      enforced on read via `fastjsonschema`.
- [x] `application/converge.py` — `ReactiveConvergeUseCase` (backstop
      short-circuit, unseeded no-op, observe-only, composite order, single
      append before backstop write).
- [x] `adapters/seeder.py` — `suppress_history` flag.
- [x] `adapters/desired_state_reader.py` — explicit intent path +
      `resolve_desired_path`.
- [x] `cli/main.py` — `_resolve_config_home`/`_resolve_desired_path`; thread
      `suppress_history` through `_run_reconcile` / `_run_regenerate_stale` /
      `_run_wallpaper_set` / `_run_converge`; `_run_reactive_converge`;
      `_build_watch_source`; `_run_daemon_run(converge=…, watch_source=…)`
      with converge-on-start + watch thread; `daemon run --activate`.
- [x] Tests (new): `test_watch_roots`, `test_watch_coordinator`,
      `test_converge_inputs`, `test_converge_backstop`,
      `test_reactive_converge`, `test_cli_reactive_converge`,
      `test_history_writer_triggers`, `integration/test_inotify_watch_source`.
- [x] Tests (updated): `test_desired_state` (explicit path + relocation),
      `test_cli_planner_wiring` (XDG_CONFIG_HOME intent), `test_daemon_run`
      (converge-on-start, watch lifecycle, command-wired signature).

## Dev Notes

- **No lock across use-case calls (AD‑35):** `ReactiveConvergeUseCase` is
  injected callables only; the daemon composes use cases that each acquire and
  release their own lock sequentially. A static test asserts the composite
  imports no mutex/lock machinery. The hub dispatcher lock is unrelated to
  use-case calls.
- **Never write a watched root (AD‑36):** the backstop lives at
  `<state_root>/last-converged.json`; a test asserts it is not in the watched
  set. The intent document moved out of `state_root` to `$XDG_CONFIG_HOME`.
- **Backstop machine contract (AD‑44, follow-up):** the v1 record shape
  (`version` + `input_hash` + additive optional `converged_at`) is defined by
  `contracts/schemas/last-converged.schema.json`, embedded byte-identically
  under `adapters/schemas/`, and enforced on read with `fastjsonschema`. A
  schema violation (unknown version, missing required field, mistyped field)
  is logged and treated as changed, preserving the AD‑36 short-circuit policy.
- **Always a full re-scan:** the converge recomputes the whole watch-set hash
  on every trigger, so `full_rescan` is presently informational (overflow and
  registration loss are already equivalent to a full rescan). The flag is kept
  on the trigger so a future incremental path can honor it.
- **Observe-only default (AD‑35/AD‑41):** `daemon run` ships observe-only;
  `--activate` opts in. The systemd unit provisioning that adds `--activate`
  (and `WatchdogSec`/`sd_notify`) is a follow-up outside this runtime story.
- **Reactive prune opt-in (default off).** See "Reactive prune policy (Gate‑2
  N1 resolution)" below: the reactive prune is gated by
  `daemon run --prune-on-reactive` / `$DOTFILES_REACTIVE_PRUNE` (default
  false). It lives outside every watched root (CLI flag/env), never escalates
  past the AD‑30 floor, and is inert while observe-only.
- **Bounded depth alignment (AD‑39):** the backstop hash is bounded to the same
  depth the watcher installs, so a hash change always corresponds to a
  fireable event (a deeper change changes neither).
- **File-root parent absence:** a file root whose immediate parent does not
  exist is surfaced with a warning and left unwatched; when it appears, the
  next registration-loss rebuild or process start re-arms it. No watch is
  installed above the immediate parent (AD‑39).
- **No polling (AD‑40):** the coordinator never sleeps/stats; the source blocks
  in `select` on the inotify fd with a self-pipe wake for shutdown. The
  debounce quiet window is a read timeout, not a state poll.
- **Deferred / follow-up slice candidates:** unit `--activate` wiring +
  `WatchdogSec`/`sd_notify`; `max_user_watches` exhaustion recovery beyond the
  warn+rebuild path; multi-session `state_root` scoping; a live systemd
  end-to-end as an unattended test.

## Reactive prune policy (Gate‑2 N1 resolution)

Gate‑2 review N1 flagged the reactive converge wiring
`prune=lambda: _run_prune(dry_run=False, keep=..., prune_pinned=False)` as a
**surprise‑deletion surface**: with `daemon run --activate`, every
input‑change‑triggered converge deleted cache entries (beyond `keep`/pins)
without an explicit user prune. Owner decision: **make the reactive prune
OPT‑IN, default OFF.**

- **Opt‑in mechanism:** `daemon run --prune-on-reactive` (default `False`)
  with the equivalent env var `$DOTFILES_REACTIVE_PRUNE`; either opts in, and
  neither is required. Both live outside every watched root (a flag/env is not
  a config file under a watched root).
- **Default OFF (shipped):** the reactive composite still runs
  regenerate/reconcile/declarative, but the prune leg is **skipped** — no
  deletion and **no `prune` history line** (dry‑run appends nothing per
  AD‑30). The AD‑30 would‑be removal count is computed read‑only via the
  shared plan and logged at INFO, e.g. `reactive: prune skipped (opt-in off:
  --prune-on-reactive / DOTFILES_REACTIVE_PRUNE); N entries would be removed
  under the AD-30 floor`.
- **ON:** behavior is exactly the prior one — real prune bounded by the AD‑30
  floor (active ∪ last‑N ∪ seed‑pinned ∪ undated survive), `--keep` /
  `desired.keep` precedence unchanged, per‑entry failure logging, exactly one
  `prune` history line with counts, plus the `reactive` line. Never escalates
  past the floor.
- **Observe‑only unchanged (AD‑41):** `daemon run` still ships observe‑only
  and `--prune-on-reactive` is inert until `--activate` reaches the composite.
- **Implementation:** `cli/main.py` `_run_reactive_converge(prune_on_reactive=
  False)` passes `prune=None` when off (the use case already skips a `None`
  prune) and logs the read‑only count via `_log_reactive_prune_skipped`; a
  shared `_build_prune_plan` is used by both the real prune and the skip
  count. `application/converge.py` is unchanged: prune policy is a
  composition‑root decision.
- **Provisioning:** `runtime_daemon_prune_on_reactive` (default `false`)
  conditionally appends `--prune-on-reactive` to the unit's `ExecStart`,
  analogous to `runtime_daemon_activate`. Observe‑only remains the shipped
  default.
- **Tests:** `test_cli_reactive_converge.py` (default‑off = zero deletions +
  exactly one `reactive` line + no `prune` line + skip count; opt‑in = one
  `reactive` + one `prune` line with the floor respected),
  `test_daemon_run.py` (`--prune-on-reactive` and `$DOTFILES_REACTIVE_PRUNE`
  reach `_run_reactive_converge`; flag without `--activate` stays
  observe‑only), `test_cli_inspect_daemon.py` (daemon‑path prune line now
  opts in), `test_runtime_daemon_role.py` (provisioning default off + opt‑in
  flag).

## Verification (exact)

- `uv run --directory src/runtime pytest` → **1315 passed, 2 skipped**
  (baseline before this story: 1206 passed, 2 skipped; +109 tests, all green).
- `uv run --directory src/runtime ruff check src` → **3 errors, all
  pre-existing and unrelated** (2× B008 `typer.Option` defaults in
  `cli/main.py` `main_callback`/`version`; 1× E501 in `domain/models.py`);
  every new/changed file passes `ruff` clean.
- `tests/architecture/test_layering.py` → **90 passed**.
- `make contracts-check` → **22 passed** (schema conformance, event-contract
  conformance, per-language drift, history-trigger enum).
- `uv run --directory src/runtime pytest tests/integration/test_inotify_watch_source.py`
  → **3 passed** (live inotify: dir watch, rebuild, file-root filename filter).

## Files

New: `domain/watch.py`, `ports/watch_source.py`, `adapters/watch_roots.py`,
`adapters/inotify_watch_source.py`, `adapters/converge_inputs.py`,
`adapters/converge_backstop.py`, `application/watch.py`,
`application/converge.py`, and the test files listed above.
Changed: `adapters/desired_state_reader.py`, `adapters/seeder.py`,
`cli/main.py`, `tests/unit/test_desired_state.py`,
`tests/unit/test_cli_planner_wiring.py`, `tests/unit/test_daemon_run.py`.

Untouched by this story: `src/runtime/src/runtime/adapters/bar_subscriber.py`
(another owner) and all of `contracts/`.

## P5 follow-up closed (runtime/provisioning surface)

The four deferred items from the "Deferred / follow-up slice candidates" list
are now closed on the runtime/provisioning surface (no `contracts/` change;
no change to the hub wire contract):

1. **Multi-session `state_root` scoping.** `_resolve_state_root(session_id=None)`
   resolves a session identifier and scopes to
   `<xdg_state>/dotfiles/sessions/<id>`; with none it returns the historical
   path **byte-identically**. Resolution: `$DOTFILES_SESSION_ID` (explicit,
   sanitized `[A-Za-z0-9._-]`, hostile/empty ⇒ safe fallback), else when
   `$DOTFILES_SESSION_SCOPE` is truthy `$XDG_SESSION_ID` then the
   `$XDG_RUNTIME_DIR` basename. Tests: `tests/unit/test_cli_state_root.py`.
2. **inotify watch-registration exhaustion recovery (AD‑40).** The adapter
   records unwatchable roots and exposes a pure
   `WatchStatus(registered, failed, last_error)`; exhaustion
   (`ENOSPC`/`EMFILE`/`ENFILE`) is logged at **ERROR**, not silently dropped.
   `WatchCoordinator` retries a degraded set **once per burst on the next
   arriving event** (never a poll) and re-installs via `rebuild()`; the latest
   status is persisted atomically to `<state_root>/watch-health.json`
   (`adapters/watch_health.py`) so the daemon-independent surface can read it.
   Tests: `tests/unit/test_inotify_registration_recovery.py`,
   `tests/unit/test_watch_health.py`.
3. **`WatchdogSec` + `sd_notify` (AD‑33/AD‑41 residual).** New adapter
   `adapters/systemd_notify.py` (stdlib unix datagram; abstract `@` socket
   supported). The daemon sends `READY=1` **after owning the name**, pings
   `WATCHDOG=1` on a background thread at half `$WATCHDOG_USEC` (default
   30 s/2), and `STOPPING=1` on shutdown; with no `NOTIFY_SOCKET` every call
   is a graceful no-op (never gates, never crashes). The unit sets
   `WatchdogSec=30` + `NotifyAccess=main`. Tests:
   `tests/unit/test_systemd_notify.py` + `TestSystemdNotify` in
   `test_daemon_run.py`.
4. **Provisioning opt-in live mode (`--activate`).** `runtime_daemon_activate`
   (default `false`, observe-only) conditionally appends `--activate` to the
   unit's `ExecStart`; the CLI option also honours
   `$DOTFILES_RUNTIME_ACTIVATE`. Manager-less enablement via
   `graphical-session.target.wants/` is retained and re-pinned. The reactive
   prune is a **separate** opt-in: `runtime_daemon_prune_on_reactive`
   (default `false`) conditionally appends `--prune-on-reactive`; the CLI
   option also honours `$DOTFILES_REACTIVE_PRUNE`. Tests:
   `tests/unit/test_runtime_daemon_role.py`.

**Observability of a degraded watch set.** `inspect daemon` reports
`watch health: unknown|ok|degraded (N unwatched: …)` and names each unwatched
root (JSON `watch_health`); `doctor` appends the same one-line summary without
changing its exit code (watch exhaustion is an environment limit, not desktop
drift).

## Verification (follow-up, exact)

- `uv run --directory src/runtime pytest` → **1532 passed, 2 skipped**
  (pre-follow-up baseline: 1488 passed, 2 skipped; **+44 tests, all green**).
- `uv run --directory src/runtime ruff check src` → **3 errors, all
  pre-existing/unrelated** (2× B008 `typer.Option` in `main.py`; 1× E501
  `domain/models.py`).
- `tests/architecture/test_layering.py` → **103 passed**.
- `make contracts-check` → **27 passed**.
- Provisioning unit: **572 passed, 2 failed, 28 deselected** — the 2 failures
  (`test_compositor_configs_role`, `test_packages_role`) are pre-existing and
  unrelated (untouched files; provisioning shows no other diff). The
  `runtime_daemon` role: **20 passed** (was 15).
- Provisioning integration: `test_ansible_dryrun.py` + `test_settings_parity.py`
  → **21 passed, 1 skipped**; the real `runtime-daemon.yaml --check` dry-run →
  **1 passed**.

**Genuinely remaining (not this surface):** out-of-process `Control(job_id,
action)` delivery / daemon-hosted job runner (Epic 5‑4) needs an owner/contract
decision — **no contract change was invented here**; the container-target
provisioning integration test (`test_apply_verify_container.py`) is not run
unattended (heavy nested-engine/network target).
