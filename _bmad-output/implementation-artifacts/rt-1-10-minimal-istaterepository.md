---
baseline_commit: 77f1b94
---

# Story 1.10: Minimal IStateRepository with JSON adapter

Status: ready-for-dev

## Story

As a developer,
I want the minimal state store (current.json read/write per the pinned schema),
So that Epic 2's crash recovery is grounded in recorded state.

## Acceptance Criteria

1. **Given** the `shared-data-contract.md` `current.json` schema (schema_version `2`, `wallpaper: {hash, source_path, applied_at}`, `monitors: {<name>: {backend, source_hash, fit_mode, mpv_options, ipc_socket}}`, `palette/effects/icons: {hash, generated_at}` or `null`, `applied_at`), **When** `IStateRepository.save(state: DesktopState)` and `load_current() -> DesktopState | None` are invoked via `JsonStateRepository` at `state_root = XDG_STATE_HOME/dotfiles` (default `~/.local/state/dotfiles`), **Then** `save` is **atomic** via sibling `tmp` (`current.json.tmp.<pid>-<rand8>` in same dir) + `os.replace` (POSIX atomic), `load_current` **projection-round-trips** the `DesktopState`: `wallpaper` (hash+source_path+applied_at) + `monitors` (exact) + `palette/effects/icons` **projection** (`hash`+`generated_at` only, per shared-data-contract — full `PaletteEntry.input_template_hash`/`artifact_hashes` live in `cache/<layer>/<hash>/meta.json` and are reconstructed as sentinel `input_template_hash="0"*64` + `artifact_hashes={}` on load), **And** `palette/effects/icons` may be `null` (serialized as `null`, deserialized as `None`) when that layer was never derived for the current wallpaper (wallpaper is always present once seeded), **And** all `*hash` fields round-trip as lowercase `64-hex` validated via `adapters/hashing._validate_hex64`, `applied_at/generated_at` as strict `ISO-8601 UTC` ending with `Z` (`datetime.now(UTC).isoformat().replace("+00:00","Z")`, validated with `s.endswith("Z")` before `fromisoformat`), `hash_algorithm` literal `"sha256"` never appears in `current.json` (it lives in `meta.json` only) — but reconstructed `DesktopState` entries carry `hash_algorithm=="sha256"` for entry symmetry. The file is written with `json.dump(..., indent=2, sort_keys=True, ensure_ascii=False)` UTF-8 + trailing `\n`, deterministic (`sort_keys` + `indent`), parent dir `state_root` created `mkdir(parents=True, exist_ok=True)`. (AC 1, shared-data-contract current.json, ARCHITECTURE-SPINE.md AD-3, AD-5, AD-6).

2. **Given** the persisted `current.json` on disk, **When** `load_current()` runs and detects a `schema_version` mismatch (file contains `schema_version != 2`, e.g. `1` or `3` or missing), **Then** it raises a **typed error** surfacing the mismatch: `ValueError(f"unsupported schema_version: {v!r}, expected 2")` (or subclass `SchemaVersionError(ValueError)` if defined), **And** does **not** silently migrate or return `None` — caller sees a clean exception (for later error mapping / `OutputPort.error()` serialization), **And** the check happens **immediately after JSON parse, before any other field deserialization** so a truncated/migrated v1 blob does not partially deserialize. If `monitors` key is **absent** (v1 legacy, `schema_version` already verified as `2`), the loader **tolerantly** returns `monitors: {}` (not crash) and documents `# v1 migration deferred to SeedCacheUseCase (1.11)`; this keeps `1.10` minimal while not crashing on a stale file. Schema-version failure always takes precedence over monitors-tolerance. (AC 2, shared-data-contract Rules schema_version 2, Migration note).

3. **Given** absent store (first run, `state_root/current.json` does not exist), **When** `load_current()` is called, **Then** it returns `None` **without** raising, **without** creating the file, **without** logging an error — `None` signals "never seeded" to `SeedCacheUseCase` (1.11), **And** a subsequent `save(state)` still atomically creates the file (tmp + replace). `save` must also handle the **empty parent** case: `state_root` may not exist (fresh `~/.local/state`); `save` creates it. `load_current` must distinguish `FileNotFoundError` (return `None` only when `not exists` and not a symlink) from `IsADirectoryError` / `PermissionError` / `JSONDecodeError` / `OSError` (propagate as `RuntimeError`/`ValueError` with context, not swallowed). Symlink check (`is_symlink()`) happens **before** `exists()` to avoid TOCTOU symlink attack. Missing required fields (`wallpaper`, `applied_at`) raise `ValueError(f"current.json missing required field: {name!r}")` wrapping `KeyError`, not bare `KeyError`. (AC 3, AD-5 state_root runtime-owned, AD-3 JSON store, AD-14 domain purity).

4. **Given** hexagonal boundary (AD-1, AD-14, AD-15) and `NFR-1` domain purity, **When** the JSON adapter is added, **Then** `domain/` stays pure (allowlist `dataclasses, enum, typing, collections, collections.abc, functools, re, __future__` only; no `os`/`subprocess`/`shutil`/`pathlib`), `ports/IStateRepository` remains **ABC** with `load_current`/`save` unchanged (no concrete class in `ports/`), adapter lives in `adapters/` only (allowed `os`/`json`/`pathlib`/`uuid`/`hashlib` via `hashing` + `runtime.domain.models`), cross-package forbidden set untouched (`provisioning, core, infrastructure, color_scheme_generator, wallpaper_effects_generator, icon_templates_renderer, config_assembler_engine, oci_runtime`), and `uv run --directory src/runtime pytest` + `ruff check` + `ruff format --check` + `mypy --strict src/runtime/adapters/json_state_repository.py` + `tests/architecture/test_layering.py` all pass (`42` layering checks). Adapter **MUST** use `adapters/hashing._validate_hex64` for every hash field and `hashlib` only via `hashing.py` — no inline `hashlib.sha256(...).hexdigest()` reimplementation. Adapter **MUST NOT** import `config_assembler_engine` or read provisioning `settings.toml` to discover `state_root` — `state_root` is XDG only. (AC 4, AD-1, AD-14, NFR-1, NFR-10).

## Tasks / Subtasks

- [ ] Task 1 — Create `adapters/json_state_repository.py` implementing `IStateRepository` (AC: 1, 4)
  - [ ] **Location MUST be `src/runtime/src/runtime/adapters/json_state_repository.py`** (mirrors `cache.py`, `csg_adapter.py`, `weg_adapter.py`, `itr_adapter.py`). **MUST be in `adapters/`**, NOT `domain/`/`ports`/`application`.
  - [ ] Imports allowed ONLY in this file: `os`, `json`, `pathlib.Path`, `uuid`, `typing.Final/Literal`, `datetime` (`datetime.now(UTC)`), `errno`, `hashlib` only via `hashing.py`. Do NOT add `os`/`json`/`pathlib`/`uuid` to `domain/` or `ports/`.
  - [ ] Export typed class — strict `mypy` signatures:
    ```python
    from pathlib import Path
    from runtime.ports.state_repository import IStateRepository
    from runtime.domain.models import DesktopState, WallpaperEntry, MonitorWallpaperConfig, PaletteEntry, EffectsEntry, IconsEntry

    class JsonStateRepository(IStateRepository):
        def __init__(self, state_root: Path | None = None, current_json: Path | None = None) -> None: ...
        def load_current(self) -> DesktopState | None: ...
        def save(self, state: DesktopState) -> None: ...
        # helpers (private): _state_to_dict(state) -> dict, _dict_to_state(data) -> DesktopState, _atomic_write(path, data) -> None
    ```
  - [ ] Constructor: `state_root` defaults to `Path((os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state"))) / "dotfiles"` (AD-5) — `or` handles empty-string `XDG_STATE_HOME=""` (would otherwise yield relative `dotfiles`). If `current_json` not supplied, `self._path = self.state_root / "current.json"`. Validate `state_root` contains no `"\x00"` and `len(str(state_root)) < 4096` and no `..` traversal component (`".."` in `Path.parts` → `ValueError`). Store `self.state_root: Path`, `self._path: Path`.
  - [ ] Keep `HASH_ALGORITHM` checked via `from runtime.adapters.hashing import HASH_ALGORITHM` guard `if HASH_ALGORITHM != "sha256": raise AssertionError(...)` fail-closed (mirrors `cache.py`, `csg_adapter.py`). Define sentinel `SENTINEL_HASH = "0" * 64  # placeholder; hydrated from cache/meta.json` for reconstructed `input_*_hash`.
  - [ ] Adapter must NOT import `provisioning`, `color_scheme_generator`, etc. Verify `test_layering.py` cross-package forbidden set. Must NOT import `config_assembler_engine` — `state_root` is XDG only, never from `settings.toml`.
  - [ ] Domain stays pure: `src/runtime/src/runtime/domain/models.py` already defines `DesktopState` + `WallpaperEntry` + `MonitorWallpaperConfig` + `PaletteEntry`/`EffectsEntry`/`IconsEntry` (Story 1.2 done). Do NOT modify domain models in this story — they already match shared-data-contract.

- [ ] Task 2 — Implement `save` with atomic tmp + os.replace (AC: 1)
  - [ ] Serialize `DesktopState` → `dict` per `shared-data-contract.md` current.json exactly:
    ```python
    {
      "schema_version": 2,
      "wallpaper": {"hash": state.wallpaper.content_hash, "source_path": state.wallpaper.source_path, "applied_at": state.wallpaper.imported_at},
      "monitors": {name: {"backend": cfg.backend.value, "source_hash": cfg.source_hash, "fit_mode": cfg.fit_mode.value, "mpv_options": cfg.mpv_options, "ipc_socket": cfg.ipc_socket} for name, cfg in state.monitors.items()},
      "palette": {"hash": state.palette.entry_hash, "generated_at": state.palette.generated_at} if state.palette else None,
      "effects": {"hash": state.effects.entry_hash, "generated_at": state.effects.generated_at} if state.effects else None,
      "icons": {"hash": state.icons.entry_hash, "generated_at": state.icons.generated_at} if state.icons else None,
      "applied_at": state.applied_at,
    }
    ```
    Note: `wallpaper.imported_at` (domain field) maps to `wallpaper.applied_at` in JSON (`TODO: field rename is spine change per shared-data-contract disclaimer`); `applied_at` top-level is `state.applied_at`. Use `Literal[2]` for `schema_version`.
  - [ ] Validate before write: `schema_version == 2` literal, `wallpaper.content_hash` 64-hex via `_validate_hex64`, each `MonitorWallpaperConfig.source_hash` 64-hex, `palette.entry_hash`/`effects.entry_hash`/`icons.entry_hash` 64-hex if not None, `applied_at`/`generated_at` are strict ISO-8601 UTC ending with `Z` (`if not v.endswith("Z"): raise ValueError` then `datetime.fromisoformat(v.replace("Z","+00:00"))` — raise `ValueError` if invalid). `monitors` keys are non-empty strings, `backend`/`fit_mode` enum values (write `.value`).
  - [ ] Ensure `state_root` / `self._path.parent` exists: `self._path.parent.mkdir(parents=True, exist_ok=True)`. Handle `PermissionError` → propagate with context.
  - [ ] Atomic write: `tmp = self._path.with_name(f"{self._path.name}.tmp.{os.getpid()}-{uuid.uuid4().hex[:8]}")` sibling in same dir (ensures same filesystem for atomic `os.replace`; `uuid` avoids PID-reuse collision per `cache.py` `.staging-<pid>-<uuid>` pattern). Write `tmp.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")` deterministic (`sort_keys` + `indent`). Then `os.replace(tmp, self._path)` (POSIX atomic, overwrites if exists). In `try/finally`, if `tmp.exists()` after failure, `tmp.unlink(missing_ok=True)` (best-effort, no `shutil.rmtree` — it's a file). Do NOT use `Path.rename` (not guaranteed atomic) or `tempfile.NamedTemporaryFile(delete=False)` cross-filesystem risk — use `os.replace`.
  - [ ] Verify `save` never leaves `current.json.tmp.*` orphans: `finally` cleanup handles crash during write; test via injected `OSError` on `os.replace` → tmp removed. Also assert raw `current.json` is deterministic (`sort_keys` → bytes stable except timestamps).
  - [ ] Do NOT write `history.jsonl` here — that is Story 3.1 (must-not-lose) owned by `InspectStateUseCase`; this story is `current.json` only. Assert `not (state_root / "history.jsonl").exists()` after `save` in tests.

- [ ] Task 3 — Implement `load_current` with schema validation + absent handling + tolerant v1 (AC: 1, 2, 3)
  - [ ] Symlink guard first (TOCTOU): `if self._path.is_symlink(): raise ValueError(f"current.json is not a regular file (symlink): {self._path}")`. Then fast-path absent: `if not self._path.exists(): return None`. Distinguish `FileNotFoundError` (return None, not a symlink) from `IsADirectoryError` (if `self._path` is a directory, raise `IsADirectoryError(self._path)`). Do NOT create the file.
  - [ ] Guard `self._path.is_file()` else raise `ValueError(f"current.json is not a regular file: {self._path}")`.
  - [ ] Read: `raw = self._path.read_text(encoding="utf-8")` → `data = json.loads(raw)` wrapped in `try/except json.JSONDecodeError as e: raise ValueError(f"current.json is not valid JSON: {e}") from e`. `OSError`/`PermissionError` propagate.
  - [ ] Validate `schema_version` **first**: `v = data.get("schema_version")`; `try: if v != 2: raise ValueError(f"unsupported schema_version: {v!r}, expected 2")` — before any other field access. Wrap missing-key case as `unsupported` (when `v is None`).
  - [ ] Deserialize `wallpaper`: wrap `try: w = data["wallpaper"] except KeyError as e: raise ValueError(f"current.json missing required field: {e.args[0]!r}") from e`; validate `w["hash"]` 64-hex via `_validate_hex64("wallpaper.hash", w["hash"])`, `w["source_path"]` is `str` (empty allowed), `w["applied_at"]` strict ISO-8601 Z (`endswith("Z")` check). Construct `WallpaperEntry(hash_algorithm="sha256", kind="wallpaper", content_hash=w["hash"], source_path=w["source_path"], imported_at=w["applied_at"])`.
  - [ ] Deserialize `monitors`: `m = data.get("monitors")`; if `m is None` (v1 legacy absent, `schema_version` already verified `==2`): set `monitors = {}` and document `# v1 migration deferred to SeedCacheUseCase (1.11)` (do NOT crash; return empty). If `m is not None` and not `dict`, raise `ValueError`. For each `name, cfg` in `m.items()`: validate `name` non-empty `str`, `cfg["backend"]` in `BackendType` members, `cfg["source_hash"]` 64-hex, `cfg["fit_mode"]` in `FitMode`, `mpv_options`/`ipc_socket` are `str|None`, and if `backend != "mpvpaper"` then both must be `None` else raise `ValueError` (mirrors `MonitorWallpaperConfig.__post_init__`). Construct `MonitorWallpaperConfig(backend=BackendType(cfg["backend"]), source_hash=cfg["source_hash"], fit_mode=FitMode(cfg["fit_mode"]), mpv_options=cfg["mpv_options"], ipc_socket=cfg["ipc_socket"])`.
  - [ ] Deserialize `palette/effects/icons` projection: each is either `None` or `{"hash": <64hex>, "generated_at": <ISO Z>}` — wrap `KeyError` similarly. For non-None, validate 64-hex (`_validate_hex64`) and strict `Z` ISO, then reconstruct minimal entries:
    ```python
    SENTINEL = "0" * 64  # placeholder; hydrated from cache/<layer>/<hash>/meta.json
    palette = PaletteEntry(hash_algorithm="sha256", kind="palette", entry_hash=d["hash"], source_wallpaper_hash=w["hash"], input_template_hash=SENTINEL, artifact_hashes={}, generated_at=d["generated_at"]) if d else None
    # effects: source_wallpaper_hash=w["hash"], input_catalog_hash=SENTINEL
    # icons: source_palette_hash=d["hash"], input_templates_hash=SENTINEL, input_mappings_hash=SENTINEL
    ```
    Document `projection reconstruction; full derivation hashes live in cache meta.json` — Epic 2/3 cache readers hydrate from `cache/<layer>/<hash>/meta.json` when needed.
  - [ ] Validate `applied_at` top-level: strict `Z` + `fromisoformat`; wrap `KeyError` → `ValueError` for missing field.
  - [ ] Construct `DesktopState(schema_version=2, wallpaper=..., monitors=..., palette=..., effects=..., icons=..., applied_at=data["applied_at"])` and return it.
  - [ ] Error types: `FileNotFoundError` → `None` only for absent path (non-symlink); `JSONDecodeError`/`ValueError`/`OSError`/`PermissionError` propagate (do NOT swallow). Ensure callers see typed errors for `OutputPort.error()` later.

- [ ] Task 4 — Tests: unit + integration, strict green (AC: 1,2,3,4)
  - [ ] Create `src/runtime/tests/unit/test_json_state_repository.py` under `tests/unit/`, fast path (`pytest -k "not integration"`).
  - [ ] Cover at minimum (projection-round-trip, not full equality):
    | Test | Inputs | Expectation |
    |---|---|---|
    | `test_save_and_load_projection_roundtrip` | `DesktopState` with wallpaper + 2 monitors (hyprpaper + mpvpaper with `mpv_options`/`ipc_socket`) + palette non-None | `save` creates `current.json` with `schema_version==2` + `wallpaper.hash`+ `monitors` exact + `palette.hash`+`applied_at` (raw JSON `sort_keys`); `load_current` returns `DesktopState` where `loaded.wallpaper` exact, `loaded.monitors` exact, `loaded.palette.entry_hash == original.palette.entry_hash` + `generated_at` equal, `loaded.palette.input_template_hash == SENTINEL` (documented projection, not full equality `loaded == original`) |
    | `test_roundtrip_with_mpvpaper_monitor` | `MonitorWallpaperConfig(backend=mpvpaper, mpv_options="no-audio", ipc_socket="/run/mpv.sock")` | round-trips monitor with mpv fields preserved; non-mpv monitor with mpv_options raises |
    | `test_save_is_atomic_tmp_replace` | mock `os.replace` tracking, assert tmp path is sibling `current.json.tmp.<pid>-<8hex>`, `tmp` removed on success, data is valid JSON `indent=2 sort_keys` + trailing `\n` | `json.dumps` indent verification, no `*.tmp.*` left |
    | `test_current_json_is_deterministic` | `save(state)` twice with same state | raw `current.json` bytes identical |
    | `test_save_creates_state_root_if_missing` | `tmp_path/state` not existing | `save` creates `state_root` + `current.json` |
    | `test_load_returns_none_on_absent` | no file | `None` without exception, no file created |
    | `test_load_rejects_symlink_current_json` | `current.json` is symlink → target | `ValueError` symlink, not `None` |
    | `test_load_raises_on_schema_mismatch` | `{"schema_version":1,...}` | `ValueError` with `unsupported schema_version` + `expected 2` |
    | `test_load_raises_on_schema_missing` | `{"wallpaper":...}` no schema_version | `ValueError` unsupported |
    | `test_load_tolerates_monitors_absent_v1_but_schema_first` | `{"schema_version":1, "wallpaper":{...}}` no monitors | raises `unsupported schema_version` (schema check precedence, not `monitors=={}`) |
    | `test_load_tolerates_monitors_absent_v1` | `{"schema_version":2, "wallpaper":{...}}` no monitors | returns `DesktopState` with `monitors=={}` |
    | `test_roundtrip_with_null_palette_effects_icons` | `DesktopState(palette=None, effects=None, icons=None)` | JSON has `null` values, `load` returns `None` for those fields |
    | `test_load_raises_on_invalid_json` | truncate file to `"{invalid"` | `ValueError` with `not valid JSON` |
    | `test_load_raises_on_missing_required_field` | `{"schema_version":2}` no wallpaper | `ValueError` `missing required field: 'wallpaper'` (KeyError wrapped) |
    | `test_load_distinguishes_is_directory` | `current.json` is a directory | `IsADirectoryError` or `ValueError` not `None` |
    | `test_save_validates_hex64` | `wallpaper.content_hash="nothex"` | `ValueError` before writing (no file created) |
    | `test_save_rejects_non_z_timestamp` | `applied_at="2026-08-30T00:00:00+00:00"` (no Z) | `ValueError` before write |
    | `test_save_never_writes_history_jsonl` | `save(state)` | `not (state_root / "history.jsonl").exists()` |
    | `test_init_rejects_null_byte_and_traversal` | `state_root=Path("/tmp/\x00")` or `Path("/tmp/../etc")` | `ValueError` at `__init__` |
    | `test_save_overwrites_atomically` | `save(state1)` then `save(state2)` with different hashes | second `load` returns projection of `state2`, no partial interleaving, tmp cleaned |
    | `test_desktopstate_frozen_equality` | same projection data twice via `_dict_to_state` | `DesktopState` equality holds for projection fields |
    - [ ] Create `src/runtime/tests/integration/test_json_state_repository_integration.py` marked `integration`, uses real `tmp_path` + `JsonStateRepository(state_root=tmp_path)`, exercises filesystem authority: `save` then `load` then assert `current.json` is authoritative (`current.json` raw JSON `wallpaper.hash` matches), and `history.jsonl` not touched.
  - [ ] Fixtures: Reuse `hashing.hash_file` for wallpaper hash from `tests/fixtures/wallpaper.png` (74 bytes `619cd350...`), `BackendType.hyprpaper`/`FitMode.cover` + `BackendType.mpvpaper`, `datetime.now(UTC)` strict `Z`.
  - [ ] Atomicity verification: `list(state_root.glob("current.json.tmp.*")) == []` after `save` success; on simulated `OSError` during `write_text`/`os.replace`, tmp removed via `finally`.

- [ ] Task 5 — Ensure zero layering debt and full green (AC: 4)
  - [ ] Keep adapter in `adapters/json_state_repository.py` only; verify `domain/` stays pure (allowlist `dataclasses, enum, typing, collections, collections.abc, functools, re, __future__`), `ports/state_repository.py` stays ABC only, no cross-package imports.
  - [ ] Run and require green before marking done:
    ```bash
    uv run --directory src/runtime pytest -q                               # all unit + layering
    uv run --directory src/runtime pytest tests/architecture/test_layering.py -v
    uv run --directory src/runtime ruff check src/runtime/adapters/json_state_repository.py
    uv run --directory src/runtime ruff format --check src/runtime/adapters/json_state_repository.py
    uv run --directory src/runtime mypy --strict src/runtime/adapters/json_state_repository.py
    ```
    All must pass; `ruff check` clean for changed file; `mypy --strict` success; `test_layering.py` 42 passed.
  - [ ] Document in `adapters/json_state_repository.py` docstring: ADR references (AD-3 JSON store, AD-4 history must-not-lose deferral, AD-5 state_root empty-string handling, AD-6 symlinks lead, AD-14 domain purity) + `current.json` schema pin + sibling `tmp.<pid>-<rand>` + `os.replace` + `None` on absent + `ValueError` on mismatch + projection sentinel `SENTINEL="0"*64`.

## Dev Notes

### Scope boundary — this story is MINIMAL IStateRepository (current.json ONLY)

Story 1.10 **defines** the minimal state store adapter that persists `current.json` per `shared-data-contract.md` (the manifest: `schema_version 2` + `wallpaper` + `monitors` + `palette/effects/icons` + `applied_at`) via atomic sibling `tmp + os.replace`, and loads it with projection round-trip + `schema_version` guard + `None` on absent (first run). It does **NOT** implement:
- `history.jsonl` append-only must-not-lose (Story 3.1, owned by `InspectStateUseCase` / `SeedCacheUseCase` history)
- `SeedCacheUseCase` self-seeding from provisioning `generated/` (Story 1.11)
- `ApplyWallpaperUseCase` derive/cache/persist orchestration (Story 1.13)
- `ReconcileDesktopStateUseCase` swap sequencing (Stories 2.1–2.7)
- Cache `meta.json` hydration (that lives in `cache/<layer>/<hash>/meta.json`, AD-2)

Keep scope to `IStateRepository` `load_current`/`save` only, in `adapters/json_state_repository.py` + `ports/state_repository.py` (already ABC) + `domain/models.py` (already frozen dataclasses). Do NOT add `history` methods to `IStateRepository` in this story — the port is minimal `load_current`/`save` by design; `history` extension is Phase 3 (AD-3 deferred).

### IStateRepository-specific design challenges

| Challenge | Resolution |
|-----------|------------|
| **Port is minimal `load_current`/`save` only** | Keep it minimal. Do NOT add `load_history`/`append_history`/`list_cache` methods here. Those belong to `InspectStateUseCase` (Epic 3). The adapter owns `current.json` only. History is separate file with different durability contract (append-only, never rewrite). |
| **current.json projection vs full DesktopState (C1 fix)** | `current.json` per `shared-data-contract.md` stores only `hash`+`generated_at` for `palette/effects/icons` (projection), NOT full `input_template_hash`/`artifact_hashes`. `DesktopState` holds full entries for in-memory use, but on disk we persist projection. On `load`, reconstruct minimal entries with `entry_hash=d["hash"]`, `generated_at`, `source_wallpaper_hash=wallpaper.hash` (derived), `input_template_hash=SENTINEL="0"*64`, `artifact_hashes={}` — document that full `artifact_hashes` live in `cache/<layer>/<hash>/meta.json` and will be hydrated by future hydrators. Round-trip test asserts **projection equality** (`entry_hash`+`generated_at`) not `loaded == original` full equality. This prevents false-`==` failures. |
| **Atomicity contract (C4 fix)** | Use sibling `tmp` (`current.json.tmp.<pid>-<8hex>`) in same dir, write `json.dumps(indent=2, sort_keys=True, ensure_ascii=False) + "\n"` UTF-8 deterministic, then `os.replace(tmp, target)` (POSIX atomic). `uuid4().hex[:8]` avoids PID-reuse collision per `cache.py` `.staging-<pid>-<uuid>` pattern. Do NOT use `Path.rename` or `tempfile.NamedTemporaryFile(delete=False)`. Sibling guarantees same mount (AD-5). Clean `tmp` in `finally` if still exists. Do NOT `fsync` directory in Phase 2 (atomic `os.replace` sufficient for CLI synchronous use). |
| **Schema_version guard vs migration (E3 fix)** | Validate `schema_version !=2 → ValueError` **immediately after `json.loads`**, before any other field. `monitors` absent tolerance (`monitors=={}`) only applies when `schema_version==2`. Test `test_load_tolerates_monitors_absent_v1_but_schema_first` enforces precedence. Document `# v1 migration deferred to SeedCacheUseCase (1.11)` in code. |
| **state_root resolution (C3 fix)** | `state_root = Path((os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state"))) / "dotfiles"` — `or` handles empty-string `XDG_STATE_HOME=""` (would otherwise yield relative `dotfiles`). Matches `cache-model.md` layout: `state_root/cache/`, `state_root/current/`, `state_root/current.json`, `state_root/history.jsonl`. Constructor allows injection for tests (`tmp_path`). Validate `"\x00"` and `..` traversal and `len<4096`. |
| **Null palette/effects/icons** | Per shared-data-contract: any of `palette/effects/icons` may be `null` only when never derived. Serialize `None` as `null`, deserialize `null` as `None`. Validate `wallpaper` always present after seeding — wrap missing `wallpaper`/`applied_at` `KeyError` → `ValueError("missing required field")` (C2 fix). |
| **ISO-8601 Z handling (E2 fix)** | Use `datetime.now(UTC).isoformat().replace("+00:00","Z")` for write (matches `csg/wep/itr` pattern). On read, enforce `if not s.endswith("Z"): raise ValueError` then `datetime.fromisoformat(s.replace("Z","+00:00"))`. |
| **Error surface (C2 fix)** | `load_current` returns `None` ONLY for truly absent file (non-symlink `not exists`). All other `OSError`/`JSONDecodeError`/`ValueError` propagate. Wrap every `data["field"]` / `w["hash"]` access in `except KeyError → ValueError` with `missing required field` message. `save` validates inputs before mutation so invalid `DesktopState` never creates partial file. |
| **Symlink TOCTOU (E1 fix)** | Check `is_symlink()` **before** `exists()` (symlink → file attack). If symlink, raise `ValueError` immediately, never return `None`. |

### Source tree components to touch

| Path | Action | Notes |
|------|--------|-------|
| `src/runtime/src/runtime/adapters/json_state_repository.py` | **CREATE** | `JsonStateRepository(IStateRepository)` with `load_current() -> DesktopState \| None` and `save(state: DesktopState) -> None`; literal `schema_version==2` first; `tmp.<pid>-<rand>` + `os.replace` atomic; `monitors` v1 tolerant `{}`, `KeyError→ValueError`; strict `Z` + symlink-before-exists; `None` on absent; `json` UTF-8 `indent=2 sort_keys=True` + `\n` deterministic; no `history.jsonl` touch; `SENTINEL="0"*64` projection; XDG `or` empty-string handling |
| `src/runtime/src/runtime/ports/state_repository.py` | **NO-OP** (verify) | Already `IStateRepository(ABC)` with `load_current`/`save` abstract; verify ABC only, no concrete class; `mypy` strict; do NOT add history methods |
| `src/runtime/src/runtime/domain/models.py` | **NO-OP** (verify) | Already `DesktopState(frozen, slots)` + `WallpaperEntry` + `MonitorWallpaperConfig` + `PaletteEntry`/`EffectsEntry`/`IconsEntry` from Story 1.2; already `StrEnum` `BackendType`/`FitMode` with `__post_init__` `mpvpaper` guard; keep pure (allowlist only) |
| `src/runtime/tests/unit/test_json_state_repository.py` | **CREATE** | Unit tests mocked `os.replace` for atomicity + `tmp_path` real FS for projection round-trip, 17 tests covering AC 1-4 + C/E fixes; fast path `pytest -k "not integration"` |
| `src/runtime/tests/integration/test_json_state_repository_integration.py` | **CREATE** | Real FS integration: `JsonStateRepository(state_root=tmp_path)` → `save` → `load_current` → assert `current.json` authoritative; `history.jsonl` not touched; deterministic bytes |

### Testing standards summary

- Runner: `uv run --directory src/runtime pytest`
- Lint/type: `ruff check`, `ruff format --check`, `mypy --strict src/runtime/adapters/json_state_repository.py`
- Layering: `uv run --directory src/runtime pytest tests/architecture/test_layering.py -v` (42 checks, `domain` stdlib allowlist, `ports` ABC-only, `adapters` allowed `os`/`json`/`pathlib`/`uuid`/`hashlib` via `hashing`)
- Fixtures: reuse `tmp_path`, `tests/fixtures/wallpaper.png` (74 bytes `619cd350...07be`), `hashing.hash_file` for `wallpaper_hash`, `BackendType.hyprpaper`/`FitMode.cover` + `BackendType.mpvpaper`, `datetime.now(UTC)` strict `Z`
- Atomic assertion: after `save`, `list(state_root.glob("current.json.tmp.*")) == []`; mock `write_text` raises → no partial `current.json` (original preserved if exists)
- Schema mismatch: `ValueError` substring `"unsupported schema_version"` + `"expected 2"`; precedence test for monitors absent
- Absent: `None` without file creation; symlink → `ValueError` not `None`; `KeyError` wrapped
- Null handling: `palette == None` round-trips as `null`; non-`Z` timestamp rejected
- No `history.jsonl` touch: assert `not (state_root / "history.jsonl").exists()` after `save`; `XDG_STATE_HOME=""` fallback tested

### Architecture extraction — what this story must respect

| Decision | Relevance | What to do |
|----------|-----------|------------|
| **AD-1 Hexagonal** | Subprocess/FS I/O only in adapters | Keep JSON FS + `os.replace` + `uuid` in `adapters/json_state_repository.py`; **MUST NOT** import `os`/`json`/`pathlib`/`uuid` into `domain` |
| **AD-2 Layered cache key** | `current.json` `hash` fields are entry hashes (not derivation inputs) | Use `wallpaper.hash`/`palette.hash` from `hashing` lineage; `current.json` stores projection hashes, `meta.json` stores input hashes; `SENTINEL` documents missing input hashes |
| **AD-3 JSON / dict-like store** | Filesystem is authority | `current.json` is index + `cache/` + `current/` symlinks are authority (NFR-3 / AD-6); store is re-derivable except `history.jsonl` (deferred to 3.1); `current.json` deterministic `sort_keys` |
| **AD-4 history must-not-lose** | NOT in this story | Do NOT implement `history.jsonl`; that is `3.1` with `O_APPEND` + `os.fsync` + atomic append; keep this story `current.json` only |
| **AD-5 state_root** | Runtime-owned path | Default `(XDG_STATE_HOME or ~/.local/state)/dotfiles`, `or` handles empty-string, runtime never writes under install spine |
| **AD-6 Swap = symlinks lead** | Recovery reads `current.json` | This story makes crash-recovery possible: Epic 2's `ReconcileDesktopStateUseCase` will read `current.json` written here to re-derive `current/` symlinks idempotently |
| **AD-8 SHA-256** | Every `meta.json` records `hash_algorithm` | `DesktopState` entries carry `hash_algorithm=="sha256"` literal; `current.json` projection reconstructs with `sha256`; adapter asserts `HASH_ALGORITHM=="sha256"` |
| **AD-10 Domain is derivation graph** | `DesktopState` = projection | `DesktopState` frozen dataclass with `monitors: dict[str, MonitorWallpaperConfig]` + `palette/effects/icons: Entry | None`; graph `WallpaperEntry → PaletteEntry/EffectsEntry → IconsEntry` |
| **AD-13 Nested hexagon** | Package layout | `src/runtime/src/runtime/{domain,ports,adapters,application,cli}` + `tests/architecture/test_layering.py` + `tests/unit`/`tests/integration` |
| **AD-14 Domain purity** | Allowlist enforced | Domain imports only allowlist; adapter is the only place with `os`/`json`/`pathlib`/`uuid` |
| **AD-15 Cross-package boundary** | Forbidden set | Do NOT `import provisioning`/`color_scheme_generator`/`wallpaper_effects_generator`/`config_assembler_engine`… — runtime reads install spine as data only; `state_root` never from `settings.toml` |

### Previous story intelligence — what exists now

- **Story 1.9 (itr adapter):** `ItrAdapter(IIconRenderer)` at `adapters/itr_adapter.py` with dual env `ICON_RENDERER__OUTPUT__OUTPUT_DIR` + `ICON_RENDERER__COLOR_SCHEME__PATH`, timeout 60s, 11 unit + 1 integration tests. **Pattern to mirror for FS adapters:** defensive `..`/symlink/`\x00`/length guards, `type(timeout) is int` strict, `null` byte check, `FileExistsError` wrapping, `build_env` allowlist (not needed here — JSON adapter has no subprocess, but `os` usage minimal and `or` XDG handling), `hash_file` via `hashing.py` (reuse `_validate_hex64`), `ruff`/`mypy`/`test_layering` green gate.
- **Story 1.8 (weg adapter):** `WegAdapter(IEffectsGenerator)` at `adapters/weg_adapter.py` with `WALLPAPER__OUTPUT__DIRECTORY`, catalog discovery, 10 unit + 1 integration. **Learnings:** `_validate_output_dir` checks `..`, symlink, case-sensitive, length guard, `FileExistsError` wrapping; `hash_file` wrapped `OSError`; `bool` timeout bypass via `type(x) is int`; `"\x00"` in paths check.
- **Story 1.7 (csg adapter):** `CsgAdapter(IColorSchemeGenerator)` at `adapters/csg_adapter.py` with `COLORSCHEME__OUTPUT__DIRECTORY` + `COLORSCHEME__OUTPUT__OVERWRITE`, 10 unit + 1 integration. **Learnings:** literal double-underscore keys, no `-o` flag, container forwarding via env passthrough, `datetime.now(UTC).isoformat().replace("+00:00","Z")` with strict `Z` check, `HASH_ALGORITHM` guard, `Empty dir hash` sentinel not valid.
- **Story 1.6 (cache populator):** `adapters/cache.py` `populate_via_staging(target, fn)` sibling staging `cache/.staging-<pid>-<uuid>` + `os.rename` + `shutil.rmtree(ignore_errors=True)` + sweep orphans, `hardlink_or_copy`, `cache_entry_path` validation `cache/<layer>/<hash>` 64-hex, `CACHE_LAYERS` frozenset. **Directly reuses** `JsonStateRepository.save` pattern for atomicity (sibling `tmp.<pid>-<rand>` + `os.replace`); also `cache.py` is the caller that will hydrate `DesktopState.hash` → `cache/<layer>/<hash>/` lookups in later stories.
- **Review learnings from 1.7–1.9:**
  - `build_env()` allowlist — not needed for JSON store, but `os.environ.get(...) or fallback` pattern for XDG (C3 fix).
  - Null bytes: check `"\x00" in str(state_root)` early (E4).
  - `hash_file` must be via `hashing.py` — use `_validate_hex64` for wall/source hashes.
  - `shutil.which` pattern not needed (no binary), but `Path.is_symlink()` before `exists()` (E1) and `KeyError→ValueError` wrapping (C2) are critical.

### Project Structure Notes

- **Alignment (AD-13):** `src/runtime/src/runtime/{domain,ports,adapters,application,cli}` + `tests/architecture/test_layering.py` + `tests/unit`/`tests/integration`. This story adds `adapters/json_state_repository.py` (I/O layer) + `tests/unit/test_json_state_repository.py` + `tests/integration/test_json_state_repository_integration.py`.
- **Detected conflicts:** None. `ports/state_repository.py` already exists as minimal ABC (`load_current`/`save`) — matches spec; no update needed. `domain/models.py` already has `DesktopState` with `monitors: dict[str, MonitorWallpaperConfig]` from Story 1.2/1.3 — no migration needed. Projection vs full entry variance is intentional: `current.json` `hash`+`generated_at` vs `DesktopState` full hashes — sentinel `SENTINEL="0"*64` + `artifact_hashes={}` documents hydration deferral, and tests assert projection equality not `==` full equality.
- **Naming:** `adapters/json_state_repository.py` mirrors `adapters/cache.py` + `adapters/csg_adapter.py`; class `JsonStateRepository` implements `IStateRepository`; tests `test_json_state_repository.py` mirrors `test_csg_adapter.py`/`test_weg_adapter.py`/`test_itr_adapter.py`.
- **Tech stack (pinned):** `python>=3.14`, `typer>=0.12`, `cli-output` (via `uv.sources`). Adapter uses stdlib `json` + `os` + `pathlib` + `uuid` + `datetime` + `hashing` only; `pytest>=8.0`, `ruff>=0.15.17`, `mypy>=1.10` (pyproject).

### References

- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md` — AD-1 (hexagonal), AD-3 (JSON store + deterministic `sort_keys`), AD-4 (history must-not-lose deferred to 3.1), AD-5 (state_root `or` empty-string handling), AD-6 (symlinks lead), AD-8 (SHA-256), AD-10 (derivation graph), AD-13 (nested hexagon), AD-14 (domain purity `uuid` allowed only in adapters), AD-15 (cross-package boundary, never `config_assembler_engine`)
- Shared data contract: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md` — `current.json` schema `schema_version 2` (wallpaper/monitors/palette/effects/icons/applied_at) + `history.jsonl` + `meta.json` + deterministic JSON + Swap sequence ownership (Reconcile reads `current.json`)
- Spec: `_bmad-output/specs/spec-dotfiles-runtime-phase2/SPEC.md` — CAP-1/4/5/7, Constraints (hexagonal, filesystem authority, state_root JSON store, SHA-256, swap symlinks), Assumptions (CSG/ITR deterministic)
- Cache model: `_bmad-output/specs/spec-dotfiles-runtime-phase2/cache-model.md` — cache layout (`state_root/cache/<layer>/<hash>`, `state_root/current.json`, `state_root/current/` symlinks, `state_root/history.jsonl`)
- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md` — Epic 1 Story 1.10 ACs (FR-1 minimal IStateRepository, FR-4 state persistence CAP-4, R1 state-first)
- Domain models: `src/runtime/src/runtime/domain/models.py` — `DesktopState`/`WallpaperEntry`/`MonitorWallpaperConfig`/`PaletteEntry`/`EffectsEntry`/`IconsEntry`/`BackendType`/`FitMode` (frozen, slots, `StrEnum`, `__post_init__` mpv guard + field rename disclaimer `imported_at` ↔ `applied_at`)
- Port: `src/runtime/src/runtime/ports/state_repository.py` — `IStateRepository(ABC)` minimal `load_current`/`save` (verify ABC only)
- Hashing helpers: `src/runtime/src/runtime/adapters/hashing.py` — `hash_file`, `canonical_hash_dir`, `palette_entry_hash`/`effects_entry_hash`/`icons_entry_hash`, `HASH_ALGORITHM="sha256"`, `_validate_hex64`, `_is_hex64`
- Cache helper: `src/runtime/src/runtime/adapters/cache.py` — `populate_via_staging` staging sibling `.staging-<pid>-<uuid>` + `os.rename` + atomic write-once (pattern for `JsonStateRepository.save` `tmp.<pid>-<rand>` + `os.replace`)
- Adapters (patterns): `src/runtime/src/runtime/adapters/csg_adapter.py` — `CsgAdapter` `HASH_ALGORITHM` guard + `datetime.now(UTC)` ISO Z strict `Z`; `weg_adapter.py` + `itr_adapter.py` — same defensive patterns (`..`/symlink/`\x00`/length, `type(...) is int`, `KeyError→ValueError`)
- Env allowlist: `src/runtime/src/runtime/adapters/env.py` — `build_env` allowlist (not directly used, but `XDG_STATE_HOME` `or` handling respects it)
- Layering test: `src/runtime/tests/architecture/test_layering.py` — `domain` allowlist `dataclasses, enum, typing, collections, collections.abc, functools, re, __future__`; banned `os/subprocess/shutil/pathlib/io/uuid`; `ports` ABC-only; forbidden cross-package set; 42 checks
- Tests fixtures: `src/runtime/tests/fixtures/wallpaper.png` (74 bytes), `src/runtime/tests/unit/test_hashing.py` + `test_cache.py` reference atomic + deterministic patterns
- Previous story (1.9): `_bmad-output/implementation-artifacts/rt-1-9-itr-adapter-env-overrides.md` — 11 unit tests pattern + `SENTINEL` projection + symlink-before-exists + `KeyError` wrapping learnings
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` — `rt-1-10-minimal-istaterepository: ready-for-dev`

## Dev Agent Record

### Agent Model Used

muse-spark-1.2-contributor-free (opencode/muse-spark-1.2-contributor-free)

### Debug Log References

### Completion Notes List

### File List

### Change Log

