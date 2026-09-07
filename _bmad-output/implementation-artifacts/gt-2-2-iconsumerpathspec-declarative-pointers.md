---
baseline_commit: 47d23cb
---

# Story 2.2: `IConsumerPathSpec` — declarative consumer pointers

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want the consumer-pointer table as contract data driving a single adapter loop,
So that adding a consumer (rofi, dunst, wlogout) is a spec entry, never bespoke code.

## Acceptance Criteria

### Verbatim contract (epics-gtk-theming.md, Story 2.2)

**Given** the pinned ConsumerPointer table in `shared-data-contract.md` (ags/gtk-3.0/gtk-4.0 entries + rules)
**When** `IConsumerPathSpec` (ports) exposes the table and `CacheSeeder.repoint_consumer_symlinks` consumes it generically
**Then** each pointer follows the rules: palette null → pointer removed (`missing_ok`); regular file at destination → replaced with symlink; missing target artifact → skip + warn (never dangling)
**Then** — additionally — the AGS behavior is byte-compatible with today's (P2 migration preserved)
**And** doctor and `inspect status` report the new pointers (ok/missing/diverged/dangling) without bespoke per-consumer code
**And** no new writes under the install spine beyond the spec'd pointers (AD-11 exception class, NFR-2); layering test green

### Operational sub-ACs (dev contract — derived from the verbatim block + the investigation §3 table)

1. **Given** `src/runtime/src/runtime/domain/models.py`, **When** the consumer-pointer contract data is modeled, **Then** two new frozen dataclasses appear — `ConsumerPointer(path: str, target: str)` (both plain `str`, posix-relative: `path` relative to the install spine, e.g. `"config/ags/colors.css"`; `target` relative to `current/`, e.g. `"colors.gtk.css"`) and `ConsumerPointerRules(remove_on_null_palette: bool, replace_regular_file: bool, skip_on_missing_target: bool, skip_on_missing_parent: bool)` (all defaults `True`) — pure data, zero I/O, no new imports (domain purity allowlist intact) (AC: verbatim "Given the pinned ConsumerPointer table … + rules").

2. **Given** `src/runtime/src/runtime/ports/`, **When** the new port is added, **Then** `ports/consumer_path_spec.py` holds `IConsumerPathSpec(ABC)` with exactly two abstract methods — `consumer_pointers() -> tuple[ConsumerPointer, ...]` and `rules() -> ConsumerPointerRules` — mirroring the repo ABC conventions (`ports/state_repository.py` pattern: no concrete logic, no imports beyond `abc` + `runtime.domain.models`); `ports/__init__.py` re-exports it (AC: verbatim "When IConsumerPathSpec (ports) exposes the table").

3. **Given** `src/runtime/src/runtime/adapters/consumer_path_spec.py` (NEW), **When** the pinned table is implemented, **Then** `StaticConsumerPathSpec` returns EXACTLY the three investigation §3 entries in this order — `{path: "config/ags/colors.css", target: "colors.gtk.css"}`, `{path: "config/gtk-3.0/colors.css", target: "colors.gtk.css"}`, `{path: "config/gtk-4.0/colors.css", target: "colors.adw.css"}` — plus the default `ConsumerPointerRules()`; this table is contract data shared with gt-4.2's `shared-data-contract.md` wording (coordinate in Dev Notes) (AC: verbatim "Given … (ags/gtk-3.0/gtk-4.0 entries + rules)").

4. **Given** `adapters/seeder.py` `CacheSeeder.repoint_consumer_symlinks` (lines 585-643), **When** the loop runs, **Then** it iterates the injected spec generically — for each `ConsumerPointer`: `dest = install_spine / pointer.path`, `target = state_root / "current" / pointer.target`, and applies the rules read from `spec.rules()`: (a) palette `None` → every existing pointer dest removed (`unlink(missing_ok)` semantics; existing pointer removed with the same warning tone as today's "palette layer is null; … removed"), (b) a regular FILE at dest → replaced with the symlink (the existing `_repoint_symlink` tmp + `os.replace` already does this — never delete-then-create), (c) `current/<target>` absent (neither file nor symlink) → skip + warn, NEVER a dangling consumer link, (d) `dest.parent` not an existing directory → skip + warn, NEVER `mkdir` under the install spine, NEVER a crash (the pre-gt-3-1 case: `config/gtk-3.0/` and `config/gtk-4.0/` don't exist until Story gt-3-1 provisions them) (AC: verbatim "Then each pointer follows the rules …").

5. **Given** the AGS pointer specifically, **When** the loop runs on a provisioned machine (`config/ags/` exists), **Then** the behavior is BYTE-COMPATIBLE with today's hardcoded code — same dest (`<install>/config/ags/colors.css`), same target (`current/colors.gtk.css`), same null-palette removal (`missing_ok`), same stale-file replacement on one run, same skip+warn on missing `current/colors.gtk.css` — and the existing tests' assertions on it keep passing (only the mechanism changes, not the observable outcome) (AC: verbatim "Then — additionally — the AGS behavior is byte-compatible with today's").

6. **Given** the four `CacheSeeder(...)` construction sites in `cli/main.py` (lines 126, 266, 278, 439), **When** the composition root is updated, **Then** it passes the spec explicitly (`CacheSeeder(state_root, consumer_spec=StaticConsumerPathSpec())`); the constructor signature is `def __init__(self, state_root: Path, consumer_spec: IConsumerPathSpec | None = None)` with a `None` fallback to a module-default `StaticConsumerPathSpec()` so the 87 direct `CacheSeeder(state_root)` test constructions keep compiling and behaving identically (byte-compat + minimal blast radius); `seed_cache.py` and `reconcile.py` call sites (`seed_cache.py:236-239`, `reconcile.py:247-250`) are signature-unchanged — VERIFY ONLY (AC: verbatim "When … CacheSeeder.repoint_consumer_symlinks consumes it generically").

7. **Given** `application/inspect.py` + `cli/main.py` (`_run_inspect_status`, lines 523-540), **When** `inspect status` runs, **Then** `InspectStateUseCase` projects the spec'd spine pointers ADDITIVELY — a new `consumer_pointers: dict[str, LinkStatus]` field on `InspectStatusResult` (keyed by the spine-relative `pointer.path`, values reusing the existing `LinkStatus`/ok-missing-diverged-dangling vocabulary), populated ONLY when `state.palette is not None` (a null palette omits the pointers entirely, mirroring `_build_expected_targets`' palette branch) and ONLY when the use case was constructed with an install spine + spec (both optional constructor args, `None` = projection omitted — read-only invariant AC 4 preserved); `current_symlinks` and the plain-text summary stay untouched except an additive pointer-count suffix if the CLI summary grows; the CLI passes `_resolve_install_spine()` and the spec at `_run_inspect_status` (AC: verbatim "And doctor and `inspect status` report the new pointers (ok/missing/diverged/dangling) without bespoke per-consumer code" — doctor interpretation pinned in Dev Notes; no doctor command exists in the runtime, so the coverage mechanism is the spec-driven projection a future doctor reuses, surfaced today through `inspect status`).

8. **Given** the AD-11 spine-write guard tests, **When** seed/reconcile run, **Then** the ONLY spine writes are the spec'd pointer symlinks — `test_seed_cache.py::TestNothingWrittenToInstallSpine` (lines 805-833) and `test_seed_cache_integration.py::test_install_spine_unmodified_except_r2_symlink` (lines 235-256) are updated from "allowed = ags symlink + created parents" to "allowed = exactly the spec'd pointer paths that exist" (parents are NEVER created anymore — the `allowed` dir entries are removed and `_setup_install_spine` (line 220-245) gains `config/ags/` (and, in dedicated new-pointer tests, `config/gtk-3.0/` + `config/gtk-4.0/`) to reflect provisioned reality (AC: verbatim "And no new writes under the install spine beyond the spec'd pointers (AD-11 exception class, NFR-2)").

9. **Given** the layering + gates contract, **When** the story lands, **Then** `tests/architecture/test_layering.py` passes with zero new violations (new port is a pure ABC; `_PORTS_ALLOWED_AGGREGATES` (line 137-138) stays EMPTY — the spec returns domain dataclasses, never defines its own); `ReconcileResult.consumer_symlinks` (reconcile.py:80-84) keeps its contract (list of actually-repointed pointer paths, separate from `repointed`) and now naturally carries up to 3 entries — CLI `consumer link(s)` counts grow additively, NOT an AR-3 violation (AR-3 pins `cache list` output, history schema, swap order — all untouched); full gate suite green at the documented baseline (AC: verbatim "And … layering test green").

## Tasks / Subtasks

- [ ] Task 1 — Domain: contract data models (AC: 1)
  - [ ] `src/runtime/src/runtime/domain/models.py`: add `ConsumerPointer` and `ConsumerPointerRules` frozen dataclasses (style: `@dataclass(frozen=True, slots=True)`, placed near `PaletteArtifacts`/`PaletteEntry`). Docstrings cite the investigation §3 table and the gt-4.2 contract pin. No imports added; no other model touched.
  - [ ] Verify domain purity: both are plain dataclasses — no `os`/`pathlib` (layering allowlist intact).

- [ ] Task 2 — Port: `IConsumerPathSpec` (AC: 2)
  - [ ] NEW `src/runtime/src/runtime/ports/consumer_path_spec.py`: pure ABC, two abstract methods (`consumer_pointers`, `rules`), docstring pinning the table's canonical home (`shared-data-contract.md` ConsumerPointer table, authored in gt-4.2) and the AD-11 exception-class reference (ARCHITECTURE-SPINE AD-11).
  - [ ] `src/runtime/src/runtime/ports/__init__.py`: re-export `IConsumerPathSpec` in imports + `__all__`.
  - [ ] Confirm `tests/architecture/test_layering.py` ports rules pass for the new file (imports only `abc` + `runtime.domain.models`).

- [ ] Task 3 — Adapter: pinned spec table (AC: 3)
  - [ ] NEW `src/runtime/src/runtime/adapters/consumer_path_spec.py`: `StaticConsumerPathSpec(IConsumerPathSpec)` returning the 3-entry tuple (ags → colors.gtk.css; gtk-3.0 → colors.gtk.css; gtk-4.0 → colors.adw.css) and default rules. Module docstring notes: adding a consumer = one spec line + its `@import` (never adapter code); gtk-{3,4}.0 pointer paths target `{install}/config/gtk-{3,4}.0/colors.css` — the spine dirs arrive in gt-3-1, until then the loop's missing-parent rule keeps them skip+warn.
  - [ ] Grep-verify NO other module hardcodes the AGS path after this story (`config/ags/colors.css` survives only in the spec table + tests asserting behavior).

- [ ] Task 4 — Seeder: generic loop (AC: 4, 5)
  - [ ] `src/runtime/src/runtime/adapters/seeder.py`:
    - Constructor (line 108-109): add `consumer_spec: IConsumerPathSpec | None = None` (keyword-or-positional compatible with `CacheSeeder(state_root)` call sites); `None` → `StaticConsumerPathSpec()` module default. Import the port + default adapter (adapters→ports/domain imports are legal).
    - `repoint_consumer_symlinks` (lines 585-643): replace the hardcoded AGS block with the generic loop over `self._consumer_spec.consumer_pointers()`; keep the method name, signature, `list[Path]` return (actually created/updated paths only), and the existing docstring's AD-11 note (update it to cite the spec class + the three pointers). Rules are read ONCE via `self._consumer_spec.rules()`; the loop implements the semantics.
    - Null-palette branch: iterate ALL pointers, remove existing dests (`missing_ok`), collect nothing into the result, warn-logged per removal (match today's message shape: `"seeding: palette layer is null; consumer symlink removed: %s"`).
    - Parent guard: `if not dest.parent.is_dir(): logger.warning(...skipped: parent missing...); continue` — placed BEFORE any `_repoint_symlink` call (its line-64 `mkdir(parents=True)` must never fire for consumer pointers).
    - Target guard: `if not (self._state_root / "current" / p.target).exists() and not .is_symlink(): skip + warn` (mirror today's `"current/colors.gtk.css missing, R2 consumer symlink skipped"`).
    - Regular-file replacement: rely on `_repoint_symlink`'s `os.replace` (tmp symlink replaces the file atomically) — do NOT pre-unlink.
    - Keep the "Deliberately NOT covered" docstring paragraph (hypr colors.conf, hyprpaper, ITR) accurate.
  - [ ] `repoint_current_symlink` / `repoint_current_symlinks` (current/ loops): UNTOUCHED.

- [ ] Task 5 — Wiring: composition root + verify-only flows (AC: 6)
  - [ ] `src/runtime/src/runtime/cli/main.py`: import `StaticConsumerPathSpec` alongside the other adapter imports in each lazy-import block; pass `consumer_spec=StaticConsumerPathSpec()` at the 4 construction sites (lines 126, 266, 278, 439).
  - [ ] VERIFY ONLY (no edit expected): `application/seed_cache.py` (call at 236-239), `application/reconcile.py` (call at 247-250), `application/apply_wallpaper.py` (no consumer repoint), `application/derive.py` — signatures unchanged because the spec lives inside the seeder.

- [ ] Task 6 — Inspect status: additive pointer projection (AC: 7)
  - [ ] `src/runtime/src/runtime/application/inspect.py`:
    - `InspectStateUseCase.__init__`: add optional `install_spine: Path | None = None` and `consumer_spec: IConsumerPathSpec | None = None` (application→ports/domain imports legal; NO adapter import — the spec instance is injected).
    - `run()`: when `state.palette is not None` AND both optional args are present, build `consumer_pointers` via a new read-only `_inspect_consumer_pointers(state)` method: for each spec pointer, `dest = install_spine / pointer.path`, `expected = state_root / "current" / pointer.target`, classify with the SAME status semantics as `_link_status` (ok = resolves to expected; dangling = symlink to nonexistent target; diverged = resolves elsewhere; missing = no symlink, INCLUDING the absent-parent pre-gt-3-1 case — never crash, never follow a spine dir that doesn't exist). Reuse `LinkStatus`/`LinkStatusKind` and `_raw_target`; do NOT touch `_link_status`/`current_symlinks` logic.
    - `InspectStatusResult` (lines 117-128): add `consumer_pointers: dict[str, LinkStatus]` (default empty dict for backward-compat constructions — check test constructors; `slots` dataclass field ordering: give it a default LAST).
    - Module docstring (lines 13-25): name the spec-driven pointer projection + the doctor note.
  - [ ] `src/runtime/src/runtime/cli/main.py` `_run_inspect_status` (lines 523-540): pass `install_spine=_resolve_install_spine()` and `consumer_spec=StaticConsumerPathSpec()`; `inspect_status` command renderer (lines 574-600): add the additive `"consumer_pointers": {path: {"status": …, "target": …}}` object key (plain summary may gain an additive pointer count — existing summary wording for `current_symlinks` unchanged).
  - [ ] Read-only invariant: the projection performs only `Path` reads — no mkdir, no unlink, no repoint (grep-verify no write call in the new code path).

- [ ] Task 7 — Tests: spec loop, statuses, spine guard, fixtures (AC: 4, 5, 7, 8)
  - [ ] `tests/unit/test_seed_cache.py`:
    - `_setup_install_spine` (line 220-245): add `(install_spine / "config" / "ags").mkdir(parents=True, exist_ok=True)` (provisioned-machine reality; the no-mkdir rule now requires it).
    - `TestNothingWrittenToInstallSpine::test_install_spine_unmodified_except_r2_symlink` (805-833): `allowed` = exactly the ags pointer path (no dir entries; assert the gtk pointers were NOT created — parents absent).
    - `TestR2ConsumerSymlink` (836-865): keep both tests green unchanged (byte-compat proof); ADD a `TestConsumerPointerSpec` class covering: (a) all 3 pointers created when `config/gtk-3.0/` + `config/gtk-4.0/` exist (targets: ags + gtk-3.0 → `current/colors.gtk.css`; gtk-4.0 → `current/colors.adw.css`); (b) gtk pointers skip+warn when their parent dirs are absent (pre-gt-3-1), ags still created, no crash, no dirs created; (c) regular file at gtk-3.0 dest replaced with symlink; (d) missing `current/colors.adw.css` skips only the gtk-4.0 pointer (per-pointer guard, not all-or-nothing); (e) null palette removes ALL existing pointers (ags + gtk), `missing_ok`, empty result list; (f) re-run idempotent (same 3 paths, no divergence).
  - [ ] `tests/unit/test_reconcile.py`: `TestReconcileHappyPath::test_repoints_all_consumer_symlinks_with_cache_targets` (318-362) — fixture gains `config/ags/` (+ gtk dirs in a dedicated test); assertion grows to the 3-pointer set when parents exist, and `test_null_palette_removes_r2_consumer_symlink` (489-516) grows to assert all spec'd pointers removed. `_SpySeeder`-based delegation test (381-405) unchanged.
  - [ ] `tests/unit/test_inspect.py`: NEW consumer-pointer status tests — ok (symlink resolves to `current/<target>`), missing (dest absent / parent absent), diverged (symlink to a wrong path), dangling (symlink to a deleted target), null-palette omission, and `consumer_spec=None` → field empty (backward-compat).
  - [ ] `tests/unit/test_cli_inspect_status.py`: additive `consumer_pointers` serialization assertion (JSON view carries status+target per pointer path; absent-spec path renders empty dict).
  - [ ] VERIFY ONLY (constructor compat, default spec — touch ONLY if a consumer-symlink assertion exists): `tests/unit/test_apply_wallpaper.py`, `test_crash_recovery.py`, `test_cli_crash_recovery.py`, `test_cli_reconcile.py`, `test_cli_wallpaper_set.py`, `test_terminal_color_applier.py`, `test_hyprland_reloader.py`, `test_hyprpaper_reloader.py`, `test_ags_reloader.py`, `test_cache.py`, `test_find_default_effects_catalog.py` (all construct `CacheSeeder(state_root)` — the default-spec fallback keeps them compiling/behaving).
  - [ ] Integration: `test_seed_cache_integration.py` (`_setup` gains `config/ags/`; spine-guard test updated per AC 8; NEW gtk-pointer assertions in the seed path); `test_reconcile_integration.py` (fixture + consumer coverage); `test_inspect_integration.py` (pointer statuses end-to-end with a real spine layout); VERIFY ONLY: `test_apply_wallpaper_integration.py`, `test_crash_recovery_integration.py`, `test_wallpaper_set_capstone_integration.py`, `test_terminal_color_applier_integration.py`, `test_hyprpaper_reloader_integration.py`, `test_hyprland_reloader_integration.py`, `test_ags_reloader_integration.py`, `test_inspect_cache_list_integration.py`, `test_inspect_history_integration.py`.
  - [ ] `tests/architecture/test_layering.py`: expect green with zero edits; if the ports classifier flags the new ABC, fix the port (never weaken the test).

- [ ] Task 8 — Full green (AC: 9)
  - [ ] Run and require green (no test runs are part of story CREATION — this task list is for the dev agent):
    ```bash
    uv run --directory src/runtime pytest -q
    uv run --directory src/runtime pytest tests/architecture/test_layering.py -v
    uv run --directory src/runtime ruff check .
    uv run --directory src/runtime ruff format --check .
    uv run --directory src/runtime mypy --strict src/runtime
    ```
  - [ ] Record gate results at baseline FIRST (`git stash` trick from gt-2-1): ruff check = 104 pre-existing errors in tests, ruff format --check = 26 pre-existing files, mypy --strict = 4 pre-existing errors (FitMode/StrEnum py314 + missing cli_output stubs). Post-implementation must be EXACTLY at baseline — zero new violations, never `# type: ignore`.
  - [ ] AR-3 byte-compat guard: history 7-field schema, `inspect cache list` shape, swap order, and the `current/` name sets are unchanged; only consumer-pointer counts grow.

## Dev Notes

### Scope boundary — this story is the SPEC + GENERIC LOOP only

Story gt-2-2 turns the hardcoded AGS repoint into contract-driven data and extends the health projection. It does **NOT** implement:

- **Contract-doc text** — `shared-data-contract.md` ConsumerPointer table wording is **gt-4.2's**, and gt-4.2 SHARES this story's table (AR-1: "adding a consumer = spec entry + `@import`, no adapter code change"). Coordinate the wording NOW so 4.2 transcribes instead of re-decides: the canonical table = the 3 entries + 4 rules exactly as pinned in Task 3 / investigation §3; ARCHITECTURE-SPINE AD-11's "Epic 4 exception (R2 consumer symlink)" paragraph is amended by 4.2 to reference the spec'd pointer class. This story amends the runtime behavior ahead of the doc pin (same precedent as gt-2-1 vs. the artifact-set doc).
- **Provisioning spine dirs** — `config/gtk-3.0/` + `config/gtk-4.0/` skeletons, backup-guard migration, `config_links`, `~/.config/gtk-{3,4}.0` symlinks are **gt-3-1**. Until then the gtk pointers skip+warn on the missing destination parent (sub-AC 4d) — they must never crash, never mkdir into the spine, and never exist as dangling links.
- **`TerminalColorApplier` artifact switch** (reading `current/colors.sequences` bytes) — Story 2.3. The applier is untouched here.
- **Prune / future doctor command** — investigation §3 says "Doctor, `inspect status`, and (Phase 3) prune inherit coverage for free" — this story delivers the spec-driven mechanism; Phase 3 prune and any doctor command simply consume the same projection.

### The doctor question (interpretation pinned — raise in review)

**No `doctor` command exists anywhere in the runtime or provisioning code** (verified: `grep -rn doctor` over `src/`, `dotfiles/`, specs — zero source hits; runtime CLI = version / wallpaper set / reconcile / inspect status / history / cache list). The epics AC clause "doctor and `inspect status` report the new pointers" is therefore interpreted as: the pointer-status projection must be spec-driven and REUSABLE — surfaced today through `inspect status` (the only existing health surface), so a future doctor inherits coverage by consuming the same projection without bespoke per-consumer code. The investigation's actor table ("runtime application/cli — zero new use cases") forbids inventing a doctor use case in this story. If review or gt-4.2 disagrees, the follow-up is a new story, not scope creep here.

### Design decision 1 — rules as typed data, semantics implemented once

The spec exposes BOTH the table and the rules (`ConsumerPointerRules` flags), but the loop in `repoint_consumer_symlinks` implements the rule SEMANTICS exactly once and reads the flags from the spec — there is deliberately no per-pointer rule variation in the pinned table (all four flags default True). This keeps "adding a consumer = one spec line" true while making the rules contract-visible rather than buried in loop code. Do not add per-pointer rule overrides (YAGNI; revisit only when a real consumer needs different semantics).

### Design decision 2 — skip+warn on missing destination parent (no spine mkdir)

`_repoint_symlink` (seeder.py:55-74) calls `current_path.parent.mkdir(parents=True, exist_ok=True)` — correct for `current/` links (runtime-owned), wrong for spine pointers pre-gt-3-1: creating `config/gtk-3.0/` under the install spine would (a) write beyond the spec'd pointers (violates the AC-8 spine guard), and (b) pre-empt gt-3-1's provisioning of those dirs (backup guard, skeleton files). Hence the generic loop checks `dest.parent.is_dir()` FIRST and skips+warns. Consequences pinned here:

- The AGS pointer's parent-creation behavior changes on a machine where `config/ags/` is absent — but every machine provisioned by this repo has it (provisioning deploys the AGS config; R2 replaces a provisioning copy), so the observable AGS behavior is preserved (sub-AC 5). This is the ONE deliberate deviation from today's code; it is a strict improvement (never writes dirs into the spine).
- Test fixtures must reflect provisioned reality: `_setup_install_spine`-style helpers that exercise the seed/reconcile flows gain `config/ags/` (and gtk dirs only in dedicated tests). The old `allowed`-sets that tolerated created parent dirs (`config/`, `config/ags/`) shrink to the pointer files only.
- `inspect status` classifies an absent-parent pointer as `missing` (correct: the consumer skeleton isn't provisioned yet) — this is EXPECTED output until gt-3-1 lands, not a defect.

### Design decision 3 — spec injected with a module-default fallback

`CacheSeeder(state_root, consumer_spec=None)` → falls back to `StaticConsumerPathSpec()`. Rationale: (a) 87 existing direct constructions in tests keep compiling and keep the current AGS behavior (byte-compat by default), (b) the composition root (cli/main.py) still wires the spec explicitly (hexagonal: concrete choice at the outer shell), (c) reconcile/seed use cases need zero signature changes (they receive the seeder already carrying the spec). The alternative (required explicit spec) would churn every test fixture for no architectural gain.

### Design decision 4 — inspect projection is additive, `current_symlinks` untouched

`InspectStatusResult.consumer_pointers` is a NEW field (default `dict()`), keyed by spine-relative path. The existing `current_symlinks` (current/-only, keyed by bare name) keeps its exact key set and semantics — no re-keying, no merge — so existing JSON consumers and tests stay byte-stable. A null palette omits the pointers entirely (mirrors `_build_expected_targets`' palette branch). `None` constructor args = field empty (all existing `InspectStateUseCase(state_repo, state_root)` call sites and tests compile unchanged).

### Byte-compatibility notes (AGS + AR-3)

- Null-palette removal today warns `"seeding: palette layer is null; R2 consumer symlink removed: %s"` (seeder.py:631-634) — keep the message shape (drop "R2" only if the wording naturally becomes spec-neutral; tests should not pin the exact "R2" token — prefer matching the prefix). Same for the missing-target warn (`seeding: current/colors.gtk.css missing, R2 consumer symlink skipped`, seeder.py:640).
- `ReconcileResult.consumer_symlinks` stays `list[Path]` of actually-repointed pointers (reconcile.py:80-84, 247-250, 302-309); CLI counts (`wallpaper set` summary line 381-384, `reconcile` summary 502-506) grow additively.
- Swap sequence order unchanged: consumer pointers ride the EXISTING repoint step after `current/` (seed_cache.py:236-239, reconcile.py:247-250) — the spec table's entries are processed in table order (ags, gtk-3.0, gtk-4.0), all after `current/` repoint.
- The `current/` name set, palette artifact loop, history, and `inspect cache list` are untouched by this story.

### Source tree components to touch

| Path | Action | Notes |
|------|--------|-------|
| `src/runtime/src/runtime/domain/models.py` | **UPDATE** | `ConsumerPointer` + `ConsumerPointerRules` (pure data, no imports) |
| `src/runtime/src/runtime/ports/consumer_path_spec.py` | **NEW** | `IConsumerPathSpec` pure ABC (table + rules accessors) |
| `src/runtime/src/runtime/ports/__init__.py` | **UPDATE** | Re-export |
| `src/runtime/src/runtime/adapters/consumer_path_spec.py` | **NEW** | `StaticConsumerPathSpec` — the pinned 3-entry table |
| `src/runtime/src/runtime/adapters/seeder.py` | **UPDATE** | Constructor + generic `repoint_consumer_symlinks` loop |
| `src/runtime/src/runtime/application/inspect.py` | **UPDATE** | Additive `consumer_pointers` projection (+ module docstring) |
| `src/runtime/src/runtime/cli/main.py` | **UPDATE** | 4 `CacheSeeder` sites + `_run_inspect_status` + renderer |
| `src/runtime/src/runtime/application/seed_cache.py` | **VERIFY ONLY** | Signature unchanged |
| `src/runtime/src/runtime/application/reconcile.py` | **VERIFY ONLY** | Signature unchanged; docstring may gain a spec mention |
| `src/runtime/src/runtime/adapters/ags_reloader.py` | **LEAVE ALONE** | Its `current/colors.gtk.css` reload path is correct |
| `src/runtime/src/runtime/adapters/hashing.py` | **LEAVE ALONE** | NFR-4 |
| `src/runtime/tests/architecture/test_layering.py` | **EXPECT GREEN, no edits** | New port is a pure ABC |
| `tests/unit/test_seed_cache.py` | **UPDATE** | Fixture + spine guard + NEW `TestConsumerPointerSpec` |
| `tests/unit/test_reconcile.py` | **UPDATE** | Consumer assertions 1 → 3 pointers; fixture |
| `tests/unit/test_inspect.py` | **UPDATE** | NEW pointer-status tests |
| `tests/unit/test_cli_inspect_status.py` | **UPDATE** | Additive serialization assertions |
| `tests/integration/test_seed_cache_integration.py` | **UPDATE** | `_setup` + spine guard + gtk pointers |
| `tests/integration/test_reconcile_integration.py` | **UPDATE** | Fixture + consumer coverage |
| `tests/integration/test_inspect_integration.py` | **UPDATE** | Pointer statuses end-to-end |
| 11 further unit + 9 further integration test files | **VERIFY ONLY** | Full inventory in Task 7 |
| `_bmad-output/planning-artifacts/**/shared-data-contract.md`, `ARCHITECTURE-SPINE.md`, `consumer-wiring.md`, `docs/99` | **DO NOT TOUCH** | gt-4.2 scope (wording coordinated above) |

### Testing standards summary

- Runner: `uv run --directory src/runtime pytest` (`testpaths=["tests"]`, `pythonpath=["src","."]`, py314); fast path `pytest -k "not integration"`.
- Lint/type: `ruff check` + `ruff format --check` (line 100, double quotes) + `mypy --strict` — the new port's return types (`tuple[ConsumerPointer, ...]`, `ConsumerPointerRules`) must typecheck under strict mode with no `# type: ignore`; record baseline counts BEFORE coding (gt-2-1 procedure).
- `tests/architecture/test_layering.py` must stay green: ports = pure ABCs (`_PORTS_ALLOWED_AGGREGATES` empty — the spec returns domain models, never defines classes), domain stays I/O-free, adapters may import ports+domain.
- Deterministic fixtures only (reuse `tests/fixtures/wallpaper.png`); symlink assertions use `os.readlink` on raw targets (repo test convention, e.g. test_seed_cache.py:848).
- Every new warning path is asserted (pytest `caplog` at WARNING) — skip paths must be OBSERVABLE, not silent (mirror `TestRepointCurrentSymlinksPaletteArtifactSkip` from gt-2-1).

### Architecture extraction — what this story must respect

| Decision | Relevance |
|----------|-----------|
| AD-1/AD-14 hexagonal + domain purity | Contract data = plain dataclasses in `domain/`; port = pure ABC; loop I/O stays in the seeder adapter |
| AD-5/AD-15 + NFR-2 (§11 boundary) | Runtime writes under the install spine ONLY the spec'd pointer symlinks — the parent guard enforces this mechanically (no mkdir) |
| AD-6 (atomic swap, tmp + `os.replace`) | Pointer replacement reuses `_repoint_symlink` verbatim — no new atomicity code; loop is idempotent and re-runnable |
| AD-11 (spine exception class) | The exception extends from ONE symlink to the SPEC'D POINTER CLASS — the spec table is the enforceable boundary definition (pinned in the port docstring; ARCHITECTURE-SPINE text lands in gt-4.2) |
| AD-17 (consumer wiring) | The declarative table IS the amended consumer-wiring mechanism (investigation §3: "One adapter loop implements the rules once") |
| NFR-3 (same atomicity, idempotent) | Every loop iteration is a no-op when converged; re-run safe |
| NFR-4 | No hash formulas, no cache-layout change, no SQLite — nothing in `hashing.py`/`cache.py` is touched |
| NFR-5 (relaunch pickup) | No daemon, no reload changes — GTK/AGS read through the pointers at process start |

### Previous story intelligence (gt-2-1) + git intelligence

- gt-2-1 (commits 90d59c8 + review fix 47d23cb) grew the artifact set to 5 and is DONE: `current/colors.adw.css` + `current/colors.sequences` now exist in seed AND reconcile paths — the gtk-4.0 pointer's target artifact (`current/colors.adw.css`) is real, and `repoint_consumer_symlinks` was deliberately left hardcoded AGS-only for THIS story to generalize.
- gt-2-1 pinned the baseline-gate procedure (stash → count → compare post-implementation at exactly baseline) and the shared-helper doctrine ("one rule, three callers") — this story's analog: ONE loop, all pointers; never duplicate rule logic per consumer or per call site (seed vs reconcile).
- gt-2-1's review moved `test_missing_palette_artifact_skipped_never_dangling` → `test_missing_palette_artifact_triggers_regeneration` (semantics tightened); the seeder-level skip+warn stayed as defense-in-depth covered by `TestRepointCurrentSymlinksPaletteArtifactSkip` — mirror that split here: spec-loop skip paths get direct `caplog` coverage.
- Repo convention: story commits are `feat(runtime): ...` with `baseline_commit` frontmatter (this story: `47d23cb`); review fixes follow as separate commits.
- Sprint-status `story_location` still points at the MAIN repo (stale, correction pending) — this story's file lives in the WORKTREE `_bmad-output/implementation-artifacts/` per the gt-1-1/gt-2-1 precedent.
- Environment caveat (gt-2-1, still open): host `csg` binary predates gt-1-1; real-csg integration tests skip with a refresh instruction. Unrelated to this story (no csg changes here) — do not refresh as part of gt-2-2.

### Project Structure Notes

- Blast radius is exactly the `repoint_consumer_symlinks` / `consumer_symlinks` / inspect-status projection surfaces enumerated by `grep -rn 'repoint_consumer_symlinks\|consumer_symlink' src/runtime` at HEAD `47d23cb`: 5 source files (seeder.py, seed_cache.py, reconcile.py, cli/main.py, ports/desktop_config_writer.py — the latter is an unrelated ABC, VERIFY only) + the test files in Task 7. Nothing else references consumer pointers.
- The new port + adapter follow the repo's one-port-per-file / one-adapter-per-file convention (`ports/state_repository.py`, `adapters/flock_seed_mutex.py` style); re-export from `ports/__init__.py` (the layering test resolves re-exports through `__init__.py`).
- `inspect` stays read-only: the pointer projection is a filesystem reflection like `current_symlinks` — it must never trigger a repoint or a removal.
- The spec table is the SINGLE source of the consumer set in code — after this story, grep for `config/ags/colors.css` must hit only `adapters/consumer_path_spec.py` + behavior tests.

### References

- Epics: `_bmad-output/planning-artifacts/epics-gtk-theming.md` — Story 2.2 (verbatim AC block), FR-3, NFR-1/2/3/4, AR-1
- Investigation: `_bmad-output/planning-artifacts/gtk-theming-investigation.md` — §3 (ConsumerPointer table + rules — the pinned contract data), §2 (actor duties: ports/adapters/application rows), §4 item 2 (contract change list: table replaces AD-11 prose)
- Contract (pre-pointer-table pin; doc update is 4.2): `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md` — AD-11 Epic-4 exception paragraph (line 99); `shared-data-contract.md` — swap sequence
- Wiring spec: `_bmad-output/specs/spec-dotfiles-runtime-phase2/consumer-wiring.md` — R2 chain (`config/ags/colors.css` → `current/colors.gtk.css`, lines 15-19)
- Done predecessor: `_bmad-output/implementation-artifacts/gt-2-1-palette-artifact-set-growth.md` — 5-artifact state, baseline-gate procedure, shared-helper precedent
- Runtime code: `src/runtime/src/runtime/adapters/seeder.py` (`repoint_consumer_symlinks` 585-643, `_repoint_symlink` 55-74), `application/reconcile.py` (247-250, `ReconcileResult` 71-84), `application/seed_cache.py` (236-239), `application/inspect.py` (`_link_status` 206-225, `_build_expected_targets` 235-286), `cli/main.py` (`_resolve_install_spine` 52-66, CacheSeeder sites 126/266/278/439, `_run_inspect_status` 523-540), `ports/state_repository.py` (ABC convention), `ports/__init__.py`, `tests/architecture/test_layering.py` (ports rules, line 137-138)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
