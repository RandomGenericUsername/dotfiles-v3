# Story 2.3: Hyprland reload adapter

Status: ready-for-dev

## Story

As a user,
I want Hyprland to pick up the new colors.conf after a swap,
so that the compositor's borders/decoration match the new palette.

## Acceptance Criteria

1. **Given** a swap repointed `current/colors.conf` (through the `~/.config/hypr` spine symlink), **When** the Hyprland reload adapter runs, **Then** it invokes `hyprctl reload` (FR-6).

2. **Given** `hyprctl reload` succeeds (exit code 0), **When** the adapter reports, **Then** it returns success (True) and the reload is considered complete.

3. **Given** `hyprctl reload` fails (non-zero exit code or command not found), **When** the adapter reports, **Then** it returns failure (False) with the error details, and the reconcile command surfaces which consumer failed and exits non-zero (R5 reload-failure handling).

4. **Given** the adapter is wired into `ReconcileDesktopStateUseCase`, **When** the swap sequence reaches step 5 (reload), **Then** the Hyprland reload adapter is invoked once (Hyprland reload is global — not per-monitor) and its result is collected into `ReconcileResult.reload_failures`.

## Tasks / Subtasks

- [ ] Task 1 — Create `adapters/hyprland_reloader.py` (AC: 1, 2, 3)
  - [ ] Create `src/runtime/src/runtime/adapters/hyprland_reloader.py` implementing `IDesktopReloader`.
  - [ ] The class `HyprlandReloader` accepts a `hyprctl_path: Path | None = None` constructor parameter. Default: resolve via `shutil.which("hyprctl")`; if not found, store `None` for fail-later behavior. Mirror the binary resolution pattern from `csg_adapter.py:135-163` (check path separators → `shutil.which` → verify executable via `os.access`).
  - [ ] `reload()` method:
    - If `hyprctl_path` is `None`, log warning `hyprctl not found in PATH; Hyprland reload skipped` and return `False`.
    - Run `subprocess.run([str(self._hyprctl_path), "reload"], capture_output=True, text=True, timeout=10)`. **Must pass `text=True`** so `result.stderr` is `str` (matching `csg_adapter.py:297` pattern).
    - If exit code == 0, return `True`.
    - If exit code != 0, log at warning level with stderr output, return `False`.
    - Catch `FileNotFoundError`, `PermissionError`, `subprocess.TimeoutExpired`, and `OSError` (matching `csg_adapter.py:301-319` exception set). On any of these, log at warning level and return `False`.
  - [ ] Module docstring cites AD-17 (consumer wiring), FR-6 (reload after swap), R5 (reload-failure handling).

- [ ] Task 2 — Wire into `ReconcileDesktopStateUseCase` (AC: 4)
  - [ ] Add `reloaders: list[IDesktopReloader]` constructor parameter to `ReconcileDesktopStateUseCase` (default: `field(default_factory=list)`).
  - [ ] After step 4 (history append) in `run()`, invoke each reloader once: `for reloader in self._reloaders:` call `reloader.reload()`. If it returns `False`, append the reloader's class name to `reload_failures`. Note: `hyprctl reload` is global — do NOT call per-monitor. Each reloader in the list is called exactly once.
  - [ ] Return `ReconcileResult` with `reload_failures` populated (already exists on `ReconcileResult` from rt-2-2).
  - [ ] The reload step runs OUTSIDE the lock (after history append, same scope as history). Reload is fire-and-report — it does not affect the symlink swap or state persistence.

- [ ] Task 3 — Update CLI composition root (AC: 4)
  - [ ] In `cli/main.py` `_run_reconcile()`, add a **lazy import** inside the function body (matching the pattern at cli/main.py:309-315): `from runtime.adapters.hyprland_reloader import HyprlandReloader`.
  - [ ] Construct `HyprlandReloader()` and pass `[HyprlandReloader()]` as the `reloaders` parameter to `ReconcileDesktopStateUseCase`.
  - [ ] The existing reload-failure handling in the `reconcile` command (rt-2-2 placeholder at cli/main.py:362-371) already checks `result.reload_failures` and exits non-zero — verify it works with real adapter output.

- [ ] Task 4 — Unit tests `tests/unit/test_hyprland_reloader.py` (AC: 1, 2, 3)
  - [ ] Follow `test_crash_recovery.py`'s fake-adapter style. Use `unittest.mock.patch` for `subprocess.run`.
  - [ ] **Success tests:**
    - `test_reload_success_returns_true`: Mock `subprocess.run` returning exit code 0 → `reload()` returns `True`.
    - `test_reload_invokes_hyprctl_reload`: Assert `subprocess.run` called with `[hyprctl_path, "reload"]`.
  - [ ] **Failure tests:**
    - `test_reload_nonzero_exit_returns_false`: Mock exit code 1 → returns `False`.
    - `test_reload_timeout_returns_false`: Mock `subprocess.TimeoutExpired` → returns `False`.
    - `test_reload_command_not_found_returns_false`: Mock `FileNotFoundError` → returns `False`.
    - `test_reload_permission_denied_returns_false`: Mock `PermissionError` → returns `False` (matching csg_adapter.py:304-306).
  - [ ] **Missing hyprctl tests:**
    - `test_reload_no_hyprctl_returns_false`: Construct with `hyprctl_path=None` → returns `False`, no subprocess call.
  - [ ] **Integration with ReconcileResult:**
    - `test_reload_failure_populates_reload_failures`: Wire a failing reloader into reconcile → `result.reload_failures` contains the adapter label.

- [ ] Task 5 — Integration test `tests/integration/test_hyprland_reloader_integration.py` (AC: 1, 4)
  - [ ] End-to-end: seed → apply wallpaper → run reconcile with a real `HyprlandReloader` (skip if `hyprctl` not in PATH via `pytest.importorskip` or `shutil.which`).
  - [ ] Assert `result.reload_failures` is empty on success.
  - [ ] If `hyprctl` is not available, skip the test with a clear message.

- [ ] Task 6 — Full green gate (AC: all)
  - [ ] `uv run --directory src/runtime pytest -q` (baseline: ~283+ passed, ~2 skipped)
  - [ ] `uv run --directory src/runtime ruff check src/runtime` (zero NEW violations)
  - [ ] `uv run --directory src/runtime ruff format --check src/runtime` (new/edited files format-clean)
  - [ ] `uv run --directory src/runtime mypy --strict src/runtime` (zero NEW errors)
  - [ ] `tests/architecture/test_layering.py` green (adapters can import from ports, application can import from adapters via constructor injection)

## Dev Notes

### Scope boundary — Hyprland reload ONLY

This story delivers the Hyprland reload adapter only. It deliberately does NOT:
- implement AGS restart (Story 2.4),
- implement Hyprpaper reload (Story 2.5),
- implement terminal palette application (Story 2.6),
- rewire `wallpaper set` (Story 2.7 capstone).

### The `IDesktopReloader` port (existing)

The port is already defined at `ports/desktop_reloader.py`:

```python
class IDesktopReloader(ABC):
    @abstractmethod
    def reload(self) -> bool:
        """Reload the desktop consumer. Returns True on success."""
```

The adapter implements this interface. The `ReconcileDesktopStateUseCase` already has a `reload_failures: list[str]` field on `ReconcileResult` (added in rt-2-2) — this story populates it.

### `hyprctl reload` behavior

- `hyprctl reload` re-reads Hyprland's config files (including `colors.conf` which is symlinked to `current/colors.conf` through the `~/.config/hypr` spine).
- Exit code 0 = success. Non-zero = failure.
- Command is synchronous and fast (<1s typical).
- `hyprctl` is available when Hyprland is running; on non-Hyprland systems (or during testing), it won't be in PATH — the adapter must handle this gracefully (return False, log warning).

### Reuse — leverage existing infrastructure

- `IDesktopReloader` port (ports/desktop_reloader.py) — already defined, use as-is.
- `ReconcileResult.reload_failures` field (application/reconcile.py:69) — already exists from rt-2-2, populated by this story.
- CLI reload-failure handling (cli/main.py:362-371) — already wired from rt-2-2, activates when `reload_failures` is non-empty.
- **Binary resolution + subprocess pattern**: mirror `csg_adapter.py:135-319` exactly — `shutil.which` with path-separator pre-check, `os.access` executable verification, `subprocess.run(capture_output=True, text=True, timeout=)`, and the full exception set (`FileNotFoundError`, `PermissionError`, `subprocess.TimeoutExpired`, `OSError` with errno checks). The hyprland_reloader is simpler (no env override, no args) but the error-handling contract must match.

### Code style gates (enforced)

Python 3.14, `mypy --strict` (no untyped defs, `from __future__ import annotations` at top), ruff line-length 100, ruff select E/F/I/N/W/UP/B. Parenthesize multi-except tuples (PEP 758). Timestamps: `datetime.now(UTC).isoformat().replace("+00:00", "Z")`. House style: dense module docstrings citing AD-numbers, no inline "why" comments beyond those. Application→adapters module-level imports are established (seed/apply/reconcile do it and pass layering) — mirror exactly.

### Previous story intelligence (rt-2-2 — the direct predecessor)

- **`ReconcileResult.reload_failures` is a structural placeholder.** rt-2-2 added the field with `default_factory=list` and the CLI already checks it and exits non-zero. This story populates it with real adapter results. No changes needed to `ReconcileResult` or the CLI error path.
- **Reload runs OUTSIDE the lock.** The shared-data-contract swap sequence is: ensure entries → repoint symlinks → save current.json → append history → reload. Reload is step 5, after history, outside the mutex. Same pattern as history append.
- **Test patterns.** rt-2-2 tests use `_apply_state()` to establish post-apply environments, `_make_reconcile()` to construct the use case with fake adapters, `_symlink_map()` to inspect current/ symlinks, `_FakeCsg`/`_FakeWeg`/`_FakeItr` with `calls` counters and `fail` flags. For the reload adapter, create a `_FakeReloader` that tracks calls and can be configured to fail.
- **Baseline suite.** 283 collected, ~281 passed, ~2 skipped. `src/runtime/` is clean — expect a green baseline before you start.
- **Layering test.** `tests/architecture/test_layering.py` enforces: domain purity (no os/subprocess/shutil/pathlib), ports are ABCs, cross-package forbidden set. The new adapter in `adapters/` can import from `ports/` (allowed) and from `subprocess`/`os`/`shutil` (adapters own I/O). Application layer can import from adapters only via constructor injection — verify no direct adapter imports from application.

### Git intelligence

HEAD = `98ac342` (auto-commit code review findings). Runtime last touched by `a139854` (Story 2.2 crash-mid-swap recovery). Baseline suite: ~281 passed, ~2 skipped. `src/runtime/` is clean — expect a green baseline before you start.

### Latest technical information

No new external dependencies — `hyprctl` is a system binary (Hyprland), subprocess is stdlib. Python 3.14, Typer, pytest, ruff, mypy versions are pinned in `src/runtime/pyproject.toml`/`uv.lock`; do not bump them in this story.

### Testing standards summary

- Runner: `uv run --directory src/runtime pytest -q`. Integration tests use contract-honest fakes (no real tools, no skip logic); the real-tool skip pattern belongs to the adapter integration tests only. Unit tests are pure fakes.
- Lint/type gates in Task 6, all with `--directory src/runtime`; baseline debt documented above — zero NEW violations is the bar.
- Layering: domain purity (no os/subprocess/shutil/pathlib), ports are ABCs, cross-package forbidden set (`provisioning`, `core`, `infrastructure`, `color_scheme_generator`, `wallpaper_effects_generator`, `icon_templates_renderer`, `config_assembler_engine`, `oci_runtime`).
- Assertion style: unit tests assert behavior + contracts (invocation counts, return values); integration tests assert filesystem outcomes end-to-end.

### Project Structure Notes

New files:
- `src/runtime/src/runtime/adapters/hyprland_reloader.py` (NEW — Hyprland reload adapter)
- `src/runtime/tests/unit/test_hyprland_reloader.py` (NEW — unit tests)
- `src/runtime/tests/integration/test_hyprland_reloader_integration.py` (NEW — integration test with real hyprctl)

Modified:
- `src/runtime/src/runtime/application/reconcile.py` (add `reloaders` parameter, invoke reloaders after history append)
- `src/runtime/src/runtime/cli/main.py` (wire `HyprlandReloader` into `_run_reconcile`)

No changes: `domain/`, `ports/` (IDesktopReloader already exists), `pyproject.toml`, `seeder.py`, `json_state_repository.py`, provisioning.

### References

- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md` — Epic 2 intro, Story 2.3 ACs, FR-6, R5
- Architecture spine: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md` — AD-6 (swap sequence step 5: reload), AD-17 (consumer wiring, colors.conf → current/colors.conf)
- Shared data contract: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md` — Swap sequence section (step 5: "trigger desktop reloads per monitor")
- Existing code: `src/runtime/src/runtime/ports/desktop_reloader.py` (IDesktopReloader), `src/runtime/src/runtime/application/reconcile.py` (ReconcileResult.reload_failures at line 69, ReconcileDesktopStateUseCase), `src/runtime/src/runtime/cli/main.py` (reload-failure handling at lines 362-371)
- Previous stories: `_bmad-output/implementation-artifacts/rt-2-2-crash-mid-swap-recovery.md` (reload_failures field, CLI placeholder), `_bmad-output/implementation-artifacts/rt-2-1-atomic-symlink-repoint.md` (swap sequence, scope boundary)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
