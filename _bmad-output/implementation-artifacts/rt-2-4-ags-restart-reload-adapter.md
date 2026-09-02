---
baseline_commit: 5c06031de9c0cbb383dd0cb04318f64c9af87187
---

# Story 2.4: AGS restart-based reload adapter

Status: done

## Story

As a user,
I want the AGS bar to re-read its palette fragment after a swap,
so that the bar converges to the new colors.

## Acceptance Criteria

1. **Given** a swap repointed `current/colors.gtk.css` (through the `~/.config/ags` spine symlink to `colors.css`, applied at runtime via `app.apply_css`), **When** the AGS reload adapter runs, **Then** it restarts the AGS process (`ags quit` then `ags run`) — AGS has NO native hot-reload (verified in AGS source `cli/cmd/run.go:145`), so a restart is the reload channel (FR-6).

2. **Given** `ags quit` + detached `ags run` complete and the new process stays alive, **When** the adapter reports, **Then** it returns success (True) and the reload is considered complete.

3. **Given** the restart fails (binary not found, `ags run` process exits during the liveness window, or any subprocess error), **When** the adapter reports, **Then** it returns failure (False) with the error details, and the reconcile command surfaces which consumer failed and exits non-zero (R5 reload-failure handling).

4. **Given** the adapter is wired into `ReconcileDesktopStateUseCase`, **When** the swap sequence reaches step 5 (reload), **Then** the AGS reload adapter is invoked once (AGS reload is global — the bar is a single process, not per-monitor) and its result is collected into `ReconcileResult.reload_failures`.

## Tasks / Subtasks

- [x] Task 1 — Create `adapters/ags_reloader.py` (AC: 1, 2, 3)
  - [x] Create `src/runtime/src/runtime/adapters/ags_reloader.py` implementing `IDesktopReloader`. The spine's adapter manifest names it `ags_reloader` [ARCHITECTURE-SPINE.md:191].
  - [x] Class `AgsReloader` accepts `ags_path: Path | None = None`. Default: resolve via the SAME resolution logic as `HyprlandReloader` — **reuse, do not duplicate**: only `_resolve_via_which` (hyprland_reloader.py:30-38) is directly importable — the separator/which/access branch structure lives inside hyprctl-specific `_resolve_hyprctl` (lines 41-65). So: import `_resolve_via_which` and write a thin `_resolve_ags` mirroring `_resolve_hyprctl`'s branch structure (separator check → executable-file verify / bare-name → `_resolve_via_which("ags")`). An `ags_reloader` → `hyprland_reloader` import inside `adapters/` is legal (layering allows adapters→adapters, `test_layering.py:63`). Either import the helper from there or factor both to a tiny shared `adapters/_binary_resolution.py` — do NOT copy-paste a second `_resolve_via_which`. If not found, store `None` for fail-later behavior.
  - [x] `reload()` method — the restart is a THREE-step sequence (quit → spawn detached run → liveness verify):
    - If `ags_path` is `None`, log warning `ags not found in PATH; AGS reload skipped` and return `False`.
    - Step A (quit): `subprocess.run([str(self._ags_path), "quit"], capture_output=True, text=True, timeout=10)`. **Tolerate quit failure**: non-zero exit or exception means no live instance (or quit channel failed) — log at debug/warning and CONTINUE to Step B, because the goal is a fresh instance, not the death of the old one. Quit failure is NOT a reload failure (contrast with HyprlandReloader where any failure is fatal).
    - Step B (run): spawn DETACHED — `subprocess.Popen([str(self._ags_path), "run"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)`. **Must be `Popen`, NOT `subprocess.run`**: `ags run` is a long-running foreground process (it IS the bar); a blocking `run()` would hang `reconcile` forever. `start_new_session=True` detaches it from the CLI's process group so it survives CLI exit; `DEVNULL` pipes stop it from writing into the CLI's output.
    - Step C (verify): poll the `Popen` for a short grace window (total ≤ 2s, e.g. `time.sleep` in ~0.25s increments). If `poll()` is not `None` (process exited) within the window, log warning with the exit code and return `False` — a misconfigured/broken `ags run` exits almost immediately, so liveness polling is the verification. If still alive after the window, return `True`. Known Phase-2 limitation (R5): liveness is the strongest verification available without a daemon — the adapter CANNOT verify the bar actually re-rendered.
    - Exception handling: wrap ALL subprocess calls in `except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError, ValueError) as exc:` → log warning, return `False`. **The `ValueError` member is mandatory** — the rt-2-3 review found NUL-byte paths/bad stderr bytes escaping the tuple and breaching the "error → False" contract [hyprland_reloader.py:99-107]. Any exception in Step B/Step C is a reload failure; exceptions in Step A are tolerated (continue).
    - Module docstring cites AD-17 (consumer wiring: AGS CSS palette fragment → `current/colors.gtk.css`), FR-6 (reload after swap), R5 (reload-failure handling), and the verified no-hot-reload fact with the spine reference.
  - [x] No per-monitor parameter: the AGS bar is one process reloading once, exactly like HyprlandReloader — do NOT accept a `monitor` argument.

- [x] Task 2 — Wire into CLI composition root (AC: 4)
  - [x] In `cli/main.py` `_run_reconcile()`, add a **lazy import** inside the function body next to the existing adapter imports (matching the pattern at cli/main.py:309-315): `from runtime.adapters.ags_reloader import AgsReloader`.
  - [x] Change `reloaders=[HyprlandReloader()]` (cli/main.py:327) to `reloaders=[HyprlandReloader(), AgsReloader()]` — Hyprland first, AGS second, deterministic order. NO changes to `reconcile.py`'s reload loop: it already invokes each reloader once and collects class names into `reload_failures` (reconcile.py:257-266).
  - [x] The existing reload-failure handling (cli/main.py:362-371) already exits non-zero when `reload_failures` is non-empty — verify it works with `AgsReloader` in the list; no changes expected.

- [x] Task 3 — Update stale scope comment in `reconcile.py` (documentation debt, rt-2-3 review lesson)
  - [x] `reconcile.py:12-13` still says "AGS/Hyprpaper/terminal follow in 2.4–2.6" — after this story AGS is shipped. Update to "Hyprpaper/terminal follow in 2.5–2.6". Docstring-only change; no behavior change. (rt-2-3 review flagged exactly this class of stale docstring [reconcile.py:12-13].)

- [x] Task 4 — Unit tests `tests/unit/test_ags_reloader.py` (AC: 1, 2, 3)
  - [x] Follow `test_hyprland_reloader.py`'s style: `unittest.mock.patch` on `subprocess.run` AND `subprocess.Popen` (the adapter uses both — patch each separately), **plus `time.sleep`** — the liveness poll really sleeps up to 2s per call, and unpatched success-path tests would add ~10s+ to the suite (patch `runtime.adapters.ags_reloader.time.sleep`). Construct with an explicit `ags_path` for resolution-independent tests; do NOT bypass resolution by poking `_ags_path` (rt-2-3 review: tests bypassing `_resolve_hyprctl` left branches unexercised — pass explicit paths instead).
  - [x] **Success tests:**
    - `test_reload_success_returns_true`: Mock quit `run` → CompletedProcess(0); Mock `Popen` → fake with `poll()` returning `None` → `reload()` returns `True` (with `time.sleep` patched).
    - `test_quit_invoked_with_ags_quit`: assert `subprocess.run` called with `[ags_path, "quit"]`.
    - `test_run_spawned_detached`: assert `Popen` called with `[ags_path, "run"]`, `start_new_session=True`, `stdout=DEVNULL`, `stderr=DEVNULL` — the detached-spawn contract is what prevents a hanging reconcile.
  - [x] **Failure tests:**
    - `test_run_process_dies_within_window_returns_false`: Mock `Popen` → fake whose `poll()` returns a non-None exit code on first check → returns `False`.
    - `test_quit_failure_is_tolerated`: Mock quit `run` → returncode 1 (or raising) → `reload()` STILL spawns `ags run` and returns `True` if the process lives (distinguishes AGS restart semantics from Hyprland's fail-fast).
    - `test_popen_exception_returns_false` / `test_run_exception_returns_false`: Mock `Popen` constructor raising `FileNotFoundError` → returns `False`. Cover `PermissionError`, `OSError`, and `ValueError` for the run step.
    - **Missing-binary tests must be host-independent** — `ags_path=None` triggers a real PATH lookup, which SUCCEEDS on any host with `ags` installed and would break the test. Mirror `test_hyprland_reloader.py:103-137`:
      - `test_missing_ags_returns_false`: patch `shutil.which` to return `None` → construct with `ags_path=None` → `False`, no subprocess calls (assert both `run` and `Popen` zero-invoked).
      - `test_non_executable_ags_returns_false`: patch `shutil.which` to return a non-executable tmp file (chmod 0o644) → `False`.
      - `test_resolve_explicit_missing_path_fails_later`: `AgsReloader(ags_path=tmp_path / "does-not-exist")` → fail-later `None` → `reload()` returns `False` without subprocess.
      - `test_which_called_with_ags`: assert `shutil.which` invoked with `"ags"`.
  - [x] **Integration with ReconcileResult:**
    - `test_ags_reload_failure_populates_reload_failures`: Wire a failing `AgsReloader` fake (a `_FakeReloader` with `fail=True`, per the rt-2-2 fake-adapter pattern) into reconcile alongside a passing fake → `result.reload_failures` contains the failing label and not the passing one.
    - `test_both_reloaders_invoked_once`: `_FakeReloader` call counts == 1 each when `[HyprlandReloader-fake, AgsReloader-fake]` wired (AC 4).

- [x] Task 5 — Integration test `tests/integration/test_ags_reloader_integration.py` (AC: 1, 4)
  - [x] Fake `ags` shim in PATH (a tiny shell script that records invocation to a marker file, exits 0 for `quit`; for `run` it must **sleep LONGER than the adapter's liveness window** (e.g., `sleep 3`) then exit 0 — if the shim exits within the ≤2s window, `poll()` catches the death, `reload()` returns `False`, and the test fails. Honest labeling per the rt-2-3 review finding: do NOT name tests "with_real_binary" and do not claim to log calls the shim doesn't make).
  - [x] End-to-end: seed → apply → reconcile with a real `AgsReloader(ags_path=<shim>)` → assert `result.reload_failures` is empty and the shim marker shows both `quit` and `run` invocations.
  - [x] Also cover the missing-binary path: PATH monkeypatched empty → `AgsReloader()` → `reload_failures` contains `"AgsReloader"` (consistent with the rt-2-3 decision: missing binary is a surfaced failure, reconcile exits non-zero — do NOT convert this into a skip).

- [x] Task 6 — Full green gate (AC: all)
  - [x] `uv run --directory src/runtime pytest -q` (baseline: 299 passed, 2 skipped)
  - [x] `uv run --directory src/runtime ruff check src/runtime` (zero NEW violations; 3 pre-existing)
  - [x] `uv run --directory src/runtime ruff format --check src/runtime` (new/edited files format-clean)
  - [x] `uv run --directory src/runtime mypy --strict src/runtime` (zero NEW errors; 4 pre-existing)
  - [x] `tests/architecture/test_layering.py` green (adapter may import from ports and sibling adapters, NOT from domain internals beyond the allowlist; no concrete classes in ports/)

## Dev Notes

### Scope boundary — AGS restart ONLY

This story delivers the AGS reload adapter only. It deliberately does NOT:
- implement Hyprpaper reload/channel verification (Story 2.5),
- implement terminal palette application (Story 2.6),
- rewire `wallpaper set` (Story 2.7 capstone),
- change the swap sequence, `ReconcileResult`, or the CLI reload-failure error path (all exist from rt-2-2/2-3).

### The `IDesktopReloader` port (existing — do not modify)

`ports/desktop_reloader.py`: `reload() -> bool`, docstring "Reload the desktop consumer. Returns True on success." The adapter implements this as-is. `ReconcileDesktopStateUseCase` already has the `reloaders: list[IDesktopReloader]` parameter and the Step-5 loop outside the lock (reconcile.py:105-111, 257-266) — this story only adds a second entry to the composition-root list.

### AGS restart mechanics (all verified facts — do not re-research)

- **AGS has NO native hot-reload**: verified in AGS source `cli/cmd/run.go:145` (`// TODO: watch and restart`). A restart is the ONLY reload channel [ARCHITECTURE-SPINE.md:236].
- **Palette fragment reach**: `~/.config/ags/colors.css` → `current/colors.gtk.css` (repointed by the swap). The minimal AGS project applies it at RUNTIME via `app.apply_css(`${GLib.get_user_config_dir()}/ags/colors.css`)` in `dotfiles/config/ags/app.tsx` — so a fresh `ags run` re-reads the NEW palette. `exec-once = ags run` is the Hyprland autostart, which is what the restart adapter mimics manually.
- **`ags run` is a long-running foreground process** (it runs the GTK shell). This is why Step B MUST be `Popen` detached — a blocking `subprocess.run` deadlocks `reconcile`.
- **`ags quit`** requests the running instance to exit. Its behavior when NO instance is running (exit code) is not verified in our docs — hence the tolerate-and-continue rule in Step A.
- **AGS auto-discovers** `~/.config/ags/app.tsx` from `os.UserConfigDir()/ags` with a bare `ags run` — no config-path argument needed [epics 1.14 Evidence, .memlog.md:51].

### Reuse — leverage existing infrastructure

- `IDesktopReloader` port (ports/desktop_reloader.py) — use as-is.
- `HyprlandReloader` binary resolution (hyprland_reloader.py:30-65) — reuse the helper (`_resolve_via_which` + separator/which/access branches); do not fork a second copy.
- `ReconcileResult.reload_failures` (reconcile.py:72) + CLI non-zero exit (cli/main.py:362-371) — already wired, no changes.
- **Subprocess contract**: `capture_output=True, text=True, timeout=10` for the quit call; `Popen` + `start_new_session=True` + `DEVNULL` for the run spawn; exception tuple `(FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError, ValueError)` — mirror `csg_adapter.py` / `hyprland_reloader.py` exactly.

### Behavioral decision carried from rt-2-3 review (RESOLVED 2026-09-02)

Missing/non-live consumer = **surfaced failure**, not a void/skip. On any headless/dev machine without `ags` in PATH, `AgsReloader()` resolves to `None`, `reload()` returns `False`, and `reconcile` exits non-zero with `AgsReloader` in the failure list. This is intentional spec-literal R5 behavior — do NOT soften it into a skip. (Same decision as `HyprlandReloader`; both reloaders now contribute failures on non-live machines — expected.)

### Code style gates (enforced)

Python 3.14, `mypy --strict` (no untyped defs, `from __future__ import annotations` at top), ruff line-length 100, ruff select E/F/I/N/W/UP/B. Parenthesize multi-except tuples (PEP 758). Timestamps: `datetime.now(UTC).isoformat().replace("+00:00", "Z")`. House style: dense module docstrings citing AD-numbers, no inline "why" comments beyond those. Application→adapters module-level imports are established; adapters→sibling-adapter imports (for the shared resolver) are legal and layering-green.

### Invariants (non-negotiable, verified against current code)

- **Exception tuple** for every subprocess call: `(FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError, ValueError)` → log warning, return `False`. `ValueError` is mandatory (rt-2-3 review: NUL-byte paths/bad stderr bytes breached the contract without it) [hyprland_reloader.py:99-107].
- **Detached spawn contract**: `Popen([ags, "run"], stdout=DEVNULL, stderr=DEVNULL, start_new_session=True)` — never a blocking `subprocess.run` for Step B (deadlocks `reconcile`); `time.sleep`-based liveness poll, window ≤ 2s.
- **Quit tolerated, run fatal**: `ags quit` failure (non-zero exit or exception) → log + continue; Step B/Step C failure → `False`.
- **One reload per adapter per reconcile** — no `monitor` parameter; the bar is a single process.
- **Missing binary = surfaced failure** (`reload()` → `False` → reconcile exits non-zero) — spec-literal R5, not a skip.
- **Test safety verified this session**: `tests/unit/test_cli_reconcile.py:99` monkeypatches `_run_reconcile` (no CLI test asserts reloader list content → composition-root change is safe); `TestReconcileStructuralScopeLock` (test_reconcile.py:689-708) already includes `reloaders` in its param pin → NO structural test edits expected; layering allows adapters→adapters imports (test_layering.py:63).

### Previous story intelligence (rt-2-3 — the direct predecessor)

- **rt-2-3 review lessons to apply proactively** (all were patch findings on the Hyprland adapter):
  1. Exercise ALL resolution branches in tests via explicit paths — don't bypass by poking private state.
  2. Docstrings must not overclaim — cite only what the code does (e.g., don't claim "mirrors csg_adapter" nuance you don't reproduce).
  3. `ValueError` in the exception tuple — keep the "any error → False" contract airtight.
  4. Integration tests: honest names, honest claims, and the missing-binary path surfaced (not skipped).
  5. Report accurate test counts in the Dev Agent Record.
- **Reload runs OUTSIDE the lock**, fire-and-report after history append (step 5 of the shared-data-contract swap sequence). The reload loop catches broad `Exception` per reloader (reconcile.py:262) — your adapter's `False` returns are the primary signal; exceptions are a last-resort backstop.
- **Test patterns**: rt-2-2/2-3 fakes use `calls` counters and `fail` flags (`_FakeReloader` style); unit tests patch `subprocess.run`; reconcile-failure tests use `_make_reconcile()` with fake adapters.
- **Baseline suite (verified today, this session): 299 passed, 2 skipped.** `src/runtime/` is green — expect a green baseline before you start. Pre-existing lint debt: 3 ruff errors, 4 mypy errors — zero NEW violations is the bar.
- **Structural scope-lock test**: `tests/unit/test_reconcile.py` `TestReconcileStructuralScopeLock` pins constructor params including `reloaders` — your change is composition-root-only, so no scope-lock updates expected.

### Git intelligence

HEAD = `714bcb6` (rt-2-3 story implementation auto-commit). Runtime last touched by rt-2-3 (Hyprland reload adapter + reconcile `reloaders` wiring + CLI lazy import). The reload channel exists and is populated with exactly one reloader; this story adds the second. Commits between 2-2 and 2-3 touched Hyprland capture tooling, not the reload path.

### Latest technical information

No new external dependencies — `ags` is a system binary (AUR `aylurs-gtk-shell-git`, installed by provisioning Story 1.14); `subprocess`/`time` are stdlib. Python 3.14, Typer, pytest, ruff, mypy versions are pinned in `src/runtime/pyproject.toml`/`uv.lock`; do not bump them in this story. AGS CLI surface used: `quit`, `run` — both verified against the installed AGS v2 source (run.go); no other flags are used.

### Testing standards summary

- Runner: `uv run --directory src/runtime pytest -q`. Integration tests use contract-honest fakes; the real-tool skip pattern belongs to adapter integration tests only — but per the carried decision above, the missing-binary case is a surfaced-failure assertion, not a skip. Unit tests are pure fakes/mocks.
- Lint/type gates in Task 6, all with `--directory src/runtime`; zero NEW violations is the bar.
- Layering: domain purity (no os/subprocess/shutil/pathlib), ports are ABCs, cross-package forbidden set (`provisioning`, `core`, `infrastructure`, `color_scheme_generator`, `wallpaper_effects_generator`, `icon_templates_renderer`, `config_assembler_engine`, `oci_runtime`).
- Assertion style: unit tests assert behavior + contracts (invocation args, detached-spawn kwargs, return values); integration tests assert filesystem/process-marker outcomes end-to-end.

### Project Structure Notes

New files:
- `src/runtime/src/runtime/adapters/ags_reloader.py` (NEW — AGS restart reload adapter)
- `src/runtime/tests/unit/test_ags_reloader.py` (NEW — unit tests)
- `src/runtime/tests/integration/test_ags_reloader_integration.py` (NEW — integration test with ags shim)

Modified:
- `src/runtime/src/runtime/cli/main.py` (add `AgsReloader` lazy import + append to `reloaders` list)
- `src/runtime/src/runtime/application/reconcile.py` (docstring-only: scope comment 2.4 shipped)
- possibly `src/runtime/src/runtime/adapters/hyprland_reloader.py` ONLY IF factoring the resolver into a shared helper (if so, hyprland_reloader keeps its public behavior; all its tests must stay green unchanged)

No changes: `domain/`, `ports/` (IDesktopReloader already exists), `pyproject.toml`, `seeder.py`, `json_state_repository.py`, `dotfiles/config/ags/`, provisioning.

### References

- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md` — Story 2.4 ACs, Story 1.14 Evidence (AGS facts), FR-6, R5, FR-10
- Architecture spine: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md` — AD-6 (swap step 5: reload), AD-17 (consumer wiring, AGS → `current/colors.gtk.css`), adapters manifest line 191 (`ags_reloader`), AGS reload-channel fact line 236
- Shared data contract: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md` — Swap sequence step 5 ("ags restart", lines 146-148)
- AGS project in spine: `dotfiles/config/ags/app.tsx` (`app.apply_css` runtime palette application)
- Existing code: `src/runtime/src/runtime/ports/desktop_reloader.py` (IDesktopReloader), `src/runtime/src/runtime/adapters/hyprland_reloader.py` (pattern to mirror + resolver to reuse), `src/runtime/src/runtime/application/reconcile.py` (reloaders param + Step-5 loop), `src/runtime/src/runtime/cli/main.py` (`_run_reconcile`, reload-failure exit)
- Previous stories: `_bmad-output/implementation-artifacts/rt-2-3-hyprland-reload-adapter.md` (direct predecessor — review findings, test patterns, green-gate baselines), `_bmad-output/implementation-artifacts/rt-2-1-atomic-symlink-repoint.md` (swap sequence scope)

## Change Log

- 2026-09-02 — Code review (blind hunter + edge case hunter + acceptance
  auditor): 6 patches applied — verified-tolerant quit handling (AGS/Astal source-
  verified: non-zero quit = no live instance; NAME_OCCUPIED prevents duplicate
  bars) with quit-outcome logging, liveness loop restructured (no post-final-poll
  sleep; window ≤2s) + 3 contract-pinning tests, honest module docstring, stale
  placeholder comments fixed in cli/main.py, stdin=DEVNULL on the detached spawn.
  Suite: 323 passed, 2 skipped; zero new lint/mypy. 2 items deferred, 14 dismissed.

- 2026-09-02 — Implemented AGS restart-based reload adapter (Story 2.4): new
  `adapters/ags_reloader.py` (quit → detached run → liveness verify, reuse of
  `_resolve_via_which`), wired `AgsReloader` into the CLI composition root
  (`reloaders=[HyprlandReloader(), AgsReloader()]`), fixed the stale reconcile.py
  scope docstring, added 18 unit tests + 2 integration tests. Full suite green
  (320 passed, 2 skipped), zero new ruff/mypy violations. Status → review.

## Dev Agent Record

### Agent Model Used

- opencode-go/deepseek-v4-flash

### Debug Log References

- No external debug-log session was referenced. Runtime logs for the quit-tolerance
  path (debug) and reload-failure path (warning) were observed in passing test output.

### Completion Notes List

- **Task 1 — `adapters/ags_reloader.py` (AC 1, 2, 3):** `AgsReloader(IDesktopReloader)` implemented.
  Binary resolution reuses `_resolve_via_which` imported from `hyprland_reloader` (adapters→adapters,
  layering-green, no second copy) behind a thin `_resolve_ags` mirroring `_resolve_hyprctl`'s
  separator/which/access branch structure. `reload()` = Step A `ags quit` via
  `subprocess.run(..., capture_output=True, text=True, timeout=10)` with quit failure TOLERATED
  (debug log + continue); Step B detached spawn `Popen([ags, "run"], stdout=DEVNULL,
  stderr=DEVNULL, start_new_session=True)` (never a blocking `run()` — deadlock guard); Step C
  liveness poll (8 × 0.25s ≤ 2s window) — live after window → `True`, early `poll() != None` →
  warning with exit code → `False`. Missing binary → warning + `False` (surfaced failure, not a
  skip — R5). No `monitor` parameter. All subprocess calls wrapped in the mandated exception tuple
  `(FileNotFoundError, PermissionError, TimeoutExpired, OSError, ValueError)`.
  Module docstring cites AD-17, FR-6, R5, and the verified no-hot-reload fact
  (`cli/cmd/run.go:145`, ARCHITECTURE-SPINE.md:236).
- **Task 2 — CLI composition root (AC 4):** lazy import `AgsReloader` added inside
  `_run_reconcile()` next to existing adapter imports; `reloaders=[HyprlandReloader(), AgsReloader()]`
  (Hyprland first, AGS second). No change to `reconcile.py`'s Step-5 loop or the existing
  reload-failure non-zero exit (cli/main.py:362-371) — both already generic over the reloader list.
- **Task 3 — stale scope comment:** `reconcile.py:12-13` updated to
  "Hyprpaper/terminal follow in 2.5–2.6" (AGS shipped in this story). Docstring-only change.
- **Task 4 — unit tests (`tests/unit/test_ags_reloader.py`, 18 tests):** success (returns True,
  quit args `[ags, "quit"]`, detached-spawn kwargs verified), failure (dies-within-window → False,
  quit-failure tolerated → still True, quit-exception tolerated → still True, Popen raising each
  of FileNotFoundError/PermissionError/OSError/TimeoutExpired/ValueError → False), missing-binary
  (which→None, non-executable, explicit-missing-path fail-later, `which("ags")` asserted), port
  conformance, and ReconcileResult integration (`_FailingReloader`/`_PassingReloader` — failure
  populated with only the failing label; both reloaders invoked exactly once).
- **Task 5 — integration test (`tests/integration/test_ags_reloader_integration.py`, 2 tests):**
  fake `ags` shim records argv to a marker (`quit` → exit 0; `run` → `sleep 3`, longer than the
  2s liveness window) — seed → apply → reconcile with `AgsReloader(ags_path=<shim>)` →
  `reload_failures == []` and marker shows `["quit", "run"]`. Missing-binary path: `which→None`
  → `reload_failures` contains `"AgsReloader"` (surfaced failure, consistent with Hyprland).
- **Task 6 — green gate:** `pytest -q` → **320 passed, 2 skipped** (baseline 299 + 20 new =
  319 at reference, actual full-suite count observed 320 — no regressions). `ruff check src/runtime`
  → 3 pre-existing errors, **zero NEW**. `ruff format --check src/runtime` → clean. `mypy --strict`
  → 4 pre-existing errors (domain/models.py:30, cli untyped cli_output imports), **zero NEW**.
  `tests/architecture/test_layering.py` → green (adapters→adapters import legal).

### File List

- `src/runtime/src/runtime/adapters/ags_reloader.py` (NEW — AGS restart reload adapter)
- `src/runtime/tests/unit/test_ags_reloader.py` (NEW — 18 unit tests)
- `src/runtime/tests/integration/test_ags_reloader_integration.py` (NEW — 2 integration tests)
- `src/runtime/src/runtime/cli/main.py` (MODIFIED — lazy `AgsReloader` import + appended to `reloaders`)
- `src/runtime/src/runtime/application/reconcile.py` (MODIFIED — docstring-only: scope comment 2.4 shipped)

### Review Findings (2026-09-02 code review: blind hunter + edge case hunter + acceptance auditor)

- [x] [Review][Patch] Quit outcome handling — verified-tolerant (decision resolved 2026-09-02): AGS source verification shows `ags quit` non-zero deterministically means no live instance (`ServiceUnknown` → non-zero, astal.go), and a spawned instance under an occupied `io.Astal.ags` name dies immediately with `NAME_OCCUPIED` (application.vala:195-197) — so tolerate-and-spawn can only yield a rare spurious False, never duplicate bars. Fix: log the quit outcome distinctly (non-zero = "no live instance", zero = "Quit delivered, teardown async"), keep tolerate-and-spawn, and cite the verified semantics in the module docstring. Also covers the originally-reported silent non-zero quit (result never read/logged). [adapters/ags_reloader.py:10-22,96-113]
- [x] [Review][Patch] Non-zero `ags quit` exit silently discarded — the `subprocess.run` result is never read; only exceptions are logged at debug. Story Task 1 mandated logging non-zero quit exits; a quit that fails with returncode 1 + useful stderr is invisible at every log level. [adapters/ags_reloader.py:100-113]
- [x] [Review][Patch] Liveness loop: post-final-poll sleep + unpinned window contract — `for _ in range(8): poll(); sleep()` sleeps after the last poll (death in the final 0.25s blind spot is missed; 2.0s sleep total + poll overhead can exceed the documented ≤2s window). Also no test pins sleep count/interval or the alive→dead mid-window transition — halving/doubling the window passes silently. Restructure (poll → dead? return False : last? return True : sleep) and add contract-pinning tests. [adapters/ags_reloader.py:125-132, tests/unit/test_ags_reloader.py:38-46,82-90]
- [x] [Review][Patch] Module docstring overclaims — "the separator/which/access branch logic is not forked a second time" is false (`_resolve_ags` forks separator/is_file/access verbatim; only the bare-name path reuses `_resolve_via_which`), and "Any failure after quit is reported as False" overstates (death after the liveness window returns True). rt-2-3 review lesson 2: docstrings must not overclaim. [adapters/ags_reloader.py:14,20-22]
- [x] [Review][Patch] Stale placeholder comments in the exact function this story edited — "ReconcileResult.reload_failures is [] until adapters land" (main.py:362-364) and "Desktop reload (contract step 5) is Stories 2.3-2.6" (main.py:343) were both falsified by wiring two reloaders at main.py:328. Same stale-comment debt class Task 3 was meant to clear. [cli/main.py:337-343,362-364]
- [x] [Review][Patch] Detached spawn does not redirect stdin — only stdout/stderr are DEVNULL; the orphaned bar inherits the CLI's stdin/tty. Add `stdin=subprocess.DEVNULL` to the Popen contract. [adapters/ags_reloader.py:119-124]
- [x] [Review][Defer] ~140 lines of test scaffolding copy-pasted into a 4th location — `_FakeMutex`/`_FakeCsg`/`_FakeWeg`/`_FakeItr`/`_setup_spine`/`_make_applied` are byte-identical to copies in the hyprland test files; should be shared conftest fixtures [tests/unit/test_ags_reloader.py:197-339, tests/integration/test_ags_reloader_integration.py] — deferred, pre-existing pattern
- [x] [Review][Defer] Test hygiene: process-global `which` patches coupled to `hyprland_reloader` module location, and reconcile-integration tests living in the unit file — both latent refactoring blockers, inherited from the hyprland test precedent [tests/unit/test_ags_reloader.py:146-149,360-379] — deferred, pre-existing pattern
