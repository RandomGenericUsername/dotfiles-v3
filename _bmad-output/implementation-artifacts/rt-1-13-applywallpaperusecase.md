---
baseline_commit: cf0f931746a87913de6a8bed3ea6544d4a9a6226
---

# Story 1.13: ApplyWallpaperUseCase — derive, cache, persist

Status: done

## Story

As a user,
I want `dotfiles-runtime wallpaper set <img>` to derive, cache, and persist the desktop state,
so that my wallpaper's palette/effects/icons are ready for instant reuse and the state is recorded.

## Acceptance Criteria

1. **Given** a provisioned machine with seeded state, **When** `dotfiles-runtime wallpaper set <img>` runs with a NEW wallpaper, **Then** the image path is resolved to an absolute path and validated (must be an existing regular file — missing file, directory, or empty path fail loud with a clear message and non-zero exit), the wallpaper is hashed (`sha256(file_bytes)`), cache entries are ensured for all three derived layers (miss path invokes csg/weg/itr exactly once per layer via the staging-dir pattern), and `current.json` is updated (schema_version 2, atomic tmp+`os.replace`) with the new wallpaper hash, the real entry hashes, and the absolute `source_path`. (AC 1, FR-1 partial, FR-2)

2. **Given** the same `<img>` is set again, **When** the command runs, **Then** it is a cache hit: ZERO csg/weg/itr subprocess invocations (existing entries are detected by cache-entry-dir existence and rebuilt from their co-located `meta.json` via `CacheSeeder.load_*_entry`), and `current.json` is re-saved with a refreshed `applied_at`. (AC 2, FR-2)

3. **Given** a previously-used wallpaper (different from the currently applied one) is set again, **When** the command runs, **Then** it is a cache hit: zero tool invocations, existing cache entries are reused, and `current.json` reflects the restored wallpaper's hash + entry hashes. (AC 3, FR-2)

4. **Given** CSG (palette) generation fails, **When** the command runs, **Then** the apply aborts (palette is a HARD dependency, mirroring `SeedCacheUseCase`'s policy), `current.json` is left unchanged, and the CLI exits non-zero with a `palette apply failed:` context message. **Given** WEG (effects) or ITR (icons) fails, **Then** the apply degrades gracefully with a visible warning and the corresponding `current.json` field is `null` (history schema allows nulls; consumers handle absence). (AC 4, seed precedent)

5. **Given** `current.json` exists with monitor configs, **When** a new wallpaper is applied, **Then** each existing monitor's `backend`, `fit_mode`, `mpv_options`, `ipc_socket` are PRESERVED and only `source_hash` is updated to the new wallpaper hash; **Given** no `current.json` exists (seed was skipped — e.g. no provisioning spine) OR the loaded state has an EMPTY `monitors` dict (possible: `JsonStateRepository._dict_to_state` coerces absent `monitors` to `{}`), **Then** the state is constructed with the default monitor config (`DP-1`, `hyprpaper`, `cover`) mirroring the seeder. (AC 5, AD-18, shared-data-contract monitors rules)

6. **Given** the shared-data-contract ownership rules, **When** the apply completes, **Then** ApplyWallpaperUseCase does NOT repoint `current/` symlinks, does NOT append `history.jsonl`, and does NOT invoke any desktop reload — the swap sequence (symlink repoint → `current.json` → history → reload) is owned by `ReconcileDesktopStateUseCase` (Epic 2) and full convergence lands in Story 2.7. `current.json` is the only persisted artifact of this story. (AC 6, AD-6, shared-data-contract Swap sequence)

7. **Given** the hexagonal/boundary rules (AD-1, AD-14, AD-15), **When** the story lands, **Then** the use case lives in `runtime.application`, imports only ports/domain/adapters-via-injection, holds no raw `os`/`json` FS I/O itself; the CLI command renders via `cli_output` (`create_renderer` + `CustomView`/`ErrorView`), exits 0 on success and non-zero on failure; the layering test and all existing suites stay green. (AC 7, NFR-1, AD-19/AD-20)

## Tasks / Subtasks

- [x] Task 1 — `application/apply_wallpaper.py`: ApplyWallpaperUseCase (AC: 1, 2, 3, 4, 5, 6)
  - [x] Constructor injects ports + adapters exactly like `SeedCacheUseCase`: `state_repo: IStateRepository`, `csg: IColorSchemeGenerator`, `weg: IEffectsGenerator`, `itr: IIconRenderer`, `install_spine: Path`, `state_root: Path`, `seeder: CacheSeeder` (concrete adapter injected per the established pattern — do NOT construct adapters inside the use case; the 1.11 review fixed exactly this).
  - [x] `run(image_path: Path) -> ApplyWallpaperResult` where `ApplyWallpaperResult` is a frozen dataclass defined in this module (application layer may define its own result type): fields `wallpaper_hash: str`, `palette: PaletteEntry`, `effects: EffectsEntry | None`, `icons: IconsEntry | None`, `cache_hit_palette: bool`, `cache_hit_effects: bool`, `cache_hit_icons: bool`, `state: DesktopState`.
  - [x] Validate + resolve input: `image_path.expanduser().resolve()` (absolute — dangling-symlink lesson from 1.11), reject non-existent / non-regular-file / directory with `ValueError` (CLI maps to non-zero exit).
  - [x] Load existing state: `existing = self._state_repo.load_current()` — a `ValueError`/`RuntimeError` from a corrupt store propagates loudly (corrupt-state guard, do NOT swallow into a fresh state).
  - [x] Wallpaper layer: `wallpaper_hash = hash_file(img)`; reuse `self._seeder.hardlink_wallpaper(img, wallpaper_hash)` (idempotent + content-verified). Write `write_wallpaper_meta` ONLY when `cache/wallpapers/<wh>/` did not pre-exist (check before hardlink) — cache entries are write-once immutable (spine convention); re-writing meta over an existing entry is not allowed.
  - [x] Palette (hard dependency): compute `template_set_hash = canonical_hash_dir(templates_dir)` from spine templates, `peh = palette_entry_hash(wallpaper_hash, template_set_hash)`, `target = cache_entry_path(state_root, "palettes", peh)`. If `target.exists()` → cache hit: `return self._seeder.load_palette_entry(target)` + flag. Else populate via `populate_via_staging(target, _populate)` where `_populate(staging)` invokes `self._csg.generate(wallpaper_path, staging / peh)` (output dir NAME must equal `peh` — adapter contract), verifies `generated.entry_hash == peh` (mismatch = RuntimeError, templates divergence), then `drain_work_dir(staging / peh, staging)` and `write_palette_meta_in(staging, ...)`. Wrap failures as `RuntimeError(f"palette apply failed: {exc}")`.
  - [x] Effects + icons: identical pattern with `effects_entry_hash(wallpaper_hash, catalog_hash)` / `icons_entry_hash(peh, templates_hash, mappings_hash)`, spine discovery via the SAME helpers as seed (see Task 2). Failures degrade: log `logger.warning("apply: effects generation failed; continuing: %s", exc)` → `None`.
  - [x] Build `DesktopState`: `WallpaperEntry(source_path=str(img))` (absolute path — contract allows `<abs-or-empty>`; seed used `""` because provisioning output, a user-set wallpaper legitimately records where it came from), monitors per AC 5 (preserve non-empty monitors with `source_hash` updated to `wallpaper_hash`; DEFAULT `DP-1`/`hyprpaper`/`cover` when `existing is None` OR `existing.monitors == {}`), `applied_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")`.
  - [x] `self._state_repo.save(state)` — atomic; NO symlink repoint, NO `append_history`, NO reload (AC 6 — do not "helpfully" add them; ReconcileDesktopStateUseCase owns the swap sequence).
- [x] Task 2 — Share the derivation plumbing with SeedCacheUseCase without breaking it (AC: 1, 7)
  - [x] The spine-discovery helpers (`_find_templates_dir`, `_find_effects_catalog`, `_find_icon_templates`, `_find_icon_mappings`) and the per-layer populate pattern are currently private methods of `SeedCacheUseCase`. Extract them into a shared application-layer collaborator — recommended: `application/derive.py` module-level functions (e.g. `find_templates_dir(install_spine)`, `find_effects_catalog(install_spine)`, `find_icon_templates(install_spine)`, `find_icon_mappings(install_spine)`) plus a `DerivationPipeline`-style helper taking `(state_root, seeder, csg, weg, itr, install_spine)` exposing `ensure_palette(img, wh)`, `ensure_effects(img, wh)`, `ensure_icons(peh)` returning `(entry, cache_hit: bool)`.
  - [x] Refactor `SeedCacheUseCase` to delegate to the shared helpers — behavior-identical (same failure policy: palette hard, effects/icons graceful; same staging + drain + meta-in-staging flow; same load-on-race path). The existing `tests/unit/test_seed_cache.py` + `tests/integration/test_seed_cache_integration.py` MUST pass unmodified (they lock the behavior). If extraction threatens seed behavior, fall back: keep `SeedCacheUseCase` untouched and have `apply_wallpaper.py` use the shared module alone (seed refactor becomes follow-up debt — record the decision in Dev Agent Record).
  - [x] Do NOT move or rename `adapters/seeder.py`, `adapters/cache.py`, `adapters/hashing.py` — they are the stable substrate both use cases compose.
- [x] Task 3 — CLI: `wallpaper set` command + composition root (AC: 1, 4, 7)
  - [x] In `cli/main.py` add `wallpaper_app = typer.Typer(help="Wallpaper commands")` and `app.add_typer(wallpaper_app, name="wallpaper")`.
  - [x] `@wallpaper_app.command("set")` with argument `image_path: Path` and the standard `--format/-f OutputFormat` option. The root callback's `_run_seed_if_needed()` already runs first — do NOT call it again inside the command.
  - [x] Add a `_run_wallpaper_set(image_path)` composition function mirroring `_run_seed_if_needed`'s wiring: resolve `state_root`/`install_spine` via the EXISTING `_resolve_state_root()`/`_resolve_install_spine()` (both already resolve to absolute), construct `JsonStateRepository`, `CsgAdapter`, `WegAdapter`, `ItrAdapter`, `CacheSeeder`, then `ApplyWallpaperUseCase`. No factory/mutex needed for this story (see Dev Notes — concurrency decision).
  - [x] Error mapping: `ValueError`/`RuntimeError`/`OSError` from the use case → `renderer.error(ErrorView(...))` + `raise typer.Exit(code=1)` (OSError covers `hash_file`'s `PermissionError`/`FileNotFoundError` on unreadable/missing input — a raw traceback is never the right UX); success → `renderer.custom(CustomView(plain=<human summary>, object={wallpaper, palette, effects, icons, cache_hits...}, rich=<summary>))` following the `version` command's pattern. Unexpected exceptions: log via `logger.exception` and exit non-zero.
- [x] Task 4 — Unit tests `tests/unit/test_apply_wallpaper.py` (AC: 1–6)
  - [x] Follow `test_seed_cache.py`'s fake-adapter style (`_FakeCsg`/`_FakeWeg`/`_FakeItr` with invocation counters — record invocation counts in the fakes so cache-hit/miss is assertable). Cover: new-wallpaper happy path (entries created, csg/weg/itr invoked once each, current.json updated with real hashes + absolute source_path); same-img re-set (counters stay 0, applied_at refreshed); previously-used wallpaper re-set (counters 0, state restored); palette failure aborts (current.json unchanged — snapshot before/after); effects/icons failure degrades (nulls in state); missing input file / directory input raise; monitors preserved with source_hash updated; absent-state default monitors; existing-state-empty-monitors default monitors (`load_current()` state with `monitors == {}`); NO symlink created under `current/` and NO `history.jsonl` line appended (negative assertions locking AC 6's scope boundary).
  - [x] Hash/entry contract: assert cache dir names equal computed entry hashes; assert meta.json written in staging (pre-rename) matches shared-data-contract schemas.
- [x] Task 5 — Integration test `tests/integration/test_apply_wallpaper_integration.py` (AC: 1–3)
  - [x] Mirror `test_seed_cache_integration.py` EXACTLY: fake adapters (`_FakeCsg`/`_FakeWeg`/`_FakeItr` with invocation counters — no real tools, no skip logic; the real-tool skip pattern belongs to the csg/weg/itr adapter integration tests, not use-case integration tests), tmp `state_root` + fake install spine with `generated/default.png` and spine inputs. Seed first via `SeedCacheUseCase` (proves the seeded-state `Given` of AC 1), then apply a new small generated PNG and assert: cache entries exist with meta.json, current.json reflects new hashes, second apply of the same image performs zero adapter invocations (counters unchanged). Add a re-set of a previously-used wallpaper scenario (AC 3 end-to-end).
- [x] Task 6 — Full green gate (AC: 7)
  - [x] `uv run --directory src/runtime pytest -q`
  - [x] `uv run --directory src/runtime ruff check src/runtime`
  - [x] `uv run --directory src/runtime ruff format --check src/runtime`
  - [x] `uv run --directory src/runtime mypy --strict src/runtime`
  - [x] `tests/architecture/test_layering.py` green (no new violations; application layer may import adapters only via constructor injection — verify the layering test's actual rule for application→adapters imports before importing `CacheSeeder` at module level; `SeedCacheUseCase` already does this, so mirror it exactly).

## Dev Notes

### Scope boundary — this is the Epic-1-to-Epic-2 seam

This story delivers derive → cache → persist ONLY. It deliberately does NOT:
- repoint `current/` symlinks (ReconcileDesktopStateUseCase, Story 2.1),
- append `history.jsonl` (step 4 of the swap sequence — Reconcile-owned per shared-data-contract; Story 2.7 capstone appends on the full pipeline),
- reload any desktop component (Stories 2.3–2.6),
- invoke wallpaper backends / `IWallpaperBackendFactory` (Epic 2; auto-detect FR-11 lands there).

Consequence: after this story, `current.json` (the index) can be AHEAD of the `current/` symlinks (the filesystem authority) until Epic 2 lands. This transient inversion of "symlinks lead, current.json follows" (NFR-7) is the intended seam — the epic AC pins it: "current.json reflects the new wallpaper hash (full desktop convergence + reload land in Epic 2)". Do not "fix" it by repointing symlinks here; that would duplicate Reconcile's ownership and break Story 2.1's crash-recovery design.

### The flow is uniform — "cache hit" falls out of entry-existence checks

There is no separate hit/miss code path. Per layer: compute the entry hash from the canonical input set → if `cache/<layer>/<hash>/` exists, rebuild the entry from its `meta.json` (`load_palette_entry` / `load_effects_entry` / `load_icons_entry`) → zero tool invocations. If absent, populate via staging (tool invoked once). AC 2 ("same img re-set") and AC 3 ("previously-used wallpaper re-set") both route through this. The one subtlety: entry hashes depend on spine inputs (templates/catalog/mappings hashes) which are re-read on EVERY derivation (AD-11, read-only) — if the user edits CSG templates, the palette hash CHANGES and the same wallpaper becomes a miss. That is correct per AD-2 (input changes invalidate).

### Entry-hash formulas and the adapter output-dir name contract (get these exactly right)

From `adapters/hashing.py` (already implemented, do not reinvent):
- wallpaper: `hash_file(img)` (chunked SHA-256)
- palette: `palette_entry_hash(wallpaper_hash, template_set_hash)` where `template_set_hash = canonical_hash_dir(<install>/config/color-scheme-generator/templates/)`
- effects: `effects_entry_hash(wallpaper_hash, catalog_hash)` where `catalog_hash = hash_file(<install>/config/weg/effects.yaml)`
- icons: `icons_entry_hash(palette_entry_hash, templates_hash, mappings_hash)`

Adapters validate `output_dir.name == expected_entry_hash` and reject symlinked/`..`-containing output dirs (CsgAdapter `_validate_output_dir`) — so inside `populate_fn(staging)` you MUST call `self._csg.generate(img, staging / entry_hash)` and then `self._seeder.drain_work_dir(staging / entry_hash, staging)` (moves artifacts to the staging root where `populate_via_staging` expects them + its meta.json guard). This staging-dir-name dance exists because Story 1.11's review found the adapters reject `.staging-*` names — do not bypass it. `populate_via_staging` REQUIRES `meta.json` in the staging root: write it via `self._seeder.write_palette_meta_in(staging, ...)` / `write_effects_meta_in` / `write_icons_meta_in` (schemas pinned in shared-data-contract — the `*_in` variants write into a given dir, exactly what staging needs).

Race semantics of `populate_via_staging`: returns `True` if this call created the entry, `False` if the target already existed (staging discarded, never overwritten). On `False`, rebuild the entry from meta.json like seed does — never return a constructed entry whose hashes weren't verified.

### Failure policy (mirror seed exactly)

- Palette = hard dependency: any exception → `RuntimeError(f"palette apply failed: {exc}")`, propagates, `current.json` untouched (save happens after all layers succeed/degrade).
- Effects/icons = graceful: `logger.warning(...)`, entry `None`, `current.json` field `null`.
- Corrupt current.json (`ValueError` from `load_current`) propagates loudly — do NOT treat as absent state.

### Monitor handling decision

Preserve-or-default (AC 5): when `existing` state has monitors, rebuild each `MonitorWallpaperConfig` with the SAME `backend`/`fit_mode`/`mpv_options`/`ipc_socket` but `source_hash=wallpaper_hash` — a wallpaper change must not silently reset a user's per-monitor backend (AD-18). When `existing is None` (seed skipped: no provisioning spine on this machine), default to the seeder's convention: single monitor `DP-1`, `BackendType.hyprpaper`, `FitMode.cover`, `mpv_options=None`, `ipc_socket=None`. Note `MonitorWallpaperConfig.__post_init__` rejects `mpv_options`/`ipc_socket` for non-mpvpaper backends — preserving a real mpvpaper config passes, constructing defaults never sets those fields.

### Concurrency decision (recorded, not an oversight)

`wallpaper set` does NOT take the seed mutex in this story. Justification: (a) `populate_via_staging` is race-safe (sibling staging + `os.rename`, live-PID protection, write-once); (b) `current.json` writes are atomic (tmp + `os.replace`) — concurrent applies converge to last-writer-wins with both cache entries valid; (c) `ISeedMutex`'s contract is the once-only seeding invariant (AD-11), not apply serialization; (d) the swap — where serialization will actually matter — is Epic 2 and Reconcile will own that decision. If review disagrees, the fix is additive (reuse `FlockSeedMutex` around `run()`), not structural.

### Serialization note — `current.json` round-trip is lossy by design

`JsonStateRepository.load_current()` reconstructs entries with `SENTINEL_HASH` ("0"*64) placeholder input hashes — the projection contract (C1) stores only `hash`+`generated_at`. Therefore NEVER persist entry objects obtained from `load_current()` back to `save()` unchanged; this story always rebuilds all entries from real cache meta.json values (or `None`), so the saved state carries real hashes throughout — the exact bug 1.11's review caught ("Sentinel hashes persisted in current.json"). The one field legitimately carried from `load_current()` is the monitors' backend/fit_mode/mpv config (validated enum values, not hashes).

### `source_path` divergence on re-set — accepted behavior, do not "fix"

Re-setting a previously-used wallpaper from a DIFFERENT path updates `current.json.wallpaper.source_path` to the latest path, while `cache/wallpapers/<wh>/meta.json.source_path` keeps the FIRST-import path (meta is write-once). This is correct: `current.json` records where the currently-applied wallpaper came from; cache meta records provenance of first import. Filesystem is authority (NFR-3); the hash-addressed entry is identical either way.

### Spine discovery — reuse, and read-only

Reuse/extract the seed's discovery helpers rather than writing new ones; they check the spine path first, then walk repo ancestors for dev checkouts (deferred-work: this repo-layout coupling is a known deferred item — not this story's job to fix). All spine reads are READ-ONLY (AD-11 post-seed rule, AD-15): hash the templates dir / catalog / mappings, never write under the install spine.

### CLI composition details

- The root callback (`main_callback`) runs `_run_seed_if_needed()` before EVERY command — `wallpaper set` gets seeding for free. If the spine is absent, seeding warns and skips; then apply's absent-state default (AC 5) makes `wallpaper set` still work on a machine with no provisioning output.
- Follow the `version` command's renderer pattern (`create_renderer(output_format)`, `CustomView`/`ErrorView`); `cli_output` is the ONLY cross-package import allowed (AD-15 — forbidden set: `provisioning`, `core`, `color_scheme_generator`, `wallpaper_effects_generator`, `icon_templates_renderer`, `config_assembler_engine`, `oci_runtime`).
- `wallpaper set` returns nothing to shell except exit code + rendered output; keep the summary one-line-ish in plain format.

### Code style gates (enforced by CI-style commands)

Python 3.14, `mypy --strict` (no untyped defs, `from __future__ import annotations` at top), ruff line-length 100 (config in `src/runtime/pyproject.toml`), ruff select E/F/I/N/W/UP/B. Parenthesize multi-except tuples (`except (ValueError, RuntimeError):` — PEP 758 unparenthesized form was flagged in 1.11 review). Timestamps: `datetime.now(UTC).isoformat().replace("+00:00", "Z")` — strict ISO-8601 Z (validators reject non-Z). No comments explaining "why" beyond docstrings — the repo's house style is dense module docstrings citing AD-numbers.

### Previous story intelligence (rt-1-11 — the direct runtime-side precedent; rt-1-12 was provisioning-side and touched nothing under `src/runtime/`)

- Review remediation hardened EVERYTHING this story composes: idempotent hash-verified hardlink, `drain_work_dir` staging contract, `load_*_entry` meta rebuilds, atomic symlink repoint with tmp cleanup (unused here — no repoints), O_APPEND+O_NOFOLLOW full-write history loop (unused here — no appends), absolute-path resolution at the composition root, loud CLI failure surfacing, injected `CacheSeeder` (no hard construction in application layer). All of these are tests-locked — regression means a red suite, treat the seed tests as the spec for shared behavior.
- Fake adapters in tests must satisfy the REAL adapter contract (output dir named `<entry_hash>`, artifacts + meta.json present) — 1.11's review flagged fakes that encoded a contract-violating generate; write fakes against the contract, not against convenience.
- Deferred items that touch this story's area (do not fix here, but do not worsen): template-discovery repo walk coupling (deferred-work rt-1-11), unbounded `hash_file` read on huge files (deferred rt-1-7), CSG raw-output nondeterminism — colors.yaml bytes differ run-to-run while normalized hashes match (deferred, `.csg_determinism.json`) — consequence: artifact_hashes in meta.json for the SAME palette entry could differ if regenerated; entry reuse via existence-check masks this in practice; do not add re-generation logic.

### Git intelligence

HEAD = `2ad4a18` (rt-1-12 marked done). Runtime code last touched by `d953a29` (Story 1.11 seeder + CLI hook) and `7dc11e6` (review fixes). Stories 1.12/1.14 commits touched only provisioning — expect a clean `src/runtime/`. Baseline suite is green for `src/runtime` (171 tests at 1.11; more since). Sprint-status quirk: `rt-1-14` (AGS swap) was pulled ahead and is done; `rt-1-13` is the last open Epic-1 story.

### Testing standards summary

- Runner: `uv run --directory src/runtime pytest -q` (unit + integration + architecture). Integration tests skip gracefully when real csg/weg/itr tools are unavailable — keep that pattern; unit tests are pure fakes.
- Lint/type: `ruff check`, `ruff format --check`, `mypy --strict` scoped to `src/runtime` (commands in Task 6 — run from repo root with `--directory src/runtime`).
- Layering: `tests/architecture/test_layering.py` — domain purity (no os/subprocess/shutil/pathlib), ports are ABCs, cross-package forbidden set. Application layer imports: `SeedCacheUseCase` imports `runtime.adapters.hashing`/`runtime.adapters.seeder` at module level and passes the layering test today — mirror that pattern; if you add a NEW application→adapters import and the layering test fails, the fix is constructor injection, not weakening the test.
- Assertion style: unit tests assert behavior + contracts (invocation counts, file outcomes, schema shapes); integration tests assert filesystem outcomes end-to-end.

### Project Structure Notes

New files:
- `src/runtime/src/runtime/application/apply_wallpaper.py` (NEW — ApplyWallpaperUseCase + ApplyWallpaperResult)
- `src/runtime/src/runtime/application/derive.py` (NEW — shared discovery + ensure-layer helpers, IF Task 2 extraction lands; else seed stays untouched)
- `src/runtime/tests/unit/test_apply_wallpaper.py` (NEW)
- `src/runtime/tests/integration/test_apply_wallpaper_integration.py` (NEW)
Modified:
- `src/runtime/src/runtime/cli/main.py` (wallpaper sub-app + set command + composition function)
- `src/runtime/src/runtime/application/seed_cache.py` (ONLY if Task 2 extraction lands — delegate to shared helpers, behavior-identical)
No changes: `domain/`, `ports/`, `adapters/`, `pyproject.toml`, provisioning, manifests.

### References

- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md` — Story 1.13 ACs; Implementation notes R1/R2; Epic 2 story 2.1/2.7 (what this story hands off)
- Architecture spine: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md` — AD-1/2/5/6/7/9/10/11/12/14/15/18/19/20
- Shared data contract: same folder `shared-data-contract.md` — current.json schema v2, monitors rules, history schema (trigger enum incl. "set"), meta.json schemas, derivation-input hashing table, env-override protocol, Swap sequence ownership ("ApplyWallpaperUseCase updates desired state and delegates the actual swap to Reconcile")
- Existing code: `src/runtime/src/runtime/application/seed_cache.py` (orchestration pattern, failure policy, discovery helpers), `adapters/seeder.py` (CacheSeeder: hardlink_wallpaper, write_*_meta_in, drain_work_dir, load_*_entry), `adapters/cache.py` (populate_via_staging, cache_entry_path), `adapters/hashing.py` (hash_file, canonical_hash_dir, *_entry_hash), `adapters/json_state_repository.py` (projection + sentinel contract), `cli/main.py` (_run_seed_if_needed wiring, version command renderer pattern), `adapters/csg_adapter.py` (output-dir validation contract)
- Previous stories: `_bmad-output/implementation-artifacts/rt-1-11-first-run-self-seeding.md` (review findings + completion notes), `rt-1-12-provisioning-dont-clobber-guard.md` (latest; provisioning-side only)
- Deferred ledger: `_bmad-output/implementation-artifacts/deferred-work.md` — rt-1-5/6/7/8/9/10/11 entries

## Dev Agent Record

### Agent Model Used

GLM (opencode-go/glm-5.3-flash) via opencode, 2026-08-31.

### Debug Log References

- Full suite: `212 passed, 1 skipped` (was 189+1 at baseline; +23 new: 20 unit, 4 integration, minus 1 renumbering — net new 23 in the two new files).
- `ruff check src/runtime`: 3 remaining violations, ALL pre-existing at baseline (verified via `git stash`): `main.py` version-command B008+E501, `domain/models.py:35` E501, `main.py` main_callback B008. Zero new violations from this story.
- `ruff format --check src/runtime`: 5 files would be reformatted, ALL pre-existing at baseline (adapters/cache.py, adapters/seeder.py, application/seed_cache.py, domain/models.py, ports/wallpaper_backend_factory.py). New/edited files by this story are format-clean.
- `mypy --strict src/runtime`: 4 errors, ALL pre-existing at baseline (domain/models.py:30 StrEnum, 3x cli_output import-untyped). Zero new errors.
- `tests/architecture/test_layering.py`: 49 passed — application→adapters module-level imports mirror SeedCacheUseCase's existing pattern.

### Completion Notes List

- **Task 2 extraction LANDED**: `application/derive.py` holds the four spine-discovery functions (`find_templates_dir`, `find_effects_catalog`, `find_icon_templates`, `find_icon_mappings`) + `DerivationPipeline` with `ensure_palette(img, wh)` / `ensure_effects(img, wh)` / `ensure_icons(peh)` → `(entry, cache_hit)`. `SeedCacheUseCase` delegates: its `_populate_*` methods are thin wrappers applying the seed failure policy (`palette seeding failed:` wrap / graceful warning + None) around pipeline calls; its `_find_*` methods are deleted. The full seed unit + integration suites pass UNMODIFIED.
- **Cache-hit semantics**: `cache_hit=True` covers both the fast-path (entry dir exists pre-check) and a lost `populate_via_staging` rename race — in both cases the entry is rebuilt from co-located `meta.json` with real hashes (no sentinels ever persisted).
- **Behavior deltas vs. pre-refactor seed (cosmetic, tests-locked outcomes identical)**: missing spine inputs now surface as `RuntimeError` inside the graceful-degradation warning (e.g. "seeding: effects generation failed; continuing: effects catalog not found (...)") instead of dedicated info-style messages. Seed tests only assert `"effects"/"icon" in message` — pass unchanged.
- **Seed's `write_wallpaper_meta` stays unconditional in `_seed`** (pre-existing seed behavior, untouched); only ApplyWallpaperUseCase implements write-once wallpaper meta (checks `cache/wallpapers/<wh>/` existence BEFORE hardlink, per Task 1).
- **Concurrency decision honored**: `wallpaper set` takes no seed mutex — race-safe staging + atomic `current.json` converge (last-writer-wins); recorded in story Dev Notes, not a defect.
- **CLI**: `wallpaper set` uses module-level `typer.Argument`/`typer.Option` singletons to avoid adding NEW B008 violations (3 pre-existing B008/E501 remain in `main.py` from the version command era — out of scope). Error mapping: `ValueError`/`RuntimeError`/`OSError` → ErrorView + exit 1 (verified live: missing file → exit 1); unexpected exceptions → `logger.exception` + exit 1. Success renders one-line plain summary + structured object.
- **Live smoke test** (real CLI, synthetic spine): `wallpaper set` correctly surfaces `palette apply failed: output_dir hash mismatch: ...` when the real CsgAdapter resolves a different templates dir than a synthetic fixture — identical failure occurs via the untouched seed path at baseline; a fixture artifact, not a regression. Contract-honest fakes in tests lock the real contract (output dir named `<entry_hash>`).
- **AC 6 scope boundary locked by negative assertions** (unit + integration): no `current/` symlink created/modified and no `history.jsonl` line appended by apply — `current.json` is the only persisted artifact.
- **Serialization contract honored**: entries carried into `current.json` are always rebuilt from real cache `meta.json` values (pipeline ensure-* or load-on-race) — the sentinel-hash persistence bug class from 1.11 cannot recur here.
- Deferred items NOT touched (per story): template-discovery repo-walk coupling, unbounded `hash_file` read, CSG raw-output nondeterminism. Pre-existing baseline lint/format/mypy debt left as-is (out of story scope; recorded above).

### File List

- src/runtime/src/runtime/application/derive.py (NEW — shared spine discovery + DerivationPipeline)
- src/runtime/src/runtime/application/apply_wallpaper.py (NEW — ApplyWallpaperUseCase + ApplyWallpaperResult)
- src/runtime/src/runtime/application/seed_cache.py (MODIFIED — delegates to DerivationPipeline; behavior-identical)
- src/runtime/src/runtime/cli/main.py (MODIFIED — wallpaper sub-app + `set` command + `_run_wallpaper_set` composition)
- src/runtime/tests/unit/test_apply_wallpaper.py (NEW — 20 unit tests)
- src/runtime/tests/integration/test_apply_wallpaper_integration.py (NEW — 4 integration tests)

### Change Log

- 2026-08-31: Story 1.13 implemented — ApplyWallpaperUseCase (derive → cache → persist `current.json` only), shared `DerivationPipeline` extracted from SeedCacheUseCase (seed refactored to delegate, seed tests green unmodified), `dotfiles-runtime wallpaper set` CLI command with renderer-based output and exit-code mapping. 23 tests added; full suite green (212 passed, 1 skipped); no new lint/type/layering violations.
- 2026-09-01: Review remediation (code review: 2 decision-needed resolved as patches, 8 patches applied, 1 deferred, 5 dismissed). D1: apply's current.json read-modify-write now serialized via the seed mutex — `ISeedMutex.hold(blocking=)` added (port + FlockSeedMutex), ApplyWallpaperUseCase injects ISeedMutex and holds it blocking around reload→build→save (double-checked pattern; derivation stays outside the lock). D2: new `CacheSeeder.import_wallpaper(src, hash, source_mutable=)` — copy policy for user files (cache owns its bytes, no mutable-source alias), hardlink policy for provisioning (AD-16), post-place content verification removes TOCTOU poisoning, write-once meta backfill repairs crash-stranded entries (subsumed patch P1). Also: CLI tests for `wallpaper set` (7), missing-spine palette wrap + lost-rename-race + mutex-ordering tests, `find_icon_mappings` `.is_file()`, dead attrs removed from SeedCacheUseCase, TYPE_CHECKING import in cli/main.py, `DEFAULT_MONITOR` single-sourced in domain. Suite: 229 passed, 1 skipped; zero new lint/format/mypy/layering violations vs baseline.

### Review Findings

- [x] [Review][Decision] Apply-vs-seed race can silently revert a just-applied wallpaper — `wallpaper set` takes no mutex; concurrent with a first-run seed in another process, the applier observes `load_current() → None`, saves default-monitor state, then the seed's save wins last (SeedLockedError skip path lets apply proceed mid-seed). Recorded no-mutex decision covered apply-vs-apply only; fix would be additive (share `FlockSeedMutex` around apply's load→save) [cli/main.py:168, seed_cache.py:149]
- [x] [Review][Decision] User wallpaper is hardlinked into cache — aliases the user's mutable file; hash-then-link TOCTOU (or later in-place source rewrite) can put content under the wrong hash address with no post-link verification and no self-heal (hardlink_wallpaper verifies only when dst pre-exists). Options: copy for user-supplied wallpapers / post-link content verification / defer to Epic 2 [apply_wallpaper.py:130-137, seeder.py:110-147]
- [x] [Review][Patch] Wallpaper meta write-once guard uses entry-dir existence, not meta.json existence — crash between hardlink and meta write permanently strands an entry without meta.json (apply never backfills); concurrent applies can both write meta (last-writer-wins). Fix: guard on `meta.json` existence and backfill when missing [apply_wallpaper.py:135-142]
- [x] [Review][Patch] `wallpaper set` CLI command has zero test coverage — error mapping, exit codes, summary ternaries, cache_hits object all untested; regression would pass the whole suite. Fix: add CliRunner-based CLI tests [cli/main.py:223-282]
- [x] [Review][Patch] Top-level `ApplyWallpaperResult` import in cli/main.py defeats the file's deliberate lazy-import pattern; used only as a return annotation. Fix: `TYPE_CHECKING` import [cli/main.py:16]
- [x] [Review][Patch] Dead attributes `self._csg/_weg/_itr` in SeedCacheUseCase — assigned, never read after the pipeline extraction. Fix: remove the assignments (constructor params stay, feeding the pipeline) [seed_cache.py:89-91]
- [x] [Review][Patch] `find_icon_mappings` probes with `.exists()` while sibling finders use `.is_file()`/`.is_dir()` — a directory named `icons.yaml` passes discovery and is dir-hashed. Fix: `.is_file()` [derive.py:169]
- [x] [Review][Patch] Tautological unit assertions — `_FakeStateRepo` never touches disk, so disk-absence assertions (palette-failure test, scope-boundary test) cannot fail; palette-failure test also doesn't snapshot pre-existing state per Task 4. Fix: persist fake to disk or drop tautologies; seed pre-existing state before the palette-failure test [tests/unit/test_apply_wallpaper.py:374-387]
- [x] [Review][Patch] Missing coverage for apply's subtle paths — missing-spine `ensure_palette` → `"palette apply failed:"` wrap, and lost-rename-race (`populate_via_staging` → False) rebuild-from-meta. Fix: two unit tests [derive.py:234, 277-282]
- [x] [Review][Patch] `_DEFAULT_MONITOR = "DP-1"` duplicated across seed_cache.py and apply_wallpaper.py — fix: single shared constant [seed_cache.py:58, apply_wallpaper.py:56]
- [x] [Review][Defer] Corrupt/missing `meta.json` in an existing palette/effects/icons entry bricks that layer permanently (cache-hit = dir existence, populate is write-once, no self-heal) [derive.py:239-240, seeder.py:344-353] — deferred, pre-existing (pattern from rt-1-11, now shared; self-heal is cache-hygiene beyond story scope)
