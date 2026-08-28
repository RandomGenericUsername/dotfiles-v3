# Story 1.3: Ports — domain capabilities

Status: ready-for-dev

## Story

As a developer,
I want ABC ports for every runtime capability,
so that adapters can be swapped without touching the core.

## Acceptance Criteria

1. `IStaticWallpaperBackend`, `IVideoWallpaperBackend`, `IWallpaperBackendFactory`, `IColorSchemeGenerator`, `IEffectsGenerator`, `IIconRenderer`, `IDesktopConfigWriter`, `IDesktopReloader`, `IStateRepository` are defined as ABCs (or Protocols) with abstract methods in `runtime.ports` (AC 1)
2. All ports are ABCs — any concrete class in `ports/` fails the layering test (AC 2)
3. `IStaticWallpaperBackend` defines `set_image(path, monitor, fit_mode)`, `set_color(color, monitor)`, `reload()` (AC 3)
4. `IVideoWallpaperBackend` defines `set_video(path, monitor, mpv_options, ipc_socket, auto_pause, auto_stop, layer)`, `set_playlist(paths, monitor, mpv_options)`, `control(monitor, command)` (AC 4)
5. `IWallpaperBackendFactory` defines `create_static(backend_type)`, `create_video(backend_type)`, `auto_detect(source_path) -> backend_type` (AC 5)
6. Domain layer remains pure — ports import only domain + stdlib allowlist (AC 6, AD-14)
7. `uv run --directory src/runtime pytest` passes, including layering test (AC 7)

## Tasks / Subtasks

- [ ] Define `IColorSchemeGenerator` port (AC: 1)
  - [ ] ABC in `runtime.ports.color_scheme_generator`
  - [ ] Abstract method: `generate(wallpaper_hash: str, template_dir: str, output_dir: str) -> PaletteEntry`
  - [ ] Imports: `runtime.domain.models.PaletteEntry` only
- [ ] Define `IEffectsGenerator` port (AC: 1)
  - [ ] ABC in `runtime.ports.effects_generator`
  - [ ] Abstract method: `generate(wallpaper_hash: str, catalog_path: str, output_dir: str) -> EffectsEntry`
  - [ ] Imports: `runtime.domain.models.EffectsEntry` only
- [ ] Define `IIconRenderer` port (AC: 1)
  - [ ] ABC in `runtime.ports.icon_renderer`
  - [ ] Abstract method: `render(palette_hash: str, templates_dir: str, mappings_path: str, output_dir: str) -> IconsEntry`
  - [ ] Imports: `runtime.domain.models.IconsEntry` only
- [ ] Define `IStaticWallpaperBackend` port (AC: 1, 3)
  - [ ] ABC in `runtime.ports.wallpaper_backend`
  - [ ] Abstract methods:
    - `set_image(path: str, monitor: str, fit_mode: str) -> None`
    - `set_color(color: str, monitor: str) -> None`
    - `reload() -> None`
  - [ ] Imports: stdlib only (no domain types needed — raw strings for paths/colors)
- [ ] Define `IVideoWallpaperBackend` port (AC: 1, 4)
  - [ ] ABC in `runtime.ports.wallpaper_backend` (same module as IStatic)
  - [ ] Abstract methods:
    - `set_video(path: str, monitor: str, mpv_options: str | None, ipc_socket: str | None, auto_pause: bool, auto_stop: bool, layer: str) -> None`
    - `set_playlist(paths: list[str], monitor: str, mpv_options: str | None) -> None`
    - `control(monitor: str, command: str) -> None`
  - [ ] Imports: stdlib only
- [ ] Define `IWallpaperBackendFactory` port (AC: 1, 5)
  - [ ] ABC in `runtime.ports.wallpaper_backend_factory`
  - [ ] Abstract methods:
    - `create_static(backend_type: BackendType) -> IStaticWallpaperBackend`
    - `create_video(backend_type: BackendType) -> IVideoWallpaperBackend`
    - `auto_detect(source_path: str) -> BackendType`
  - [ ] Imports: `runtime.domain.models.BackendType`, `runtime.ports.wallpaper_backend`
- [ ] Define `IDesktopConfigWriter` port (AC: 1)
  - [ ] ABC in `runtime.ports.desktop_config_writer`
  - [ ] Abstract method: `write_consumer_symlink(source_path: str, target_path: str) -> None`
  - [ ] Purpose: repoint current/ symlinks to new cache entries
- [ ] Define `IDesktopReloader` port (AC: 1)
  - [ ] ABC in `runtime.ports.desktop_reloader`
  - [ ] Abstract method: `reload() -> bool`  # returns success/failure
  - [ ] Implementors will wrap hyprctl reload, ags restart, etc.
- [ ] Define `IStateRepository` port (AC: 1)
  - [ ] ABC in `runtime.ports.state_repository`
  - [ ] Minimal interface for this story — history methods arrive in Epic 3 (Story 3.1)
  - [ ] Abstract methods:
    - `load_current() -> DesktopState | None`  # None on first run
    - `save(state: DesktopState) -> None`  # atomic write
  - [ ] Imports: `runtime.domain.models.DesktopState` only
- [ ] Update `src/runtime/src/runtime/ports/__init__.py` (AC: 1)
  - [ ] Re-export all port ABCs via explicit imports (not star imports)
  - [ ] `__all__` list:
    ```python
    __all__ = [
        "IColorSchemeGenerator",
        "IEffectsGenerator",
        "IIconRenderer",
        "IStaticWallpaperBackend",
        "IVideoWallpaperBackend",
        "IWallpaperBackendFactory",
        "IDesktopConfigWriter",
        "IDesktopReloader",
        "IStateRepository",
    ]
    ```
- [ ] Verify all ports are importable (AC: 1)
  - [ ] Run `uv run --directory src/runtime python -c "from runtime.ports import *; print(__all__)"`
  - [ ] Confirm all 9 port ABCs are exported
- [ ] Verify layering test passes (AC: 2, 6, 7)
  - [ ] Run `uv run --directory src/runtime pytest`
  - [ ] Confirm ports import only domain + stdlib allowlist
  - [ ] Confirm any concrete class in ports/ fails layering test

## Dev Notes

### Scope boundary — this story is PORTS ONLY

Story 1.3 creates the ABC interfaces. It does **NOT** implement:
- Adapters (csg_runner, weg_runner, itr_runner, json_state_repository, wallpaper backends, etc.)
- Application use cases (ApplyWallpaperUseCase, ReconcileDesktopStateUseCase, etc.)
- CLI commands

Resist the urge to implement adapter logic — adapters arrive in later stories.

### Domain models already defined (Story 1.2)

The following domain types exist in `runtime.domain.models` and are available for type annotations:
- `WallpaperEntry`, `PaletteEntry`, `EffectsEntry`, `IconsEntry` — derivation graph nodes
- `MonitorWallpaperConfig` — per-monitor backend config
- `DesktopState` — projection of current derivation outputs
- `BackendType(StrEnum)` — hyprpaper, swaybg, swww, mpvpaper
- `FitMode(StrEnum)` — cover, contain, fill, tile, center, stretch

### Port naming convention (Architecture Spine)

Ports prefixed `I` (ABCs): `IColorSchemeGenerator`, `IEffectsGenerator`, `IIconRenderer`, `IStaticWallpaperBackend`, `IVideoWallpaperBackend`, `IWallpaperBackendFactory`, `IDesktopConfigWriter`, `IDesktopReloader`, `IStateRepository`

### Port method signatures — exact specification

**IColorSchemeGenerator:**
```python
class IColorSchemeGenerator(ABC):
    @abstractmethod
    def generate(
        self,
        wallpaper_hash: str,
        template_dir: str,
        output_dir: str,
    ) -> PaletteEntry:
        """Generate palette from wallpaper hash + CSG templates.

        Writes colors.yaml, colors.conf, colors.gtk.css to output_dir.
        Returns the PaletteEntry with artifact_hashes computed.
        """
```

**IEffectsGenerator:**
```python
class IEffectsGenerator(ABC):
    @abstractmethod
    def generate(
        self,
        wallpaper_hash: str,
        catalog_path: str,
        output_dir: str,
    ) -> EffectsEntry:
        """Generate effects from wallpaper hash + effects catalog.

        Writes effect PNGs to output_dir.
        Returns the EffectsEntry with artifact_hashes computed.
        """
```

**IIconRenderer:**
```python
class IIconRenderer(ABC):
    @abstractmethod
    def render(
        self,
        palette_hash: str,
        templates_dir: str,
        mappings_path: str,
        output_dir: str,
    ) -> IconsEntry:
        """Render icons from palette + icon templates/mappings.

        Writes SVG icons to output_dir.
        Returns the IconsEntry with artifact_hashes computed.
        """
```

**IStaticWallpaperBackend:**
```python
class IStaticWallpaperBackend(ABC):
    @abstractmethod
    def set_image(self, path: str, monitor: str, fit_mode: str) -> None:
        """Set a static image as wallpaper on the given monitor."""

    @abstractmethod
    def set_color(self, color: str, monitor: str) -> None:
        """Set a solid color as wallpaper on the given monitor."""

    @abstractmethod
    def reload(self) -> None:
        """Reload the wallpaper backend (e.g., hyprctl reload)."""
```

**IVideoWallpaperBackend:**
```python
class IVideoWallpaperBackend(ABC):
    @abstractmethod
    def set_video(
        self,
        path: str,
        monitor: str,
        mpv_options: str | None,
        ipc_socket: str | None,
        auto_pause: bool,
        auto_stop: bool,
        layer: str,
    ) -> None:
        """Set a video as wallpaper on the given monitor."""

    @abstractmethod
    def set_playlist(
        self,
        paths: list[str],
        monitor: str,
        mpv_options: str | None,
    ) -> None:
        """Set a video playlist as wallpaper."""

    @abstractmethod
    def control(self, monitor: str, command: str) -> None:
        """Send a control command (pause, resume, next, etc.)."""
```

**IWallpaperBackendFactory:**
```python
from runtime.domain.models import BackendType

class IWallpaperBackendFactory(ABC):
    @abstractmethod
    def create_static(self, backend_type: BackendType) -> IStaticWallpaperBackend:
        """Create a static wallpaper backend by BackendType enum."""

    @abstractmethod
    def create_video(self, backend_type: BackendType) -> IVideoWallpaperBackend:
        """Create a video wallpaper backend by BackendType enum."""

    @abstractmethod
    def auto_detect(self, source_path: str) -> BackendType:
        """Detect backend type from file extension.

        Returns: BackendType enum (e.g., BackendType.MPVAPER, BackendType.SWWW).
        """
```

**IDesktopConfigWriter:**
```python
class IDesktopConfigWriter(ABC):
    @abstractmethod
    def write_consumer_symlink(self, source_path: str, target_path: str) -> None:
        """Atomically repoint a consumer symlink (tmp + os.replace)."""
```

**IDesktopReloader:**
```python
class IDesktopReloader(ABC):
    @abstractmethod
    def reload(self) -> bool:
        """Reload the desktop consumer. Returns True on success."""
```

**IStateRepository:**
```python
class IStateRepository(ABC):
    @abstractmethod
    def load_current(self) -> DesktopState | None:
        """Load current state. Returns None on first run (no current.json)."""

    @abstractmethod
    def save(self, state: DesktopState) -> None:
        """Atomically persist current state (tmp + os.replace)."""
```

### Port validation contract

Ports define the interface only. Exception semantics are adapter-specific:
- Adapters should document raised exceptions in docstrings
- ABCs do not add input validation (that belongs in adapters)
- A port method failing means the adapter hit an error — the caller (use case) handles it

### Domain purity contract (AD-14)

Ports live in `runtime.ports` and may import from:
- `runtime.domain.*` (domain models for type annotations)
- `abc` (for ABC base class)
- `typing` (for Protocol if used)

Ports must NOT import:
- `os`, `subprocess`, `shutil`, `pathlib` (I/O belongs in adapters)
- `runtime.adapters.*`, `runtime.application.*`, `runtime.cli.*`

### Env-override integration (AD-7)

`IColorSchemeGenerator`, `IEffectsGenerator`, `IIconRenderer` are called by adapters that set env overrides (`COLORSCHEME__OUTPUT__DIRECTORY`, `WALLPAPER__OUTPUT__DIRECTORY`, `ICON_RENDERER__OUTPUT__OUTPUT_DIR`). The port itself is agnostic to output routing — it receives `output_dir` as a parameter and writes there.

### Package layout after this story

```text
src/runtime/src/runtime/ports/
├── __init__.py                    ← explicit imports + __all__ (no star imports)
├── color_scheme_generator.py      ← IColorSchemeGenerator
├── effects_generator.py           ← IEffectsGenerator
├── icon_renderer.py               ← IIconRenderer
├── wallpaper_backend.py           ← IStaticWallpaperBackend, IVideoWallpaperBackend
├── wallpaper_backend_factory.py   ← IWallpaperBackendFactory
├── desktop_config_writer.py       ← IDesktopConfigWriter
├── desktop_reloader.py            ← IDesktopReloader
└── state_repository.py            ← IStateRepository (minimal: load_current/save)
```

### Layering enforcement

The layering test (`tests/architecture/test_layering.py`) already enforces:
- Ports may import from `runtime.domain.*` and `runtime.ports.*`
- Ports must NOT import from `runtime.adapters.*`, `runtime.application.*`, `runtime.cli.*`
- Any concrete class in `ports/` (non-ABC) fails the test

### Previous story intelligence (Story 1.2)

- Domain models: `WallpaperEntry`, `PaletteEntry`, `EffectsEntry`, `IconsEntry`, `MonitorWallpaperConfig`, `DesktopState`, `BackendType`, `FitMode` — all frozen dataclasses in `runtime.domain.models`
- All dataclasses use `@dataclass(frozen=True, slots=True)`
- `artifact_hashes: dict[str, str]` fields are mutable inside frozen dataclasses (intentional)
- Domain imports only stdlib allowlist — no I/O

### Previous story intelligence (Story 1.1)

- Package scaffolded at `src/runtime/src/runtime/{domain,ports,adapters,application,cli}`
- Layering test at `tests/architecture/test_layering.py` enforces domain purity
- `cli-output` is the ONLY cross-package dependency
- Python version: `>=3.14`
- All 30 tests pass after Story 1.2

### Architecture compliance checklist

- [ ] **AD-1 (hexagonal):** ports layer sits between domain and adapters
- [ ] **AD-14 (domain purity):** ports import only domain + stdlib allowlist
- [ ] **AD-15 (cross-package boundary):** ports do not import provisioning or other packages
- [ ] **AD-18 (wallpaper backend abstraction):** IStaticWallpaperBackend + IVideoWallpaperBackend + IWallpaperBackendFactory defined

### References

- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md` — AD-1, AD-14, AD-18
- Shared data contract: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md`
- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md` — Story 1.3 ACs
- Previous stories: `rt-1-1-nested-hexagon-scaffold.md`, `rt-1-2-domain-model-derivation-graph.md`
- Domain models: `src/runtime/src/runtime/domain/models.py`
- Layering test: `src/runtime/tests/architecture/test_layering.py`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

### Review Findings
