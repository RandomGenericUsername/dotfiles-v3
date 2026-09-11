# Story 4.3: Actual-State Projection (Pure)

Status: ready-for-dev

baseline_commit: a8333ed

Epic: Phase 4 Epic 2 — Declarative State (`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase4.md`)

## Story

As the future diff engine,
I want a single pure projection of everything the desktop has actually got,
so that desired-vs-actual comparison reads one value object instead of four adapters.

## Acceptance Criteria

1. `ActualState` frozen dataclass carries `{current_wallpaper, monitors, prunable_hashes, pinned_hashes, undated_hashes}`: `current_wallpaper` is `source_path` or `None` (never derived); `monitors` is the sorted monitor-name tuple; `pinned_hashes`/`undated_hashes` are sorted flat tuples; `prunable_hashes` is per-layer `dict[str, tuple[str, ...]]` mirroring `PrunePlan.removals` shape (AC 1)
2. `build_actual_state(current, entries_for, seed_pins, keep=5)` is pure (no I/O, no repo access): `current` is an already-loaded `DesktopState | None`; `entries_for`/`seed_pins` are the same injected-callable shapes `PruneUseCase` takes; `keep` mirrors the `PruneUseCase` default and is validated the same way (`keep < 0` → `ValueError`) (AC 2)
3. Prune policy has exactly one source: `prunable_hashes` is computed by delegating to `PruneUseCase(...).run()` (default `prune_pinned=False`), never by re-implementing active/last-N/seed-pin/undated rules (AC 3)

## Tasks / Subtasks

- [ ] Add `ActualState` frozen slots dataclass to `src/runtime/src/runtime/domain/models.py` (AC: 1)
  - [ ] Fields: `current_wallpaper: str | None`, `monitors: tuple[str, ...]`, `prunable_hashes: dict[str, tuple[str, ...]]`, `pinned_hashes: tuple[str, ...]`, `undated_hashes: tuple[str, ...]`. Sorting/canonicalization happens in the builder, not the model — the model is a dumb carrier (document this on the class).
  - [ ] stdlib allowlist only; no I/O imports.
- [ ] Create `src/runtime/src/runtime/application/actual_state.py` (AC: 2, 3)
  - [ ] `build_actual_state(current, entries_for, seed_pins, keep=5) -> ActualState`: `current is None` → `current_wallpaper=None`, `monitors=()` (fresh machine — actual is empty, not an error); otherwise `current_wallpaper=current.wallpaper.source_path`, `monitors=tuple(sorted(current.monitors))`.
  - [ ] `pinned_hashes` = sorted union of `seed_pins()` across layers; `undated_hashes` = sorted union of `ref.entry_hash` for refs with `timestamp is None` across all four layers (call `entries_for(layer)` once per layer and reuse the results for both undated and prunable — no double listing).
  - [ ] `prunable_hashes`: needs a state repo for `PruneUseCase`, but this function takes loaded `current`, not a repo — wrap it in a minimal inline `IStateRepository` stub whose `load_current()` returns `current` (check the interface in `ports/state_repository.py`; implement only what `PruneUseCase` touches — `load_current` — and raise `NotImplementedError` on the rest, documented as projection-only). Then `PruneUseCase(repo_stub, entries_for, seed_pins, keep).run().removals`.
  - [ ] `keep` validation: delegate to `PruneUseCase` (it raises on `keep < 0`) — do not pre-validate (one source for the rule, matching AC 3).
- [ ] Create `src/runtime/tests/unit/test_actual_state.py` (AC: 1, 2, 3)
  - [ ] Mirror the `_desktop_state` helper shape from `tests/unit/test_cli_check_inputs.py:148` for fixtures (wallpaper + monitors + palette/effects/icons entries).
  - [ ] `current=None` → empty projection (`None` wallpaper, empty monitors) with entries still classified (pins/undated/prunable computed from the injected callables alone).
  - [ ] Full state → exact `ActualState` (wallpaper path, sorted monitor names, sorted flat pins/undated, per-layer prunable matching an independent `PruneUseCase(...).run().removals` on the same fakes — locks the single-source rule).
  - [ ] `entries_for` call count: at most once per layer (no double listing — assert with a counting fake).
  - [ ] `keep < 0` → `ValueError`; `keep=0` → dated all prunable except active/pinned/undated (mirrors prune semantics).
  - [ ] Purity: no I/O imports in `application/actual_state.py` beyond the adapter-provided callables (covered by layering test — run it).
- [ ] Run `uv run --directory src/runtime pytest tests/unit/test_actual_state.py tests/architecture/test_layering.py` and confirm green

## Dev Notes

### Scope boundary — projection ONLY

Story 4.3 builds the actual-side value object. It does **NOT** implement:
- Loading `current` from disk inside the builder (caller supplies it — disk wiring is Epic 3 CLI scope)
- The diff engine or planner (p4-3-1 / p4-3-2)
- Any new port (the `IStateRepository` stub is projection-local; a real wiring decision belongs to Epic 3)
- Any change to existing commands, `PruneUseCase`, or `DesiredState`

### Layering (AD-25, locked)

- `ActualState` in `domain/` (pure); builder in `application/` (pure orchestration over injected callables — same pattern as `PruneUseCase`, which also does no I/O)
- `test_layering.py` is the mechanical gate — run it, do not modify it

### Conventions consumed (do not redefine)

1. `PruneUseCase` injection shapes (`entries_for(layer)`, `seed_pins()`) — reuse exactly, so Epic 3 can pass the same adapter callables to both.
2. `LAYERS` canonical order from `application/prune.py` — import it, do not redeclare.
3. Sorted/deterministic collection outputs (repo-wide snapshot-testability rule).
4. `keep=5` default mirrors `PruneUseCase`; the desired-state `keep` overrides it at the Epic 3 call site (AD-30).
