---
baseline_commit: 2f5b47ed6c05b455f15c975b9be5fbd4c80c2360
---

# Story 2.1: Atomic `current/` symlink repoint and swap sequencing

Status: ready-for-dev

## Story

As a user,
I want a wallpaper swap to converge the desktop by repointing the `current/` symlinks only,
so that all consumers atomically see the new state with no file copying.

## Acceptance Criteria

1. **Given** a completed derivation (wallpaper/palette/effects/icons cached, `current.json` written in Epic 1 — by seed or `wallpaper set`), **When** `ReconcileDesktopStateUseCase` performs a swap, **Then** it executes the shared-data-contract swap sequence steps 1–4 exactly, in this order:
   - **Step 1 — ensure cache entries:** every entry referenced by `current.json` must exist; a missing entry is a cache miss regenerated via the shared `DerivationPipeline` (palette hard dependency, effects/icons graceful, mirroring seed/apply policy). A regenerated entry whose hash differs from the recorded one is a loud failure, not a silent repoint (see AC 6b).
   - **Step 2 — repoint ONLY the `current/` symlinks:** `current/wallpaper-<monitor>.png` per monitor in `current.json.monitors`, `current/colors.conf`, `current/colors.gtk.css`, `current/colors.yaml` → `cache/palettes/<ph>/…`, `current/effects/` → `cache/effects/<eh>/`, `current/icons/` → `cache/icons/<ih>/` (AR-8, NFR-7).
   - **Step 3 — `current.json` follows:** atomic tmp + `os.replace`, refreshed `applied_at`.
   - **Step 4 — history:** append one `history.jsonl` line with `trigger: "reconcile"` (schema per shared-data-contract; `CacheSeeder.append_history`). (FR-3 partial, AD-6, shared-data-contract Swap sequence)

2. **Given** the swap runs, **When** it completes, **Then** NO file is copied during the swap — every `current/` entry is a symlink whose target resolves into `cache/` (a consumer-visible assertion: repointing must not duplicate artifact bytes; the only legitimate byte placement is step 1's cache-miss regeneration via staging-dir, which is cache population, not swap). (AC 2, AD-6)

3. **Given** the pinned sequence, **When** the swap is implemented, **Then** it is structured as ONE discrete ordered step (a single `ReconcileDesktopStateUseCase` method boundary: entries → symlinks → `current.json` → history) so Story 2.2 can identify the single non-atomic point for crash recovery — no reload invocations, no backend calls, no consumer-path writes outside `current/` in this story. Desktop reload (contract step 5) is Stories 2.3–2.6. (AC 3, R5, shared-data-contract Swap sequence)

4. **Given** `ReconcileDesktopStateUseCase` exists, **When** the CLI runs `dotfiles-runtime reconcile`, **Then** it is an independently-invoked top-level command (AD-20) that: exits non-zero with a clear `ErrorView` message when `current.json` is absent (never seeded / nothing to reconcile), propagates a corrupt-store `ValueError`/`RuntimeError` loudly (never silently reseeds), renders success via `cli_output` (`create_renderer` + `CustomView`/`ErrorView`) with the repointed symlink list, and exits 0 on success. The full-pipeline orchestration (derive → cache → swap → reload in one `wallpaper set`) is owned by Story 2.7 — `wallpaper set` is NOT rewired in this story. (AC 4, AD-19/AD-20)

5. **Given** the desktop state already matches `current.json` (idempotent re-run, or run twice in a row), **When** `reconcile` runs again, **Then** it is a no-op-with-verification: symlinks are re-repointed (atomic tmp+`os.replace` is idempotent by construction), no cache entry is regenerated (entry-dir existence check, zero tool invocations), and exactly ONE history line is appended per run (append-only; a re-run is a new `trigger: "reconcile"` line, never an edit). (AC 5, NFR-3, AR-3)

6. **Given** `current.json` has `effects` or `icons` as `null` (graceful degradation from seed/apply), **When** the swap repoints, **Then** the corresponding `current/effects/` or `current/icons/` symlink is skipped with a visible warning (existing `CacheSeeder.repoint_current_symlinks` behavior) and the remaining symlinks are still repointed. **Given** `current.json.monitors` is empty or the state was seeded with the default, **Then** wallpaper symlinks follow the monitors dict keys (empty monitors → default `DP-1`, mirroring `ApplyWallpaperUseCase._build_monitors`). **Given** a palette artifact file is missing from the cache entry, **Then** that consumer symlink is skipped with a warning (never a dangling symlink). (AC 6, AD-17, AD-18)

6b. **Given** a cache entry referenced by `current.json` is missing and regenerated in step 1, **When** the `DerivationPipeline` returns the regenerated entry, **Then** its `entry_hash` MUST equal the hash recorded in `current.json` for that layer — a mismatch means the recorded entry cannot be rebuilt from the current spine inputs (templates/catalog/mappings changed since `wallpaper set`, AD-2 invalidation): fail loud with `RuntimeError("cache entry <hash> cannot be regenerated from current spine inputs; re-run wallpaper set")` and do NOT repoint to the different-hash entry. **Given** the WALLPAPER cache entry (`cache/wallpapers/<wh>/wallpaper.png`) itself is missing, **Then** it is re-imported from `state.wallpaper.source_path` via `CacheSeeder.import_wallpaper(source_mutable=True)`; **given** `source_path` is empty (seeded state) or no longer exists, **Then** fail loud — the wallpaper cache entry cannot be rebuilt without its source and the desktop must not be repointed to a partially repaired state. (AC 6b, AD-2, AD-9, NFR-3, shared-data-contract crash-recovery premise)

7. **Given** the hexagonal/boundary rules (AD-1, AD-12, AD-14, AD-15), **When** the story lands, **Then** the use case lives in `runtime/application/reconcile.py`, is synchronous and imperative, imports adapters only via constructor injection in the established pattern (module-level adapter imports mirror `SeedCacheUseCase`/`ApplyWallpaperUseCase` — they pass the layering test today), holds no raw `os`/`json` FS I/O itself (delegated to `CacheSeeder`/`IStateRepository`), never imports provisioning packages, and the layering test + full suite stay green. (AC 7, NFR-1, NFR-2)

## Tasks / Subtasks

- [ ] Task 1 — `application/reconcile.py`: `ReconcileDesktopStateUseCase` (AC: 1, 2, 3, 5, 6)
  - [ ] Constructor injects: `state_repo: IStateRepository`, `csg: IColorSchemeGenerator`, `weg: IEffectsGenerator`, `itr: IIconRenderer`, `install_spine: Path`, `state_root: Path`, `seeder: CacheSeeder` (concrete adapter injected per the established pattern), `mutex: ISeedMutex` — mirroring `ApplyWallpaperUseCase` exactly: construct NO adapters inside the use case, and construct the shared `DerivationPipeline` internally from the injected deps (`DerivationPipeline(state_root=state_root, seeder=seeder, csg=csg, weg=weg, itr=itr, install_spine=install_spine)`) exactly as apply does at apply_wallpaper.py:111-118 — do NOT inject the pipeline as a constructor parameter (that diverges from the established pattern and double-injects the same ports).
  - [ ] Define a frozen result dataclass `ReconcileResult` in this module (application layer defines its own result types): at minimum `repointed: list[Path]`, `skipped: list[str]` (consumer names skipped with reason), `state: DesktopState`, `cache_regenerated: list[str]` (layer names regenerated on a cache miss).
  - [ ] Deriving `skipped` WITHOUT forking the seeder: `repoint_current_symlinks` returns only the created paths (skips are log-only). Compute the EXPECTED symlink-name set from the post-step-1 state — `wallpaper-<monitor>.png` per monitor key, `colors.conf`/`colors.gtk.css`/`colors.yaml` when `state.palette` is non-null (minus artifacts actually absent from the palette entry dir), `effects` when `state.effects` non-null, `icons` when `state.icons` non-null — and diff it against the returned paths. The diff IS the skip list; no seeder changes needed.
  - [ ] `run() -> ReconcileResult` steps (ONE discrete method the dev can name as the swap step — AC 3):
    1. Load `current.json`: `state = self._state_repo.load_current()` — `None` → `RuntimeError("nothing to reconcile: no current state (never seeded)")`; corrupt-store `ValueError` propagates loudly (fail-fast guard, do NOT swallow into a reseed/reseed path).
    2. Hold `self._mutex.hold(blocking=True)` and RE-LOAD state inside the critical section (double-checked pattern, mirroring apply's D1 remediation — a concurrent `wallpaper set` must not be overtaken mid-swap).
    3. Step 1 of the contract sequence — ensure cache entries: for each layer referenced by the state, check `cache_entry_path(state_root, layer, entry_hash).exists()`.
       - Wallpaper layer missing: re-import from `state.wallpaper.source_path` via `self._seeder.import_wallpaper(Path(source_path), wh, source_mutable=True)`; `source_path` empty or no longer a regular file → `RuntimeError` (AC 6b — the wallpaper entry cannot be rebuilt without its source).
       - Derived layer missing: regenerate through `self._pipeline.ensure_palette(cached_wallpaper_img, wh)` / `ensure_effects(...)` / `ensure_icons(peh)` where `cached_wallpaper_img = state_root / "cache" / "wallpapers" / wh / "wallpaper.png"` (the cache owns its bytes — derivation NEVER needs the original source path). Palette failure aborts (`RuntimeError(f"palette reconcile failed: {exc}")`); effects/icons failure logs a warning and leaves the state field `null` (mirroring seed/apply policy). Record regenerated layers in the result.
       - Hash-mismatch guard (AC 6b — do NOT skip): whenever a derived layer is regenerated, assert the returned `entry.entry_hash ==` the hash recorded in the loaded state for that layer; mismatch → `RuntimeError(f"cache entry <hash> cannot be regenerated from current spine inputs; re-run wallpaper set")` — never repoint to an entry the recorded state does not name (spine inputs changed since the state was written; AD-2 invalidation is `wallpaper set`'s job, not reconcile's).
    4. Step 2 — repoint symlinks via `self._seeder.repoint_current_symlinks(wallpaper_target=..., monitor_names=[...], palette_entry_hash=..., effects_entry_hash=..., icons_entry_hash=...)`: wallpaper target = the cached `wallpaper.png` path, monitor names = `list(state.monitors)` (empty → `[DEFAULT_MONITOR]`), entry hashes from the (post-step-1) state. Collect the returned paths as `repointed`; the seeder logs warnings and skips missing palette artifacts / null layers (surfaced as `skipped` — parse from the seeder's return contract or re-derive the skip set; do NOT fork the repoint logic into the use case).
    5. Step 3 — `current.json` follows: re-save the state with a refreshed `applied_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")` via `self._state_repo.save(state)`. NOTE the serialization rule: NEVER persist entry objects obtained from `load_current()` unchanged (sentinel-hash bug class from rt-1-11) — rebuild entries from real cache `meta.json` via `self._seeder.load_palette_entry(entry_dir)` / `load_effects_entry` / `load_icons_entry` when an entry was regenerated, and otherwise keep the loaded state's projection (monitors are the only field legitimately carried — validated enums, not hashes). If the state was loaded (not rebuilt), re-saving it as-loaded is acceptable ONLY because `JsonStateRepository` re-projects; if review disagrees, rebuild from meta.json unconditionally.
    6. Step 4 — `self._seeder.append_history(trigger="reconcile", wallpaper_hash=state.wallpaper.content_hash, palette_hash=..., effects_hash=..., icons_hash=..., source_path=state.wallpaper.source_path)`.
  - [ ] NO reload invocations, NO `IWallpaperBackend` calls, NO writes outside `state_root` (AC 3; Stories 2.3–2.6 own reload).
- [ ] Task 2 — CLI: `reconcile` top-level command + composition (AC: 4)
  - [ ] In `cli/main.py` add `@app.command(help=...)` named `reconcile` with the standard `--format/-f OutputFormat` option (module-level `typer.Option` singleton to avoid NEW B008 violations — 3 pre-existing remain in `main.py`, do not add more).
  - [ ] Add `_run_reconcile()` composition function mirroring `_run_wallpaper_set`: resolve `state_root`/`install_spine` via the EXISTING `_resolve_state_root()`/`_resolve_install_spine()` (both already absolute), construct `JsonStateRepository`, `CsgAdapter`, `WegAdapter`, `ItrAdapter`, `CacheSeeder`, `FlockSeedMutex(state_root / ".seed.lock")` (the SAME lock file — apply and reconcile must serialize), then `ReconcileDesktopStateUseCase(...)` — the `DerivationPipeline` is constructed INSIDE the use case (mirroring apply); the CLI never builds it.
  - [ ] Error mapping: absent state / palette failure (`RuntimeError`) and `ValueError`/`OSError` → `renderer.error(ErrorView(kind=type(exc).__name__, message=str(exc)))` + `raise typer.Exit(code=1) from None`; unexpected exceptions → `logger.exception` + exit 1. Success → `renderer.custom(CustomView(plain=<one-line summary>, object={"repointed": [...], "skipped": [...], "cache_regenerated": [...]}, rich=<summary>))` following the `wallpaper set` command's pattern.
  - [ ] Do NOT rewire `wallpaper set` to call reconcile (capstone Story 2.7 owns full-pipeline orchestration; the AC 4 boundary).
- [ ] Task 3 — Unit tests `tests/unit/test_reconcile.py` (AC: 1–7)
  - [ ] Follow `test_apply_wallpaper.py`'s fake-adapter style (contract-honest fakes with invocation counters — fakes must satisfy the REAL adapter contract: output dir named `<entry_hash>`, artifacts + meta.json present; rt-1-11 review flagged contract-violating fakes). Persist the fake state repo to `tmp_path` where disk assertions matter (rt-1-13 review: `_FakeStateRepo` never touching disk made absence assertions tautological).
  - [ ] Cover: happy-path swap (all symlinks created with correct names/targets — `wallpaper-DP-1.png`, `colors.conf`, `colors.gtk.css`, `colors.yaml`, `effects`, `icons`; targets resolve into `cache/`); NO-COPY assertion (every `current/` entry `.is_symlink()` and no duplicated artifact bytes appear under `current/`); delegation (reconcile routes the whole repoint through `CacheSeeder.repoint_current_symlinks` — the seeder's internal wallpaper→palette→effects→icons ordering is its own already-locked behavior from the seed tests and is NOT observable from final on-disk state, so reconcile's tests assert delegation + correct arguments, not order); idempotent re-run (second run: zero csg/weg/itr invocations, symlinks unchanged in target, exactly one NEW history line per run); absent `current.json` → `RuntimeError` with "nothing to reconcile"; corrupt store (`ValueError` from repo fake) propagates; null effects/icons → symlink skipped, warning logged, other symlinks still repointed; empty monitors → default `DP-1` wallpaper symlink; missing palette artifact in cache entry → consumer symlink skipped (not dangling); cache-miss regeneration (delete a cache entry dir, reconcile regenerates via pipeline fake, state rebuilt from meta.json — no sentinel hashes persisted); hash-mismatch guard (pipeline fake returns an entry whose hash differs from the recorded one → `RuntimeError`, no repoint); missing wallpaper entry with usable `source_path` → re-imported; missing wallpaper entry with empty/dead `source_path` → `RuntimeError`; history line schema (`trigger: "reconcile"`, correct hashes); structural scope lock: `inspect.signature(ReconcileDesktopStateUseCase.__init__)` accepts NO `IDesktopReloader`/backend/factory parameter — the reload channel is structurally absent, which is the honest negative assertion for AC 3 (there is no reloader instance to count invocations on, and that absence is the assertion).
  - [ ] Mutex assertions: reconcile holds the blocking mutex around load→repoint→save — the fake mutex records `hold(blocking=True)` and exposes hold/release ordering; assert the SECOND `load_current()` (the re-check) occurs inside the `with` block (i.e., after hold, before release), mirroring apply's double-checked pattern.
- [ ] Task 4 — Integration test `tests/integration/test_reconcile_integration.py` (AC: 1, 2, 5)
  - [ ] Mirror `test_apply_wallpaper_integration.py` EXACTLY: fake adapters with counters, tmp `state_root`, fake install spine with `generated/default.png` + spine inputs. Seed first (`SeedCacheUseCase`), then apply a new PNG (`ApplyWallpaperUseCase` — produces the ahead-of-symlinks `current.json` this story reconciles), then: reconcile → all `current/` symlinks point at the NEW palette/effects/icons entries (real paths, `.is_symlink()`, `os.readlink` target correctness); re-running reconcile is idempotent (counters unchanged, one new history line); a deleted palette cache entry is regenerated on reconcile (contract crash-recovery premise: missing target = cache miss); a deleted wallpaper cache entry is re-imported from `current.json`'s `source_path` end-to-end.
- [ ] Task 5 — CLI tests for `reconcile` (AC: 4)
  - [ ] Extend the `test_cli_wallpaper_set.py` pattern: `reconcile` success (exit 0, summary rendered), absent-state failure (exit 1, ErrorView rendered), `--format json` object shape. Use the same CliRunner + env/monkeypatch wiring for `state_root`/`install_spine`.
- [ ] Task 6 — Full green gate (AC: 7)
  - [ ] `uv run --directory src/runtime pytest -q` (baseline: 229 passed, 1 skipped / 230 collected)
  - [ ] `uv run --directory src/runtime ruff check src/runtime` (baseline: 3 pre-existing violations in main.py/models.py — zero NEW)
  - [ ] `uv run --directory src/runtime ruff format --check src/runtime` (baseline: 5 pre-existing unformatted files — new/edited files format-clean)
  - [ ] `uv run --directory src/runtime mypy --strict src/runtime` (baseline: 4 pre-existing errors — zero NEW)
  - [ ] `tests/architecture/test_layering.py` green (module-level application→adapters imports mirror `SeedCacheUseCase`/`ApplyWallpaperUseCase`; if a NEW import fails the test, the fix is constructor injection, not weakening the test)

## Dev Notes

### Scope boundary — this is the swap-sequencing story, NOT convergence

This story delivers the swap sequence steps 1–4 ONLY. It deliberately does NOT:
- reload ANY desktop component (Hyprland `hyprctl reload` → Story 2.3, AGS restart → 2.4, Hyprpaper channel → 2.5, terminal palette → 2.6),
- invoke wallpaper backends or `IWallpaperBackendFactory` (backend invocation per monitor is Stories 2.5+ / the capstone),
- implement crash-mid-swap detection/reversion (Story 2.2 — it builds on THIS story's discrete-step ordering; make the swap one named method so 2.2 can wrap/instrument it),
- rewire `wallpaper set` to call reconcile (Story 2.7 capstone owns derive → cache → swap → reload orchestration; until then `wallpaper set` still persists only `current.json` and `reconcile` is the manual convergence step — this is the intended Epic-1-to-Epic-2 seam),
- implement history.jsonl hardening/paging (Story 3.1 — the append here is the contract-pinned step 4 reusing the existing, tests-locked `CacheSeeder.append_history`).

Consequence: after this story, a user runs `wallpaper set <img>` then `dotfiles-runtime reconcile` to visually converge. `current.json` can still be AHEAD of `current/` between the two commands — that inversion is what reconcile fixes.

### The swap sequence is PINNED — shared-data-contract is the spec

Owner rule (shared-data-contract "Swap sequence"): `ReconcileDesktopStateUseCase` is the SOLE owner of the swap; `SeedCacheUseCase` performs the identical sequence once at seed time (already implemented — do not touch seed); `ApplyWallpaperUseCase` updates desired state and delegates the actual swap to Reconcile (the delegation wiring is 2.7's). Order is non-negotiable: entries → symlink repoint (wallpaper → palette → effects → icons) → `current.json` → history → (later) reload. "Symlinks lead, `current.json` follows" means a crash mid-swap leaves the store lagging the filesystem — recoverable by re-deriving symlinks from `current.json` (2.2). Each repoint is atomic per-symlink (tmp symlink + `os.replace`) — the sequence as a whole is NOT atomic, and that is by design (AC 3).

### Reuse — almost everything exists; do not reinvent

- `CacheSeeder.repoint_current_symlinks(wallpaper_target, monitor_names, palette_entry_hash, effects_entry_hash, icons_entry_hash)` (adapters/seeder.py:508) already implements the full repoint set with per-monitor names, null-layer skips, missing-artifact skips with warnings, and atomic repoints. Reconcile should CALL it, not fork it.
- `CacheSeeder.append_history(trigger, ...)` (adapters/seeder.py:569) — O_APPEND + O_NOFOLLOW + full-write loop + fsync. Pass `trigger="reconcile"` (the contract's trigger enum includes it).
- `CacheSeeder.load_palette_entry` / `load_effects_entry` / `load_icons_entry` — rebuild entries from co-located `meta.json` with real hashes (no sentinels).
- `DerivationPipeline.ensure_palette/ensure_effects/ensure_icons` (application/derive.py) — cache-miss regeneration. Feed them the CACHED wallpaper path (`cache/wallpapers/<wh>/wallpaper.png`), never the original source path — the cache owns its bytes (apply copies user files; source may be gone).
- `cache_entry_path(state_root, layer, entry_hash)` (adapters/cache.py:107) — existence checks.
- `FlockSeedMutex(state_root / ".seed.lock")` — the SAME lock file apply uses (rt-1-13 D1). Reconcile must serialize against concurrent `wallpaper set`, or a reconcile repointing to hash A can be overtaken by an apply saving hash B and the desktop converges to a stale state.

### Contract subtleties (get these exactly right)

- **Symlink targets are absolute cache paths** — the seeder passes `Path` targets that resolve under `state_root`; keep that convention (the spine consumer symlinks point INTO `current/`, not into `cache/` directly).
- **Effects/icons are directory symlinks** (`current/effects/` → `cache/effects/<eh>/`), palette artifacts are file symlinks. The seeder already distinguishes them.
- **`current.json` re-save**: the state loaded from disk is a projection (only `hash` + `generated_at` on entries — `JsonStateRepository` sentinel contract). Re-saving the loaded state as-is is safe ONLY because `JsonStateRepository._state_to_dict` re-projects the projection; but entries that were REGENERATED in step 1 must be rebuilt from real meta.json (`load_*_entry`) so the saved state never carries `SENTINEL_HASH` ("0"*64). The rt-1-11 review bug class ("Sentinel hashes persisted in current.json") must not recur here.
- **`source_path` in the history line**: use `state.wallpaper.source_path` (may be `""` for seeded state — the contract allows `<abs-or-empty>`).
- **Missing `current.json` is a hard error for reconcile** (unlike seed, which creates it): reconcile reconciles TO recorded state; with no state there is nothing to reconcile and no basis for consumer symlinks. Do NOT fall back to provisioning's `generated/` here — that is the seeder's job.
- **Regeneration must reproduce the recorded hash, or reconcile must not proceed** (AC 6b): `ensure_*` recomputes entry hashes from the CURRENT spine inputs (AD-2). If templates/catalog/mappings changed since `wallpaper set`, the recomputed hash names a different entry — repointing to it would converge the desktop to state the recorded `current.json` never described, silently violating "filesystem + index agree". Reconcile repairs a crashed swap for the state that was recorded; it does not re-derive a NEW desired state (that is `wallpaper set`'s job). Hence: regenerated hash ≠ recorded hash → loud `RuntimeError`.

### Failure policy (mirror seed/apply exactly)

- Palette = hard dependency: regeneration failure → `RuntimeError(f"palette reconcile failed: {exc}")`, propagates, `current.json` untouched (save happens after all layers succeed/degrade).
- Effects/icons = graceful: `logger.warning(...)`, layer stays `null`, its symlink skipped with a warning.
- Corrupt current.json (`ValueError` from `load_current`) propagates loudly — never treated as absent state.

### Concurrency (recorded decision)

Reconcile holds the seed mutex BLOCKING around its load→repoint→save critical section, re-loading state inside the lock (double-checked, mirroring apply's D1 remediation). Derivation (step 1) stays OUTSIDE the lock (staging is race-safe; tool invocations stay parallel) — same split apply uses. AC-concurrent `wallpaper set` + `reconcile` serialize on the same `.seed.lock`.

### Code style gates (enforced)

Python 3.14, `mypy --strict` (no untyped defs, `from __future__ import annotations` at top), ruff line-length 100, ruff select E/F/I/N/W/UP/B. Parenthesize multi-except tuples (PEP 758 unparenthesized form was flagged in 1.11 review). Timestamps: `datetime.now(UTC).isoformat().replace("+00:00", "Z")` — strict ISO-8601 Z. House style: dense module docstrings citing AD-numbers, no inline "why" comments beyond those. Application→adapters module-level imports are established (seed/apply do it and pass layering) — mirror exactly.

### Previous story intelligence (rt-1-13 — the direct predecessor; the apply/reconcile seam)

- Review remediation D1 added `ISeedMutex.hold(blocking=)` and made apply hold it around its read-modify-write — reconcile MUST join the same protocol or the apply-vs-reconcile race is reintroduced.
- Review remediation D2 added `CacheSeeder.import_wallpaper(source_mutable=)` with post-place content verification — reconcile's regeneration path inherits this correctness via `DerivationPipeline`; do not bypass `populate_via_staging`.
- Negative assertions lock scope boundaries (apply's "no symlink, no history" tests) — reconcile's tests need the mirror image: "no reload, no backend invocation, no writes outside state_root/current/".
- Tautological-test lesson (rt-1-13 review): fake state repos must persist to disk when tests assert disk absence/presence.
- Pre-existing debt NOT this story's job (do not worsen): corrupt/missing meta.json in an existing entry bricks that layer (deferred rt-1-13 — reconcile's cache-miss regeneration does NOT cover a dir that EXISTS with bad meta; `load_*_entry` raises → for reconcile a corrupt entry surfaces as a loud failure, do NOT silently rmtree+regenerate beyond what the pipeline already does); template-discovery repo-walk coupling (deferred rt-1-11); unbounded `hash_file` read (deferred rt-1-7); CSG raw-output nondeterminism — artifact_hashes for the same entry could differ if regenerated; entry reuse via existence-check masks it; do not add regeneration logic beyond genuine misses.

### Git intelligence

HEAD = `2f5b47e` (auto-commit of review findings). Runtime last touched by `6dc250f` (Story 1.13) + review fixes; commits since touched AGS capture tooling, not `src/runtime/`. Baseline suite: 229 passed, 1 skipped (230 collected). `src/runtime/` is clean of unrelated churn — expect a green baseline before you start.

### Latest technical information

No new external dependencies are needed — the swap is stdlib-only (`os.symlink`, `os.replace`, `pathlib`). Python 3.14, Typer, pytest, ruff, mypy versions are pinned in `src/runtime/pyproject.toml`/`uv.lock`; do not bump them in this story. The `os.replace`-over-symlink atomicity guarantee used by `_repoint_symlink` is POSIX rename semantics — same-filesystem, already verified in rt-1-11; no version research required.

### Testing standards summary

- Runner: `uv run --directory src/runtime pytest -q`. Integration tests use contract-honest fakes (no real tools, no skip logic); the real-tool skip pattern belongs to the csg/weg/itr adapter integration tests only. Unit tests are pure fakes.
- Lint/type gates in Task 6, all with `--directory src/runtime`; baseline debt documented above — zero NEW violations is the bar.
- Layering: domain purity (no os/subprocess/shutil/pathlib), ports are ABCs, cross-package forbidden set (`provisioning`, `core`, `infrastructure`, `color_scheme_generator`, `wallpaper_effects_generator`, `icon_templates_renderer`, `config_assembler_engine`, `oci_runtime`).
- Assertion style: unit tests assert behavior + contracts (invocation counts, symlink targets, history schema); integration tests assert filesystem outcomes end-to-end.

### Project Structure Notes

New files:
- `src/runtime/src/runtime/application/reconcile.py` (NEW — ReconcileDesktopStateUseCase + ReconcileResult)
- `src/runtime/tests/unit/test_reconcile.py` (NEW)
- `src/runtime/tests/integration/test_reconcile_integration.py` (NEW)
Modified:
- `src/runtime/src/runtime/cli/main.py` (top-level `reconcile` command + `_run_reconcile` composition)
No changes: `domain/`, `ports/`, `adapters/` (reuse `CacheSeeder` as-is), `pyproject.toml`, `SeedCacheUseCase`, `ApplyWallpaperUseCase`, provisioning.

### References

- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md` — Epic 2 intro, Story 2.1 ACs, Implementation notes R1/R5, Story 2.2 (what builds on this), Story 2.7 (capstone)
- Architecture spine: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md` — AD-1/2/5/6/8/9/10/12/13/14/15/17/18/19/20, Derivation Graph mermaid (which symlinks exist), Structural Seed (current/ layout)
- Shared data contract: same folder `shared-data-contract.md` — current.json schema v2 + monitors rules, history.jsonl schema (trigger enum incl. "reconcile"), Swap sequence section (THE spec for this story: owner, order, crash-recovery premise)
- Existing code: `src/runtime/src/runtime/adapters/seeder.py` (repoint_current_symlinks, append_history, load_*_entry, _repoint_symlink atomicity), `application/apply_wallpaper.py` (mutex protocol D1, seam docstring, monitor defaulting), `application/seed_cache.py` (swap-sequence precedent, failure policy), `application/derive.py` (DerivationPipeline ensure-*), `adapters/cache.py` (cache_entry_path, populate_via_staging), `adapters/json_state_repository.py` (projection + sentinel contract), `cli/main.py` (composition wiring, renderer pattern)
- Previous stories: `_bmad-output/implementation-artifacts/rt-1-13-applywallpaperusecase.md` (D1/D2 remediations, scope-boundary test pattern), `rt-1-11-first-run-self-seeding.md` (seeder hardening, sentinel-hash lesson)
- Deferred ledger: `_bmad-output/implementation-artifacts/deferred-work.md` — rt-1-5/6/7/8/9/10/11/13 entries

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
