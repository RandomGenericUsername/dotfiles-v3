# Story 1.9: itr adapter with env overrides

Status: ready-for-dev

## Story

As a developer,
I want an itr adapter that directs icon output and palette input via env overrides,
So that icons land in the cache chained to the cached palette without editing settings.toml.

## Acceptance Criteria

1. **Given** a cached palette entry at `state_root/cache/palettes/<ph>/colors.yaml` (where `ph = palette_entry_hash(wallpaper_hash, template_set_hash)` computed by a prior `CsgAdapter.generate` call and `colors.yaml` is the YAML palette artifact inside that cache entry), and a target icons cache entry dir `state_root/cache/icons/<ih>/` where `ih = icons_entry_hash(palette_hash, templates_hash, mappings_hash)` computed from `adapters/hashing.py` (with `palette_hash = ph`, `templates_hash = canonical_hash_dir(<install>/icon-templates/)`, `mappings_hash = canonical_hash_dir(<install>/icon-mappings/)` — both READ-ONLY spine inputs), and `output_dir: Path = state_root/cache/icons/<ih>` (not yet existing), **When** `ItrAdapter.render(palette_hash: str, templates_dir: Path, mappings_path: Path, output_dir: Path) -> IconsEntry` (implementing `IIconRenderer`) is invoked, **Then** it invokes the `itr` binary via `subprocess.run` with env `ICON_RENDERER__OUTPUT__OUTPUT_DIR=str(output_dir)` (literal double-underscore key per `shared-data-contract.md` Env-override protocol — note: key is `output_dir`, NOT `directory`) **and** `ICON_RENDERER__COLOR_SCHEME__PATH=<state>/cache/palettes/<ph>/colors.yaml` (input redirection for palette chaining, the adapter resolves this path from the palette cache entry), **and** passes `output_dir` via env override only (no `-o`/`--output` flag on the CLI — output dir comes solely from env override to exercise container forwarding contract), **And** `itr` writes SVG icon files into `output_dir` (verified via `list(output_dir.rglob("*.svg"))` non-empty and all are files), **And** the method returns an `IconsEntry` with `hash_algorithm=="sha256"`, `kind=="icons"`, `entry_hash==ih`, `source_palette_hash==palette_hash`, `input_templates_hash==templates_hash`, `input_mappings_hash==mappings_hash`, `artifact_hashes=={<name>.svg: hash_file(...)}` computed via `adapters/hashing.hash_file` binary chunked for every SVG artifact, `generated_at==ISO-8601 UTC` (`datetime.now(UTC).isoformat().replace("+00:00","Z")`), **And** the provisioning-rendered `settings.toml` (read-only via discovery, never written) remains untouched — verified by stat mtime unchanged before/after (AC 1, AD-7, AD-2, shared-data-contract icons meta.json).

2. **Given** a `ItrAdapter` instance configured for local or container runtime mode (resolved externally; adapter itself takes no `runtime.mode` flag — container mode forwarding is an env passthrough property tested in integration), **When** the adapter runs in container mode (`itr` itself configured to use `podman`/`docker` via `oci-runtime` — provisioning owns engine install), **Then** both `ICON_RENDERER__OUTPUT__OUTPUT_DIR` and `ICON_RENDERER__COLOR_SCHEME__PATH` overrides are passed **INTO** the container environment (not just host process) — proven by the integration test that uses zero `-o`/`--output` flag and relies solely on the env overrides, where host `output_dir` still receives artifacts even when `runtime.mode==container` (the container's `RunConfig` must include `env={"ICON_RENDERER__OUTPUT__OUTPUT_DIR": ..., "ICON_RENDERER__COLOR_SCHEME__PATH": ...}` per `ARCHITECTURE-SPINE.md` AD-7 last sentence + `shared-data-contract.md` Env-override protocol note). The adapter MUST NOT perform any `settings.toml` rewrite or file copy to simulate this — only env injection (AC 2, AD-7 container-mode override).

3. **Given** `itr` binary availability, **When** `ItrAdapter.is_available() -> bool` (or equivalent health check) is queried — OR `render` is called when `itr` not on PATH / container image missing, **Then** `render` raises a typed error that preserves subprocess stderr (for later error mapping in Epic 3/4) — either `FileNotFoundError("itr not on PATH")` or `RuntimeError(f"itr render failed: {stderr}")` with `stderr` truncated to 2 KiB, non-zero exit code handled, timeout handled (see AC 4) — **and** the caller (future `ApplyWallpaperUseCase`/`populate_via_staging`) sees a clean exception, not an unhandled `CalledProcessError` or silent swallow. The adapter MUST NOT suggest install via custom message beyond preserving stderr — suggestion logic lives in CLI layer (Story 2.9 future), but the error type/message must be predictable for `OutputPort.error()` to serialize (AC 3, NFR-2 reliability, shared-data-contract).

4. **Given** subprocess-based invocation, **When** `itr render` hangs or exceeds a configurable timeout (default 60s, parameter `timeout: int = 60` on the adapter constructor, overrideable per-call), **Then** the adapter kills the process via `subprocess.run(..., timeout=timeout)` which raises `subprocess.TimeoutExpired`, which is caught and re-raised as `RuntimeError(f"itr render timed out after {timeout}s")` (or `TimeoutError`) with the partial stdout/stderr preserved; **And** `output_dir` is left without partial files (caller is responsible for staging-dir cleanup via `populate_via_staging` — adapter itself must not leave half-written SVGs if it created `output_dir` directly; recommended pattern: caller creates `output_dir` as the staging dir and passes it, so adapter writes straight into staging — adapter must not `shutil.rmtree` itself, just raise) (AC 4, Story 1.7 timeout pattern reused, cache-model.md staging-dir AC 3).

5. **Given** hexagonal boundary (AD-1, AD-14, AD-15), **When** the itr adapter is added, **Then** `domain/` stays pure (allowlist `dataclasses, enum, typing, collections, collections.abc, functools, re, __future__` only; no `os`/`subprocess`/`shutil`/`pathlib`), `ports/IIconRenderer` remains ABC with `render` abstract method unchanged (no concrete class in `ports/`), adapter lives in `adapters/` only (allowed `os`/`subprocess`/`pathlib`/`hashlib` plus `runtime.adapters.hashing` + `runtime.domain.models`), cross-package forbidden set untouched (`provisioning, core, infrastructure, color_scheme_generator, wallpaper_effects_generator, icon_templates_renderer, config_assembler_engine, oci_runtime` — runtime may `shutil.which("itr")` but never `import icon_templates_renderer`), and `uv run --directory src/runtime pytest` + `ruff check` + `ruff format --check` + `mypy --strict` + `tests/architecture/test_layering.py` all pass (37 layering checks). The adapter MUST use `adapters/hashing.py:hash_file` + `canonical_hash_dir` + `icons_entry_hash` for every hash — no `hashlib.sha256(data).hexdigest()` inline reimplementation (AC 5, AD-1, AD-14, NFR-1, NFR-10).

## Tasks / Subtasks

- [ ] Task 1 — Create `adapters/itr_adapter.py` implementing `IIconRenderer` (AC: 1, 5)
  - [ ] **Location MUST be `src/runtime/src/runtime/adapters/itr_adapter.py`** (mirrors `csg_adapter.py` and `weg_adapter.py`). **MUST be in `adapters/`**, NOT `domain/`/`ports`/`application`.
  - [ ] Imports allowed ONLY in this file: `subprocess`, `os`, `shutil`, `hashlib` (only via `hashing.py`), `pathlib.Path`, `typing.Final/Literal`, `datetime` (`datetime.now(UTC)`), `stat`, `errno`. Do NOT add `os`/`subprocess` to `domain/` or `ports`.
  - [ ] Export typed class — strict `mypy` signatures:
    ```python
    from pathlib import Path
    from runtime.ports.icon_renderer import IIconRenderer
    from runtime.domain.models import IconsEntry
    from runtime.adapters.hashing import hash_file, canonical_hash_dir, icons_entry_hash, HASH_ALGORITHM

    class ItrAdapter(IIconRenderer):
        def __init__(self, timeout: int = 60, itr_bin: str | None = None,
                     templates_dir: Path | None = None, mappings_path: Path | None = None) -> None: ...
        def render(self, palette_hash: str, templates_dir: Path, mappings_path: Path, output_dir: Path) -> IconsEntry: ...
        def is_available(self) -> bool: ...
    ```
  - [ ] Keep `HASH_ALGORITHM` import from `adapters/hashing.py` — assert returned `IconsEntry.hash_algorithm == HASH_ALGORITHM == "sha256"`.

- [ ] Task 2 — Implement `render` with literal env overrides, no settings.toml edit (AC: 1, 2)
  - [ ] Resolve `palette_hash`: validate it is a 64-char hex string via `hashing._validate_hex64("palette_hash", palette_hash)`. This is the `ph` from a prior `CsgAdapter.generate` call — NOT recomputed here. Raise `ValueError` if invalid.
  - [ ] Resolve `templates_dir`: if `__init__(templates_dir)` provided use it; else discover via `_find_default_icon_templates()` searching repo parents for `src/cli-tools/icon-templates-renderer/src/icon_templates_renderer/defaults/templates` and fallback patterns. Compute `templates_hash = canonical_hash_dir(templates_dir)`. Raise `FileNotFoundError` if not found.
  - [ ] Resolve `mappings_path`: if `__init__(mappings_path)` provided use it; else discover via `_find_default_icon_mappings()` searching for `src/cli-tools/icon-templates-renderer/src/icon_templates_renderer/defaults/mappings`. Compute `mappings_hash = canonical_hash_dir(mappings_path)` (if path is a directory) or `hash_file(mappings_path)` (if file). Raise `FileNotFoundError` if not found.
  - [ ] Compute `ih = icons_entry_hash(palette_hash, templates_hash, mappings_hash)` (validates 64-hex inputs). Assert `output_dir.name == ih` else `ValueError(f"output_dir hash mismatch: expected {ih}, got {output_dir.name}")`.
  - [ ] Ensure `output_dir` parent exists; `output_dir` itself mkdir. Same validation as CsgAdapter/WegAdapter: `_validate_output_dir` checks `..`, symlink, case-sensitive, length guard, FileExistsError wrapping.
  - [ ] Resolve `colors_yaml_path = <state>/cache/palettes/<palette_hash>/colors.yaml` — the adapter needs the full path to `colors.yaml` inside the palette cache entry. This must be passed in or derived from `state_root` (injected) + `palette_hash`. Adapter should accept `palette_cache_dir: Path | None` or derive from `output_dir.parent.parent / "palettes" / palette_hash`. **Key design decision:** the adapter must know the palette cache entry path to set `ICON_RENDERER__COLOR_SCHEME__PATH`. Accept `palette_cache_dir: Path` as constructor param (recommended: `__init__(..., palette_cache_dir: Path | None = None)`) and validate `palette_cache_dir / "colors.yaml"` exists.
  - [ ] Build `env = build_env({"ICON_RENDERER__OUTPUT__OUTPUT_DIR": str(output_dir), "ICON_RENDERER__COLOR_SCHEME__PATH": str(colors_yaml_path)})` — literal keys, double underscores, uppercase, per `shared-data-contract.md`. Do NOT use single underscores or lowercase. Adapter MUST NOT touch `settings.toml`.
  - [ ] Build args: `[itr_bin or "itr", "render"]` — intentionally NO `-o`/`--output` flag and NO `--color-scheme` flag; output dir and color scheme come solely from env overrides to exercise container forwarding contract. Add `timeout` handling and `capture_output=True, text=True`.
  - [ ] Run `subprocess.run(args, capture_output=True, text=True, env=env, timeout=self.timeout)` — on success verify SVG artifacts exist via `list(output_dir.rglob("*.svg"))` non-empty and all are files. On failure raise `RuntimeError(f"itr render failed (exit {code}): {stderr[:2048]}")` truncated.
  - [ ] Compute `artifact_hashes = {p.relative_to(output_dir).as_posix(): hash_file(p) for p in svg_files}` — use relative paths for nested SVGs; basename when flat. Assert all hashes are 64-hex.
  - [ ] Return `IconsEntry(hash_algorithm=HASH_ALGORITHM, kind="icons", entry_hash=ih, source_palette_hash=palette_hash, input_templates_hash=templates_hash, input_mappings_hash=mappings_hash, artifact_hashes=artifact_hashes, generated_at=datetime.now(UTC).isoformat().replace("+00:00","Z"))`.

- [ ] Task 3 — Handle container-mode env forwarding (AC: 2)
  - [ ] Same as CSG/WEG: adapter only sets host env dict; `itr` container_processor forwards into RunConfig. Document in docstring.
  - [ ] Do NOT attempt Docker/Podman `-e` flags — that is `itr`'s responsibility.

- [ ] Task 4 — Implement timeout + error preservation (AC: 3, 4)
  - [ ] Constructor `timeout: int = 60` validated `isinstance(timeout, int) and timeout > 0`.
  - [ ] Wrap `subprocess.run(..., timeout=self.timeout)` catching `TimeoutExpired -> TimeoutError` with "timed out" substring.
  - [ ] On non-zero exit raise `RuntimeError` with stderr truncated 2 KiB + stdout 500, handle negative signal returncode to signal name.
  - [ ] Validate `palette_hash` early: 64-hex check. Validate `templates_dir` exists and is directory. Validate `mappings_path` exists. Validate `output_dir` name matches `ih`. Validate `palette_cache_dir / "colors.yaml"` exists.

- [ ] Task 5 — Tests: unit + integration, strict green (AC: 1,2,3,4,5)
  - [ ] Create `src/runtime/tests/unit/test_itr_adapter.py` under `tests/unit/`, fast path.
  - [ ] Cover at minimum:
    | Test | Inputs | Expectation |
    |---|---|---|
    | `test_itr_render_env_override_writes_to_output_dir` | tmp templates dir, tmp mappings, mocked run writes SVGs into env dirs | entry_hash==icons_entry_hash, artifact_hashes match, ICON_RENDERER__OUTPUT__OUTPUT_DIR and ICON_RENDERER__COLOR_SCHEME__PATH in env, no -o flag |
    | `test_itr_adapter_never_touches_settings_toml` | real settings.toml mtime | unchanged after render |
    | `test_itr_adapter_container_env_passthrough` | capture env | both ICON_RENDERER__* keys present even when global env missing |
    | `test_itr_adapter_raises_on_non_zero_exit` | returncode=1 | RuntimeError with stderr |
    | `test_itr_adapter_timeout_raises` | TimeoutExpired | TimeoutError with timed out |
    | `test_itr_adapter_raises_on_missing_templates_dir` | missing path | FileNotFoundError before run |
    | `test_itr_adapter_raises_on_missing_mappings` | missing path | FileNotFoundError before run |
    | `test_itr_adapter_entry_hash_mismatch` | wrong output_dir name | ValueError |
    | `test_itr_adapter_artifact_hashes_are_hex64` | successful mocked | artifact_hashes values 64-hex, hash_algorithm sha256, kind icons |
    | `test_itr_adapter_is_available` | which patched | True/False |
    | `test_itr_adapter_no_settings_toml_rewrite_even_on_container` | container env | still no settings.toml modification |
  - [ ] Create `src/runtime/tests/integration/test_itr_adapter_integration.py` marked integration, calls real `itr` if available else skip, verifies SVGs land and hashes match.

- [ ] Task 6 — Ensure zero layering debt and full green (AC: 5)
  - [ ] Keep adapter in `adapters/itr_adapter.py` only; verify domain purity, ports ABC only, no cross-package imports.
  - [ ] Run and require green: `uv run --directory src/runtime pytest -q`, `ruff check`, `ruff format --check`, `mypy --strict src/runtime/adapters/itr_adapter.py`, `pytest tests/architecture/test_layering.py -v`

## Dev Notes

### Scope boundary — this story is ITR ADAPTER ENV OVERRIDE ONLY

Story 1.9 **defines** the icon-rendering adapter that directs `itr` output via `ICON_RENDERER__OUTPUT__OUTPUT_DIR` + `ICON_RENDERER__COLOR_SCHEME__PATH` env overrides into `cache/icons/<ih>/`. It does **NOT** implement:
- IStateRepository (1.10), SeedCacheUseCase (1.11), ApplyWallpaperUseCase (1.13), etc.
- Keep scope to `IIconRenderer` env overrides only.
- Do NOT implement the `IIconRenderer` port update — the port already exists at `src/runtime/src/runtime/ports/icon_renderer.py`. If the port signature needs updating (it currently takes `str` args, not `Path`), update it in this story following the same pattern as CSG port update in Story 1.7.

### ITR-specific design challenges

| Challenge | Resolution |
|---|---|
| **Port takes `str` args (not `Path`)** | The current `IIconRenderer.render` signature is `(palette_hash: str, templates_dir: str, mappings_path: str, output_dir: str) -> IconsEntry`. This differs from CSG/WEG which take `Path` objects. **Option A (recommended):** Update port to accept `Path` objects for `templates_dir`, `mappings_path`, `output_dir` while keeping `palette_hash` as `str` (it's a hash, not a path). Option B: adapter bridges `str` → `Path` internally. Choose Option A for consistency with CSG/WEG ports updated in Stories 1.7–1.8. Verify `test_layering.py` allows `pathlib` in ports layer. |
| **Two env overrides (not one)** | ITR needs both `ICON_RENDERER__OUTPUT__OUTPUT_DIR` and `ICON_RENDERER__COLOR_SCHEME__PATH`. The adapter must set both in the `env` dict via `build_env({"ICON_RENDERER__OUTPUT__OUTPUT_DIR": ..., "ICON_RENDERER__COLOR_SCHEME__PATH": ...})`. Both pass the `ICON_RENDERER__` prefix allowlist in `env.py`. |
| **Palette cache path resolution** | The adapter needs the full path to `cache/palettes/<ph>/colors.yaml` to set `ICON_RENDERER__COLOR_SCHEME__PATH`. Options: (A) accept `palette_cache_dir: Path` as constructor param, (B) compute from `output_dir` (parent chain), (C) require caller to compute and pass `colors_yaml_path: Path`. **Recommended:** Option A — constructor takes `palette_cache_dir: Path | None = None`, validated at render time that `palette_cache_dir / "colors.yaml"` exists. |
| **Three input hashes** | Unlike CSG (2 inputs) and WEG (2 inputs), ITR has 3: `palette_hash`, `templates_hash`, `mappings_hash`. All feed into `icons_entry_hash(palette_hash, templates_hash, mappings_hash)` from `adapters/hashing.py`. |
| **SVG artifacts** | ITR produces `.svg` files (not `.png` like WEG or fixed files like CSG). Verify via `list(output_dir.rglob("*.svg"))`. Handle nested SVGs via `relative_to(output_dir)` for artifact hash keys. |
| **No `-o`/`--output` flag** | Like CSG/WEG, output dir comes solely from env override. Do NOT pass `--output` or `-o` on the CLI. |

### Source tree components to touch

| Path | Action | Notes |
|------|--------|-------|
| `src/runtime/src/runtime/adapters/itr_adapter.py` | **CREATE** | `ItrAdapter(IIconRenderer)` with `render(palette_hash, templates_dir, mappings_path, output_dir) -> IconsEntry`; literal env `ICON_RENDERER__OUTPUT__OUTPUT_DIR` + `ICON_RENDERER__COLOR_SCHEME__PATH`; `subprocess.run` with timeout 60s; computes IconsEntry via hashing; no settings.toml edit; container forwarding via env passthrough |
| `src/runtime/src/runtime/ports/icon_renderer.py` | **MODIFY** (if needed) | Update to Path-based `render(self, palette_hash: str, templates_dir: Path, mappings_path: Path, output_dir: Path) -> IconsEntry` — mirror CSG/WEG port update. Keep ABC. Verify `pathlib` allowed in ports (test_layering.py allows it for ports, domain is banned). |
| `src/runtime/tests/unit/test_itr_adapter.py` | **CREATE** | Unit tests mocked subprocess |
| `src/runtime/tests/integration/test_itr_adapter_integration.py` | **CREATE** | Real itr integration, skipped if missing |

### Testing standards summary

- Runner: `uv run --directory src/runtime pytest`
- Lint/type: `ruff check`, `mypy --strict`
- Fixtures: Reuse `tmp_path`, `tests/fixtures/wallpaper.png` (74 bytes `619cd350...`), create temp templates dir with at least one `.j2` file, temp mappings dir/file.
- Env override assertion: Verify `ICON_RENDERER__OUTPUT__OUTPUT_DIR == str(output_dir)` AND `ICON_RENDERER__COLOR_SCHEME__PATH == str(colors_yaml_path)` — literal keys, never single underscore.
- Timeout: mocked TimeoutExpired → TimeoutError with "timed out".
- No settings.toml edit: mtime unchanged.

### Architecture extraction — what this story must respect

| Decision | Relevance | What to do |
|----------|-----------|------------|
| **AD-1 Hexagonal** | Subprocess I/O in adapters | Keep itr subprocess + env injection in `adapters/itr_adapter.py`; **MUST NOT** import `os`/`subprocess`/`pathlib` into `domain` |
| **AD-2 Layered cache key** | Key = hash of ALL inputs via `adapters/hashing.py` | Use `icons_entry_hash(palette_hash, templates_hash, mappings_hash)` to compute `<ih>`; entry dir = `cache/icons/<ih>` |
| **AD-7 ITR env override** | Literal keys, no settings.toml edit, container forwarding | Use literal `ICON_RENDERER__OUTPUT__OUTPUT_DIR` + `ICON_RENDERER__COLOR_SCHEME__PATH`; **MUST NOT** edit `settings.toml`; container mode passes overrides INTO container env |
| **AD-14 Domain purity** | Allowlist enforced | Domain imports only allowlist; adapter is the only place with `os`/`subprocess`/`pathlib` |
| **AD-15 Cross-package boundary** | Runtime imports only `cli-output` | Do NOT `import icon_templates_renderer` package; adapter uses `shutil.which("itr")` + `subprocess.run(["itr", ...])` as black box |

### Previous story intelligence — what exists now

- **Story 1.7 (csg adapter):** `CsgAdapter(IColorSchemeGenerator)` at `adapters/csg_adapter.py` with env override `COLORSCHEME__OUTPUT__DIRECTORY`, timeout 60s, error handling, no settings.toml edit, 10 unit + 1 integration tests. **Pattern to mirror exactly** — copy defensive patterns (empty path, symlink, size guards, timeout validation, signal handling). Port updated from str-based to Path-based.
- **Story 1.8 (weg adapter):** `WegAdapter(IEffectsGenerator)` at `adapters/weg_adapter.py` with env override `WALLPAPER__OUTPUT__DIRECTORY`, timeout 60s, catalog discovery pattern, 10 unit + 1 integration tests. **Pattern to mirror exactly** — same defensive patterns, same test structure.
- **Review learnings from 1.7 + 1.8:**
  - `build_env()` from `adapters/env.py` is the centralized allowlist builder — use it, never `dict(os.environ)`.
  - `_validate_output_dir` must check `..`, symlink, case-sensitive, length guard, `FileExistsError` wrapping.
  - Wallpaper/paths must check `exists()`, `is_file()`, `is_symlink()`, `stat.S_ISREG`, size guards.
  - `hash_file` must be wrapped in try/except OSError for artifact verification.
  - `bool` timeout bypass: check `type(timeout) is int`, not just `isinstance`.
  - Null bytes in paths: check `"\x00" in str(path)` early.
  - PNG/SVG detection: case-insensitive glob or explicit `*.SVG` fallback.
  - `Catalog_path` / `templates_dir` type validation: `isinstance(Path)`.
  - Empty catalog/dir sentinel: raise `FileNotFoundError` not `ValueError`.

### Project Structure Notes

- **Alignment (AD-13):** `src/runtime/src/runtime/{domain,ports,adapters,application,cli}` + `tests/architecture/test_layering.py` + `tests/unit`/`tests/integration`. This story adds `adapters/itr_adapter.py` (I/O layer) + `tests/unit/test_itr_adapter.py` + `tests/integration/test_itr_adapter_integration.py`.
- **Detected conflicts:** The port `IIconRenderer.render` currently declares `(palette_hash: str, templates_dir: str, mappings_path: str, output_dir: str) -> IconsEntry` (all `str`). The adapter needs `Path` args for FS operations. **Resolution:** Update port ABC to accept `Path` objects in this story (preferred: same as CSG port update in Story 1.7). Verify `test_layering.py` doesn't ban `pathlib` in ports layer (it only bans `pathlib` in domain).
- **Naming:** `adapters/itr_adapter.py` mirrors `csg_adapter.py` + `weg_adapter.py`; class `ItrAdapter` implements `IIconRenderer`; tests `test_itr_adapter.py` mirrors `test_csg_adapter.py`/`test_weg_adapter.py`.
- **Tech stack (pinned):** `python>=3.14`, `typer>=0.12`, `cli-output` (via `uv.sources`). Adapter shells out to `itr` binary (installed via `itr` console_scripts, or via container image when container mode). `itr` discovery via `shutil.which("itr")`.

### References

- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md` — AD-1, AD-2, AD-7 (env override literal keys for ITR), AD-14, AD-15
- Shared data contract: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md` — `ICON_RENDERER__OUTPUT__OUTPUT_DIR` (note `output_dir`), `ICON_RENDERER__COLOR_SCHEME__PATH`, icons meta.json schema, derivation-input hashing (icons = `sha256(palette_hash || templates_hash || mappings_hash)`)
- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md` — Epic 1 Story 1.9 ACs (FR-1, CAP-1, AD-7)
- Hashing helpers: `src/runtime/src/runtime/adapters/hashing.py` — `hash_file`, `canonical_hash_dir`, `icons_entry_hash`, `HASH_ALGORITHM`, `_validate_hex64`
- Env allowlist: `src/runtime/src/runtime/adapters/env.py` — `build_env()` with `ICON_RENDERER__` prefix allowed
- CSG adapter (pattern): `src/runtime/src/runtime/adapters/csg_adapter.py` — full pattern to mirror
- WEG adapter (pattern): `src/runtime/src/runtime/adapters/weg_adapter.py` — full pattern to mirror
- Port: `src/runtime/src/runtime/ports/icon_renderer.py` — current ABC, may need Path update
- Domain models: `src/runtime/src/runtime/domain/models.py` — `IconsEntry`, `IconsArtifacts`
- ITR defaults: `src/cli-tools/icon-templates-renderer/src/icon_templates_renderer/defaults/settings.toml` — never edited by runtime
- ITR binary: `itr` console_scripts entry point, `src/cli-tools/icon-templates-renderer/pyproject.toml`
- Layering test: `src/runtime/tests/architecture/test_layering.py` — verify pathlib allowed in ports
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` — `rt-1-9-itr-adapter-env-overrides: backlog`

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
