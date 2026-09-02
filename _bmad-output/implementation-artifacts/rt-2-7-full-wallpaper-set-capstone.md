---
baseline_commit: dab6f3d
---

# Story 2.7: Full `wallpaper set` end-to-end capstone

Status: ready-for-dev

## Story

As a user,
I want `dotfiles-runtime wallpaper set <img>` to converge the entire desktop in one command,
so that changing a wallpaper is a single synchronous step that derives, caches, swaps, reloads, and persists.

## Acceptance Criteria

1. **Full pipeline in one command (FR-1).** **Given** the pipeline components from Epic 1 (derive/cache/persist) and Epic 2 (swap + reload adapters 2.3–2.6), **When** `dotfiles-runtime wallpaper set <img>` runs, **Then** it (a) derives + caches via `ApplyWallpaperUseCase`, (b) delegates the atomic `current/` symlink swap to `ReconcileDesktopStateUseCase` (story 2.1 ordering: cache-ensure → repoint wallpaper→palette→effects→icons → `current.json` → `history.jsonl` → reload), (c) reloads all four consumers (2.3 Hyprland, 2.4 AGS, 2.5 Hyprpaper, 2.6 terminal), and (d) persists `current.json` + appends a `history.jsonl` line. The command stays a single synchronous imperative process (AD-12/NFR-2 — no daemon, async, event bus).

2. **Cache hit on repeat (FR-2).** **Given** a wallpaper has already been set, **When** `wallpaper set <same img>` runs again, **Then** the derivation is a cache hit — zero csg/weg/itr tool invocations, both in the apply pass AND the reconcile pass — yet the swap (symlink repoint), `current.json` write, `history.jsonl` append, and reload all still run. The combined output reports palette/effects/icons as cache hits (reusing the existing per-layer descriptors).

3. **Crash repair on next run (FR-3, R5 → 2.2).** **Given** a swap crashed mid-sequence (killed process, power loss, reload failure), **When** the next `wallpaper set` (or standalone `reconcile`) runs, **Then** `ReconcileDesktopStateUseCase`'s existing story-2.2 `_revert_stale_symlinks` detection reverts stray `current/` repoints to the last-good `current.json` before the new swap proceeds; re-running the interrupted wallpaper is a cache hit (no tool re-invocation).

4. **Reload-failure reporting (R5).** **Given** one or more consumers fail to reload (Hyprland/AGS/Hyprpaper/terminal), **When** the pipeline completes, **Then** the command reports WHICH consumer failed and exits non-zero — via `ReconcileResult.reload_failures` → `ErrorView(kind="ReloadError")` listing the failed consumer(s) + `typer.Exit(code=1)` (the exact pattern already used by the `reconcile` command, `cli/main.py`). Known Phase-2 limitation: no daemon retry.

5. **History trigger semantics (shared-data-contract).** **Given** a `wallpaper set` completes, **Then** the appended `history.jsonl` line uses trigger `"set"` (pinned enum `seed|set|reconcile|force` — never invent `"apply"`), while the standalone `reconcile` command continues to use trigger `"reconcile"`. The line is appended AFTER the symlink repoint and BEFORE desktop reload is considered complete (AR-3/AD-4); a correction is a new line, never an edit.

6. **Per-monitor config preserved (AD-18).** **Given** non-default per-monitor configs exist (`current.json.monitors`: backend / fit_mode / mpv_options / ipc_socket), **When** `wallpaper set` performs the swap, **Then** monitor entries are PRESERVED and only each monitor's `source_hash` is updated — never silently reset to the `DP-1`/hyprpaper/cover default.

7. **Existing CLI contracts preserved.** **Given** the `reconcile` command and all existing runtime tests, **When** this story lands, **Then** `reconcile` behavior is unchanged (same 4-reloader wiring, same `"reconcile"` trigger, same exit semantics), the `__init__` signature of `ReconcileDesktopStateUseCase` is untouched (`TestReconcileStructuralScopeLock` stays green), and the full baseline suite stays green at ≥ 385 passed / 2 skipped with zero NEW ruff/mypy violations.

## Tasks / Subtasks

- [ ] Task 1 — Composition-root chain: `wallpaper set` runs apply → reconcile (AC: 1, 2, 6, 7)
  - [ ] In `src/runtime/src/runtime/cli/main.py` `_run_wallpaper_set()` (currently 175-207), after constructing `ApplyWallpaperUseCase` and calling `.run(image_path)`, construct `ReconcileDesktopStateUseCase` with the SAME adapters (`JsonStateRepository(state_root=...)`, `CsgAdapter()`, `WegAdapter()`, `ItrAdapter()`, `install_spine`, `state_root`, `CacheSeeder(state_root)`, `FlockSeedMutex(state_root / ".seed.lock")`) and `reloaders=_build_reloaders(state_root)`, then call `.run(trigger="set")`.
  - [ ] Extract the 4-reloader construction into a module-level helper `_build_reloaders(state_root: Path) -> list[IDesktopReloader]` (`cli/main.py`) used by BOTH `_run_reconcile` and `_run_wallpaper_set`. Deterministic order: `[HyprlandReloader(), AgsReloader(), HyprpaperReloader(state_root=state_root), TerminalColorApplier(state_root=state_root)]` — identical to the current `_run_reconcile` list (`cli/main.py:330-335`). Move the lazy `from runtime.adapters...` reloader imports into the helper. Do NOT duplicate the list in two places (drift risk; a shared helper is the whole point).
  - [ ] Change `_run_wallpaper_set` to return a private frozen dataclass (module-level in `cli/main.py`) carrying both results, e.g. `_WallpaperSetResult(apply: ApplyWallpaperResult, reconcile: ReconcileResult)` — preserves the apply's per-layer cache-hit descriptors AND the reconcile's `repointed`/`skipped`/`cache_regenerated`/`reload_failures`. Fully typed (mypy `--strict`). NOTE: this return-type change ripples into `tests/unit/test_cli_wallpaper_set.py`'s `_fake_composition`/`_result()` fakes and `test_json_format_renders_structured_object`'s object-shape assertions — update them in the same commit.
  - [ ] Keep the double mutex (apply holds the flock around load→save; reconcile holds it again around load→repoint→save). Sequential, no deadlock — it matches AD-12's pipeline. Do NOT build a new application-layer orchestration use case; the design is composition-root-only.
  - [ ] `main_callback`'s seed guard is unchanged: `wallpaper set` still auto-seeds first (only `"reconcile"` in `sys.argv` skips seeding); reconcile in the combined flow is fine because apply just wrote `current.json`.

- [ ] Task 2 — History trigger seam (AC: 5, 7)
  - [ ] In `src/runtime/src/runtime/application/reconcile.py`, change `def run(self) -> ReconcileResult:` to `def run(self, trigger: str = "reconcile") -> ReconcileResult:` and thread it into the `append_history(trigger=..., ...)` call (currently hardcoded `trigger="reconcile"` at reconcile.py:249). Default keeps the standalone `reconcile` command and `TestReconcileHistory.test_history_line_schema` green. Validate the trigger value against the pinned enum `{"seed", "set", "reconcile", "force"}` (surface a `ValueError` otherwise — fail-loud, consistent with house validation style) **ONLY inside `run()`** — do NOT add validation or any docstring "fix" to `CacheSeeder.append_history` (seeder.py): it must stay trigger-agnostic (its docstring example uses `"apply"` and `test_seed_cache.py:397,402` intentionally write `"apply"` — AC-7 requires the suite stay green). Update the docstrings (`reconcile.py:21`, `:85`) to mention the parameter and that `wallpaper set` passes `"set"`.
  - [ ] NO `__init__` signature change — `TestReconcileStructuralScopeLock` (`test_reconcile.py:689-708`) pins the constructor param set; a `run()` parameter is outside that lock. Do NOT add a new constructor param or a new use case.
  - [ ] `_run_reconcile()` continues calling `.run()` (default triggers `"reconcile"`); `_run_wallpaper_set()` calls `.run(trigger="set")`.

- [ ] Task 3 — Reload-failure exit for `wallpaper set` (AC: 4)
  - [ ] In the `wallpaper_set` command handler (`cli/main.py:233-292`), after the try/except and before rendering the success `CustomView`, mirror the `reconcile` command block (`cli/main.py:373-384`): if `result.reconcile.reload_failures` is non-empty → `logger.error` + `renderer.error(ErrorView(kind="ReloadError", message=f"reload failed for: {', '.join(...)}"))` + `raise typer.Exit(code=1) from None`.
  - [ ] Extend the success `CustomView` `object` to include the swap/reload data: `"repointed": [str(p) for p in result.reconcile.repointed]`, `"skipped": list(result.reconcile.skipped)`, `"cache_regenerated": list(result.reconcile.cache_regenerated)`, `"reload_failures": list(result.reconcile.reload_failures)` — keep the existing keys (`wallpaper`, `palette`, `effects`, `icons`, `cache_hits`). Update the `plain`/`rich` summary to a `wallpaper set`-appropriate one-line that includes the apply descriptors AND the repoint count (e.g. `wallpaper applied: <h> (palette hit, effects hit, icons hit), N symlink(s) repointed`). Hand-curate the human text via `CustomView(plain=..., object=..., rich=...)` — never auto-serialize.
  - [ ] Update the `wallpaper_set` command docstring (cli/main.py:238-244, stale text at :242-243 — currently claims "Symlink repoint, history, and desktop reload are Epic 2 scope") to describe the full end-to-end behavior; refresh the module-list docstring in `cli/main.py` if it names the seam.

- [ ] Task 4 — Stale scope comments (AC: 7)
  - [ ] `reconcile.py:12-14` — remove/replace "Does NOT rewire `wallpaper set` (Story 2.7 capstone)" with a note that the capstone chains apply into reconcile (shipped).
  - [ ] `application/apply_wallpaper.py` — refresh its scope header/docstring: the "does NOT repoint symlinks / append history / reload" statements remain TRUE for the apply use case itself (its contract is unchanged — it updates desired state and delegates the swap to Reconcile per shared-data-contract); soften only the sentence that claims the seam is still open, if present.

- [ ] Task 5 — Unit tests (AC: 1, 4, 5, 7)
  - [ ] `tests/unit/test_cli_wallpaper_set.py` — update `_result()` / `_fake_composition` to the new `_WallpaperSetResult` shape; update `test_json_format_renders_structured_object` for the added keys; ADD `test_reload_failures_maps_to_exit_1` (a `_WallpaperSetResult` whose `reconcile.reload_failures = ["HyprpaperReloader"]` → `ErrorView(kind="ReloadError")` rendered + `typer.Exit(1)`), `test_reload_success_renders_repointed_summary`, and a `wallpaper set`-specific composition-root positive test: `TestWallpaperSetCompositionRootWiring.test_composition_root_wires_apply_then_reconcile` proving `_run_wallpaper_set` constructs `ReconcileDesktopStateUseCase` with the four reloaders and `state_root` plumbed (mirror `TestReconcileCompositionRootWiring` in `test_cli_reconcile.py:141-169`, asserting `reloaders[2]._state_root`/`reloaders[3]._state_root`, mirroring `TestReconcileCompositionRootWiring` in `test_cli_reconcile.py:141-177` incl. the `_state_root` assertions at 176-177). Because the existing CLI tests monkeypatch `_run_wallpaper_set` wholesale, no live-host isolation is needed for THEM — only for any NEW test that exercises the real composition root (see Task 6 bullet 2).
  - [ ] `tests/unit/test_reconcile.py` — add `test_run_default_trigger_is_reconcile` (existing behavior pinned), `test_run_trigger_set_append_history` + `test_run_invalid_trigger_raises_value_error` (parametrized over the 4 valid values + invalid ones like `"apply"`). Assert `TestReconcileStructuralScopeLock` stays green (no `__init__` change) and `TestReconcileHistory.test_history_line_schema` untouched.
  - [ ] No new CLI arguments — reuse the module-level `_IMAGE_PATH_ARG`/`_OUTPUT_FORMAT_OPTION` singletons; a new `typer.Option`/`typer.Argument` would add NEW ruff B008 violations (baseline already has 2 pre-existing B008).

- [ ] Task 6 — Integration tests (AC: 2, 3, 4, 5, 6)
  - [ ] New `tests/integration/test_wallpaper_set_capstone_integration.py` (honest family pattern — compose use cases DIRECTLY, never through the CLI in integration): helper mirrors `_make_reconcile`/`_apply_state`/`_setup_spine` (`test_hyprpaper_reloader_integration.py`): real `JsonStateRepository` + fake csg/weg/itr (contract-honest fakes that write real artifacts + expose `calls` counters) + fake mutex + real `CacheSeeder`.
    - **E2E full pipeline:** seed → `ApplyWallpaperUseCase.run(img)` → `ReconcileDesktopStateUseCase.run(trigger="set")` with `reloaders=[_PassingReloaders...]` (or the real adapters pointed at shim/sink seams, mirroring the terminal `tty_path` sink pattern). Assert: `current/` symlinks repointed (wallpaper-<monitor>.png, colors.conf, colors.gtk.css, colors.yaml, effects/, icons/), `current.json` written, `history.jsonl` gained exactly one line with `"trigger":"set"`, and every reloader invoked exactly once.
    - **Cache hit on repeat (FR-2):** run the full pipeline twice on the same image; assert fake csg/weg/itr call counters are ZERO on the second run while history gains a new line and symlinks are repointed again.
    - **Crash repair through the combined flow (2.2):** after a first full set, manufacture a stray `current/colors.gtk.css` symlink pointing at an old/wrong cache entry (simulating a mid-swap crash), then run a second full `wallpaper set`; assert the stray symlink was reverted to the new last-good state before/along the new swap (`_revert_stale_symlinks` at reconcile start) and the run completes. **Pin the transient revert, not just the final state** — a final-state-only assertion passes even with `_revert_stale_symlinks` disabled (an idempotent same-image set masks the missing revert). Assert a direct observable: the reconcile-start `recovery: reverted N stray symlink(s)` INFO log via `caplog` (mirroring `test_cli_crash_recovery.py:212`) or an `_EventRecorder` on the mutex/repo (TestReconcileMutex pattern). This is AC-3's whole story — a wrong-reason test is a review magnet (rt-2-6 litmus: pin literal premises, not surrogates).
    - **Reload failure surfaced:** use a `_FailingReloader` (or unwritable terminal sink) → `reconcile.reload_failures` contains the failing class name; assert the CLI path exits 1 (covered by Task 5 unit test + this integration proves the result threading). Use `tty_path`-style apply sinks so the test never touches `/dev/tty` or a live Hyprland.
    - **Monitors preserved (AD-18):** seed with a multi-monitor `monitors` dict (e.g. `DP-1` hyprpaper + `HDMI-1` swww), run a full set, assert backend/fit_mode/mpv_options are unchanged and only `source_hash` moved.
    - **Schema drift guard (recommended, closes adversarial-F1 review hole):** a golden-file assertion pinning the exact history line + current.json emitted by the combined `set` flow for a fixed input (seed from a fixture `tests/fixtures/wallpaper.png` + fixed fake-tool artifacts) — byte-for-byte vs a checked-in golden string, guarding AR-9 ("schemas must be written exactly").
  - [ ] **Live-host isolation (at most ONE real-composition exit-code test):** reserve exactly one real-composition `wallpaper set` CLI test for exit-code/R5 evidence, and PROACTIVELY monkeypatch all four reloader classes at their adapter modules (`monkeypatch.setattr("runtime.adapters.hyprland_reloader.HyprlandReloader", _Passing...)`, plus Ags/Hyprpaper/Terminal at the corresponding modules), extending the `test_cli_crash_recovery.py:153-206` isolation pattern — otherwise the command fires the live host's `hyprctl`, `ags`, and `/dev/tty`. NOTE: because the helper does `from runtime.adapters.<x> import <Reloader>` at call time, patching the adapter-module attribute is sufficient (mirrors the existing reconcile isolation). All other E2E coverage composes the use cases directly (bullet above); wiring itself is proven by the Task 5 unit test.

- [ ] Task 7 — Stale-scope + full green gate (AC: all)
  - [ ] `uv run --directory src/runtime pytest -q` → **≥ 385 passed, 2 skipped** (baseline; expect +new tests from this story)
  - [ ] `uv run --directory src/runtime ruff check src/runtime` → zero NEW (3 pre-existing: cli/main.py B008 ×2, domain/models.py E501)
  - [ ] `uv run --directory src/runtime ruff format --check src/runtime` → clean (new/edited files)
  - [ ] `uv run --directory src/runtime mypy --strict src/runtime` → zero NEW (4 pre-existing)
  - [ ] `tests/architecture/test_layering.py` green (changes are cli/application only; no new import categories, no domain/ports edits)

## Dev Notes

### Scope boundary — this story ONLY chains what already exists

This capstone fuses the Epic-1 derive/cache/persist path with the Epic-2 swap/reload path. It does NOT:
- write any new adapter, port, domain model, or derivation logic (all machinery ships from stories 1.x/2.1-2.6);
- reimplement the swap sequence — `ReconcileDesktopStateUseCase` is the SOLE swap owner (shared-data-contract swap sequence / AD-6); apply only "updates desired state and delegates the actual swap to Reconcile";
- change the `reconcile` command's behavior, the reload loop, `ReconcileResult`, `ApplyWallpaperResult`, or any reloader;
- add dependencies (`pyproject.toml` stays `typer` + `cli-output` only, Python ≥3.14);
- add CLI arguments (no new B008);
- implement Epic-3 scope (`inspect`/`status`/`history`/`cache` commands) or cache eviction (AR-10 stubs only).

### The orchestration design (this IS the deliverable decision)

**`wallpaper set` = apply → reconcile(trigger="set"), wired in the CLI composition root only.** Per AD-12 the pipeline is `ApplyWallpaperUseCase → ReconcileDesktopStateUseCase → generate missing artifacts → write configs → reload desktop → persist`. `ApplyWallpaperUseCase.run(img)` already derives + caches + persists `current.json`; `ReconcileDesktopStateUseCase.run()` already does cache-ensure → parent-first symlink repoint (wallpaper → palette → effects → icons, each atomic tmp+`os.replace`) → `current.json` → `history.jsonl` → reload loop (outside the lock, fire-and-report). The capstone is the seam that calls the second after the first and threads the combined result — nothing else.

- **Shared reloader helper:** extract `_build_reloaders(state_root)` in `cli/main.py` so `reconcile` and `wallpaper set` can never drift. Both commands must reload the IDENTICAL four consumers in deterministic order `[Hyprland, Ags, Hyprpaper, Terminal]`.
- **`run(trigger: str = "reconcile")`:** the minimal seam for history correctness. Default preserves standalone-reconcile semantics and the `"reconcile"` trigger test; the set flow passes `"set"`. Validate against `{"seed","set","reconcile","force"}` — the contract enum is pinned; `"apply"` is NOT a valid trigger.
- **Double mutex is deliberate:** apply holds the flock (load→save), reconcile holds it again (load→repoint→save). Sequential, matches AD-12, no deadlock, D1 double-checked re-load inside the lock is preserved. The apply pass derives OUTSIDE the mutex; the reconcile pass re-derives OUTSIDE too (cache-hit normally), so tool invocations never serialize with the swap critical section.
- **Combined CLI result:** a private `_WallpaperSetResult(apply, reconcile)` dataclass keeps the apply's per-layer cache-hit descriptors AND the reconcile's swap/reload data — the CLI renders both coherently, and exits 1 if `reconcile.reload_failures` is non-empty (exact `reconcile`-command pattern). Do not build a new application-layer orchestrator to merge them.

### Reuse — leverage existing infrastructure (do NOT duplicate)

- `ReconcileDesktopStateUseCase` (swap owner + `_revert_stale_symlinks` crash repair + `_ensure_entries` cache regeneration + `_assert_hash_matches` integrity guard + `_build_expected_targets` + monitor-name traversal guard) — use as-is, compose it.
- `ApplyWallpaperUseCase` (derive + cache + `current.json` persist, monitors preservation, palette hard-fail / effects+icons degrade) — use as-is.
- `CacheSeeder.append_history(trigger, ...)` (O_APPEND + O_NOFOLLOW + full-write loop + fsync, must-not-lose) — the ONLY history writer; call it through Reconcile, never directly from the CLI.
- The four reload adapters + `_Passing*` isolation stubs + `_make_reconcile`/`_setup_spine`/`_apply_state` test helpers — copy-paste convention is the house norm (shared-conftest refactor remains a pre-existing deferred item).
- The `reconcile` command's reload-failure exit block (`cli/main.py:373-384`) — replicate for `wallpaper set`; do not invent a new error path.

### Behavioral decisions & invariants (non-negotiable)

- **Swap order parent-first** (wallpaper → palette → effects → icons) and the full swap sequence are owned by Reconcile — the combined flow must not reorder or reimplement them.
- **History `trigger` enum `seed|set|reconcile|force`** — set flow = `"set"`, standalone reconcile = `"reconcile"`, seed = `"seed"`. Never `"apply"`. Appended BEFORE reload considered complete (AR-3); immutable lines, never rewritten. **Validation lives ONLY in `ReconcileDesktopStateUseCase.run(trigger=...)`** — `CacheSeeder.append_history` stays trigger-agnostic (enforced nowhere today; `test_seed_cache.py` writes `"apply"` through it deliberately).
- **Per-monitor configs preserved (AD-18):** `current.json.monitors` backend/fit_mode/mpv_options/ipc_socket untouched by a set; only `source_hash` updates. Default `{DP-1: hyprpaper/cover}` only when no state or empty monitors.
- **Crash repair is free:** reconcile's opening `_revert_stale_symlinks` gives the combined flow story-2.2 repair on the next run; re-running the interrupted set is a cache hit. Prove it with a test (Task 6).
- **Cache-hit guarantee:** apply AND reconcile both ensure entries; a repeat set is zero csg/weg/itr invocations in either pass — but history + repoint + reload still run (cache-hit is about TOOL invocation, not about skipping the swap). When asserting "zero invocations in both passes", count ONLY the fake csg/weg/itr adapter `.calls` counters: reconcile's content-verification read of the cached wallpaper (`hash_file`, reconcile.py:357) is a FILE READ, not a tool invocation — a confused agent counting hashes will fail the test wrong.
- **Reload failures = surfaced non-fatal-with-non-zero-exit (R5):** collect via `reload_failures`, report which consumer, exit 1, no daemon retry. Do NOT convert to skips.
- **No writes under the install spine post-seed (AD-5/AD-11):** all runtime writes go under `$XDG_STATE_HOME/dotfiles/`; spine inputs are READ-only (reads required every derivation — they are cache-key parts).
- **Keep ALL existing fail-fast guards:** corrupt/absent `current.json` → loud; palette hard-fail → abort without partial save; effects/icons degrade to `null`; hash-mismatch (`cache entry cannot be regenerated`) → `RuntimeError`; path-traversal monitor guard; stale-symlink revert + cleanup at reconcile start.

### Code style gates (enforced)

Python 3.14, `mypy --strict` (no untyped defs; `from __future__ import annotations` at top), ruff select E/F/I/N/W/UP/B (ignore B905), line-length 100, double quotes, parenthesized multi-except tuples (PEP 758). Timestamps `datetime.now(UTC).isoformat().replace("+00:00", "Z")`. House style: dense module docstrings citing AD-numbers/evidence, NO inline "why" comments, no new runtime dependencies. Do not add new `typer.Argument`/`typer.Option` (B008 — baseline already has 2 pre-existing; zero NEW is the bar).

### Previous story intelligence (rt-2-6 — the direct predecessor)

- **Reloader family is COMPLETE (stories 2.3-2.6)** — `reconcile.py` docstrings and each adapter's scope noted "rewire `wallpaper set` (Story 2.7 capstone)" as the open seam. This story closes every one of those notes.
- **rt-2-6 shipped the fourth reloader** `TerminalColorApplier(state_root=state_root)` (OSC 4/10/11/12 from `current/colors.yaml`, vacuous-True precedence, surfaced-failure TTY contract) and pinned 4-reloader wiring in `TestReconcileCompositionRootWiring` + `_PassingTerminalColorApplier` isolation in `test_cli_crash_recovery.py`. Its full review history (10 patch findings: parser fail-loud, wrong-reason tests, docstring overclaims, test gaps) is the quality bar — the capstone's new tests must pin literal premises, not surrogates, and docstrings must not overclaim.
- **rt-2-5 / rt-2-4 review lessons to apply proactively:** (1) composition-root wiring needs a POSITIVE test or a mis-wire passes green; (2) real-CLI tests reach LIVE host consumers through newly wired reloaders — isolate PROACTIVELY (rt-2-5 needed an unplanned deviation commit; `wallpaper set` now also fires Hyprland/AGS/Hyprpaper/`/dev/tty`, not just `reconcile`); (3) docstrings must cite only verified facts; (4) report accurate test counts in the Dev Agent Record.
- **Baseline suite (verified): 385 passed, 2 skipped.** Pre-existing lint debt: 3 ruff errors, 4 mypy errors — zero NEW is the bar.
- The apply path's `cache_hit_palette/effects/icons` reporting and monitors-preservation (`_build_monitors`) come from rt-1-13 — the combined CLI output must keep those descriptors.

### Git intelligence

HEAD = `dab6f3d` ("fix: auto-commit code review findings" — rt-2-6 review patch; clean tree). Story-2.6 implementation commit was `1050b10 feat(rt-2-6): terminal palette applier`; 2.5 was `0fc602f feat(rt-2-5):...`. Repo commit style: `feat(rt-2-x): <story description>` for implementation, `fix: auto-commit code review findings` for review patches, `docs:`/`chore:` for story-file + sprint-status updates (commit the story `.md` + `sprint-status.yaml` with the implementation). Every rt-2-6 commit touched `cli/main.py` composition root only for reloader wiring — this capstone follows the same composition-root-only pattern, NOT an application-layer merge.

### Latest technical information

No new external dependencies or versions — stdlib + `typer` + `cli-output` only. The swap channel facts are all RESOLVED and embedded in the existing adapters (Hyprland `hyprctl reload`; AGS restart — no native hot-reload, `cli/cmd/run.go:145`; Hyprpaper per-monitor IPC `hyprctl hyprpaper wallpaper <monitor>,<path>[,<fit>]` verified hyprpaper 0.8.4 / hyprland 0.56.2; terminal OSC from `current/colors.yaml`). Do NOT re-research or second-guess them; do not bump pinned toolchain (Python 3.14, typer ≥0.12, pytest ≥8.0, ruff ≥0.15.17, mypy ≥1.10).

### Testing standards summary

- Runner: `uv run --directory src/runtime pytest -q`. Unit tests = pure fakes/isolated composition wiring; integration = REAL filesystem (`tmp_path`), real `JsonStateRepository`/`CacheSeeder`/`FlockSeedMutex`, fake csg/weg/itr (contract-honest, write real artifacts, `calls` counters), compose use cases DIRECTLY (never via CLI in integration).
- Structural pins that constrain this story: `TestReconcileStructuralScopeLock` (init params — don't add ctor params), `TestReconcileCompositionRootWiring` (4-reloader list for reconcile), `TestReconcileHistory.test_history_line_schema` (trigger `"reconcile"` default), `test_cli_crash_recovery.py` (real composition root → MUST isolate reloaders before any real-composition `wallpaper set` test), `tests/architecture/test_layering.py` (clients: `cli→all`, `application→domain,ports,adapters,application`; forbidden cross-package set unchanged; no route from `cli` importing a forbidden package).
- Assertion style: unit tests pin behavior + contracts (trigger values, exit codes, wiring introspection); integration tests assert filesystem/symlink/history outcomes and `reload_failures` end-to-end; the golden-file check pins byte shape (AR-9).

### Project Structure Notes

New files (expected):
- `src/runtime/src/runtime/cli/main.py` — MOD (composition-root chain + `_build_reloaders` + combined result + reload-failure exit)
- `src/runtime/src/runtime/application/reconcile.py` — MOD (`run(trigger=...)` seam + docstring; scope comment refresh)
- `src/runtime/src/runtime/application/apply_wallpaper.py` — MOD (docstring/scope-header refresh only)
- `src/runtime/tests/unit/test_cli_wallpaper_set.py` — MOD (fakes → `_WallpaperSetResult`, reload-failure exit, wiring test)
- `src/runtime/tests/unit/test_reconcile.py` — MOD (trigger param tests)
- `src/runtime/tests/integration/test_wallpaper_set_capstone_integration.py` — NEW (E2E capstone integration)

No changes: `domain/`, `ports/`, all adapters, `seeder.py`, `json_state_repository.py`, `pyproject.toml`, `dotfiles/config/**`, provisioning.

### References

- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md` — Story 2.7 ACs (lines 414-426), FR-1/FR-2/FR-3/FR-6, AD-18 monitors, R5; Epic-2 overview; Story 2.1 AC4 (capstone owns orchestration), Story 1.13 AC6, Story 2.2 crash recovery, Stories 2.3-2.6 seam notes.
- Architecture spine: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md` — AD-1 layering, AD-6 (swap ownership + sequence), AD-8 hashing, AD-12 (pipeline ordering), AD-5/AD-11 (state_root/spine), AD-17 (consumer wiring), AD-18 (per-monitor backends), AD-15 (cross-package boundary = what older docs call NFR-9).
- Shared data contract: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md` — swap sequence (owner `ReconcileDesktopStateUseCase`, order cache-ensure → repoint → current.json → history → reload), `history.jsonl` trigger enum `seed|set|reconcile|force`, current.json schema v2, AR-9 "must be written exactly".
- Spec: `_bmad-output/specs/spec-dotfiles-runtime-phase2/SPEC.md` — CAP-1/CAP-3/CAP-6, success signal ("derive palette + effects + icons ... repoint current/ symlinks, reload Hyprland/AGS/Hyprpaper/terminal, persist current.json + history.jsonl line — all synchronously"), FR-2 cache-hit (re-selecting a previously-used wallpaper = cache hit).
- Readiness: `_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-24.md` — FR-1/FR-3/FR-6 coverage → 2.7; dependency chain 2.1→2.2→2.3-2.6→2.7 "capstone orchestrates all"; history.jsonl written by the 2.7 capstone.
- Existing code: `src/runtime/src/runtime/cli/main.py` (`_run_wallpaper_set` 175-207, `wallpaper_set` 233-292, `_run_reconcile` 295-337, `reconcile` 340-408), `src/runtime/src/runtime/application/reconcile.py` (`run()` 121+, `append_history` 249), `src/runtime/src/runtime/application/apply_wallpaper.py`, `src/runtime/src/runtime/adapters/{hyprland,ags,hyprpaper}_reloader.py`, `terminal_color_applier.py`, `CacheSeeder.append_history` (seeder.py), `tests/unit/test_cli_reconcile.py` (wiring test pattern), `tests/unit/test_cli_crash_recovery.py` (isolation pattern), `tests/unit/test_reconcile.py` (structural scope lock + history schema).
- Previous stories: `_bmad-output/implementation-artifacts/rt-2-6-terminal-palette-applier.md` (direct predecessor — reloader-family completion, review lesson lists, isolation pattern), `rt-2-5-hyprpaper-channel-verification.md`, `rt-2-1-atomic-symlink-repoint.md` (swap sequence + reconcile command contract), `rt-1-13-applywallpaperusecase.md` (apply contract + cache-hit reporting).

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Debug Log References

- Baseline verified at story creation: `uv run --directory src/runtime pytest -q` → 385 passed, 2 skipped.
- `ruff check src/runtime` → 3 errors (all pre-existing: cli/main.py B008 ×2, domain/models.py E501); zero NEW is the bar.
- `mypy --strict src/runtime` → 4 errors (all pre-existing; 34 source files).
- Layering gate: `tests/architecture/test_layering.py` (937 lines) — green at baseline.

### Completion Notes List

- [ ] (to be filled by the implementing dev agent)

### File List

- (to be filled by the implementing dev agent)

## Change Log

- 2026-09-02 — Story created (ready-for-dev) with the capstone seam pinned: apply→reconcile(trigger="set") composition-root chain, shared `_build_reloaders` helper, `run(trigger=...)` seam validated against the `seed|set|reconcile|force` enum, `wallpaper set` reload-failure exit mirroring the `reconcile` command, monitors-preservation guarantee, crash-repair-free via 2.2, and the mandatory tests (reload-failure exit, wiring positive test, history trigger, E2E full-pipeline integration, cache-hit-on-repeat, crash-recovery-through-set, golden-file schema guard). Baseline: 385 passed, 2 skipped.
- 2026-09-02 — Independent validation pass (fresh-context adversarial review, code-fact + requirements-coverage checkers). All code facts verified live (cl/main.py/reconcile.py line refs, structural pins, 385/2 passed, ruff 3 pre-existing, mypy 4 pre-existing). Findings applied: stale `cli/main.py:257-261` cite corrected to 238-244 (:242-243); `TestReconcileCompositionRootWiring` range corrected to 141-177; crash-repair test now must pin the transient revert (caplog "recovery: reverted N stray symlink(s)" / `_EventRecorder`) — a final-state-only assertion would be a wrong-reason test; enum validation scoped to `run()` ONLY (seeder stays trigger-agnostic — `test_seed_cache.py` writes `"apply"`); cache-hit assertion scoped to csg/weg/itr `.calls` counters (reconcile's `hash_file` is a read, not a tool call); live-host isolation limited to one real-composition exit-code test.