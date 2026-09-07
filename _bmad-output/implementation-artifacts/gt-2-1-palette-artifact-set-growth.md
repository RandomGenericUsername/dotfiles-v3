---
baseline_commit: 39764ff
---

# Story 2.1: Palette artifact set growth (contract + domain + adapters)

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want the palette cache entry to contain `colors.adw.css` and `colors.sequences`,
So that GTK and shell consumers read runtime-owned, hash-addressed artifacts.

## Acceptance Criteria

### Verbatim contract (epics-gtk-theming.md, Story 2.1)

**Given** `shared-data-contract.md` pins the palette artifact set
**When** the set grows to `colors.yaml, colors.conf, colors.gtk.css, colors.adw.css, colors.sequences`
**Then** domain `PaletteArtifacts` gains `colors_adw_css` + `colors_sequences` fields
**And** `CsgAdapter` requests `-f ... -f adw.css -f sequences` and hashes all five artifacts into meta.json
**And** `derive.py`, `seeder.py`, `reconcile.py`, `inspect.py` expected-name lists include the new artifacts
**And** `current/` gains `colors.adw.css` + `colors.sequences` symlinks in seed AND reconcile paths
**And** cache keys are unchanged (`sha256(ph‖templates)` — NFR-4); `test_layering.py` green
**And** existing cache entries WITHOUT the new artifacts are cache misses → regenerated (migration note documented)

### Operational sub-ACs (dev contract — derived 1:1 from the verbatim block above)

1. **Given** `src/runtime/src/runtime/domain/models.py`, **When** `PaletteArtifacts` (TypedDict, `total=True`) is amended, **Then** it gains `colors_adw_css: str  # key: "colors.adw.css"` and `colors_sequences: str  # key: "colors.sequences"` after `colors_gtk_css` — five fields total, no renames, no other model touched. Every construction site of `PaletteArtifacts` (typed dict) must supply all five keys or `mypy --strict` fails — the Task list below enumerates all of them (AC: verbatim "Then").

2. **Given** `adapters/csg_adapter.py`, **When** `generate()` builds the csg invocation, **Then** the args list becomes `["--format", "yaml", "--format", "conf", "--format", "gtk.css", "--format", "adw.css", "--format", "sequences"]` (env-override + no `-o` flag pattern from Story rt-1-7 preserved verbatim), the post-run artifact verification loop (step 9) checks all five names as regular files, and the `PaletteArtifacts` construction (step 10) hashes all five via `hash_file` (AC: verbatim "And CsgAdapter requests…").

3. **Given** `adapters/seeder.py`, **When** a palette cache entry is loaded or repointed, **Then** (a) `load_palette_entry` reconstructs `PaletteArtifacts` from `meta.json` `artifact_hashes` for all five names — a pre-growth entry whose meta lacks the new keys must NEVER be loaded through this path (the derive hit-validation of AC 6 guarantees that; make the KeyError loud here as defense-in-depth), and (b) `repoint_current_symlinks`' palette loop iterates `("colors.conf", "colors.gtk.css", "colors.yaml", "colors.adw.css", "colors.sequences")` with the existing exists-or-symlink / skip+warn rule per artifact (AC: verbatim "And seeder.py … expected-name lists").

4. **Given** `application/derive.py` `ensure_palette._populate`, **When** `write_palette_meta_in` is called, **Then** `artifact_hashes` maps all five file names from `generated.artifact_hashes` (`colors.adw.css` ← `colors_adw_css`, `colors.sequences` ← `colors_sequences`), and the `PaletteEntry` appended to `entry_holder` carries the full 5-key `artifact_hashes` (AC: verbatim "And derive.py …").

5. **Given** `application/reconcile.py` and `application/inspect.py`, **When** the expected current/-symlink name sets are computed, **Then** every `("colors.conf", "colors.gtk.css", "colors.yaml")` tuple grows to the five-name tuple in ALL of: `reconcile._derive_skipped`, `reconcile._cleanup_stale_symlinks`, `reconcile._build_expected_targets`, `inspect._build_expected_targets` — keeping the inspect/reconcile mirror invariant documented in both docstrings (AC: verbatim "And reconcile.py, inspect.py …").

6. **Given** the swap sequence, **When** seed (`SeedCacheUseCase` → `repoint_current_symlinks`) or reconcile runs, **Then** `current/colors.adw.css` and `current/colors.sequences` symlinks exist pointing at `cache/palettes/<ph>/<name>`; `repoint_consumer_symlinks` (AGS R2 pointer) is UNCHANGED — it still points at `current/colors.gtk.css` (declarative multi-pointer wiring is Story 2.2, NOT here) (AC: verbatim "And current/ gains … in seed AND reconcile paths").

7. **Given** the cache-key contract, **When** the artifact set grows, **Then** `palette_entry_hash(wallpaper_hash, template_set_hash)` is untouched (no formula change, `adapters/hashing.py` unmodified), so existing full entries for the SAME wallpaper+templates keep the same `<ph>` — NFR-4; `tests/architecture/test_layering.py` passes with zero new violations (domain stays pure; the two new fields are plain `str` TypedDict entries) (AC: verbatim "And cache keys are unchanged … test_layering.py green").

8. **Given** an existing on-disk cache from before this change (`cache/palettes/<ph>/` holding only the 3 legacy artifacts + old meta.json), **When** any runtime command (seed/apply/reconcile) computes the same `<ph>`, **Then** the incomplete entry is treated as a cache MISS and regenerated into a complete 5-artifact entry on the next run — the migration mechanism is pinned in Dev Notes ("Migration: incomplete-entry eviction") and covered by a dedicated unit test; the same rule makes the story idempotent across re-runs (AC: verbatim "And existing cache entries WITHOUT the new artifacts are cache misses → regenerated").

## Tasks / Subtasks

- [x] Task 1 — Domain: grow `PaletteArtifacts` (AC: 1)
  - [x] Edit `src/runtime/src/runtime/domain/models.py` `PaletteArtifacts` (line 49-54): add `colors_adw_css: str  # key: "colors.adw.css"` and `colors_sequences: str  # key: "colors.sequences"`. No imports added (domain purity allowlist intact). No other model change.
  - [x] Update the `PaletteEntry` docstring comment if it names the artifact count (it does not — verify only).

- [x] Task 2 — Adapter: `CsgAdapter` requests + hashes 5 artifacts (AC: 2, 7)
  - [x] `src/runtime/src/runtime/adapters/csg_adapter.py` `generate()`:
    - args list (lines 280-290): append `"--format", "adw.css", "--format", "sequences"` — keep the intentional NO `-o` flag property; `build_env` keys unchanged.
    - post-run verification loop (line 343): `for name in ("colors.yaml", "colors.conf", "colors.gtk.css", "colors.adw.css", "colors.sequences"):`.
    - `PaletteArtifacts(...)` construction (lines 352-356): add `colors_adw_css=hash_file(output_dir / "colors.adw.css")` and `colors_sequences=hash_file(output_dir / "colors.sequences")`.
  - [x] Update the module docstring's artifact-set mentions if any (currently none — it references the env contract only).
  - [x] csg compatibility precondition (no runtime change needed — verify only): `ColorFormat.ADW_CSS = "adw.css"` and `ColorFormat.SEQUENCES = "sequences"` already exist post-gt-1-1 (`src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/enums.py:36,38`), and `colors.adw.css.j2` + `colors.sequences.j2` are in the bundled templates dir. The templates-dir hash CHANGES because gt-1-1 added `colors.adw.css.j2` — so on-disk entries are stale by BOTH the template-hash path (different `<ph>`) and the artifact-set path. The AC-8 migration still matters (same `<ph>` re-runs, template rollback, and partial entries); document this in completion notes.

- [x] Task 3 — Seeder: load + repoint 5 artifacts (AC: 3, 6)
  - [x] `src/runtime/src/runtime/adapters/seeder.py`:
    - `load_palette_entry` (lines 424-428): build `PaletteArtifacts` with all five `artifact_hashes[...]` lookups (`colors.adw.css`, `colors.sequences` added). Let the missing-key `KeyError` propagate (loud) — hit-validation upstream prevents old entries from reaching it.
    - `repoint_current_symlinks` palette loop (line 545): iterate the five-name tuple; per-artifact exists/symlink check + skip+warn unchanged.
    - Update the method docstring's `current/` inventory (lines 525-528) to list the two new links.
  - [x] `repoint_consumer_symlinks` (R2 AGS pointer) — NO behavior change; it targets `current/colors.gtk.css`. Do not touch (Story 2.2 generalizes it).

- [x] Task 4 — Derivation pipeline: meta map + hit-validation/migration (AC: 4, 8)
  - [x] `src/runtime/src/runtime/application/derive.py` `ensure_palette`:
    - `_populate`'s `write_palette_meta_in` `artifact_hashes` dict (lines 304-308): add `"colors.adw.css": generated.artifact_hashes["colors_adw_css"]` and `"colors.sequences": generated.artifact_hashes["colors_sequences"]`.
    - **Migration (AC 8):** replace the bare hit check `if target.exists(): return ...load...` with a completeness guard — the entry is a valid hit ONLY if its `meta.json` `artifact_hashes` contains all five names (cheap read via `seeder.read_entry_meta`; on `FileNotFoundError`/`KeyError`/missing artifact file, treat as miss). On invalid hit: quarantine-then-regenerate — `shutil.rmtree` the incomplete entry dir (write-once is violated ONLY for pre-growth partial entries; a one-time, logged `logger.info("palette entry incomplete (pre-growth artifact set); evicting: %s", target)`) and fall through to `populate_via_staging` so the same `<ph>` is regenerated in full. Never leave a half-evicted dir: rmtree with `ignore_errors=False`, and on OSError raise (caller failure policy applies).
    - Update the module docstring's behavior-contract bullet list with the migration rule.
  - [x] `src/runtime/src/runtime/application/seed_cache.py` — no direct name pins (delegates to the pipeline); VERIFY only, no edit expected.

- [x] Task 5 — Reconcile + inspect expected-name sets (AC: 5, 6, 8)
  - [x] `src/runtime/src/runtime/application/reconcile.py` — grow the 3-name tuple to 5 in:
    - `_derive_skipped` (line 446)
    - `_cleanup_stale_symlinks` (line 480)
    - `_build_expected_targets` (line 532)
  - [x] `src/runtime/src/runtime/application/inspect.py` — `_build_expected_targets` (line 265) grows to the same 5-name tuple; keep the docstring's mirror invariant statement accurate (line 13-16 name list too).
  - [x] Note: reconcile's `_ensure_entries` palette cache-miss check (`cache_entry_path(...).exists()`, line 334) must ALSO use the completeness guard — simplest: delegate to the same helper introduced in Task 4 (e.g. a module-level `def _palette_entry_complete(state_root, entry_hash) -> bool` in `derive.py` imported by both use cases) so seed/apply/reconcile share ONE migration rule. Do not duplicate the rmtree logic.

- [x] Task 6 — State repository SENTINEL path (AC: 1)
  - [x] `src/runtime/src/runtime/adapters/json_state_repository.py` `_load_projection` palette branch (lines 356-360): add `"colors_adw_css": SENTINEL_HASH` and `"colors_sequences": SENTINEL_HASH` to the sentinel `PaletteArtifacts` dict (current.json projection schema itself is UNCHANGED — it stores only hash+generated_at; this is the reconstruction side).

- [x] Task 7 — Docstring-only pins (no behavior change; keep the codebase self-describing)
  - [x] `src/runtime/src/runtime/adapters/cache.py` module + `populate_via_staging` docstrings (lines 9, 124): artifact inventory mentions 3 names → 5.
  - [x] `src/runtime/src/runtime/ports/color_scheme_generator.py` `generate` docstring (line 18): artifact list → 5. Port ABC signature unchanged.
  - [x] `src/runtime/src/runtime/adapters/terminal_color_applier.py` module docstring (line 41) mentions the artifact set being "a spine change" — update the enumeration if it lists names; the applier still READS `current/colors.yaml` (its switch to `colors.sequences` is Story 2.3, NOT here).

- [x] Task 8 — Tests: update every name-set pin + migration coverage (AC: 2, 3, 5, 6, 7, 8)
  - [x] Unit tests — every fake `PaletteEntry`/`PaletteArtifacts` construction and every expected-name tuple gains the two new names (grep-verified inventory, worktree HEAD 39764ff):
    - `tests/unit/test_csg_adapter.py` (lines 62, 98, 213, 353, 438): fake subprocess writes 5 files; key-set assertion (line 353) → 5 keys; args assertions updated.
    - `tests/unit/test_seed_cache.py` (117, 338, 575): fake meta/entry + `current/` name tuple → 5.
    - `tests/unit/test_crash_recovery.py` (68, 212, 304).
    - `tests/unit/test_json_state_repository.py` (92, 175): sentinel dict + meta fixture → 5 keys.
    - `tests/unit/test_inspect.py` (53, 135).
    - `tests/unit/test_apply_wallpaper.py` (108, 118, 362, 790, 805).
    - `tests/unit/test_reconcile.py` (96) + any expected-links assertions.
    - `tests/unit/test_terminal_color_applier.py` (331, 341).
    - `tests/unit/test_hyprland_reloader.py` (179, 189, 322, 332).
    - `tests/unit/test_hyprpaper_reloader.py` (285, 295).
    - `tests/unit/test_ags_reloader.py` (269, 279).
    - `tests/unit/test_cli_wallpaper_set.py` (48), `tests/unit/test_cli_reconcile.py` (46), `tests/unit/test_cli_crash_recovery.py` (51, 61): sentinel-style `colors_gtk_css="d"*64` fakes gain the two new fields.
  - [x] Integration tests — same treatment:
    - `tests/integration/test_csg_adapter_integration.py` (105, 117): real csg writes 5 files; assert all 5 exist + hashes match `PaletteEntry.artifact_hashes`.
    - `tests/integration/test_csg_determinism.py` (360, 423, 450-455): extend artifact set + per-artifact determinism diff for the two new files (adw.css and sequences must be bit-identical across double-run).
    - `tests/integration/test_seed_cache_integration.py` (38, 48, 184, 196).
    - `tests/integration/test_reconcile_integration.py` (39, 49, 209).
    - `tests/integration/test_apply_wallpaper_integration.py` (37, 47).
    - `tests/integration/test_inspect_integration.py` (70, 111, 195-206).
    - `tests/integration/test_crash_recovery_integration.py` (31, 41, 184).
    - `tests/integration/test_terminal_color_applier_integration.py` (77, 87).
    - `tests/integration/test_hyprpaper_reloader_integration.py` (50, 60).
    - `tests/integration/test_ags_reloader_integration.py` (41, 51).
    - `tests/integration/test_hyprland_reloader_integration.py` (42, 52).
    - `tests/integration/test_wallpaper_set_capstone_integration.py` (81, 91, 284, 380-415).
  - [x] NEW migration test (AC 8) in `tests/unit/test_seed_cache.py` (or a focused `tests/unit/test_palette_migration.py`): build a cache entry dir at the correct `<ph>` with only 3 legacy artifacts + old-shape meta.json → run seed/apply/reconcile pipeline → assert the entry was evicted and regenerated with 5 artifacts + 5-key meta, `current/` carries the 2 new symlinks, and the eviction was logged. Second run: no re-eviction (idempotent, now a clean hit).
  - [x] NEW/extended assertion: seed + reconcile produce `current/colors.adw.css` and `current/colors.sequences` (extend `test_seed_cache.py:575` and `test_reconcile.py` name-tuple assertions rather than adding parallel tests).

- [x] Task 9 — Full green (AC: 7)
  - [x] Run and require green (no test runs are part of story CREATION — this task list is for the dev agent):
    ```bash
    uv run --directory src/runtime pytest -q
    uv run --directory src/runtime pytest tests/architecture/test_layering.py -v
    uv run --directory src/runtime ruff check .
    uv run --directory src/runtime ruff format --check .
    uv run --directory src/runtime mypy --strict src/runtime
    ```
  - [x] AR-3 byte-compat guard: default `inspect cache list` output, history schema (7-field line), and swap sequence order are unchanged — verify the existing capstone/reconcile tests still assert the old counts where they were pinned (they only grow by the two palette link names, nothing else).

## Dev Notes

### Scope boundary — this story is ARTIFACT-SET GROWTH ONLY (runtime)

Story gt-2-1 grows the runtime palette artifact set from 3 to 5 names end-to-end (domain → adapter → seeder → use cases → repository). It does **NOT** implement:

- **Declarative consumer pointers** (`IConsumerPathSpec`, the ConsumerPointer table, generic repoint loop, doctor/inspect coverage of gtk-3.0/gtk-4.0 pointers) — Story 2.2. `repoint_consumer_symlinks` stays hardcoded AGS → `current/colors.gtk.css` here.
- **`TerminalColorApplier` artifact switch** (reading `current/colors.sequences` bytes) — Story 2.3.
- **Contract/doc file edits** — explicitly OUT of scope here, resolved as follows: `shared-data-contract.md` (palette meta.json `artifact_hashes` schema + ConsumerPointer table), `cache-model.md` (cache layout tree), `consumer-wiring.md`, ARCHITECTURE-SPINE AD-11 note, and `docs/99` prose are ALL reconciled in **Story 4.2 (docs + contract reconciliation)**. This story amends the *runtime behavior* ahead of the doc pin; gt-2-2 owns the contract table entry for pointers. The epics' Story 2.1 "Given shared-data-contract.md pins the artifact set" clause is satisfied by the CODE matching the investigated §4 change list; the doc file itself lags until 4.2 by design (matches gt-1-1 precedent, which also did not touch shared-data-contract.md).
- **AGS/icme visual polish, GTK spine config, zshrc repoint** — Epics 3/4.
- **Any hash-formula, cache-layout, or SQLite change** — NFR-4 forbids; `adapters/hashing.py` is untouched.

### Migration note (AC 8) — the one non-obvious design decision

Existing cache entries (`cache/palettes/<ph>/` with 3 artifacts + 3-key meta.json) would otherwise be **false cache hits**: `DerivationPipeline.ensure_palette` hits on dir existence, and `load_palette_entry` would `KeyError` on the new meta keys. The pinned mechanism:

1. Hit validation: a palette entry is a valid hit only if its `meta.json` `artifact_hashes` carries all five names (and the five files exist).
2. Invalid hit = miss: the incomplete entry dir is evicted (`shutil.rmtree`, logged) and the SAME `<ph>` is regenerated via the normal staging path. Cache keys are unchanged, so regeneration reproduces the same address — eviction is what makes the write-once invariant yield exactly once, for pre-growth partials only.
3. The same guard must gate reconcile's `_ensure_entries` and (via the shared pipeline) apply — one helper, three callers.
4. Consequence for users: the first post-upgrade run re-runs csg once per palette (a few seconds); `current/` then gains the two new symlinks on that same run. No manual action, no data loss (wallpaper/effects/icons entries are unaffected).

Note ALSO: gt-1-1 added `colors.adw.css.j2` to the csg templates dir, so `template_set_hash` changed too — on-disk entries are stale by both paths in practice. The migration still ships because the artifact-set rule is the durable invariant (it also covers template-hash rollback and any future partial-entry scenario).

### Source tree components to touch

| Path | Action | Notes |
|------|--------|-------|
| `src/runtime/src/runtime/domain/models.py` | **UPDATE** | `PaletteArtifacts` +2 fields. Domain purity untouched (plain str fields, no new imports) |
| `src/runtime/src/runtime/adapters/csg_adapter.py` | **UPDATE** | args +5-format list; verification loop 5 names; `PaletteArtifacts` 5-key hash |
| `src/runtime/src/runtime/adapters/seeder.py` | **UPDATE** | `load_palette_entry` 5-key reconstruction; `repoint_current_symlinks` 5-name loop; docstrings |
| `src/runtime/src/runtime/adapters/json_state_repository.py` | **UPDATE** | SENTINEL dict +2 keys (palette branch only) |
| `src/runtime/src/runtime/application/derive.py` | **UPDATE** | meta map 5 entries; hit-completeness guard + eviction (shared helper) |
| `src/runtime/src/runtime/application/reconcile.py` | **UPDATE** | 3 name-tuples → 5; `_ensure_entries` uses the shared guard |
| `src/runtime/src/runtime/application/inspect.py` | **UPDATE** | `_build_expected_targets` 5 names + docstring |
| `src/runtime/src/runtime/application/seed_cache.py` | **VERIFY ONLY** | No direct name pins; inherits via `DerivationPipeline` |
| `src/runtime/src/runtime/adapters/cache.py` | **UPDATE (docstring only)** | Artifact inventory mentions |
| `src/runtime/src/runtime/ports/color_scheme_generator.py` | **UPDATE (docstring only)** | Artifact list; ABC signature unchanged |
| `src/runtime/src/runtime/adapters/terminal_color_applier.py` | **UPDATE (docstring only)** | Still reads `current/colors.yaml` (Story 2.3 switches it) |
| `src/runtime/src/runtime/adapters/ags_reloader.py` | **LEAVE ALONE** | Its `current/colors.gtk.css` reference is correct post-growth |
| `src/runtime/src/runtime/adapters/hashing.py` | **LEAVE ALONE** | No formula change (NFR-4) |
| 14 unit + 12 integration test files | **UPDATE** | Full inventory with line pins in Task 8 |
| `_bmad-output/planning-artifacts/.../shared-data-contract.md`, `cache-model.md`, other docs | **DO NOT TOUCH** | Story 4.2 scope (boundary resolved above) |

### Testing standards summary

- Runner: `uv run --directory src/runtime pytest` (`testpaths=["tests"]`, `pythonpath=["src","."]`, py314); fast path `pytest -k "not integration"`.
- Lint/type: `ruff check` + `ruff format --check` (line 100, double quotes) + `mypy --strict` — the TypedDict growth will make `mypy --strict` flag EVERY incomplete `PaletteArtifacts` construction, which is exactly how the Task 8 inventory was derived; fix all of them, never add `# type: ignore`.
- `tests/architecture/test_layering.py` must stay green (domain allowlist, ports-as-ABCs, cross-package forbidden set).
- Deterministic fixtures only (reuse `tests/fixtures/wallpaper.png`); no new dot-artifacts committed under `tests/integration/`.
- AR-3: history line schema, `inspect cache list` shape, and swap order unchanged — existing tests enforce; do not weaken assertions.

### Architecture extraction — what this story must respect

| Decision | Relevance |
|----------|-----------|
| AD-1/AD-14 hexagonal + domain purity | TypedDict fields only in `domain/`; all I/O stays in adapters/use cases |
| AD-2 (input changes invalidate) | gt-1-1's template addition already invalidates via `template_set_hash`; the artifact-set guard adds a second staleness axis |
| AD-3 (FS authority) | meta.json is the completeness oracle for hit validation — never trust dir existence alone |
| AD-6 (atomic swap, symlinks lead) | The 2 new `current/` links ride the existing `_repoint_symlink` (tmp + `os.replace`) — no new atomicity code |
| AD-8 (SHA-256) | New hashes via `hash_file` (chunked binary); `hash_algorithm` literal unchanged |
| AD-9 (staging-dir) | Regeneration of evicted entries goes through `populate_via_staging` — never write into the final dir directly |
| AD-11 (spine boundary) | No new spine writes; R2 pointer unchanged (Story 2.2 extends the class) |
| NFR-4 | No new hash formulas, no cache-layout change, no SQLite — the layout gains two FILES inside the existing palette entry, not a new shape |

### Previous story intelligence (gt-1-1) + git intelligence

- gt-1-1 (commit 58d9646) shipped `ColorFormat.ADW_CSS`, `colors.adw.css.j2`, docs pin, and csg unit/CLI/container tests; commit 799ce86 fixed review findings (docs inventory wording). The runtime never requested the new format until NOW.
- csg `ColorFormat.SEQUENCES = "sequences"` + `colors.sequences.j2` predate Phase 2 — zero csg changes needed in this story; do not touch `src/cli-tools/color-scheme-generator/**` at all.
- Repo convention: story commits are `feat(runtime): ...` with `baseline_commit` frontmatter (this story: `39764ff`); review fixes follow as separate commits.
- Sprint-status `story_location` still points at the main repo (stale, correction pending) — this story's file lives in the WORKTREE `_bmad-output/implementation-artifacts/` per the gt-1-1 precedent.

### Project Structure Notes

- Blast radius is exactly the name-set pins enumerated by `grep -rn 'colors.gtk.css|colors_gtk_css|"colors.conf", "colors.gtk.css", "colors.yaml"' src/runtime` at HEAD `39764ff` — 11 source/doc files + 26 test files, all listed in Tasks 2-8. Nothing else references the artifact set.
- The shared hit-completeness helper belongs in `application/derive.py` (imported by reconcile; seed/apply use the pipeline directly) — do NOT put eviction logic in the seeder adapter or duplicate it per use case.
- `inspect` stays read-only: its 5-name growth is projection-only; it must never trigger eviction.

### References

- Epics: `_bmad-output/planning-artifacts/epics-gtk-theming.md` — Story 2.1 (verbatim AC block), FR-2, NFR-1/2/4, AR-3
- Investigation: `_bmad-output/planning-artifacts/gtk-theming-investigation.md` — §2 actor duties (domain/adapter rows), §3 declarative pointers (Story 2.2 context only), §4 contract change list item 1
- Contract (pre-growth pin; doc update is 4.2): `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md` — palette meta.json schema, Derivation-input hashing, Swap sequence step 2 palette symlinks
- Cache model: `_bmad-output/specs/spec-dotfiles-runtime-phase2/cache-model.md` — layout tree, first-run seeding steps 7-8, cache-hit flow
- Format story: `_bmad-output/implementation-artifacts/gt-1-1-colorformat-adw-css-template.md` — what csg now provides (`adw.css`), mapping pin location
- Structure reference: `_bmad-output/implementation-artifacts/rt-1-7-csg-adapter-env-override.md` — story format + adapter contract this story extends
- Runtime code: paths pinned in Task tables above (all under `src/runtime/src/runtime/` and `src/runtime/tests/`)

## Dev Agent Record

### Agent Model Used

opencode (glm-5.3-flash), BMad dev-story workflow, worktree `feat/gtk-theming-consumer`, baseline 39764ff

### Debug Log References

- Baseline gates verified via `git stash` before claiming pre-existing failures: `ruff check src tests` = 104 errors (pre-existing debt in tests), `ruff format --check .` = 26 files (pre-existing), `mypy --strict src/runtime` = 4 errors (FitMode/StrEnum py314 + missing cli_output stubs — pre-existing). Post-implementation: all three EXACTLY at baseline (0 new violations; my 2 accidental format deviations in derive.py/test_csg_adapter_integration.py were fixed via targeted `ruff format`).
- `uv run --directory src/runtime pytest -q`: 573 passed, 4 skipped (baseline 569 passed, 2 skipped → +6 new tests, 2 of which skip as stale-binary skips, see below).
- `pytest tests/architecture/test_layering.py`: 57 passed — domain purity intact.
- Integration suite: 61 passed, 3 skipped (1 pre-existing + 2 stale-csg skips).

### Completion Notes List

- **Artifact set grown end-to-end**: `PaletteArtifacts` gains `colors_adw_css` + `colors_sequences` (domain/models.py:49-56, plain `str`, no new imports); `CsgAdapter` requests `--format adw.css --format sequences` (args list, NO `-o` flag preserved), verifies all 5 files, hashes all 5 via `hash_file`; `seeder.load_palette_entry` reconstructs 5 keys (missing-key `KeyError` kept loud as defense-in-depth, covered by `test_load_palette_entry_raises_on_pre_growth_meta`); `repoint_current_symlinks` iterates the 5-name tuple; `derive._populate` meta map carries all 5; `reconcile._derive_skipped`/`_cleanup_stale_symlinks`/`_build_expected_targets` and `inspect._build_expected_targets` all 5-name (mirror invariant docstrings kept accurate); `json_state_repository` SENTINEL dict +2 keys; `repoint_consumer_symlinks` (R2 AGS pointer) UNCHANGED — still `current/colors.gtk.css` (Story 2.2); `adapters/hashing.py` untouched (NFR-4); `seed_cache.py` verified: no direct name pins, no edit needed.
- **Migration mechanism (AC 8)**: ONE shared helper `ensure_palette_entry_complete(target, seeder)` in `application/derive.py` — a palette entry is a valid hit ONLY if meta.json `artifact_hashes` carries all 5 names AND the 5 files exist; invalid hits are evicted (`shutil.rmtree(ignore_errors=False)`, OSError propagates, logged `logger.info("palette entry incomplete (pre-growth artifact set); evicting: %s", target)`) and the SAME `<ph>` regenerates through `populate_via_staging`. Callers: `DerivationPipeline.ensure_palette` (seed/apply) + `reconcile._ensure_entries` — one rule, three paths. `inspect` never calls it (read-only preserved).
- **Test semantics change (documented for review)**: `test_reconcile.py::test_missing_palette_artifact_skipped_never_dangling` became `test_missing_palette_artifact_triggers_regeneration` — under the guard, an entry missing an artifact FILE is incomplete → evicted + regenerated (never a false hit, never dangling). The seeder-level skip+warn path (defense-in-depth) is now covered directly by `TestRepointCurrentSymlinksPaletteArtifactSkip` in test_seed_cache.py.
- **New migration tests (AC 8)**: `TestPreGrowthPaletteEntryMigration` in test_seed_cache.py — pre-growth 3-artifact entry at correct `<ph>` → seed evicts+regenerates (5 artifacts, 5-key meta, 2 new `current/` symlinks, eviction logged, SAME `<ph>`); `test_pipeline_migration_is_idempotent` (second pass = clean hit, no re-eviction, meta byte-identical); `test_incomplete_entry_eviction_never_leaves_half_evicted_dir` (rmtree OSError propagates).
- **Environment caveat (pre-known, NOT a code failure)**: the host `csg` binary on PATH (`~/.local/bin/csg`, pip user install) predates gt-1-1 — `dump-templates` exposes only 9 templates (no `colors.adw.css.j2`), and the container image is stale (pre-known). The two real-csg integration tests (`test_csg_adapter_integration_real_binary`, `test_csg_deterministic_double_run[custom]`) now SKIP with a refresh instruction (same policy as the existing "container image not built" skip). **Manual verification step**: refresh csg (`uv tool install --force --reinstall-package color-scheme-generator --editable src/cli-tools/color-scheme-generator` or rebuild the container image) and re-run both tests to prove real-csg 5-artifact output + adw.css/sequences bit-determinism; then run a real `wallpaper set` and confirm `current/colors.adw.css` + `current/colors.sequences` symlinks.
- **Staleness note (story Dev Notes confirmed)**: gt-1-1 changed the templates dir, so on-disk entries are stale by BOTH paths (template-set hash → different `<ph>`; artifact set → incomplete hit). The AC-8 migration is the durable invariant: it also covers same-`<ph>` re-runs, template rollback, and any future partial-entry scenario.
- **AR-3 byte-compat guard**: history 7-field line schema, `inspect cache list` shape, and swap order unchanged — existing capstone/reconcile/inspect tests still enforce them; only palette link names grew (verified by full-suite green).
- mypy `--strict src/runtime` flags zero new errors; the TypedDict growth forced every `PaletteArtifacts` construction site to supply 5 keys (test fakes updated accordingly — all 14 unit + 12 integration files from the story inventory).

### File List

Source (11):
- src/runtime/src/runtime/domain/models.py
- src/runtime/src/runtime/adapters/csg_adapter.py
- src/runtime/src/runtime/adapters/seeder.py
- src/runtime/src/runtime/adapters/json_state_repository.py
- src/runtime/src/runtime/adapters/cache.py (docstring only)
- src/runtime/src/runtime/adapters/terminal_color_applier.py (docstring only)
- src/runtime/src/runtime/ports/color_scheme_generator.py (docstring only)
- src/runtime/src/runtime/application/derive.py
- src/runtime/src/runtime/application/reconcile.py
- src/runtime/src/runtime/application/inspect.py
- src/runtime/src/runtime/application/seed_cache.py (VERIFY only — no edit)

Tests (26):
- src/runtime/tests/unit/test_csg_adapter.py
- src/runtime/tests/unit/test_seed_cache.py (incl. new migration + skip tests)
- src/runtime/tests/unit/test_crash_recovery.py
- src/runtime/tests/unit/test_json_state_repository.py
- src/runtime/tests/unit/test_inspect.py
- src/runtime/tests/unit/test_apply_wallpaper.py
- src/runtime/tests/unit/test_reconcile.py
- src/runtime/tests/unit/test_terminal_color_applier.py
- src/runtime/tests/unit/test_hyprland_reloader.py
- src/runtime/tests/unit/test_hyprpaper_reloader.py
- src/runtime/tests/unit/test_ags_reloader.py
- src/runtime/tests/unit/test_cli_wallpaper_set.py
- src/runtime/tests/unit/test_cli_reconcile.py
- src/runtime/tests/unit/test_cli_crash_recovery.py
- src/runtime/tests/integration/test_csg_adapter_integration.py (incl. stale-csg skip probe)
- src/runtime/tests/integration/test_csg_determinism.py (incl. stale-csg skip probe)
- src/runtime/tests/integration/test_seed_cache_integration.py
- src/runtime/tests/integration/test_reconcile_integration.py
- src/runtime/tests/integration/test_apply_wallpaper_integration.py
- src/runtime/tests/integration/test_inspect_integration.py
- src/runtime/tests/integration/test_crash_recovery_integration.py
- src/runtime/tests/integration/test_terminal_color_applier_integration.py
- src/runtime/tests/integration/test_hyprpaper_reloader_integration.py
- src/runtime/tests/integration/test_ags_reloader_integration.py
- src/runtime/tests/integration/test_hyprland_reloader_integration.py
- src/runtime/tests/integration/test_wallpaper_set_capstone_integration.py

Story artifacts (2):
- _bmad-output/implementation-artifacts/gt-2-1-palette-artifact-set-growth.md
- _bmad-output/implementation-artifacts/sprint-status.yaml

### Change Log

- 2026-09-07: Story gt-2-1 implemented — palette artifact set grows 3 → 5 (colors.adw.css + colors.sequences) across domain/adapter/seeder/derive/reconcile/inspect/repository; shared hit-completeness guard + evict-and-regenerate migration (AC 8); `current/` gains the 2 new symlinks in seed AND reconcile; 26 test files updated to the 5-name set; 6 new tests (5-name repoint, skip+warn defense-in-depth, 3× migration); real-csg integration tests skip on stale host binary with refresh instruction (environment, pre-known). Status → review.
