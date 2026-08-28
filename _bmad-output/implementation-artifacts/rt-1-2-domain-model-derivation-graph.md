---
baseline_commit: 128542078ff198c03362f61110ab2126effc9eb9
---

# Story 1.2: Domain model — derivation graph

Status: review

## Story

As a developer,
I want the derivation-graph domain entities,
so that the core has pure, zero-I/O representations of wallpapers, palettes, effects, and icons keyed by their derivation inputs.

## Acceptance Criteria

1. `WallpaperEntry`, `PaletteEntry`, `EffectsEntry`, `IconsEntry`, `MonitorWallpaperConfig` are defined as frozen dataclasses in `runtime.domain` (AC 1, AD-10)
2. Each carries its input hashes and `artifact_hashes` per the shared-data-contract schemas (AC 2)
3. `MonitorWallpaperConfig` holds per-monitor backend, source_hash, fit_mode, mpv_options, ipc_socket (AC 3)
4. The domain imports only the stdlib allowlist — no `os`/`subprocess`/`shutil`/`pathlib` (AC 4, AD-14)
5. `uv run --directory src/runtime pytest` passes, including the layering test (AC 5)

## Tasks / Subtasks

- [x] Create `src/runtime/src/runtime/domain/models.py` (AC: 1, 2, 3)
  - [x] Import `dataclasses` (frozen=True, slots=True), `enum.StrEnum`, `typing` only
  - [x] Use `@dataclass(frozen=True, slots=True)` for all dataclasses (Python 3.14+)
  - [x] Note: `dict[str, str]` fields (`artifact_hashes`) are mutable inside frozen dataclasses — this is intentional. The dict is a content-addressed hash map populated once at construction; the frozen constraint prevents reassignment of the field, not mutation of the dict contents.
  - [x] Define `WallpaperEntry` frozen dataclass
    - [x] `hash_algorithm: str` — always `"sha256"` (required by meta.json)
    - [x] `kind: str` — always `"wallpaper"` (required by meta.json)
    - [x] `content_hash: str` — SHA-256 hex of the wallpaper file bytes
    - [x] `source_path: str` — absolute path or empty string
    - [x] `imported_at: str` — ISO-8601 UTC timestamp
  - [x] Define `PaletteEntry` frozen dataclass
    - [x] `hash_algorithm: str` — always `"sha256"`
    - [x] `kind: str` — always `"palette"`
    - [x] `entry_hash: str` — SHA-256 hex of (wallpaper_hash ‖ template_set_hash)
    - [x] `source_wallpaper_hash: str` — reference to WallpaperEntry.content_hash
    - [x] `input_template_hash: str` — canonicalized hash of CSG templates dir
    - [x] `artifact_hashes: dict[str, str]` — fixed keys: `colors.yaml`, `colors.conf`, `colors.gtk.css` → SHA-256
    - [x] `generated_at: str` — ISO-8601 UTC timestamp
  - [x] Define `EffectsEntry` frozen dataclass
    - [x] `hash_algorithm: str` — always `"sha256"`
    - [x] `kind: str` — always `"effects"`
    - [x] `entry_hash: str` — SHA-256 hex of (wallpaper_hash ‖ catalog_hash)
    - [x] `source_wallpaper_hash: str` — reference to WallpaperEntry.content_hash
    - [x] `input_catalog_hash: str` — canonicalized hash of effects catalog
    - [x] `artifact_hashes: dict[str, str]` — keys are `<filename>.png` → SHA-256
    - [x] `generated_at: str` — ISO-8601 UTC timestamp
  - [x] Define `IconsEntry` frozen dataclass
    - [x] `hash_algorithm: str` — always `"sha256"`
    - [x] `kind: str` — always `"icons"`
    - [x] `entry_hash: str` — SHA-256 hex of (palette_hash ‖ templates_hash ‖ mappings_hash)
    - [x] `source_palette_hash: str` — reference to PaletteEntry.entry_hash
    - [x] `input_templates_hash: str` — canonicalized hash of icon templates dir
    - [x] `input_mappings_hash: str` — canonicalized hash of icon mappings
    - [x] `artifact_hashes: dict[str, str]` — keys are `<name>.svg` → SHA-256
    - [x] `generated_at: str` — ISO-8601 UTC timestamp
  - [x] Define `MonitorWallpaperConfig` frozen dataclass
    - [x] `backend: BackendType` — StrEnum: hyprpaper, swaybg, swww, mpvpaper
    - [x] `source_hash: str` — SHA-256 hex of the wallpaper content
    - [x] `fit_mode: FitMode` — StrEnum: cover, contain, fill, tile, center, stretch (default cover)
    - [x] `mpv_options: str | None` — mpv passthrough options string (only for mpvpaper)
    - [x] `ipc_socket: str | None` — absolute path to mpv IPC socket (only for mpvpaper)
  - [x] Define `DesktopState` frozen dataclass (projection of current derivation outputs)
    - [x] `schema_version: int` — always 2
    - [x] `wallpaper: WallpaperEntry`
    - [x] `monitors: dict[str, MonitorWallpaperConfig]` — keyed by monitor name (e.g., "DP-1")
    - [x] `palette: PaletteEntry | None` — None only when never derived
    - [x] `effects: EffectsEntry | None` — None only when never derived
    - [x] `icons: IconsEntry | None` — None only when never derived
    - [x] `applied_at: str` — ISO-8601 UTC timestamp
  - [x] Define `BackendType(StrEnum)` — hyprpaper, swaybg, swww, mpvpaper
  - [x] Define `FitMode(StrEnum)` — cover, contain, fill, tile, center, stretch
- [x] Update `src/runtime/src/runtime/domain/__init__.py` (AC: 1)
  - [x] Re-export all domain models via `__all__` list
  - [x] `__all__` should include: `WallpaperEntry`, `PaletteEntry`, `EffectsEntry`, `IconsEntry`, `MonitorWallpaperConfig`, `DesktopState`, `BackendType`, `FitMode`
- [x] Verify layering test passes (AC: 4, 5)
  - [x] Run `uv run --directory src/runtime pytest`
  - [x] Confirm domain files use only stdlib allowlist
  - [x] Confirm no Path FS method calls in domain

## Dev Notes

### Scope boundary — this story is domain models ONLY

Story 1.2 creates the pure data representations. It does **NOT** implement:
- Ports (Story 1.3 — IStateRepository, IColorSchemeGenerator, etc.)
- Adapters (later stories — csg_runner, json_state_repository, etc.)
- Application use cases (later stories — ApplyWallpaperUseCase, etc.)

### Domain purity contract (AD-14)

The domain layer is PURE — zero I/O. Allowed imports:

```python
_DOMAIN_ALLOWED_STDLIB = frozenset({
    "__future__",
    "dataclasses",
    "enum",
    "typing",
    "collections",
    "collections.abc",
    "functools",
    "re",
})
```

Banned imports: `os`, `subprocess`, `shutil`, `pathlib`, `io`, `select`, `selectors`, `socket`

Banned Path FS methods: `exists`, `read_text`, `read_bytes`, `write_text`, `write_bytes`, `glob`, `rglob`, `iterdir`, `mkdir`, `rmdir`, `unlink`, `chmod`, `chown`, `stat`, `lstat`, `touch`, `resolve`

Also banned: `open()` builtin calls

### Shared data contract schemas (must match exactly)

**current.json** — `DesktopState` maps to this:
```json
{
  "schema_version": 2,
  "wallpaper": { "hash": "<sha256-hex>", "source_path": "<abs-or-empty>", "applied_at": "<ISO-8601-UTC>" },
  "monitors": {
    "<monitor-name>": {
      "backend": "hyprpaper|swaybg|swww|mpvpaper",
      "source_hash": "<sha256-hex>",
      "fit_mode": "cover|contain|fill|tile|center|stretch",
      "mpv_options": "<string-or-null>",
      "ipc_socket": "<abs-path-or-null>"
    }
  },
  "palette":   { "hash": "<sha256-hex>", "generated_at": "<ISO-8601-UTC>" },
  "effects":   { "hash": "<sha256-hex>", "generated_at": "<ISO-8601-UTC>" },
  "icons":     { "hash": "<sha256-hex>", "generated_at": "<ISO-8601-UTC>" },
  "applied_at": "<ISO-8601-UTC>"
}
```

**meta.json per cache layer** — each entry class maps to this:
- `cache/wallpapers/<hash>/meta.json`: `hash_algorithm`, `kind: "wallpaper"`, `content_hash`, `source_path`, `imported_at`
- `cache/palettes/<hash>/meta.json`: `hash_algorithm`, `kind: "palette"`, `entry_hash`, `source_wallpaper_hash`, `input_template_hash`, `artifact_hashes`, `generated_at`
- `cache/effects/<hash>/meta.json`: `hash_algorithm`, `kind: "effects"`, `entry_hash`, `source_wallpaper_hash`, `input_catalog_hash`, `artifact_hashes`, `generated_at`
- `cache/icons/<hash>/meta.json`: `hash_algorithm`, `kind: "icons"`, `entry_hash`, `source_palette_hash`, `input_templates_hash`, `input_mappings_hash`, `artifact_hashes`, `generated_at`

### Derivation graph (AD-10)

```
WallpaperEntry → PaletteEntry + EffectsEntry
PaletteEntry → IconsEntry
```

Each node knows its input hashes and artifact_hashes. `MonitorWallpaperConfig` holds per-monitor backend selection and parameters. `DesktopState` = projection of the current derivation outputs (the `current.json` manifest).

### Naming conventions

- Ports prefixed `I` (ABCs): `IStateRepository`, `IColorSchemeGenerator`, etc.
- Domain entities: frozen dataclasses, no prefix
- Enums: `BackendType`, `FitMode` — use `StrEnum` (Python 3.11+, available in >=3.14)

### Serialization notes — field-name divergences

The domain model fields do NOT always match the on-disk key names. Adapters handle the mapping:

| Domain field | On-disk location | On-disk key | Notes |
|---|---|---|---|
| `WallpaperEntry.content_hash` | `current.json` → `wallpaper.hash` | `hash` | current.json uses short name |
| `WallpaperEntry.content_hash` | `cache/wallpapers/<hash>/meta.json` | `content_hash` | meta.json uses full name |
| `WallpaperEntry.imported_at` | `cache/wallpapers/<hash>/meta.json` | `imported_at` | matches |
| `PaletteEntry.entry_hash` | `current.json` → `palette.hash` | `hash` | current.json uses short name |
| `PaletteEntry.entry_hash` | `cache/palettes/<hash>/meta.json` | `entry_hash` | meta.json uses full name |
| `EffectsEntry.entry_hash` | `current.json` → `effects.hash` | `hash` | current.json uses short name |
| `IconsEntry.entry_hash` | `current.json` → `icons.hash` | `hash` | current.json uses short name |
| `DesktopState.wallpaper` | `current.json` → `wallpaper` | nested object | DesktopState wraps WallpaperEntry |
| `DesktopState.monitors` | `current.json` → `monitors` | nested object | matches |
| `hash_algorithm` (all entries) | `cache/*/meta.json` | `hash_algorithm` | always `"sha256"` (AD-8) |
| `kind` (all entries) | `cache/*/meta.json` | `kind` | literal: `"wallpaper"`, `"palette"`, etc. |

The JSON adapter (in adapters layer, not this story) performs these mappings. The domain model is the source of truth; the adapter translates to on-disk shapes.

### Expected file structure after this story

```text
src/runtime/src/runtime/domain/
├── __init__.py          ← re-exports all models via __all__
└── models.py            ← WallpaperEntry, PaletteEntry, EffectsEntry, IconsEntry,
                           MonitorWallpaperConfig, DesktopState, BackendType, FitMode
```

### Previous story intelligence (Story 1.1)

- Package scaffolded at `src/runtime/src/runtime/{domain,ports,adapters,application,cli}`
- Layering test at `tests/architecture/test_layering.py` enforces domain purity
- Domain `__init__.py` is currently empty — this story fills it
- `cli-output` is the ONLY cross-package dependency (via `uv.sources`)
- Python version: `>=3.14`
- All 29 tests pass on the scaffold

### References

- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md` — AD-10, AD-14
- Shared data contract: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md`
- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md` — Story 1.2 ACs
- Previous story: `_bmad-output/implementation-artifacts/rt-1-1-nested-hexagon-scaffold.md`
- Layering test: `src/runtime/tests/architecture/test_layering.py`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

- Created `src/runtime/src/runtime/domain/models.py` with 8 frozen dataclasses/enums: `WallpaperEntry`, `PaletteEntry`, `EffectsEntry`, `IconsEntry`, `MonitorWallpaperConfig`, `DesktopState`, `BackendType`, `FitMode`
- All dataclasses use `@dataclass(frozen=True, slots=True)` as required
- `artifact_hashes: dict[str, str]` fields are mutable inside frozen dataclasses (intentional — dict populated once at construction, frozen prevents reassignment)
- Domain imports only stdlib allowlist (`dataclasses`, `enum`, `typing`) — no `os`/`subprocess`/`shutil`/`pathlib`
- Updated `__init__.py` with `__all__` re-exports for all 8 domain types
- All 30 tests pass including layering enforcement tests
- Layering test confirms domain purity: stdlib-only imports, no Path FS methods, no cross-layer violations

### File List

- `src/runtime/src/runtime/domain/models.py` (new)
- `src/runtime/src/runtime/domain/__init__.py` (modified)
