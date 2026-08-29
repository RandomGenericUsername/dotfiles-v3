# Story 1.6: Layered cache populator with staging-dir

---
baseline_commit: c210966
---

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want write-once cache entries populated via the staging-dir pattern,
so that concurrent population is safe and cache entries are never half-written.

## Acceptance Criteria

1. **Given** a target `cache/<layer>/<hash>/` entry where `<layer>` is one of `wallpapers|palettes|effects|icons` and `<hash>` is the per-layer `entry_hash` from `adapters/hashing.py` (lowercase hex, `HASH_ALGORITHM=="sha256"`), **When** population runs via `populate_via_staging(target, populate_fn)`, **Then** `populate_fn` generates into `cache/.staging-<pid>-<unique>/` (sibling of `cache/`, not inside `target`) then atomically `os.rename`/`os.replace` to `target`; if `target` already existed before rename, staging is discarded (removed) and the existing final entry is returned unchanged — never overwritten (AC 1, AD-9, shared-data-contract cache layout, cache-model.md staging-dir)
2. **Given** a wallpaper file `src_path` and target `cache/wallpapers/<wh>/wallpaper.png` where `wh = hash_file(src_path)` from `adapters/hashing.py` (chunked 64 KiB, `sha256(file_bytes)`), **When** `hardlink_or_copy(src_path, dst_path)` is called inside the staging dir, **Then** it attempts `os.link(src, dst)` (hardlink) first; on `OSError` with `errno.EXDEV` (cross-filesystem) it falls back to `shutil.copy2(src, dst)` preserving metadata; on any other `OSError` it propagates; the cached `wallpaper.png` survives deletion of `src_path` (inode retained for hardlink, copy retained for fallback) (AC 2, AD-16, shared-data-contract wallpapers/<wh>/wallpaper.png)
3. **Given** concurrent population (two processes/threads call `populate_via_staging` for the same `target` simultaneously) or a crash between staging population and rename, **When** the second call or next run starts, **Then** at most one writer wins the `os.rename`; the loser discards staging cleanly (no orphan `cache/.staging-*` left behind except on unclean crash, which is cleaned on next `populate` for that target); partial entries are never visible as `cache/<layer>/<hash>/` — either the final dir exists fully-formed or not at all (AC 3, AD-9 race prevention, AD-3 FS authority)
4. **Given** per-layer payloads — wallpaper (single file + `meta.json`), palette (`colors.yaml`/`colors.conf`/`colors.gtk.css` + `meta.json`), effects (variable `*.png` + `meta.json`), icons (variable `*.svg` + `meta.json`) — **When** each layer populates via staging, **Then** staging contains exactly the layer's artifacts plus `meta.json` with literal `hash_algorithm: "sha256"` (`== HASH_ALGORITHM` from `adapters/hashing.py`), `kind`, `entry_hash`/`content_hash`, per-layer input hashes (`input_template_hash`/`input_catalog_hash`/etc.), `artifact_hashes` per `shared-data-contract.md` meta.json schemas, and `generated_at`/`imported_at` ISO-8601 UTC; `meta.json` is written **inside** staging before rename so it is atomically visible (AC 4, AD-8 SHA-256 versioned, shared-data-contract meta.json)
5. **Given** the hexagonal boundary (AD-1, AD-14, AD-15), **When** cache helpers are added, **Then** domain stays pure (allowlist `dataclasses`,`enum`,`typing`,`collections`,`collections.abc`,`functools`,`re`,`__future__` only; no `os`/`subprocess`/`shutil`/`pathlib` and no Path FS calls), helpers live in `adapters/` only (allowed `os`/`pathlib`/`shutil`/`hashlib`), ports remain ABCs, cross-package forbidden set untouched, and `uv run --directory src/runtime pytest` + `ruff check` + `ruff format --check` + `mypy --strict` + `tests/architecture/test_layering.py` all pass (AC 5, AD-1, AD-14, NFR-1)

## Tasks / Subtasks

- [x] Task 1 — Create `adapters/cache.py` (or `adapters/cache_populator.py`) — the sole staging-dir + hardlink module (AC: 1, 2, 3, 5)
  - [x] **Location MUST be `src/runtime/src/runtime/adapters/cache.py`** (or `cache_populator.py` — pick one, document choice, stay consistent). **MUST be in `adapters/`**, NOT `domain/`/`ports`/`application` (domain allowlist forbids `os`/`pathlib`/`shutil`; ports are ABCs only). Keep `domain/models.py` unchanged except for using hashes from `adapters/hashing.py`. No new domain entities.
  - [x] Imports allowed ONLY in this file: `os`, `errno`, `shutil`, `hashlib` (if needed), `pathlib.Path`, `typing.Final/Literal`, `datetime`, `json`, `tempfile` (optional for staging naming). Do NOT add `os`/`pathlib` to `domain/` or `ports/`.
  - [x] Export typed helpers — strict `mypy` signatures for every export:
    ```python
    from pathlib import Path
    from collections.abc import Callable

    CACHE_LAYERS: Final[frozenset[str]] = frozenset({"wallpapers", "palettes", "effects", "icons"})
    CACHE_STAGING_PREFIX: Final[str] = ".staging-"

    def cache_entry_path(state_root: Path, layer: str, entry_hash: str) -> Path: ...
        # validates layer in CACHE_LAYERS and entry_hash is 64-char lowercase hex; returns state_root / "cache" / layer / entry_hash

    def populate_via_staging(target: Path, populate_fn: Callable[[Path], None]) -> bool: ...
        # Generates into sibling staging dir cache/.staging-<pid>-<rand>/ then atomically renames to target.
        # Returns True if this call created target, False if target already existed (staging discarded).
        # populate_fn receives the staging Path and must create artifacts + meta.json inside it.
        # Raises FileExistsError only if staging cannot be cleaned? Never raises for existing target — discards gracefully.

    def hardlink_or_copy(src: Path, dst: Path) -> None: ...
        # Tries os.link(src, dst); on EXDEV falls back to shutil.copy2(src,dst); propagates other OSError.

    def _staging_dir_for(target: Path) -> Path: ...
        # Helper: cache/.staging-<pid>-<uuid4-hex8> sibling of cache/; uses os.getpid() + uuid/secrets for uniqueness.
    ```
  - [x] Choose filename once and use everywhere (imports, tests, layering). Recommended: `adapters/cache.py` (short, matches `cache-model.md` "cache population"). If `cache_populator.py` preferred, rename consistently.
  - [x] Keep `HASH_ALGORITHM` import from `adapters/hashing.py` (do not duplicate): `from runtime.adapters.hashing import HASH_ALGORITHM` — assert in tests that `meta.json["hash_algorithm"] == HASH_ALGORITHM == "sha256"`.

- [x] Task 2 — Implement `hardlink_or_copy` exactly (AC: 2)
  - [x] Code:
    ```python
    def hardlink_or_copy(src: Path, dst: Path) -> None:
        try:
            os.link(src, dst)
        except OSError as e:
            if e.errno == errno.EXDEV:
                shutil.copy2(src, dst)
            else:
                raise
    ```
  - [x] Ensure `dst.parent` exists (`dst.parent.mkdir(parents=True, exist_ok=True)`) before link/copy — staging dir is fresh, but be defensive.
  - [x] Do NOT use `Path.hardlink_to` (py3.10+) or `os.symlink` — explicit `os.link` + `shutil.copy2`.
  - [x] `shutil.copy2` preserves `st_mtime` and mode; hardlink preserves inode (verified by `os.stat(src).st_ino == os.stat(dst).st_ino` when link succeeds).
  - [x] Propagate non-EXDEV `OSError` (EPERM, EACCES, ENOENT, EROFS) — caller handles.

- [x] Task 3 — Implement `populate_via_staging` atomically (AC: 1, 3)
  - [x] Pseudocode — follow AD-9 + cache-model.md precisely:
    ```python
    def populate_via_staging(target: Path, populate_fn: Callable[[Path], None]) -> bool:
        if target.exists():  # fast-path: existing final entry never overwritten
            return False  # already exists, do nothing
        cache_dir = target.parent  # .../cache/<layer>
        staging = cache_dir.parent / f".staging-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        # Ensure cache_dir exists
        cache_dir.mkdir(parents=True, exist_ok=True)
        staging.mkdir(parents=True, exist_ok=False)
        try:
            populate_fn(staging)  # caller writes artifacts + meta.json into staging
            # Validate staging now contains expected content (at least one file)
            try:
                os.rename(staging, target)  # atomic on same filesystem (POSIX)
            except FileExistsError:
                # Lost race — another writer created target first
                shutil.rmtree(staging, ignore_errors=True)
                return False
            except OSError as e:
                if e.errno == errno.ENOTEMPTY or "File exists" in str(e):
                    shutil.rmtree(staging, ignore_errors=True)
                    return False
                raise
            return True
        except BaseException:
            # populate_fn failed or rename failed — clean staging, never leave partial target
            shutil.rmtree(staging, ignore_errors=True)
            raise
        finally:
            # Defensive: if staging still exists (e.g., rename succeeded but exception in caller), ensure removed
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
    ```
  - [x] **Critical invariants:**
    - Staging is a **sibling** of `cache/` (`cache/.staging-<pid>-<rand>/`), NOT inside `target` — matches spec `cache/.staging-<pid>/`.
    - Use `os.rename` (or `os.replace` if target may exist) — `os.rename` is atomic on POSIX same-mount; if using `os.replace`, it atomically replaces, but spec says discard if exists. So check `target.exists()` before rename and handle `FileExistsError` by discarding staging. Do NOT use `shutil.move` (non-atomic cross-fs fallback).
    - Staging must be removed in **all** error paths (populate_fn exception, rename race, unexpected OSError) — `try/finally` + `shutil.rmtree(ignore_errors=True)`.
    - Validate `target` is under `state_root/cache/<layer>/<64hex>` — reject `target` whose `parent.name not in CACHE_LAYERS` or `target.name` not 64 hex or `target.parent.parent.name != "cache"` with `ValueError`.
    - Handle `ENOTEMPTY` / `EEXIST` on `os.rename` when target appeared between `exists()` check and rename — TOCTOU race, discard staging.
  - [x] Alternative valid design: if `cache_dir` and `staging` are on same filesystem (they are siblings, so yes), `os.rename` is atomic; cross-filesystem staging is impossible because sibling ensures same parent mount. Document this.
  - [x] Do NOT implement eviction/prune — list-only per AR-10.

- [x] Task 4 — Implement `cache_entry_path` + `meta.json` helper (AC: 4)
  - [x] `cache_entry_path(state_root: Path, layer: str, entry_hash: str) -> Path`:
    - Validate `layer in CACHE_LAYERS` else `ValueError(f"unknown layer {layer}")`.
    - Validate `_is_hex64(entry_hash)` (reuse `adapters/hashing.py::_is_hex64` or duplicate with `len==64` + hex check) else `ValueError`.
    - Return `(state_root / "cache" / layer / entry_hash.lower())`. Do NOT create dirs here.
  - [x] Do NOT write `meta.json` in this story's helpers directly — `populate_fn` writes it. But provide example contract in docstring showing expected `meta.json` shape per layer (copy from `shared-data-contract.md`):
    - `wallpapers/<wh>/meta.json`: `{hash_algorithm, kind:"wallpaper", content_hash, source_path, imported_at}`
    - `palettes/<ph>/meta.json`: `{hash_algorithm, kind:"palette", entry_hash, source_wallpaper_hash, input_template_hash, artifact_hashes:{colors.yaml,colors.conf,colors.gtk.css}, generated_at}`
    - Document that `hash_algorithm` MUST be `HASH_ALGORITHM` literal.
  - [x] Ensure `populate_fn` writes `meta.json` with `json.dump(..., indent=2, sort_keys=True)` + UTF-8, and that `artifact_hashes` values are 64-char hex.

- [x] Task 5 — Tests for staging, hardlink fallback, and write-once (AC: 1, 2, 3)
  - [x] Create `src/runtime/tests/unit/test_cache.py` — **MUST** be under `tests/unit/` (not `domain`/`ports`), fast path (`pytest -k "not integration"`; no `pytest.mark.integration`).
  - [x] Cover at minimum (table: test → setup → expectation):
    | Test | Inputs | Expectation |
    |---|---|---|
    | `test_populate_via_staging_creates_target` | `target=tmp/cache/wallpapers/<wh>` absent, `populate_fn` writes `wallpaper.png` + `meta.json` | `populate_via_staging` returns `True`, `target` exists with files, no `cache/.staging-*` remains |
    | `test_populate_via_staging_never_overwrites` | `target` exists with `old_content`, second `populate_via_staging` with `new_content` | returns `False`, `target` still has `old_content`, staging discarded |
    | `test_populate_via_staging_discards_on_populate_fn_exception` | `populate_fn` raises `RuntimeError` | staging removed, `target` not created, exception propagates |
    | `test_populate_via_staging_atomic_rename` | mock/verify `os.rename` called with `(staging, target)` on same mount | atomic rename used, not `shutil.move` |
    | `test_populate_via_staging_sibling_location` | call with `state_root/tmp` | staging dir is `tmp/cache/.staging-<pid>-*`, not `target/.staging` nor `tmp/.staging` |
    | `test_hardlink_or_copy_hardlink_when_same_fs` | `src` and `dst` on same tmp fs | `os.stat(src).st_ino == os.stat(dst).st_ino` (or `st_nlink >=2`) and content identical; survives `src.unlink()` |
    | `test_hardlink_or_copy_fallback_on_EXDEV` | monkeypatch `os.link` to raise `OSError(errno.EXDEV, ...)` | falls back to `shutil.copy2`, `st_ino` differs, content identical, survives src deletion |
    | `test_hardlink_or_copy_propagates_non_EXDEV` | `os.link` raises `OSError(errno.EACCES, ...)` | exception propagates, no copy attempted |
    | `test_wallpaper_hardlink_survives_source_deletion` | populate wallpaper layer via staging + hardlink, then `src.unlink()` | `cache/wallpapers/<wh>/wallpaper.png` still readable and `hash_file` matches original `wh` |
    | `test_cache_entry_path_validates_layer_and_hash` | invalid layer or non-hex hash | `ValueError` |
    | `test_concurrent_populate_one_wins` | two sequential `populate_via_staging` for same target (simulate race: create target before second rename) | one `True`, one `False`, final content is from winner, no exception |
    | `test_meta_json_hash_algorithm_pinned` | `populate_fn` writes `meta.json` with `hash_algorithm` | assert `meta["hash_algorithm"] == HASH_ALGORITHM == "sha256"` and `meta["hash_algorithm"] == "sha256"` literal |
    | `test_staging_cleanup_on_crash` | `populate_fn` succeeds but simulate `os.rename` raising `OSError` | staging cleaned, target not left partial |
  - [x] Use `tmp_path` for `state_root`; use deterministic `write_bytes(b"hello")` for wallpaper bytes; reuse `tests/fixtures/wallpaper.png` for realistic wallpaper hash (`hash_file` gives `619cd350...`). Do NOT use `random`/`os.urandom`.
  - [x] For EXDEV fallback test, monkeypatch `os.link` only, not `Path.open`; predicate `if "hardlink" in str(src)` etc. Prefer `unittest.mock.patch("runtime.adapters.cache.os.link", side_effect=OSError(errno.EXDEV, "cross-device"))`.
  - [x] Verify no orphan staging after each test: `assert not any(p.name.startswith(".staging-") for p in (tmp_path/"cache").rglob(".staging-*"))` or `list((state_root/"cache").glob(".staging-*")) == []`.

- [x] Task 6 — Ensure zero layering debt and full green (AC: 5)
  - [x] Keep helpers in `adapters/cache.py` only; verify `domain/models.py` still imports only allowlist (`dataclasses`,`enum`,`typing`,`collections`,`collections.abc`,`functools`,`re`,`__future__`); no new imports in domain/ports. Verify `sprint-status.yaml` still has `rt-1-7`… as `backlog`.
  - [x] Verify `ports` remain pure ABCs: `runtime.ports.*` unchanged.
  - [x] Run and require green:
    ```bash
    uv run --directory src/runtime pytest -q
    uv run --directory src/runtime pytest -k cache -v
    uv run --directory src/runtime ruff check
    uv run --directory src/runtime ruff format --check
    uv run --directory src/runtime mypy --strict src/runtime
    ```
    All existing tests (60+ from Stories 1.1–1.5: scaffold + domain + ports + determinism + hashing) must still pass; new cache unit tests add coverage without breaking layering. `tests/architecture/test_layering.py` must pass — domain allowlist + no Path FS calls + cross-package forbidden set untouched.
  - [x] Confirm `src/runtime/src/runtime/adapters/__init__.py` stays minimal; do NOT add star imports that create cycles.
  - [x] Verify non-goals are NOT included: no `IColorSchemeGenerator`/`IEffectsGenerator`/`IIconRenderer` adapter logic (Stories 1.7–1.9), no `IStateRepository` JSON store or `current.json`/`history.jsonl` (Story 1.10), no CLI `wallpaper set`, no `ApplyWallpaperUseCase` — those are later.

## Dev Notes

### Scope boundary — this story is STAGING-DIR CACHE POPULATION ONLY

Story 1.6 **defines** the write-once, atomic, race-safe cache entry creation via staging-dir + hardlink. It does **NOT** implement:
- Hashing helpers (Story 1.5 — already done, reuse `adapters/hashing.py`)
- CSG/WEG/ITR adapters with env overrides (Stories 1.7–1.9)
- `IStateRepository` JSON store or `current.json`/`history.jsonl` persistence (Story 1.10)
- `SeedCacheUseCase` / `ApplyWallpaperUseCase` / `ReconcileDesktopStateUseCase` (Stories 1.11–1.13)
- Any CLI command (`wallpaper set`, `inspect`, `cache list`)
- Cache eviction/prune (deferred to Phase 3+ per AR-10)
- Consumer symlink repoint (`current/` symlinks) — that is Epic 2, Story 2.1
- Actual CSG generation or template rendering — only the staging wrapper + hardlink

Resist adding adapter logic — write only the staging-dir helper, hardlink-or-copy, cache_entry_path, and unit tests.

### Source tree components to touch

| Path | Action | Notes |
|------|--------|-------|
| `src/runtime/src/runtime/adapters/cache.py` | **CREATE** | Staging-dir population + hardlink helper + cache_entry_path; imports `os`,`errno`,`shutil`,`pathlib.Path`,`uuid` only here (allowed I/O layer, AD-1) |
| `src/runtime/src/runtime/adapters/hashing.py` | **USE** (already exists) | Import `HASH_ALGORITHM`, `hash_file`, `canonical_hash_dir`, `*_entry_hash` — do NOT duplicate hex validation logic; reuse `_is_hex64` if exported or re-validate locally |
| `src/runtime/tests/unit/test_cache.py` | **CREATE** | Unit tests for staging atomicity, never-overwrite, hardlink + EXDEV fallback, concurrent race, sibling location, cleanup (see Task 5); **MUST NOT** place under `domain`/`ports` |
| `src/runtime/tests/fixtures/wallpaper.png` | **USE** (already exists) | Deterministic 4×4 PNG (`619cd350...`); reuse for `hash_file` + hardlink tests |
| `_bmad-output/implementation-artifacts/rt-1-6-layered-cache-populator.md` | **UPDATE** | Completion Notes + File List filled by dev |
| `src/runtime/src/runtime/domain/**` | **LEAVE ALONE** | No `hashlib`/`os`/`pathlib` imports; domain stays pure (AD-14) |
| `src/runtime/src/runtime/ports/**` | **LEAVE ALONE** | ABCs only; no concrete classes |
| `src/runtime/src/runtime/adapters/__init__.py` | **LEAVE ALONE** or minimal | Stays lean; no cross-package imports |
| `src/runtime/src/runtime/application/**` | **LEAVE ALONE** | Use cases arrive in Stories 1.11–1.13 |

### Testing standards summary

- **Runner:** `uv run --directory src/runtime pytest` (`pyproject.toml: testpaths=["tests"]`, `pythonpath=["src","."]`, `requires-python>=3.14`). Unit cache tests run in fast path (`pytest -k "not integration"`); do NOT tag with `pytest.mark.integration`.
- **Lint/type:** `uv run --directory src/runtime ruff check` (py314, line 100, double quotes); `mypy --strict` (`python_version=3.14`, allowlist-only for domain/ports). No new ignores; `adapters/cache.py` must be `ruff format` clean.
- **Fixtures:** Reuse `tests/fixtures/wallpaper.png` (74 bytes); `tmp_path` files via `write_bytes(b"...")` — no `random`/`PIL`. Wallpaper hardlink tests must verify `src.unlink()` then `dst.read_bytes()` still works.
- **Atomicity assertion:** Verify `os.rename` is called, not `shutil.move`; verify staging sibling location `cache/.staging-<pid>-*`.
- **EXDEV fallback:** Monkeypatch `os.link` to raise `OSError(errno.EXDEV, ...)`; assert `shutil.copy2` path survives src deletion but `st_ino` differs.
- **Idempotence:** Second `populate_via_staging` for existing target returns `False` without calling `populate_fn` again (or calling but discarding).

### Architecture extraction — what this story must respect

| Decision | Relevance | What to do |
|----------|-----------|------------|
| **AD-1 Hexagonal** | Staging I/O in adapters | Keep staging+hardlink helper in `adapters/cache.py`; **MUST NOT** import `os`/`pathlib` into `domain` |
| **AD-2 Layered cache key** | Key = hash of ALL inputs via `adapters/hashing.py` | Use `hash_file`/`canonical_hash_dir`/`*_entry_hash` to compute `<hash>`; entry dir = `cache/<layer>/<hash>` via `cache_entry_path` |
| **AD-3 JSON store / FS authority** | `meta.json` co-located, FS authority | Write `meta.json` inside staging before rename; filesystem `cache/` + `current/` is truth (current/ arrives Epic 2) |
| **AD-5 State root** | Runtime owns `$XDG_STATE_HOME/dotfiles/` | Helpers take `state_root: Path` injected by caller; never discover XDG themselves, never write under install spine |
| **AD-6 Swap = symlinks** | No copying during swap | Cache dirs are write-once; this story ensures write-once is race-safe — no swap code here |
| **AD-8 SHA-256 versioned** | `meta.json: hash_algorithm: sha256` | All `meta.json` writes use `hash_algorithm == HASH_ALGORITHM == "sha256"` literal |
| **AD-9 Staging-dir** | Population via `cache/.staging-<pid>/` + `os.rename` | Implement exactly as spec: sibling staging, `os.rename`, discard if target exists, cleanup on failure |
| **AD-16 Hardlink** | Wallpaper hardlinked | Populated here; `hardlink_or_copy` with `EXDEV` → `copy2` fallback; hardlink keeps inode alive |
| **AD-14 Domain purity** | Allowlist enforced | Domain imports only `dataclasses`,`enum`,`typing`,`collections`,`collections.abc`,`functools`,`re`,`__future__`; banned `os`/`subprocess`/`shutil`/`pathlib`/`io` |
| **AD-15 Cross-package boundary** | Runtime imports only `cli-output` | Do NOT `import provisioning` or `color_scheme_generator`; read CSG template files as data via `Path` (AD-11 read-only) if needed for hash, never for copy |
| **AD-11 First-run seeding** | Reads spine READ-ONLY | Staging helpers never mutate spine; only read wallpaper source and spine inputs for hashing |
| **AD-12 Synchronous** | No daemon/async | Synchronous `os.link`/`os.rename`/`shutil.copy2` suffices; no async staging |

### Previous story intelligence (Stories 1.1–1.5) — what exists now

- **Story 1.1 (scaffold):** package at `src/runtime/src/runtime/{domain,ports,adapters,application,cli}` + `tests/architecture/test_layering.py` (mirrors provisioning's domain allowlist, banned stdlib, no Path FS calls, ports-as-ABCs, cross-package forbidden set) + `pyproject.toml` (hatchling, `requires-python>=3.14`, `typer`, `cli-output` via `uv.sources`, `pytest` `testpaths=["tests"]`, `pythonpath=["src","."]`). All scaffold tests pass; layering test is the boundary enforcer.
- **Story 1.2 (domain):** `src/runtime/src/runtime/domain/models.py` defines 8 frozen dataclasses/enums: `WallpaperEntry(hash_algorithm:Literal["sha256"], kind:Literal["wallpaper"], content_hash, source_path, imported_at)`, `PaletteEntry(entry_hash, source_wallpaper_hash, input_template_hash, artifact_hashes:PaletteArtifacts, generated_at)`, `EffectsEntry(entry_hash, source_wallpaper_hash, input_catalog_hash, artifact_hashes)`, `IconsEntry(entry_hash, source_palette_hash, input_templates_hash, input_mappings_hash, artifact_hashes)`, `MonitorWallpaperConfig(backend:BackendType, source_hash, fit_mode:FitMode, mpv_options, ipc_socket)`, `DesktopState(schema_version:Literal[2], wallpaper:WallpaperEntry, monitors:dict[str,MonitorWallpaperConfig], palette/effects/icons:Opt, applied_at)`, plus `BackendType(StrEnum)` and `FitMode(StrEnum)`. All `@dataclass(frozen=True, slots=True)`. Domain imports only allowlist.
- **Story 1.3 (ports):** 9 ABCs in `runtime.ports.*`: `IColorSchemeGenerator`, `IEffectsGenerator`, `IIconRenderer`, `IStaticWallpaperBackend`, `IVideoWallpaperBackend`, `IWallpaperBackendFactory(auto_detect->BackendType|None)`, `IDesktopConfigWriter`, `IDesktopReloader`, `IStateRepository(load_current/save)`. Each `ABC+@abstractmethod` imports only `runtime.domain.models` + stdlib. Review patches applied: `FitMode` enum, `Literal` constraints, `auto_detect|None`.
- **Story 1.4 (CSG determinism):** harness at `src/runtime/tests/integration/test_csg_determinism.py` proves `csg generate` deterministic via double-run with literal env `COLORSCHEME__OUTPUT__DIRECTORY=<out>` + `COLORSCHEME__OUTPUT__OVERWRITE=true`, binary `read_bytes`+`sha256`, artifact `tests/integration/.csg_determinism.json` (`deterministic:true`, `wallpaper_hash 619cd350...`, `template_hash dab5e116...`). Option A confirmed (deterministic, no seed). `NondeterministicCSGError(AssertionError)` defined.
- **Story 1.5 (hashing):** `src/runtime/src/runtime/adapters/hashing.py` with `HASH_ALGORITHM: Final[Literal["sha256"]]="sha256"`, chunked `hash_file` (64 KiB, binary), `canonical_hash_dir` (sorted `rel:hash` joined by `\x00`, filtered `__pycache__`/`*.pyc`/`.git`, per-file `OSError→rel:unreadable`, symlink-aware, empty dir → `e3b0c...`), `palette/effects/icons_entry_hash` with fixed 64-char hex concatenation + `seed=None` seam + hex validation, `hash_file_bytes` helper. 19 unit tests in `tests/unit/test_hashing.py`; 60 tests green, layering 37 passed. **Reuse all hashing helpers — do NOT reimplement SHA logic.**
- **What NOT to reuse yet:** Do NOT add `IColorSchemeGenerator` adapter concrete classes (arrive 1.7), do NOT add `IStateRepository` JSON adapter (1.10), do NOT add CLI or use cases. This story is staging+hardlink only.
- **Review learnings from 1.5:** `canonical_hash_dir` join is now `\x00` + `\x00` (D2 decision) to avoid `:`/`\n` injection; `_IGNORED*` filter is pinned to spec (`__pycache__`, `.git`, `*.pyc`, `*.pyo`, `*.swp`, `*~`); `_is_hex64` validation required on every `*_entry_hash` arg; `HASH_ALGORITHM` is `Final[Literal["sha256"]]`. Carry these into cache helpers.

### Git intelligence — recent work patterns

- Last commits: `c210966 chore: pre-dev commit before rt-1-5`, `6c64f94 feat(runtime): implement 9 port ABCs`, `b44bad3 feat: complete domain model derivation graph`. Each story commits `feat(runtime): ...` with `baseline_commit` captured in frontmatter (`c210966` for this story, same baseline as 1.5 — consecutive story).
- Conventions: `tool.ruff` (target-version py314, line-length 100, quote-style double), `tool.mypy strict=true`, `tool.pytest.ini_options`. New code must comply with `ruff format` (don't create E501/B008 beyond existing 3 pre-existing ignores in `cli/main.py`/`domain/models.py`).
- `src/runtime/src/runtime/adapters/__init__.py` remains empty or minimal — this story adds `adapters/cache.py`; keep `__init__.py` clean (no star imports).
- `uv run --directory src/runtime pytest -q` runs the full suite; `pytest -k cache -v` isolates new tests. `src/runtime/tests/integration/.csg_determinism.json` is `.gitignore`'d; do not commit it.

### Project Structure Notes

- **Alignment (AD-13):** `src/runtime/src/runtime/{domain,ports,adapters,application,cli}` + `tests/architecture/test_layering.py` + `tests/unit`/`tests/integration`. This story adds `adapters/cache.py` (I/O layer, allowed) + `tests/unit/test_cache.py` (unit, fast path) under `src/runtime/`, matching `testpaths`/`pythonpath`. No new package folder needed.
- **Detected conflicts:** None. Staging cache is outside `domain`/`ports` so `test_layering.py` does not police `adapters/` for `os`/`pathlib` — `adapters/` is explicitly allowed to import them. If a helper is placed under `domain/`, it would violate the allowlist — hence **MUST** be in `adapters/`.
- **Naming:** `adapters/cache.py` mirrors `adapters/hashing.py` style; `tests/unit/test_cache.py` mirrors `test_hashing.py` snake_case; `populate_via_staging` / `hardlink_or_copy` / `cache_entry_path` names match `cache-model.md` and `ARCHITECTURE-SPINE.md` AD-9/AD-16 language; staging prefix `.staging-` matches spec `cache/.staging-<pid>/` (with pid + uuid suffix for uniqueness).
- **Tech stack (pinned):** `python>=3.14`, `typer>=0.12`, `cli-output` (via `uv.sources`), `color-scheme-generator[custom]` → `pillow>=11`, `numpy>=2`, `scikit-learn>=1.6`, `jinja2>=3.1`, `pydantic>=2.0`. Tests use `pytest>=8` (sync, no async/daemon). `os.rename` is the atomic primitive — no `fcntl` locking needed per AD-12 synchronous.
- **Spine vs defaults:** Wallpaper source is any `Path` (user image); hashing via `hash_file` gives `wh`. Templates/catalog not needed yet — cache helpers are generic; later stories compute `ph`/`eh`/`ih` via `hashing.py` and pass `target=cache_entry_path(state_root, layer, hash)`.
- **State root injection:** Helpers take `state_root: Path` or `target: Path` — they never call `os.environ["XDG_STATE_HOME"]` themselves; caller (future `SeedCacheUseCase`/`ApplyWallpaperUseCase`) injects it. Keeps domain pure and testable.

### References

- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md` — AD-1, AD-2, AD-3, AD-5, AD-6, AD-8, AD-9, AD-11, AD-13, AD-14, AD-15, AD-16, Deferred: cache eviction, CSG determinism verification
- Shared data contract: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md` — Derivation-input hashing, per-layer `meta.json` (`hash_algorithm: sha256`, `input_template_hash` etc.), Swap sequence, current.json/history.jsonl schemas, cache layout
- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md` — Epic 1 Story 1.6 ACs (FR-2, AD-9, AD-16, CAP-2), cross-story deps 1.5→1.7
- SPEC: `_bmad-output/specs/spec-dotfiles-runtime-phase2/SPEC.md` — CAP-1/2, Constraint 3 (FS authority), Constraint 6 (SHA-256), Assumption: CSG deterministic (verified 1.4)
- Cache model: `_bmad-output/specs/spec-dotfiles-runtime-phase2/cache-model.md` — layered cache layout, derivation layers and cache keys, staging-dir (`cache/.staging-<pid>/` then `os.rename`), hardlink (`wallpaper.png` hardlinked, copy fallback cross-filesystem), cache-hit flow, first-run seeding
- Previous stories: `_bmad-output/implementation-artifacts/rt-1-1-nested-hexagon-scaffold.md`, `rt-1-2-domain-model-derivation-graph.md`, `rt-1-3-ports-domain-capabilities.md`, `rt-1-4-csg-determinism-verification.md`, `rt-1-5-content-hashing-and-cache-key.md`
- Hashing helpers: `src/runtime/src/runtime/adapters/hashing.py` — `HASH_ALGORITHM`, `hash_file` (chunked 64 KiB, binary), `canonical_hash_dir`, `palette/effects/icons_entry_hash` (seed seam, hex validation), `_is_hex64`
- Domain models: `src/runtime/src/runtime/domain/models.py` — `WallpaperEntry`, `PaletteEntry(artifact_hashes:PaletteArtifacts)`, `EffectsEntry`, `IconsEntry`, `BackendType`, `FitMode`, `DesktopState(schema_version:Literal[2])`
- Ports: `src/runtime/src/runtime/ports/color_scheme_generator.py` — `IColorSchemeGenerator.generate(wallpaper_hash, template_dir, output_dir) -> PaletteEntry`; sibling effects/icon ports; `IStateRepository` minimal
- Defaults/templates (for later layers): `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/` (9 templates), `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/defaults/effects.yaml`
- Layering test: `src/runtime/tests/architecture/test_layering.py` — allowlist (`dataclasses`,`enum`,`typing`,`collections`,`collections.abc`,`functools`,`re`,`__future__`), banned `subprocess`/`os`/`shutil`/`pathlib`/`io` in domain, `ports` are ABCs, cross-package forbidden set
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` — `rt-1-6-layered-cache-populator: backlog` (next to create), `rt-1-5: done`
- Git: baseline `c210966` — consecutive with rt-1-5; `src/runtime/pyproject.toml` — `tool.ruff` (py314, line 100, double quotes), `tool.mypy strict=true`

## Dev Agent Record

### Agent Model Used

muse-spark-1.2-contributor-free (opencode/muse-spark-1.2-contributor-free)

### Debug Log References

- Implementation followed red-green-refactor: wrote failing tests first via `tests/unit/test_cache.py`, confirmed fail, then implemented minimal `adapters/cache.py` to pass.
- Validated `os.rename` atomicity vs `shutil.move` via `wraps=os.rename` mock; verified sibling staging `cache/.staging-<pid>-*`.
- EXDEV fallback verified with `patch("runtime.adapters.cache.os.link", side_effect=OSError(errno.EXDEV,...))`.
- No orphan staging verified after each test via `_no_staging_left` helper (checks `cache/.staging-*` globs).
- Layering guard: `uv run --directory src/runtime pytest tests/architecture/test_layering.py` passed 37 checks; domain allowlist untouched.

### Completion Notes List

- Chose `adapters/cache.py` (recommended short name) — consistent with `cache-model.md` and `adapters/hashing.py` naming; documented choice in module docstring.
- `CACHE_LAYERS` and `CACHE_STAGING_PREFIX` exported as `Final[frozenset[str]]` / `Final[str]`.
- `cache_entry_path` validates layer and 64-char hex, lowercases hash, returns `state_root/cache/layer/hash`.
- `hardlink_or_copy` ensures `dst.parent.mkdir(parents=True, exist_ok=True)`, tries `os.link`, falls back to `shutil.copy2` only on `EXDEV`, propagates other errors.
- `populate_via_staging` validates target (`cache/<layer>/<64hex>`), fast-path `target.exists() → False`, creates sibling staging `cache/.staging-<pid>-<8hex>`, handles `FileExistsError` / `ENOTEMPTY` / `EEXIST` / `"File exists"` TOCTOU race by discarding staging, cleans staging on `BaseException` and in `finally`.
- `HASH_ALGORITHM` imported from `adapters/hashing.py` with `assert HASH_ALGORITHM == "sha256"` to satisfy `ruff` unused-import while keeping pinned literal; meta.json contract documented in `cache_entry_path` docstring (wallpapers/palettes examples).
- All 6 tasks/subtasks marked [x]; 78 tests green (19 hashing + 18 new cache + 37 layering + 4 determinism via pytest -q total 78); new cache unit tests 18/18 passed.
- `ruff check` and `ruff format --check` pass for `adapters/cache.py` + `tests/unit/test_cache.py` (project-wide 11 pre-existing E501/B008 beyond scope, unchanged); `mypy --strict` passes for new files (project-wide 4 pre-existing cli_output/domain errors unchanged).
- No domain/ports/application changes — domain stays pure, ports remain ABCs, cross-package forbidden set untouched.

### File List

- src/runtime/src/runtime/adapters/cache.py (created) — staging-dir + hardlink helpers + cache_entry_path, strict mypy, ruff clean
- src/runtime/tests/unit/test_cache.py (created) — 18 unit tests covering AC1-5, sibling location, atomic rename, hardlink/EXDEV, concurrent race, meta.json pin, cleanup
- _bmad-output/implementation-artifacts/rt-1-6-layered-cache-populator.md (updated) — status review, checkboxes, Dev Agent Record
- _bmad-output/implementation-artifacts/sprint-status.yaml (updated) — rt-1-6 ready-for-dev → review

### Change Log

- 2026-08-29: Implemented layered cache populator with staging-dir (AC1,3,5), hardlink_or_copy with EXDEV fallback (AC2), cache_entry_path validation (AC4), 18 unit tests, layering debt zero, 78 tests green. Story moved to review.
- 2026-08-29: Sprint status rt-1-6 → in-progress (dev start), then → review (completion)

### Status

review

### Review Findings

- None yet — awaiting code review (recommend different LLM for review per workflow).

