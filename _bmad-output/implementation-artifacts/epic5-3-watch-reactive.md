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
   `CheckInputs → RegenerateStale → Reconcile → declarative`, then a prune
   pass, then appends exactly one `trigger="reactive"` line and persists the
   backstop. Inner writes are suppressed. Daemon prune (`_run_prune`) appends
   exactly one `trigger="prune"` line with counts. Observe-only appends no
   history. ✅
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
      symlink refusal, corrupt ⇒ changed.
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
- **Always a full re-scan:** the converge recomputes the whole watch-set hash
  on every trigger, so `full_rescan` is presently informational (overflow and
  registration loss are already equivalent to a full rescan). The flag is kept
  on the trigger so a future incremental path can honor it.
- **Observe-only default (AD‑35/AD‑41):** `daemon run` ships observe-only;
  `--activate` opts in. The systemd unit provisioning that adds `--activate`
  (and `WatchdogSec`/`sd_notify`) is a follow-up outside this runtime story.
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
