# Story 1.5: Content hashing and cache-key canonicalization

---
baseline_commit: c210966
---

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want SHA-256 content hashing with canonicalized derivation-input keys,
so that cache entries are addressed by the hash of all their inputs and template/catalog changes invalidate correctly.

## Acceptance Criteria

1. **Given** the shared-data-contract canonicalization rules, **When** an input set (wallpaper+templates, wallpaper+catalog, palette+templates+mappings) is hashed, **Then** identical input sets yield identical hashes and differing sets yield differing hashes — verified for wallpapers (`sha256(file_bytes)`), palettes (`sha256(wallpaper_hash || template_set_hash)`), effects (`sha256(wallpaper_hash || catalog_hash)`), icons (`sha256(palette_hash || templates_hash || mappings_hash)`) (AC 1, FR-2, AD-2, AD-8, shared-data-contract Derivation-input hashing)
2. **Given** the canonicalization rule `sorted list of (relpath, sha256(file)) then sha256 of joined list`, **When** a templates dir (or effects catalog file, or icon mappings) is hashed, **Then** file order, absolute path, or OS walk order does NOT affect the hash — only relative paths + file contents do; the helper handles `OSError` per file as `<rel>:unreadable` (AC 2, AD-8, shared-data-contract)
3. **Given** a derived cache entry, **When** it is written, **Then** its dir is named `cache/<layer>/<hash>/` (`wallpapers/<wh>`, `palettes/<ph>`, `effects/<eh>`, `icons/<ih>`) and its co-located `meta.json` records literal `hash_algorithm: "sha256"` plus the entry's input hashes and `artifact_hashes` per the pinned schemas (AC 3, AD-3, AD-5, shared-data-contract meta.json)
4. **Given** the determinism proof from Story 1.4 (`custom` KMeans `random_state=0` + pywal/wallust deterministic, artifact `.csg_determinism.json` with `deterministic:true`), **When** the hashing story completes, **Then** the `sha256` contract is confirmed — cache keys do NOT need a pinned seed; the hashing helper documents the "no-seed" decision and leaves a seam for adding `pinned_seed` if a future determinism run fails (AC 4, FR-8, AD-2 Deferred)
5. **Given** the hexagonal boundary (AD-1, AD-14, AD-15), **When** hashing helpers are added, **Then** domain stays pure (allowlist `dataclasses`,`enum`,`typing`,`collections`,`collections.abc`,`functools`,`re`,`__future__` only; no `os`/`subprocess`/`shutil`/`pathlib` and no Path FS calls), hashing I/O lives in `adapters/`, ports remain ABCs, cross-package forbidden set is untouched, and `uv run --directory src/runtime pytest` + `ruff check` + `mypy strict` + layering test all pass (AC 5, AD-1, AD-13, AD-14, NFR-1)

## Tasks / Subtasks

- [ ] Task 1 — Create canonical hashing helper in `adapters/` (AC: 1, 2, 5)
  - [ ] Create `src/runtime/src/runtime/adapters/hashing.py` — **MUST be in `adapters/`**, NOT `domain/` or `ports/` (domain's stdlib allowlist forbids `os`/`pathlib`/`hashlib` file I/O is only allowed in adapters per AD-14; ports are ABCs only). Keep `domain/models.py` unchanged except for using the hashes. Add strict `mypy` signatures for every export.
  - [ ] Export helpers with typed contracts:
    ```python
    HASH_ALGORITHM: Final[str] = "sha256"  # must stay == Literal["sha256"] in domain/models.py

    def hash_file_bytes(data: bytes) -> str: ...  # sha256 hex, lowercase, of raw bytes
    def hash_file(path: Path) -> str: ...  # chunked binary + sha256; raises FileNotFoundError/OSError on missing/unreadable (DO NOT sentinel)
    def canonical_hash_dir(root: Path) -> str: ...  # raises FileNotFoundError if root missing/not a dir; per-file OSError -> "<rel>:unreadable" sentinel
    def canonical_hash_file(path: Path) -> str: ... # alias to hash_file for single-file catalogs/mappings
    def palette_entry_hash(wallpaper_hash: str, template_set_hash: str) -> str: ...
    def effects_entry_hash(wallpaper_hash: str, catalog_hash: str) -> str: ...
    def icons_entry_hash(palette_hash: str, templates_hash: str, mappings_hash: str) -> str: ...
    ```
    Two distinct error contracts: `hash_file`/`canonical_hash_file` **raise** on missing/unreadable single file; `canonical_hash_dir` handles `OSError` **per file** as `f"{rel}:unreadable"` sentinel and still returns a hex hash (pattern from Story 1.4 lines 97-112). Do not conflate them.
  - [ ] Implement `hash_file` chunked (wallpapers can be 30-100 MB — `read_bytes()` would OOM):
    ```python
    def hash_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()  # lowercase hex
    ```
    Same chunked pattern inside `canonical_hash_dir` per file. **DO NOT** use `read_text()` / line-ending normalization — always binary chunked `hashlib.sha256` (same guard as Story 1.4).
  - [ ] Implement `canonical_hash_dir` EXACTLY as shared-data-contract pins it:
    1. `if not root.exists(): raise FileNotFoundError(root)`; `if not root.is_dir(): raise NotADirectoryError(root)`.
    2. Walk `root.rglob("*")`; for each `p`: handle symlinks first — `if p.is_symlink(): if not p.exists(): entries.append((rel, f"{rel}:unreadable")); continue; elif p.is_file(): hash target; else: continue` (follow file symlinks only, never recurse symlink dirs).
    3. Skip non-files: `if not p.is_file(): continue`. Filter build noise: skip `__pycache__`, `*.pyc`, `*.pyo`, `.git`, `*.swp`, `*~` — they are not derivations; if uncertain, only keep files but document that a dirty checkout must not change the hash (all real template `.j2` plus any future extension count).
    4. `rel = p.relative_to(root).as_posix()` (POSIX, not OS-dependent separator).
    5. Chunked `file_hash` with `try/except OSError` per file → `f"{rel}:unreadable"` sentinel.
    6. Sort `entries` by `rel` lexicographically (array order, walk order, and absolute `root` path do NOT affect hash).
    7. Join ` "\n".join(f"{rel}:{h}" for rel,h in sorted_entries)` and `hashlib.sha256(joined.encode("utf-8")).hexdigest()`.
    8. Empty dir → `hashlib.sha256(b"").hexdigest()` == `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (empty input). Document: empty templates dir is a config error — hashing defines it but callers should treat empty as distinct.
  - [ ] Keep `HASH_ALGORITHM` in sync with domain: `WallpaperEntry.hash_algorithm: Literal["sha256"]` etc. Add assertion in tests: `assert HASH_ALGORITHM == "sha256"` and matches `get_args(WallpaperEntry.__annotations__["hash_algorithm"])[0]`.
  - [ ] Supported by preview in Story 1.4 Task 1: `input_template_hash = sha256(sorted list of (relpath, sha256(file)))` — reuse that inline logic, now canonicalized as a shared helper.
  - [ ] Add `hashlib`, `pathlib.Path`, `typing.Final` imports ONLY in `adapters/hashing.py` (allowed I/O layer per AD-1). Domain/ports must have zero new imports.

- [ ] Task 2 — Wire per-layer entry hash computation (AC: 1, 3)
  - [ ] In `adapters/hashing.py`, helpers match shared-data-contract derivation table (encodings are UTF-8 of fixed 64-char hex strings, so no separator needed — collision only possible with variable-length inputs):

    | Layer | entry_hash = | Spine path (prod) | Fallback (dev/unprovisioned) |
    |---|---|---|---|
    | wallpaper | `sha256(file_bytes)` chunked | `Path(wallpaper)` (any abs path, read `rb`) | same |
    | palette | `sha256(wallpaper_hash \|\| template_set_hash)` | `canonical_hash_dir(<install>/config/color-scheme-generator/templates/)` | `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/` |
    | effects | `sha256(wallpaper_hash \|\| catalog_hash)` | `hash_file(<install>/config/weg/effects.yaml)` | `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/defaults/effects.yaml` |
    | icons | `sha256(palette_hash \|\| templates_hash \|\| mappings_hash)` | `canonical_hash_dir(<install>/icon-templates/)` + `canonical_hash_dir(<install>/icon-mappings/)` or `hash_file` if single file (probe `is_dir` then `is_file`) | `src/cli-tools/icon-templates-renderer/...` defaults |

  - [ ] **Concatenation contract:** `hashlib.sha256(f"{a}{b}".encode("utf-8")).hexdigest()` — straight UTF-8 of the two hex strings concatenated (`||` in spec). Fixed 64-char hex → no separator needed and no `bytes.fromhex` decode; if inputs ever become variable-length, add `\x00` separator to avoid `("ab","c")` vs `("a","bc")` collision. Document this invariant in helper docstring and keep consistent across all three derived layers.
  - [ ] Helpers take `Path` args and are pure READ-ONLY from provisioning-owned spine (AD-11) — they never write under `<install>/` or `state_root`; caller (future use case) injects the resolved `Path`, this module does **not** discover `<install>` itself.
  - [ ] Expose `HASH_ALGORITHM: Final[str] = "sha256"` (AD-8 version pin) for `meta.json` writers in Stories 1.6/1.10; this story prepares the constant only.

- [ ] Task 3 — Prove identical vs differing sets diverge (AC: 1, 2)
  - [ ] Create unit tests `src/runtime/tests/unit/test_hashing.py` — **MUST** be under `tests/unit/` (not `domain`/`ports`), fast path (`pytest -k "not integration"`; **no** `pytest.mark.integration`).
  - [ ] Cover at minimum (table: test → inputs → expectation):

    | Test | Inputs | Expectation |
    |---|---|---|
    | `test_hash_file_bytes_identical_vs_differing` | same `b"hello"` vs `b"hellx"` | same hash / differing hash |
    | `test_canonical_hash_dir_sorts_relpaths` | same files in two dirs created in different walk order, plus two different `tmp_path` parents with same relpaths+contents | both pairs yield identical `canonical_hash_dir` |
    | `test_canonical_hash_dir_empty_dir` | `empty_tmp` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (`sha256(b"")`) |
    | `test_canonical_hash_dir_file_content_change_invalidates` | toggle one byte in one file | hash diverges |
    | `test_canonical_hash_dir_add_remove_file_invalidates` | add/remove a file | hash diverges |
    | `test_palette_entry_hash_deterministic` | same `(wh, template_hash)` then change either | same / differing `palette_entry_hash` |
    | `test_effects_entry_hash_deterministic` / `test_icons_entry_hash_deterministic` | parallel | parallel |
    | `test_canonical_hash_dir_unreadable_graceful` | monkeypatch `Path.open` to raise `OSError` for one file | does NOT raise; sentinel `<rel>:unreadable` present; still returns 64-char hex |
    | `test_read_bytes_not_read_text` | file with `\r\n` bytes | `hash_file` returns binary sha, not newline-normalized text |
    | `test_hash_file_chunked_large` | 1 MB file via repeated chunks | matches `hashlib.sha256(all_bytes).hexdigest()` while using chunked loop |

  - [ ] Reuse `tests/fixtures/wallpaper.png` (74-byte deterministic PNG, `619cd350...`) for wallpaper file-hash; no `random`/`PIL`. Dir tests use `tmp_path` + deterministic `write_bytes(b"hello")`, no `os.urandom`.

- [ ] Task 4 — Cache entry dir + `meta.json` contract (AC: 3)
  - [ ] No cache writes in this story (arrives in 1.6/1.10) — only document in `adapters/hashing.py` docstring: entry dir = `cache/<layer>/<hash>/` (lowercase hex `entry_hash`) and future `meta.json` **must** contain `hash_algorithm == HASH_ALGORITHM == "sha256"` plus per-layer input hashes and `artifact_hashes` per `shared-data-contract.md`. Do not add new domain entities; keep `WallpaperEntry`/`PaletteEntry` as-is.

- [ ] Task 5 — Determinism seam + no-seed documentation (AC: 4)
  - [ ] In `adapters/hashing.py` module docstring, document:
    - **Option A (current):** CSG proven deterministic 2026-08-28 (`tests/integration/.csg_determinism.json` → `deterministic:true`, `run1_hashes==run2_hashes` for `colors.conf`/`colors.gtk.css`, normalized `colors.yaml` identical). Cache key stays `sha256(wallpaper_hash || template_set_hash)` per shared-data-contract; `custom` pins `KMeans(random_state=0)` (`custom_generator.py:52-53`).
    - **Option B (future):** if a future double-run fails, amend key to `sha256(... || pinned_seed)` where `pinned_seed` is a literal (e.g., `"v1-seed-0"`) pinned in `runtime.domain` + `shared-data-contract` + `meta.json` notes. The hashing helper has a seam for this: `palette_entry_hash(wallpaper_hash, template_set_hash, seed: str | None = None)` would append seed before hashing; leave `seed=None` today and note in docstring that adding it is a spine change.
  - [ ] Add `NondeterministicCSGError` reference note: if hashing ever detects nondeterministic divergence, later cache consumers should raise `NondeterministicCSGError` with message `cache key must include pinned seed` (do not add the class here; alias lives in `tests/integration/test_csg_determinism.py` — just document the linkage).

- [ ] Task 6 — Ensure zero layering debt and full green (AC: 5)
  - [ ] Keep helpers in `adapters/hashing.py` only; verify `domain/models.py` still imports only allowlist (`dataclasses`,`enum`,`typing`,`collections`,`collections.abc`,`functools`,`re`,`__future__`); no new imports in domain/ports. Verify `sprint-status.yaml` still has `rt-1-6`/`rt-1-10` as `backlog` (no scope creep).
  - [ ] Verify `ports` remain pure ABCs: `runtime.ports.*` unchanged; run `python -c "from runtime.ports import *"` still succeeds.
  - [ ] Run and require green:
    ```bash
    uv run --directory src/runtime pytest -q
    uv run --directory src/runtime pytest -k hashing -v
    uv run --directory src/runtime ruff check
    uv run --directory src/runtime ruff format --check
    uv run --directory src/runtime mypy --strict src/runtime
    ```
    All existing tests (40+ from Stories 1.1–1.4: 29 scaffold + 30 domain + 38 ports + 2 determinism) must still pass; new hashing unit tests add coverage without breaking layering. `tests/architecture/test_layering.py` must pass — domain allowlist + no Path FS calls + cross-package forbidden set untouched.
  - [ ] Confirm `src/runtime/src/runtime/adapters/__init__.py` leaves blank or minimal (no cross-package star imports); do NOT add `from runtime.adapters.hashing import *` if it would create circular imports.
  - [ ] Verify non-goals are NOT included: no `cache/.staging-*`, no `os.rename`, no `hardlink`, no `IColorSchemeGenerator` adapter, no CLI, no `current.json` — those are Stories 1.6–1.14.

## Dev Notes

### Scope boundary — this story is HASHING ONLY

Story 1.5 **defines** canonical hashing and cache-key derivation. It does **NOT** implement:
- Staging-dir cache population or `os.rename` atomic rename (Story 1.6)
- `IColorSchemeGenerator`/`IEffectsGenerator`/`IIconRenderer` adapters with env overrides (Stories 1.7–1.9)
- `IStateRepository` JSON store or `current.json`/`history.jsonl` persistence (Story 1.10)
- `SeedCacheUseCase` / `ApplyWallpaperUseCase` / `ReconcileDesktopStateUseCase` (Stories 1.11–1.13)
- Any CLI command
- Hardlink helper (`cache/wallpapers/<wh>/wallpaper.png` hardlink) — that is Story 1.6
- `meta.json` file writing — prepared here, written in 1.6
- Determinism verification re-run — that was Story 1.4; this story documents its outcome

Resist adding cache-population logic — write only the hashing helper, its per-layer key fns, and unit tests.

### Source tree components to touch

| Path | Action | Notes |
|------|--------|-------|
| `src/runtime/src/runtime/adapters/hashing.py` | **CREATE** | Pure hashing helper + canonical dir hashing; imports `hashlib`,`pathlib.Path`,`os` only here (allowed I/O layer, AD-1) |
| `src/runtime/tests/unit/test_hashing.py` | **CREATE** | Unit tests for canonicalization + per-layer key determinism (see Task 3); **MUST NOT** place under `domain`/`ports` |
| `src/runtime/tests/fixtures/wallpaper.png` | **USE** (already exists) | Deterministic 4×4 PNG from Story 1.4 (`619cd350...`); reuse for wallpaper file-hash tests |
| `_bmad-output/implementation-artifacts/rt-1-5-content-hashing-and-cache-key.md` | **UPDATE** | Completion Notes + File List filled by dev |
| `src/runtime/src/runtime/domain/**` | **LEAVE ALONE** | No `hashlib`/`os`/`pathlib` imports; domain stays pure (AD-14) |
| `src/runtime/src/runtime/ports/**` | **LEAVE ALONE** | ABCs only; no concrete classes |
| `src/runtime/src/runtime/adapters/__init__.py` | **LEAVE ALONE** or minimal | Stays lean; no cross-package imports |

### Testing standards summary

- **Runner:** `uv run --directory src/runtime pytest` (`pyproject.toml: testpaths=["tests"]`, `pythonpath=["src","."]`, `requires-python>=3.14`). Unit hashing tests run in fast path (`pytest -k "not integration"`); determinism test is `integration`.
- **Lint/type:** `uv run --directory src/runtime ruff check` (py314, line 100, double quotes); `mypy --strict` (`python_version=3.14`, allowlist-only for domain/ports). No new ignores; `adapters/hashing.py` must be `ruff format` clean.
- **Fixtures:** Reuse `tests/fixtures/wallpaper.png` (74 bytes); `tmp_path` files via `write_bytes(b"...")` — no `random`/`PIL`.
- **Binary-only hashing:** `hash_file` chunked `open("rb")` + `sha256` (see Task 1 snippet); never `read_text()` or `read_bytes()` for large files. Per-file `OSError` → `<rel>:unreadable` only in `canonical_hash_dir`.
- **Empty dir:** `canonical_hash_dir(empty_tmp) == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"` (`sha256(b"")`).

### Architecture extraction — what this story must respect

| Decision | Relevance | What to do |
|----------|-----------|------------|
| **AD-1 Hexagonal** | Hashing I/O in adapters | Keep hashing helper in `adapters/hashing.py`; **MUST NOT** import `hashlib`/`pathlib` into `domain` |
| **AD-2 Layered cache key** | Key = hash of ALL inputs | Implement per-layer `*_entry_hash` fns exactly as shared-data-contract table; entry dir = `cache/<layer>/<hash>` |
| **AD-3 JSON store / FS authority** | meta.json + current.json are index | This story prepares `hash_algorithm:"sha256"` for meta.json but does NOT write it yet |
| **AD-5 State root** | Runtime owns `$XDG_STATE_HOME/dotfiles/` | Hashing helper never writes under `state_root` or install spine; it only `read_bytes` |
| **AD-6 Swap = symlinks** | No copying | Cache dirs are write-once; hashing must be deterministic so re-point is idempotent — no swap code here |
| **AD-8 SHA-256 versioned** | `meta.json: hash_algorithm: sha256` | All hashes use `hashlib.sha256`; expose `HASH_ALGORITHM="sha256"` constant |
| **AD-9 Staging-dir** | Population later | Do not implement staging; hashing must support staging-discard check: same inputs → same hash → same target dir |
| **AD-14 Domain purity** | Allowlist enforced | Domain imports only `dataclasses`,`enum`,`typing`,`collections`,`collections.abc`,`functools`,`re`,`__future__`; banned `os`/`subprocess`/`shutil`/`pathlib`/`io` |
| **AD-15 Cross-package boundary** | Runtime imports only `cli-output` | Do NOT `import provisioning` or `color_scheme_generator`; read CSG template files as data via `Path` (AD-11 read-only) |
| **AD-16 Hardlink** | Wallpaper hardlinked | Populated in 1.6; hashing provides the `wh` target name |
| **AD-11 First-run seeding** | Reads spine READ-ONLY | Template/catalog reads are via `Path` reads of spine; never mutate spine |
| **AD-12 Synchronous** | No daemon/async | Synchronous `read_bytes` + sha suffices; no async hashing |

### Previous story intelligence (Stories 1.1–1.4) — what exists now

- **Story 1.1 (scaffold):** package at `src/runtime/src/runtime/{domain,ports,adapters,application,cli}` + `tests/architecture/test_layering.py` (mirrors provisioning's domain allowlist, banned stdlib, no Path FS calls, ports-as-ABCs, cross-package forbidden set) + `pyproject.toml` (hatchling, `requires-python>=3.14`, `typer`, `cli-output` via `uv.sources`, `pytest` `testpaths=["tests"]`, `pythonpath=["src","."]`). All 29 scaffold tests pass; layering test is the boundary enforcer.
- **Story 1.2 (domain):** `src/runtime/src/runtime/domain/models.py` defines 8 frozen dataclasses/enums: `WallpaperEntry(hash_algorithm:Literal["sha256"], kind:Literal["wallpaper"], content_hash, source_path, imported_at)`, `PaletteEntry(entry_hash, source_wallpaper_hash, input_template_hash, artifact_hashes:PaletteArtifacts, generated_at)`, `EffectsEntry(entry_hash, source_wallpaper_hash, input_catalog_hash, artifact_hashes)`, `IconsEntry(entry_hash, source_palette_hash, input_templates_hash, input_mappings_hash, artifact_hashes)`, `MonitorWallpaperConfig(backend:BackendType, source_hash, fit_mode:FitMode, mpv_options, ipc_socket)`, `DesktopState(schema_version:Literal[2], wallpaper:WallpaperEntry, monitors:dict[str,MonitorWallpaperConfig], palette/effects/icons:Opt, applied_at)`, plus `BackendType(StrEnum)` and `FitMode(StrEnum)`. All `@dataclass(frozen=True, slots=True)`. Domain imports only allowlist.
- **Story 1.3 (ports):** 9 ABCs in `runtime.ports.*`: `IColorSchemeGenerator.generate(wallpaper_hash, template_dir, output_dir)->PaletteEntry`, `IEffectsGenerator`, `IIconRenderer`, `IStaticWallpaperBackend`, `IVideoWallpaperBackend`, `IWallpaperBackendFactory(auto_detect->BackendType|None)`, `IDesktopConfigWriter`, `IDesktopReloader`, `IStateRepository(load_current/save)`. Each `ABC+@abstractmethod` imports only `runtime.domain.models` + stdlib. `__init__.py` re-exports via explicit imports. Review findings patched: `FitMode` enum, `Literal` layer/command constraints, `auto_detect|None`.
- **Story 1.4 (CSG determinism):** harness at `src/runtime/tests/integration/test_csg_determinism.py` (integration, `@pytest.mark.parametrize("backend",["custom"])`) proves `csg generate` deterministic via double-run with literal env `COLORSCHEME__OUTPUT__DIRECTORY=<out>` + `COLORSCHEME__OUTPUT__OVERWRITE=true`, binary `read_bytes`+`sha256`, container forwarding verified (`NO -o` flag to prove `oci-runtime` mount). Artifact `tests/integration/.csg_determinism.json` (atomic tmp+replace, `.gitignore`'d) records `deterministic:true` for `pywal/podman` (`wallpaper_hash 619cd350...`, `template_hash dab5e116...`, `colors.conf sha 5ef15386...`). Mitigation contract documented: Option A confirmed (deterministic, no seed), Option B (pinned seed) not required. Introduced `NondeterministicCSGError(AssertionError)`. Code review 12 patches applied; `pytest 40 passed`, layering green.
- **What NOT to reuse yet:** Do NOT duplicate domain hashing — `PaletteEntry.entry_hash` etc. are computed by `adapters/hashing.py`, not by the dataclass. Do not add adapter concrete classes for CSG/WEG/ITR yet (arrive 1.7+).

### Git intelligence — recent work patterns

- Last commits: `c210966 fix: auto-commit code review findings`, `e03a73e feat: auto-commit story implementation - rt-1-4 csg determinism verification`, `98bc333 chore: pre-dev commit before rt-1-4 csg determinism`, `6c64f94 feat(runtime): implement 9 port ABCs`, `b44bad3 feat: complete domain model derivation graph`. Each story commits `feat(runtime): ...` with `baseline_commit` captured in frontmatter (`c210966` for this story).
- Conventions: `tool.ruff` (target-version py314, line-length 100, quote-style double), `tool.mypy strict=true`, `tool.pytest.ini_options`. New code must comply with `ruff format` (don't create E501/B008 beyond existing 3 pre-existing ignores in `cli/main.py`/`domain/models.py`).
- `src/runtime/src/runtime/adapters/__init__.py` remains empty or minimal — this story adds `adapters/hashing.py`; keep `__init__.py` clean.
- `uv run --directory src/runtime pytest -q` runs the full suite; `pytest -k hashing -v` isolates new tests.

### Project Structure Notes

- **Alignment (AD-13):** `src/runtime/src/runtime/{domain,ports,adapters,application,cli}` + `tests/architecture/test_layering.py` + `tests/unit`/`tests/integration`. This story adds `adapters/hashing.py` (I/O layer, allowed) + `tests/unit/test_hashing.py` (unit, fast path) under `src/runtime/`, matching `testpaths`/`pythonpath`. No new package folder needed.
- **Detected conflicts:** None. Hashing is outside `domain`/`ports` so `test_layering.py` does not police it; `adapters/` is allowed to import `hashlib`/`pathlib`/`os`. If a helper is placed under `domain/`, it would violate the allowlist — hence **MUST** be in `adapters/`.
- **Naming:** `adapters/hashing.py` mirrors `container_processor.py` / `default_palette.sh.j2` style; `tests/unit/test_hashing.py` mirrors `test_csg_determinism.py` snake_case; `canonical_hash_dir` name matches Story 1.4 inline helper and the preview in `_bmad-output/specs/spec-dotfiles-runtime-phase2/cache-model.md`.
- **Tech stack (pinned):** `python>=3.14`, `typer>=0.12`, `cli-output` (via `uv.sources`), `color-scheme-generator[custom]` → `pillow>=11`, `numpy>=2`, `scikit-learn>=1.6`, `jinja2>=3.1`, `pydantic>=2.0`, `oci-runtime` + `config-assembler-engine` (env-override `PREFIX__SECTION__KEY` reader). Tests use `pytest>=8` (sync, no async/daemon).
- **Spine vs defaults:** Resolve CSG template dir by probing provisioning spine when available (`<install>/config/color-scheme-generator/templates/` derived from `XDG_DATA_HOME/dotfiles/` via rendered `settings.toml` or env `DOTFILES_INSTALL_DIR`) else fallback to `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/` (bundled defaults). Same for effects catalog (`config/weg/effects.yaml` → `src/cli-tools/wallpaper-effects-generator/.../defaults/effects.yaml`) and icon templates/mappings (`icon-templates`/`icon-mappings` dirs under install). Runtime reads these READ-ONLY (AD-11).

### References

- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md` — AD-1, AD-2, AD-3, AD-5, AD-6, AD-8, AD-9, AD-11, AD-13, AD-14, AD-15, Deferred: cache eviction, CSG determinism verification
- Shared data contract: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md` — Derivation-input hashing (wallpaper/palette/effects/icons table, `sorted list of (relpath, sha256(file))`), Env-override protocol, per-layer `meta.json` (`hash_algorithm: sha256`, `input_template_hash` etc.), Swap sequence, current.json/history.jsonl schemas
- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md` — Epic 1 Story 1.5 ACs (FR-2, FR-8, CAP-2), cross-story deps 1.6+1.7
- SPEC: `_bmad-output/specs/spec-dotfiles-runtime-phase2/SPEC.md` — CAP-1/2, Constraint 6 (SHA-256), Assumption: CSG deterministic (now verified), Success signal
- Cache model: `_bmad-output/specs/spec-dotfiles-runtime-phase2/cache-model.md` — layered cache layout, derivation layers and cache keys, first-run seeding, staging-dir, cache-hit flow
- Previous stories: `_bmad-output/implementation-artifacts/rt-1-1-nested-hexagon-scaffold.md`, `rt-1-2-domain-model-derivation-graph.md`, `rt-1-3-ports-domain-capabilities.md`, `rt-1-4-csg-determinism-verification.md`
- CSG source: `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/backends/custom_generator.py:52-53` (`KMeans(random_state=0)`), `default_palette.sh.j2`, `container_processor.py` — env forwarding contract referenced in determinism harness
- Harness patterns to reuse: `src/provisioning/tests/integration/test_settings_parity.py:_create_minimal_png`, `_run_csg_generate`, `_csg_container_image_built` — minimal PNG + container guard patterns; `src/runtime/tests/integration/test_csg_determinism.py:97-130` — `canonical_hash_dir` inline + OSError sentinel + regex YAML normalization
- Determinism artifact: `src/runtime/tests/integration/.csg_determinism.json` — proves `deterministic:true` → SHA-256 key stands (Option A)
- Layering test: `src/runtime/tests/architecture/test_layering.py` — allowlist (`dataclasses`,`enum`,`typing`,`collections`,`collections.abc`,`functools`,`re`,`__future__`), banned `subprocess`/`os`/`shutil`/`pathlib`/`io` in domain, `ports` are ABCs, cross-package forbidden set (`provisioning`, `color_scheme_generator`, etc.)
- Domain models: `src/runtime/src/runtime/domain/models.py` — `WallpaperEntry`, `PaletteEntry(artifact_hashes:PaletteArtifacts)`, `EffectsEntry`, `IconsEntry`, `BackendType`, `FitMode`, `DesktopState(schema_version:Literal[2])`
- Ports: `src/runtime/src/runtime/ports/color_scheme_generator.py` — `IColorSchemeGenerator.generate(wallpaper_hash, template_dir, output_dir) -> PaletteEntry`; sibling effects/icon ports
- Defaults/templates: `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/{colors.conf.j2,colors.css.j2,colors.gtk.css.j2,...}` (9 templates), `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/defaults/effects.yaml`, `src/cli-tools/icon-templates-renderer/` (templates/mappings defaults)
- Layering enforcement refs: `src/runtime/pyproject.toml` — `tool.ruff` (py314, line 100, double quotes), `tool.mypy strict=true`
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` — `rt-1-5-content-hashing-and-cache-key: backlog` (next to create), `rt-1-4: done`

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

### Change Log

### Review Findings
