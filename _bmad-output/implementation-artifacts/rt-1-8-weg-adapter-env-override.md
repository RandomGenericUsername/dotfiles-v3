---
baseline_commit: 88f34c3
---

# Story 1.8: weg adapter with env override

Status: review

## Story

As a developer,
I want a weg adapter that directs effects output via env override,
So that effect images land in the cache without editing provisioning's settings.toml.

## Acceptance Criteria

1. **Given** a valid wallpaper image file `wallpaper_path: Path` that exists and is readable (validated via `hash_file(wallpaper_path)` producing 64-char `wallpaper_hash`), and a target cache effects entry `state_root/cache/effects/<eh>/` where `eh = effects_entry_hash(wallpaper_hash, catalog_hash)` computed from `adapters/hashing.py` (with `catalog_hash = hash_file(<install>/config/weg/effects.yaml)` READ-ONLY spine input — `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/defaults/effects.yaml` when install spine absent), and `output_dir: Path = state_root/cache/effects/<eh>` (not yet existing), **When** `WegAdapter.generate(wallpaper_path: Path, output_dir: Path) -> EffectsEntry` (implementing `IEffectsGenerator`) is invoked, **Then** it invokes the `weg` binary via `subprocess.run` with env `WALLPAPER__OUTPUT__DIRECTORY=str(output_dir)` (literal double-underscore key per `shared-data-contract.md` Env-override protocol) **and** passes `wallpaper_path` as positional arg via `weg batch all <wallpaper_path>` with **zero** `-o`/`--output` flag (output dir comes solely from env override to exercise container forwarding contract), **And** `weg` writes effect PNGs into `output_dir` (verified via: collect all `*.png` under `output_dir` recursively — weg's batch nests as `output_dir/<stem>/effect/*.png` — flattened or counted as artifacts), **And** the method returns an `EffectsEntry` with `hash_algorithm=="sha256"`, `kind=="effects"`, `entry_hash==eh`, `source_wallpaper_hash==wallpaper_hash`, `input_catalog_hash==catalog_hash`, `artifact_hashes=={<basename>: hash_file(...)}` computed via `adapters/hashing.hash_file` binary chunked for every PNG artifact, `generated_at==ISO-8601 UTC` (`datetime.now(UTC).isoformat().replace("+00:00","Z")`), **And** the provisioning-rendered `settings.toml` (read-only via discovery, never written) remains untouched — verified by stat mtime unchanged before/after (AC 1, AD-7, AD-2, shared-data-contract effects meta.json).

2. **Given** a `WegAdapter` instance configured for local or container runtime mode (resolved externally; adapter itself takes no `runtime.mode` flag — container mode forwarding is an env passthrough property tested in integration), **When** the adapter runs in container mode (`weg` itself configured to use `podman`/`docker` via `oci-runtime` — provisioning owns engine install), **Then** the `WALLPAPER__OUTPUT__DIRECTORY` override is passed **INTO** the container environment (not just host process) — proven by the integration test that uses zero `-o` flag and relies solely on the env override, where host `tmp/out` still receives artifacts even when `runtime.mode==container` (the container's `RunConfig` must include `env={"WALLPAPER__OUTPUT__DIRECTORY": host_target}` per `ARCHITECTURE-SPINE.md` AD-7 last sentence + `shared-data-contract.md` Env-override protocol note). The adapter MUST NOT perform any `settings.toml` rewrite or file copy to simulate this — only env injection (AC 2, AD-7 container-mode override).

3. **Given** `weg` binary availability, **When** `WegAdapter.is_available() -> bool` (or equivalent health check, if exposed) is queried — OR `generate` is called when `weg` not on PATH / container image missing, **Then** `generate` raises a typed error that preserves subprocess stderr (for later error mapping in Epic 3/4) — either `FileNotFoundError("weg not on PATH")` or `RuntimeError(f"weg generate failed: {stderr}")` with `stderr` truncated to 2 KiB, non-zero exit code handled, timeout handled (see AC 4) — **and** the caller (future `ApplyWallpaperUseCase`/`populate_via_staging`) sees a clean exception, not an unhandled `CalledProcessError` or silent swallow. The adapter MUST NOT suggest install via custom message beyond preserving stderr — suggestion logic lives in CLI layer (Story 2.9 future), but the error type/message must be predictable for `OutputPort.error()` to serialize (AC 3, NFR-2 reliability, shared-data-contract).

4. **Given** subprocess-based invocation, **When** `weg batch all` hangs or exceeds a configurable timeout (default 60s, parameter `timeout: int = 60` on the adapter constructor, overrideable per-call), **Then** the adapter kills the process via `subprocess.run(..., timeout=timeout)` which raises `subprocess.TimeoutExpired`, which is caught and re-raised as `RuntimeError(f"weg generate timed out after {timeout}s")` (or `TimeoutError`) with the partial stdout/stderr preserved; **And** `output_dir` is left without partial files (caller is responsible for staging-dir cleanup via `populate_via_staging` — adapter itself must not leave half-written PNGs if it created `output_dir` directly; recommended pattern: caller creates `output_dir` as the staging dir and passes it, so adapter writes straight into staging — adapter must not `shutil.rmtree` itself, just raise) (AC 4, Story 1.7 timeout pattern reused, cache-model.md staging-dir AC 3).

5. **Given** hexagonal boundary (AD-1, AD-14, AD-15), **When** the weg adapter is added, **Then** `domain/` stays pure (allowlist `dataclasses, enum, typing, collections, collections.abc, functools, re, __future__` only; no `os`/`subprocess`/`shutil`/`pathlib`), `ports/IEffectsGenerator` remains ABC with `generate` abstract method unchanged (no concrete class in `ports/`), adapter lives in `adapters/` only (allowed `os`/`subprocess`/`pathlib`/`hashlib` plus `runtime.adapters.hashing` + `runtime.domain.models`), cross-package forbidden set untouched (`provisioning, core, infrastructure, color_scheme_generator, wallpaper_effects_generator, icon_templates_renderer, config_assembler_engine, oci_runtime` — runtime may `shutil.which("weg")` but never `import wallpaper_effects_generator`), and `uv run --directory src/runtime pytest` + `ruff check` + `ruff format --check` + `mypy --strict` + `tests/architecture/test_layering.py` all pass (37 layering checks). The adapter MUST use `adapters/hashing.py:hash_file` + `effects_entry_hash` for every hash — no `hashlib.sha256(data).hexdigest()` inline reimplementation (AC 5, AD-1, AD-14, NFR-1, NFR-10). CsgAdapter remains untouched.

## Tasks / Subtasks

- [x] Task 1 — Create `adapters/weg_adapter.py` implementing `IEffectsGenerator` (AC: 1, 5)
  - [x] **Location MUST be `src/runtime/src/runtime/adapters/weg_adapter.py`** (mirror `csg_adapter.py`). **MUST be in `adapters/`**, NOT `domain/`/`ports`/`application`.
  - [x] Imports allowed ONLY in this file: `subprocess`, `os`, `shutil`, `hashlib` (only via `hashing.py`), `pathlib.Path`, `typing.Final/Literal`, `datetime` (`datetime.now(UTC)`), `stat`, `errno`. Do NOT add `os`/`subprocess` to `domain/` or `ports/`.
  - [x] Export typed class — strict `mypy` signatures:
    ```python
    from pathlib import Path
    from runtime.ports.effects_generator import IEffectsGenerator
    from runtime.domain.models import EffectsEntry
    from runtime.adapters.hashing import hash_file, effects_entry_hash, HASH_ALGORITHM

    class WegAdapter(IEffectsGenerator):
        def __init__(self, timeout: int = 60, weg_bin: str | None = None, catalog_path: Path | None = None) -> None: ...
        def generate(self, wallpaper_path: Path, output_dir: Path) -> EffectsEntry: ...
        def is_available(self) -> bool: ...
    ```
  - [x] Keep `HASH_ALGORITHM` import from `adapters/hashing.py` — assert returned `EffectsEntry.hash_algorithm == HASH_ALGORITHM == "sha256"`.

- [x] Task 2 — Implement `generate` with literal env override, no settings.toml edit (AC: 1, 2)
  - [x] Resolve `wallpaper_hash = hash_file(wallpaper_path)` (chunked 64 KiB, binary).
  - [x] Resolve `catalog_path`: if `__init__(catalog_path)` provided use it; else discover via `_find_default_effects_catalog()` searching repo parents for `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/defaults/effects.yaml` and fallback `src/cli-tools/wallpaper-effects-generator/defaults/effects.yaml`. If not found raise `FileNotFoundError`.
  - [x] Resolve `catalog_hash = hash_file(catalog_path)` binary chunked. Raise `FileNotFoundError` if empty sentinel? Empty catalog is invalid — treat similarly to CSG empty dir guard (hash of empty bytes is not valid catalog; raise).
  - [x] Compute `eh = effects_entry_hash(wallpaper_hash, catalog_hash)` (validates 64-hex inputs). Assert `output_dir.name == eh` else `ValueError(f"output_dir hash mismatch: expected {eh}, got {output_dir.name}")`.
  - [x] Ensure `output_dir` parent exists; `output_dir` itself mkdir. Same validation as CsgAdapter: `_validate_output_dir` checks `..`, symlink, case-sensitive, length guard, FileExistsError wrapping.
  - [x] Build `env = build_env({"WALLPAPER__OUTPUT__DIRECTORY": str(output_dir)})` — literal key, double underscores, uppercase, per `shared-data-contract.md`. Do NOT use single underscores or lowercase. Adapter MUST NOT touch `settings.toml`.
  - [x] Build args: `[weg_bin or "weg", "batch", "all", str(wallpaper_path)]` — intentionally NO `-o`/`--output` flag; output dir comes solely from env override to exercise container forwarding contract. Add `timeout` handling and `capture_output=True, text=True`.
  - [x] Run `subprocess.run(args, capture_output=True, text=True, env=env, timeout=self.timeout)` — on success verify PNG artifacts exist via `list(output_dir.rglob("*.png"))` non-empty and all are files. On failure raise `RuntimeError(f"weg batch all failed (exit {code}): {stderr[:2048]}")` truncated.
  - [x] Compute `artifact_hashes = {p.relative_to(output_dir).as_posix(): hash_file(p) for p in png_files}` OR flattened: use `p.name` if unique; prefer `relative_to` to preserve weg's `effect/blur.png` structure but expose as flat `blur.png`? Choose `p.name` with disambiguation if duplicates — document. For initial, use `p.name` (basename) when no duplicate, else `relative_to` fallback. Simpler: use basename and assert uniqueness; if duplicate, suffix with parent.
  - [x] Return `EffectsEntry(hash_algorithm=HASH_ALGORITHM, kind="effects", entry_hash=eh, source_wallpaper_hash=wallpaper_hash, input_catalog_hash=catalog_hash, artifact_hashes=artifact_hashes, generated_at=datetime.now(UTC).isoformat().replace("+00:00","Z"))`.

- [x] Task 3 — Handle container-mode env forwarding (AC: 2)
  - [x] Same as CSG: adapter only sets host env dict; `weg` container_processor forwards into RunConfig. Document in docstring.
  - [x] Do NOT attempt Docker/Podman `-e` flags — that is `weg`'s responsibility.

- [x] Task 4 — Implement timeout + error preservation (AC: 3, 4)
  - [x] Constructor `timeout: int = 60` validated `isinstance(int) and >0`.
  - [x] Wrap `subprocess.run(..., timeout=self.timeout)` catching `TimeoutExpired -> TimeoutError` with "timed out" substring.
  - [x] On non-zero exit raise `RuntimeError` with stderr truncated 2 KiB + stdout 500, handle negative signal returncode to signal name.
  - [x] Validate `wallpaper_path` early: `exists`, `is_file`, `is_dir`, `stat.S_ISREG`, size 0/100MB guards.

- [x] Task 5 — Tests: unit + integration, strict green (AC: 1,2,3,4,5)
  - [x] Create `src/runtime/tests/unit/test_weg_adapter.py` under `tests/unit/`, fast path.
  - [x] Cover at minimum:
    | Test | Inputs | Expectation |
    |---|---|---|
    | `test_weg_generate_env_override_writes_to_output_dir` | tmp wallpaper, mocked run writes PNGs into env dir | entry_hash==effects_entry_hash, artifact_hashes match, WALLPAPER__OUTPUT__DIRECTORY in env, no -o flag |
    | `test_weg_adapter_never_touches_settings_toml` | real settings.toml mtime | unchanged after generate |
    | `test_weg_adapter_container_env_passthrough` | capture env | WALLPAPER__OUTPUT__DIRECTORY == str(output_dir) even when global env missing |
    | `test_weg_adapter_raises_on_non_zero_exit` | returncode=1 | RuntimeError with stderr |
    | `test_weg_adapter_timeout_raises` | TimeoutExpired | TimeoutError with timed out |
    | `test_weg_adapter_raises_on_missing_wallpaper` | missing path | FileNotFoundError before run |
    | `test_weg_adapter_entry_hash_mismatch` | wrong output_dir name | ValueError |
    | `test_weg_adapter_artifact_hashes_are_hex64` | successful mocked | artifact_hashes values 64-hex, hash_algorithm sha256, kind effects |
    | `test_weg_adapter_is_available` | which patched | True/False |
    | `test_weg_adapter_no_settings_toml_rewrite_even_on_container` | container env | still no settings.toml modification |
  - [x] Create `src/runtime/tests/integration/test_weg_adapter_integration.py` marked integration, calls real `weg` if available else skip, verifies PNGs land and hashes match.

- [x] Task 6 — Ensure zero layering debt and full green (AC: 5)
  - [x] Keep adapter in `adapters/weg_adapter.py` only; verify domain purity, ports ABC only, no cross-package imports.
  - [x] Run and require green: `uv run --directory src/runtime pytest -q`, `ruff check`, `ruff format --check`, `mypy --strict src/runtime/adapters/weg_adapter.py`, `pytest tests/architecture/test_layering.py -v`

## Dev Notes

### Scope boundary — this story is WEG ADAPTER ENV OVERRIDE ONLY

Story 1.8 **defines** the effects-generation adapter that directs `weg` output via `WALLPAPER__OUTPUT__DIRECTORY` env override into `cache/effects/<eh>/`. It does **NOT** implement:
- ITR adapter (1.9), IStateRepository (1.10), SeedCacheUseCase (1.11), etc.
- Keep scope to `IEffectsGenerator` env override.

### Source tree components to touch

| Path | Action | Notes |
|------|--------|-------|
| `src/runtime/src/runtime/adapters/weg_adapter.py` | **CREATE** | `WegAdapter(IEffectsGenerator)` with `generate(wallpaper_path: Path, output_dir: Path) -> EffectsEntry`; literal env `WALLPAPER__OUTPUT__DIRECTORY`; `subprocess.run` with timeout 60s; computes EffectsEntry via hashing; no settings.toml edit; container forwarding via env passthrough |
| `src/runtime/src/runtime/ports/effects_generator.py` | **MODIFY** | Update to Path-based `generate(self, wallpaper_path: Path, output_dir: Path) -> EffectsEntry` if needed (mirrors CsgAdapter port change) |
| `src/runtime/tests/unit/test_weg_adapter.py` | **CREATE** | Unit tests mocked subprocess |
| `src/runtime/tests/integration/test_weg_adapter_integration.py` | **CREATE** | Real weg integration, skipped if missing |

### Testing standards summary

- Runner: `uv run --directory src/runtime pytest`
- Lint/type: `ruff check`, `mypy --strict`
- Fixtures: Reuse `tests/fixtures/wallpaper.png` (74 bytes `619cd350...`), `tmp_path`
- Env override assertion: Verify `WALLPAPER__OUTPUT__DIRECTORY == str(output_dir)` — literal key, never single underscore.
- Timeout: mocked TimeoutExpired → TimeoutError with "timed out".
- No settings.toml edit: mtime unchanged.

## Dev Agent Record

### Agent Model Used

muse-spark-1.2-contributor-free (opencode/muse-spark-1.2-contributor-free)

### Debug Log References

- Implementation followed red-green: wrote WegAdapter via TDD copying CsgAdapter defensive patterns (empty path, symlink, size guards, timeout validation, signal handling).
- Verified literal env key: `WALLPAPER__OUTPUT__DIRECTORY` — no single-underscore variant, checked `build_env` allowlist prefix WALLPAPER__.
- Verified no `-o`/`--output` flag in subprocess args — container forwarding proof via zero-flag pattern.
- Tested timeout via mocked `subprocess.TimeoutExpired` → `TimeoutError` with "timed out".
- Real integration test proved weg batch all with env override writes nested PNGs and hashes match.

### Completion Notes List

- ✅ Implemented `src/runtime/src/runtime/adapters/weg_adapter.py` as `WegAdapter(IEffectsGenerator)` — chosen filename `weg_adapter.py` mirrors `csg_adapter.py`; documented container forwarding via env passthrough.
- ✅ Updated `src/runtime/src/runtime/ports/effects_generator.py` from str-based `(wallpaper_hash, catalog_path, output_dir)` to Path-based `(wallpaper_path: Path, output_dir: Path)` — port remains ABC, pathlib allowed in ports layer, domain stays pure.
- ✅ Implemented `generate` with catalog discovery `_find_default_effects_catalog` (searches `wallpaper_effects_generator/defaults/effects.yaml`), computes `catalog_hash` via `hash_file`, `eh = effects_entry_hash`, validates `output_dir.name == eh`, builds env via `build_env({"WALLPAPER__OUTPUT__DIRECTORY": str(output_dir)})`, runs `weg batch all <wallpaper>` with timeout 60, verifies PNG artifacts via `rglob("*.png")`, handles nested weg output (basename uniqueness fallback to relative path), computes artifact_hashes via `hash_file` binary chunked, returns `EffectsEntry` with `hash_algorithm==sha256` and `generated_at` UTC ISO.
- ✅ Container forwarding: adapter only sets host env dict; documented that `weg`'s container_processor forwards into RunConfig — no Docker `-e` manipulation.
- ✅ Error handling: `FileNotFoundError("weg not on PATH")` on missing binary, `RuntimeError` on non-zero exit with stderr/stdout truncation, `TimeoutError` on TimeoutExpired with "timed out" substring, early `FileNotFoundError`/`IsADirectoryError` for wallpaper, `ValueError` on entry-hash mismatch.
- ✅ No `settings.toml` edit — never opens settings file; verified via mtime tests on real `src/cli-tools/wallpaper-effects-generator/defaults/settings.toml`.
- ✅ Created 10 unit tests in `src/runtime/tests/unit/test_weg_adapter.py` covering env override, no settings.toml touch, container passthrough, non-zero exit, timeout, missing wallpaper, hash mismatch, hex64, is_available, container no-rewrite — all mock subprocess.run, fast path.
- ✅ Created integration test `src/runtime/tests/integration/test_weg_adapter_integration.py` that calls real `weg` binary (skips if not on PATH) and verifies PNGs land in output_dir and hashes match — proves container forwarding when engine present.
- ✅ Layering verified: domain stays pure, ports ABC only, adapters only place with os/subprocess/pathlib, no cross-package imports, `ruff check` + `ruff format --check` + `mypy --strict` + `pytest tests/architecture/test_layering.py` all green (41 checks).

### File List

- src/runtime/src/runtime/adapters/weg_adapter.py (CREATE) — WegAdapter with env override, timeout, error handling, catalog_path injection
- src/runtime/src/runtime/ports/effects_generator.py (MODIFY) — Path-based generate signature
- src/runtime/tests/unit/test_weg_adapter.py (CREATE) — 10 unit tests for AC 1-5
- src/runtime/tests/integration/test_weg_adapter_integration.py (CREATE) — integration with real weg, skipped if missing
- _bmad-output/implementation-artifacts/sprint-status.yaml (MODIFY) — status backlog → in-progress → review
- _bmad-output/implementation-artifacts/rt-1-8-weg-adapter-env-override.md (MODIFY) — Task checkboxes, Status, Dev Record

### Change Log

- 2026-08-30: Implemented WegAdapter env override, updated port to Path signature, added 10 unit + 1 integration tests, verified layering + ruff + mypy green. Story status → review.

### Status

