# Architecture Plan: color-scheme-generator v3

## Hexagonal architecture redesign of the color scheme generation CLI, migrating v2's `layered-settings` + `container-manager` + `transparent-orchestrator` stack to v3's `config-assembler-engine` + `oci-runtime` stack, using the migrated WEG as the reference template.

---

## 0. Resolved decisions

| # | Decision |
|---|---|
| D1 | Unify v2 `color-scheme-core` + `color-scheme-orchestrator` + `color-scheme-templates` into a single package `color-scheme-generator` with one `csg` CLI and a global `--runtime local\|container` flag |
| D2 | One OCI image per backend (`color-scheme-pywal`, `color-scheme-wallust`, `color-scheme-custom`) built on a shared `Dockerfile.base` — preserves v2's dependency-isolation rationale |
| D3 | `show` is a distinct command (display-only; re-extracts the palette, writes no files) — mirrors v2 UX |
| D4 | Templates directory resolved via `config-assembler-engine`'s `CompositePathResolver` only (no parser/schema — `.j2` files are content, not config) |
| D5 | Heavy deps (pillow, numpy, scikit-learn) gated under `[project.optional-dependencies] custom`; optional `pywal` extra for the `wal` lib |
| D6 | Domain uses frozen dataclasses; Pydantic lives only in `adapters/schemas/` as boundary DTO (matches WEG) |
| D7 | CLI surface: `generate`, `show`, `install`, `uninstall`, `info`, `dump-config`, `dump-templates`, `list-backends`, `version` |
| D8 | Ephemeral in-container `/tmp` cache — no `~/.cache` host mount (each container run re-extracts) |
| D9 | `Dockerfile.base` = `python:3.14-slim`; per-backend extensions on slim (drop v2's `Dockerfile.custom.alpine-SLOW`) |
| D10 | **No `auto` backend value** — `Backend` enum is `{CUSTOM, PYWAL, WALLUST}` only; backend is always explicit (CLI flag, env, or settings.toml default). No host-side auto-detection loop. If the configured backend is not available, raise `BackendNotAvailableError` with an install hint |
| D11 | **`--param key=value` replaces dedicated `--saturation` flag** (WEG `--param` pattern). Per-backend parameter definitions live in a `backends.yaml` catalog file resolved via config-assembler-engine full pipeline (parallel to WEG `effects.yaml`). The CLI parses `--param`, coerces via `PydanticTypeCoercer`, resolves via `ParameterResolutionService`, and forwards `--param` to the inner container command in container mode |
| D12 | **Hidden display flags dropped** — `--display-image-path` / `--display-output-dir` are v2-only artefacts of `transparent-orchestrator`'s proxy-hook pattern. v3's host-side orchestration + `OutputPort` rendering makes them redundant |

---

## 1. Domain Models (pure, frozen dataclasses, zero I/O)

| Model | Purpose |
|-------|---------|
| `Backend` enum | `CUSTOM` / `PYWAL` / `WALLUST`; `image_suffix` property → `"custom"`, `"pywal"`, `"wallust"`. **No `AUTO` member** (D10) |
| `ColorAlgorithm` enum | Per-backend algorithm selectors (KMEANS / THIEF / SOLARIZED / etc.) — informational; actual valid values are enforced by `BackendParameterDefinition.choices` |
| `ColorFormat` enum | JSON / SH / CSS / GTK_CSS / YAML / RASI / SCSS / SEQUENCES — output file formats the user can request via `-f` |
| `RuntimeMode` enum | LOCAL / CONTAINER |
| `ContainerEngine` enum | DOCKER / PODMAN |
| `OutputFormat` enum | JSON / RICH / PLAIN (default: JSON) — CLI status rendering format |
| `Verbosity` enum | QUIET / NORMAL / VERBOSE / DEBUG |
| `Color` | `hex` (`^#[0-9a-fA-F]{6}$`), `rgb` tuple, optional `hsl`; pure `adjust_saturation(factor)` via `colorsys` |
| `ColorScheme` | background/foreground/cursor (`Color`), 16-tuple `colors`, `source_image: Path`, `backend: Backend`, `generated_at: datetime` |
| `BackendParameterDefinition` | `key: str`, `description: str`, `param_type: str` (`"float"`, `"int"`, `"str"`), `default: Any`, `min: float \| None`, `max: float \| None`, `choices: tuple[str] \| None`, `required: bool` — mirror of WEG `ParameterDefinition`, loaded from YAML catalog via `BackendCatalogLoaderPort` (D11) |
| `BackendDefinition` | `name: Backend`, `description: str`, `parameters: tuple[BackendParameterDefinition, ...]` |
| `GeneratorConfig` | `backend: Backend`, `params: dict[str, Any]` (resolved parameter overrides, post-coercion), `formats: tuple[ColorFormat]`, `output_dir: Path` |
| `GenerationRequest` | `image_path: Path`, `config: GeneratorConfig` |
| `GenerationResult` | `success: bool`, `color_scheme: ColorScheme`, `output_files: tuple[Path]`, `backend: Backend`, `stderr`, `return_code`, `duration` |
| `BackendInfo` | `name: Backend`, `host_available: bool`, `image_present: bool`, `image_name: str` |
| `AppSettings` | version + sub-settings |
| `OutputSettings` | `verbosity`, `directory` |
| `GenerationSettings` | `backend: Backend`, `default_formats: tuple[ColorFormat]` — **no `saturation` field** (moved to per-backend `BackendParameterDefinition` per D11) |
| `TemplateSettings` | `directory: Path \| None` — when `None`, `TemplateDirResolver` resolves via env/XDG/defaults |
| `RuntimeSettings` | `mode: RuntimeMode` — WHERE to extract |
| `ContainerSettings` | `engine: ContainerEngine`, `image_tag: str`, `image_registry: str \| None` — WHICH runtime |
| `BACKEND_DEFINITIONS` | Resolved catalog: `dict[Backend, BackendDefinition]` holding the per-backend `BackendParameterDefinition` tuples. Loaded from `backends.yaml` via `BackendCatalogLoaderPort` at startup. Parallel to WEG's `effects.yaml` (D11) |

> **`RuntimeSettings.mode` vs `ContainerSettings.engine` orthogonality** (WEG ADR-006) preserved.

---

## 2. Domain Services (pure logic, static / stateless, zero I/O)

| Service | Responsibility |
|---------|----------------|
| `ColorAdjustmentService` | `adjust_saturation(color, factor)` via `colorsys.rgb_to_hls`; clamp to 0–255. Pure function replacing v2 `Color.adjust_saturation` method |
| `PaletteNormalizationService` | Pad/truncate extracted cluster colors to exactly 16; sort by brightness (`sum(rgb)`). Replaces v2 inline KMeans-sorting |
| `HexValidationService` | `canonicalize(value: str) -> str`, `validate(value: str) -> bool` enforcing `^#[0-9a-fA-F]{6}$`. Domain-side; the Pydantic schema calls it |
| `ParameterResolutionService` | **Mirror of WEG `domain/services.py:38-58`**. `resolve(definition, overrides) -> Any`: returns override if `definition.key in overrides`, else `definition.default`, else raises `ConfigResolutionError` if `definition.required`. `resolve_all(parameters, overrides) -> dict[str, Any]` |

---

## 3. Error Hierarchy

```
ColorSchemeError (base)
+-- InvalidImageError (image_path, reason)
+-- ColorExtractionError (backend, message, stderr)
+-- BackendNotAvailableError (backend, hint)
+-- TemplateRenderError (template_name, reason)
+-- TemplateNotFoundError (template_name, searched_paths)
+-- OutputWriteError (output_path, reason)
+-- ConfigResolutionError
+-- ContainerImageNotFoundError (image, backend)
+-- ContainerRuntimeUnavailableError (runtime)
+-- ImagePullAccessError (image, registry)
+-- PaletteGenerationError (backend, message)
```

---

## 4. Ports (Protocol / ABC interfaces)

| Port | Methods | Direction |
|------|---------|-----------|
| `PaletteGeneratorPort` | `generate(image_path: Path, config: GeneratorConfig) -> ColorScheme`, `is_available() -> bool` | Core outbound |
| `ColorSchemeProcessorPort` | `process_generate(request: GenerationRequest, settings: AppSettings) -> GenerationResult`, `process_show(request: GenerationRequest, settings: AppSettings) -> GenerationResult` | Core |
| `ConfigResolverPort` | `resolve(explicit_path=None) -> AppSettings`, `get_resolved_path() -> Path \| None`, `get_applied_overrides() -> list[AppliedOverride]` | Inbound |
| `TemplateRendererPort` | `render(template_name: str, color_scheme: ColorScheme, output_path: Path) -> Path`, `list_templates() -> tuple[str]` | Outbound |
| `TemplateDirResolverPort` | `resolve(explicit_dir: str \| None = None) -> Path` | Inbound (sub-port used by `JinjaTemplateRenderer`) |
| `OutputPort` | `process_result(result)`, `palette_display(scheme)`, `backends_list(backends)`, `templates_list(names)`, `config_info(settings, sources)`, `dump_config(toml_str)`, `error(exc)`, `message(msg)` — takes **domain objects** | Outbound |
| `SettingsSerializerPort` | `serialize(settings: AppSettings) -> str` | Outbound |
| `VersionProviderPort` | `get_version() -> str` | Outbound |
| `BackendCatalogLoaderPort` | `load() -> dict[Backend, BackendDefinition]` | Inbound |

> `OutputPort` follows WEG ADR-007: takes domain objects, each adapter (JSON/Rich/Plain) renders differently; JSON is default for LLM-friendliness.

> `BackendCatalogLoaderPort` wraps config-assembler-engine's `AssembleConfiguration` for the `backends.yaml` pipeline. It resolves the catalog file, parses via `YamlConfigParser`, validates via `BackendsCatalogSchema` (Pydantic), and converts the validated schema to domain `BackendDefinition` objects — parallel to how `AssembledConfigResolver` wraps the `settings.toml` pipeline.

---

## 5. Adapters

| Adapter | Implements | Key Behavior |
|---------|------------|-------------|
| `AssembledConfigResolver` | `ConfigResolverPort` | `config-assembler-engine` + `TomlConfigParser` + strategy chain to resolve `settings.toml`. OverrideRules for all scalar fields. Converts Pydantic `CoreSettingsSchema` → domain `AppSettings` via `_schema_to_domain`. Returns resolved path + applied overrides |
| `YamlBackendCatalogLoader` | `BackendCatalogLoaderPort` | Wraps `AssembleConfiguration` for `backends.yaml`: `YamlConfigParser` + `BackendsCatalogSchema` (Pydantic). Same 5-strategy resolution chain as settings (CLI path > ENV > traversal > XDG > default). No OverrideRules — catalog content is file-source only. Converts validated schema → `dict[Backend, BackendDefinition]` at composition time |
| `TemplateDirResolver` | `TemplateDirResolverPort` | `config-assembler-engine`'s **`CompositePathResolver` only** (no Parser / Validator / Coercer — `.j2` files are content, not config). Uses engine's built-in `CliDirStrategy`, `EnvDirStrategy`, `XdgDirStrategy`, `DefaultDirStrategy` — no custom strategy classes. Order: explicit path → env `COLORSCHEME_TEMPLATES_TEMPLATES_DIR` → XDG `~/.config/color-scheme/templates` → package `defaults/templates`. Returns a directory `Path` (ADR-004) |
| `JinjaTemplateRenderer` | `TemplateRendererPort` | Jinja2 `Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)`. Loads `.j2` files from the `TemplateDirResolverPort`-resolved directory. Renders each requested format, writes to `output_dir/<filename>`. Special binary post-processing for the `sequences` format (`]` → `\x1b]`, `\` → `\x1b\\`) |
| `LocalProcessor` | `ColorSchemeProcessorPort` | Looks up the active `Backend` from `GeneratorConfig.backend` in the injected `BackendRegistry` (`dict[Backend, PaletteGeneratorPort]`). Calls `PaletteGeneratorPort.generate(image, config)` → `ColorScheme`. For `generate`: iterates `GeneratorConfig.formats`, calls `JinjaTemplateRenderer.render` for each, returns `GenerationResult`. For `show`: returns the `ColorScheme` without writing files. If the backend's `is_available()` returns False, raises `BackendNotAvailableError` |
| `ContainerProcessor` | `ColorSchemeProcessorPort` | Serialize resolved `AppSettings` as-resolved (no rewrite — the inner CLI's `--runtime local` flag overrides via OverrideRule, preventing recursion). Map `Backend` → image `color-scheme-<backend>:<tag>` (with optional registry prefix). Pre-flight `engine.images.exists()`. Build 4 BIND mounts (`/input`, `/output`, `/csg-config/settings.toml`, `/templates`). `RunConfig.command=("generate", "/input/<basename>", "-o", "/output", "--backend", "<backend>", "--config", "/csg-config/settings.toml", "--templates", "/templates", "--runtime", "local", "--no-summary")` and **forwards `--param key=value` for each resolved parameter override** (WEG `container_processor.py:157-159` pattern). Run via `engine.containers.run()`. Cleanup temp TOML in `finally` (ADR-003) |
| `DryRunProcessor` | `ColorSchemeProcessorPort` | Validates: input exists, backend available (local) or engine+image available (container), output dir writable, templates dir resolvable, **all `--param` overrides coerce cleanly against `BACKEND_DEFINITIONS[backend].parameters`**. Renders resolved command via `OutputPort` without executing |
| `Backends.CustomGenerator` | `PaletteGeneratorPort` | Lazy-imports PIL + scikit-learn; raises `BackendNotAvailableError("custom", hint="pip install color-scheme-generator[custom]")` if the import fails. KMeans extraction with `n_clusters` and `algorithm` params from `GeneratorConfig.params`. Applies `ColorAdjustmentService.adjust_saturation` to all colors using the `saturation` param |
| `Backends.PywalGenerator` | `PaletteGeneratorPort` | `is_available()` returns `shutil.which("wal") is not None`. Shells out to `wal -i <image> -n -s -t -e --backend <algorithm>` (using `algorithm` param), parses `~/.cache/wal/colors.json`. Applies `saturation` param to the palette |
| `Backends.WallustGenerator` | `PaletteGeneratorPort` | `is_available()` returns `shutil.which("wallust") is not None`. Shells out to `wallust run <image> --backend <type> -s -T -q` (using `algorithm` param), reads cache. Applies `saturation` param |
| `JsonOutput` / `RichOutput` / `PlainOutput` | `OutputPort` | Per WEG: status JSON by default (`{"success": ...}`, `{"error": {"type":..., "message":...}}`), Rich for humans, Plain for pipes |
| `TomlSettingsSerializer` | `SettingsSerializerPort` | `AppSettings` → TOML string (use `tomli-w` or hand-rolled like WEG v3). Used by `dump-config` and `ContainerProcessor` (temp TOML) |
| `TemplatesSerializer` | `dump-templates` helper | Copies bundled `defaults/templates/*.j2` into `$XDG_CONFIG_HOME/color-scheme/templates/` (mkdir parents). `--overwrite` required to replace existing |
| `ImportlibVersionProvider` | `VersionProviderPort` | `importlib.metadata.version("color-scheme-generator")` with `__version__` fallback |
| `ErrorMapping` | free fn `map_oci_error` | `oci_runtime.domain.exceptions.*` → domain exceptions (per WEG `adapters/error_mapping.py`) |

`BackendRegistry` (wiring helper in `factory.py`, not a port): `dict[Backend, PaletteGeneratorPort]` built at composition time. **No auto-detect iteration** (D10) — the active backend comes from `settings.generation.backend` and the registry is only a lookup table.

---

## 6. Application Use Cases

Collapsed into `cli/*.py` functions + `factory.py` wiring (matches the **actual** WEG layout — not its plan's `application/` package).

| Use Case | Flow |
|----------|------|
| `GenerateColors` | Resolve config → resolve `BackendCatalog` (i.e. look up `BACKEND_DEFINITIONS[settings.generation.backend]`) → **parse `--param` via `_parse_params` → coerce each via `PydanticTypeCoercer` against the backend's `BackendParameterDefinition.param_type` → `ParameterResolutionService.resolve_all` to get final `GeneratorConfig.params`** → build `GenerationRequest` → select `ColorSchemeProcessorPort` by `runtime.mode` + `--dry-run` → `processor.process_generate` → `OutputPort.process_result` |
| `ShowColors` | Same plumbing as `GenerateColors` (incl. `--param` parsing + coercion + resolution) but calls `processor.process_show` → `OutputPort.palette_display(result.color_scheme)` |
| `InstallBackends` (loops over `--backend`, default: all three) | Resolve config → locate `Dockerfile.<backend>` + `Dockerfile.base` via `importlib.resources` → `engine.images.build(BuildContext(build_file_path=..., context_path=repo_root, build_contexts=...), image_name)` per backend. Optional `--dump-config` / `--dump-templates` post-build to XDG |
| `UninstallBackends` | Resolve config → loop `engine.images.remove(image, force)` per selected backend. `--yes` skips confirmation |
| `ListBackends` | For each `Backend`: `host_available = registry[backend].is_available()`; if `runtime.mode == CONTAINER`: `image_present = engine.images.exists(image_name)`. Build `BackendInfo` tuple → `OutputPort.backends_list` |
| `DumpConfig` | `ConfigResolverPort.resolve` → `SettingsSerializerPort.serialize` → file or stdout |
| `DumpTemplates` | Resolve bundled templates dir → copy `.j2` files to user dir (or emit listing). `--overwrite` semantics |
| `ShowInfo` | Resolve config + templates → `OutputPort.config_info(settings, template_names, backend_infos, applied_overrides)` with resolved paths |
| `Version` | `VersionProviderPort.get_version` |

---

## 7. Config System (config-assembler-engine)

### Design Principle: Single-File Resolution, No Merging (ADR-001)

Mirrors WEG §7 exactly. Resolution order: **CLI explicit path > ENV path > XDG > Directory traversal > Package default**.

### Settings (TOML) — full pipeline

```
Prefix: COLORSCHEME
Default file: package-bundled defaults/settings.toml
Strategies (all with `kind=ResourceKind.FILE`):
  CliPathStrategy(kind=ResourceKind.FILE)
  EnvPathStrategy(var="CONFIG_FILE_PATH", kind=ResourceKind.FILE)      # COLORSCHEME_CONFIG_FILE_PATH
  XdgStrategy(xdg_subdir="color-scheme", filename="settings.toml", kind=ResourceKind.FILE)
  DirectoryTraversalStrategy(filename="settings.toml", max_levels=3, kind=ResourceKind.FILE)
  DefaultFileStrategy(path=<package defaults/settings.toml>, kind=ResourceKind.FILE)
Parser: TomlConfigParser
Schema: CoreSettingsSchema (Pydantic)
  @field_validator enforces runtime.mode ∈ {local, container}
  @field_validator enforces container.engine ∈ {docker, podman}
  @field_validator strips trailing slash on container.image_registry
  @field_validator enforces generation.backend ∈ {custom, pywal, wallust}  # NO "auto" (D10)
```

OverrideRules (each `{ENV, CLI}`):
- `output.verbosity`, `output.directory`
- `generation.backend`, `generation.default_formats`
- `templates.directory`
- `runtime.mode`
- `container.engine`, `container.image_tag`, `container.image_registry`

> **Note** — no `generation.saturation` OverrideRule. Saturation became a per-backend parameter (D11) and is overridden at the CLI via `--param saturation=...`, NOT via config-assembler-engine's `cli_overrides`. It bypasses the assembler and goes through `ParameterResolutionService` instead, exactly mirroring how WEG's `--param` bypasses `AssembleConfiguration` and goes through its own `ParameterResolutionService`.

ENV var examples:
```
COLORSCHEME__RUNTIME__MODE=container
COLORSCHEME__CONTAINER__ENGINE=podman
COLORSCHEME__GENERATION__BACKEND=wallust
COLORSCHEME_CONFIG_FILE_PATH=/custom/path.toml
```

### Templates Directory — path-resolver only (ADR-004)

```
Prefix: COLORSCHEME_TEMPLATES
Default dir: package-bundled defaults/templates/
Strategies (engine's built-in directory subclasses):
  CliDirStrategy()                                    # --templates explicit path
  EnvDirStrategy(var="TEMPLATES_DIR")                 # COLORSCHEME_TEMPLATES_TEMPLATES_DIR
  XdgDirStrategy(xdg_subdir="color-scheme", dirname="templates")
  DefaultDirStrategy(path=<package defaults/templates>)
Resolver: CompositePathResolver   (NO AssembleConfiguration, NO parser, NO schema)
Returns: directory Path
```

ENV var: `COLORSCHEME_TEMPLATES_TEMPLATES_DIR=/custom/templates`

### Backend parameter definitions — YAML catalog file (D11)

Backend parameter definitions are declared in a `backends.yaml` catalog file resolved via config-assembler-engine's full pipeline (parallel to WEG `effects.yaml`). This makes them user-editable and discoverable, consistent with the architecture decision that backend catalog content should be resolvable, introspectable, and overridable through the same deterministic resolution machinery as settings.

```yaml
# defaults/backends.yaml
custom:
  description: "PIL + scikit-learn KMeans"
  parameters:
    - key: saturation
      param_type: float
      default: 1.0
      min: 0.0
      max: 2.0
      description: "Saturation adjustment factor"
    - key: n_clusters
      param_type: int
      default: 16
      min: 1
      max: 32
      description: "Number of color clusters"
    - key: algorithm
      param_type: str
      default: kmeans
      choices: ["kmeans"]
      description: "Clustering algorithm"
pywal:
  description: "pywal (wal binary) backend"
  parameters:
    - key: saturation
      param_type: float
      default: 1.0
      min: 0.0
      max: 2.0
    - key: algorithm
      param_type: str
      default: auto
      choices: ["auto", "thief", "color", "haishoku", "colorthief", "wal"]
wallust:
  description: "wallust (Rust binary) backend"
  parameters:
    - key: saturation
      param_type: float
      default: 1.0
      min: 0.0
      max: 2.0
    - key: algorithm
      param_type: str
      default: kmeans
      choices: ["kmeans", "kmeans-new", "kmeans-old", "kmeans-improved", "fastkmeans", "kmeans-euclid", "pam", "pam-new", "pam-old"]
```

The `ParameterResolutionService` pattern, the `--param key=value` CLI, the `PydanticTypeCoercer` coercion, and the container `--param` forwarding remain unchanged — they consume `BackendDefinition` domain objects regardless of whether those objects originate from a constant table or a YAML file.

**Resolution pipeline:**
```
Prefix: COLORSCHEME_BACKENDS
Default file: package-bundled defaults/backends.yaml
Strategies (same 5-chain as settings, all with `kind=ResourceKind.FILE`):
  CliPathStrategy(kind=ResourceKind.FILE)                          # COLORSCHEME_BACKENDS_CONFIG_FILE_PATH
  EnvPathStrategy(var="BACKENDS_CONFIG_FILE_PATH", kind=ResourceKind.FILE)
  DirectoryTraversalStrategy(filename="backends.yaml", max_levels=3, kind=ResourceKind.FILE)
  XdgStrategy(xdg_subdir="color-scheme", filename="backends.yaml", kind=ResourceKind.FILE)
  DefaultFileStrategy(path=<package defaults/backends.yaml>, kind=ResourceKind.FILE)
Parser: YamlConfigParser
Validator: BackendsCatalogSchema (Pydantic)
OverrideRules: none (catalog content is file-source only, like WEG effects.yaml)
```

### Config-assembler-engine usage summary

| Aspect | Settings | Templates | Backends |
|--------|----------|-----------|----------|
| Component used | `AssembleConfiguration` (full pipeline) | `CompositePathResolver` only | `AssembleConfiguration` (full pipeline) |
| Parser | `TomlConfigParser` | none | `YamlConfigParser` |
| Schema | `CoreSettingsSchema` (Pydantic) | none |
| OverrideRules | all scalar fields | none |
| Returns | `AppSettings` (domain dataclass via `_schema_to_domain`) + `resolved_path` + `applied_overrides` | `Path` (directory) |

---

## 8. Container Execution Flow

### Design Principle: Pre-Resolved Config, Backend-Scoped Image, No Host Cache

```
HOST:
  1. Resolve settings via AssembledConfigResolver -> AppSettings + resolved path + applied overrides
  2. Resolve templates dir via TemplateDirResolver -> Path
  3. Resolve backend params:
     - active = settings.generation.backend                  (always one of CUSTOM/PYWAL/WALLUST — D10)
     - defs = BACKEND_DEFINITIONS[active].parameters          (domain constant table)
     - raw_overrides = _parse_params(--param list)            (cli/process.py:37-46 WEG pattern)
     - coerced = {k: PydanticTypeCoercer.coerce(v, def.param_type) for k, v in raw_overrides}
       (validate min/max/choices; raise ConfigResolutionError on bad value)
     - resolved = ParameterResolutionService.resolve_all(defs, coerced)  # override -> default
  4. If RuntimeMode.CONTAINER:
     a. image_name = f"{registry or ''}color-scheme-{active.image_suffix}:{tag}"
     b. engine = RuntimeFactory.create(RuntimePreference(RuntimeKind(container.engine), container.engine))
        if not engine.is_available(): raise ContainerRuntimeUnavailableError
        if not engine.images.exists(image_name): raise ContainerImageNotFoundError (suggest install)
      c. Serialize AppSettings as-resolved (no rewrite -- the inner CLI's `--runtime local` flag at step 4f overrides this via OverrideRule, so the config stays truthful for debugging) -> temp TOML
     d. chmod output_dir 0o777 (non-root container user)
     e. Mounts (tuple of VolumeMount, BIND):
        - input parent dir   -> /input                 (RO)
        - output dir         -> /output                (RW)
        - temp settings TOML -> /csg-config/settings.toml (RO)
        - templates dir      -> /templates              (RO)
        (NO /cache mount — ADR-008)
     f. RunConfig:
        image: color-scheme-{active.image_suffix}:{tag}
        command: ("generate", "/input/<input_basename>",
                  "-o", "/output",
                  "--backend", "<active.image_suffix>",
                  "--config", "/csg-config/settings.toml",
                  "--templates", "/templates",
                  "--runtime", "local",
                  "--no-summary")
        + for each (k, v) in resolved:
            extend command with ["--param", f"{k}={v}"]      # WEG container_processor.py:157-159
        + for each fmt in GeneratorConfig.formats:
            extend command with ["-f", fmt.value]
        volumes: tuple of 4 mounts
        ports: ()
        remove: True
        detach: False
        stream_output: False (JSON mode prints final result only)
        timeout: configurable (default 3600)
        runtime_flags: engine.capabilities.default_run_flags
     g. engine.containers.run(run_config)
     h. Cleanup temp TOML (try/finally)
  5. If RuntimeMode.LOCAL:
     LocalProcessor with AppSettings + BackendRegistry + JinjaTemplateRenderer + resolved GeneratorConfig
```

### Mount Table

| Host Resource | Container Path | Mode | When |
|---------------|---------------|------|------|
| Input file's parent dir | `/input` | RO | Always (realpath first; reject `/`) |
| Output directory | `/output` | RW (chmod 0o777 first) | Always (mkdir parents) |
| Pre-resolved settings TOML | `/csg-config/settings.toml` | RO | Always |
| Resolved templates dir | `/templates` | RO | Always |

### Which Commands Run Where

| Command | Runs where | Reason |
|---------|-----------|--------|
| `generate` | Local OR Container | needs backend binaries (`wal` / `wallust` / numpy+sklearn) |
| `show` | Local OR Container | re-extracts the palette for display (ADR-011) |
| `install` / `uninstall` | Always local | host-side `docker build`/`rmi` via oci-runtime |
| `info` / `dump-config` / `dump-templates` / `list-backends` / `version` | Always local | only reads config/templates |

The runtime mode `--runtime local|container` only affects `generate` and `show`.

---

## 9. CLI Structure

```
csg
  generate <image_path>
    [-o, --output-dir DIR]                        default: settings.output.directory
    [-b, --backend custom|pywal|wallust]           default: settings.generation.backend
    [-f, --format ...] (repeatable)                default: settings.output.default_formats; empty => all loaded templates
    [--param key=value] (repeatable)                per-backend runtime parameter overrides (D11)
    [--no-summary]                                suppress post-run summary (auto-on in container)
    [--dry-run/-n]                                pre-flight + render command, no exec
  show <image_path>
    [-b, --backend ...]
    [--param key=value] (repeatable)
    [--dry-run/-n]
  install
    [--backend custom|pywal|wallust]  (repeatable; default: all three)
    [--engine docker|podman]
    [--dry-run]
    [--dump-config] [--dump-templates]
  uninstall
    [--backend ...] [--engine ...] [--yes] [--dry-run]
  info
  dump-config [--output PATH] [--overwrite]
  dump-templates [--output DIR] [--overwrite]
  list-backends
  version

Global:
  -q/--quiet, -v/--verbose (count)               -> OverrideRule("output.verbosity")
  --output-format json|rich|plain               (default: json)  — selects OutputPort adapter
  --config PATH                                  settings.toml explicit path  -> CliPathStrategy(kind=ResourceKind.FILE)
  --templates PATH                                templates dir explicit path  -> CliDirStrategy()
  --runtime local|container                      overrides runtime.mode         -> OverrideRule via cli_overrides
  --container-engine docker|podman               overrides container.engine     -> OverrideRule via cli_overrides
```

### `--param key=value` semantics (mirror of WEG `cli/process.py:37-46`, WEG plan §9 Resolved Decision #2)

- Repeatable; `--param saturation=1.5 --param algorithm=thief`.
- **Last value wins** for duplicate keys.
- **Split on the first `=` only** — values containing `=` are preserved.
- Malformed entries (no `=`) are silently dropped (matches WEG `_parse_params`).
- **Non-existent parameter** for the active backend (e.g. `--param bogus=1`): raises `ConfigResolutionError` (CSG chooses strict-fail here; WEG warns-and-ignores for forward compat. CSG has no plugin/forward-compat story for backend params, so we fail fast).
- **Coercion failure** (e.g. `--param saturation=abc` where `saturation` is `float`): `PydanticTypeCoercer` raises `OverrideCoercionError`; the CLI maps it to `ConfigResolutionError` with a clear message.
- **Validation failure** (out of `min`/`max`/`choices`): `ConfigResolutionError` raised after coercion.
- In **container mode**, `--param` pairs are forwarded verbatim to the inner container command (`cmd.extend(["--param", f"{key}={value}"])`), identical to WEG `container_processor.py:157-159`. The inner `csg` re-parses, re-coerces, and re-resolves them against `BACKEND_DEFINITIONS[backend]` — same pure domain logic on both sides. The container does NOT receive them via `cli_overrides` of config-assembler-engine.

### `--backend` semantics (D10)

- Accepts only `custom`, `pywal`, `wallust`. **No `auto` value**.
- Default: `settings.generation.backend` (which has a concrete default in `defaults/settings.toml`, e.g. `backend = "pywal"`).
- Override path: maps to OverrideRule `generation.backend` via `cli_overrides={"generation.backend": "<value>"}` to `AssembleConfiguration.execute`. The Pydantic schema's `@field_validator` rejects `"auto"` and any other invalid value at config resolution time.
- In container mode, `--backend` must match the image's backend (one image per backend, D2). Mismatch raises `BackendNotAvailableError` because the in-container `BackendRegistry` will only have one adapter and the requested one won't be in it.

---

## 10. Package Structure

```
color-scheme-generator/
├── pyproject.toml
├── Makefile
├── .python-version
├── docs/
│   └── ARCHITECTURE_PLAN.md
└── src/
    └── color_scheme_generator/
        ├── __init__.py                  # __version__ = "0.1.0"
        ├── constants.py                 # XDG subdir ("color-scheme"), filenames, traversal depth
        ├── errors.py                    # re-exports domain exceptions + __all__
        ├── factory.py                   # composition root: CliDependencies + create_* helpers + BackendRegistry builder
        ├── domain/
        │   ├── __init__.py
        │   ├── enums.py                 # Backend, ColorAlgorithm, ColorFormat, RuntimeMode, ContainerEngine, OutputFormat, Verbosity
        │   ├── models.py                # frozen dataclasses incl. BackendParameterDefinition, BackendDefinition, Color, ColorScheme, GeneratorConfig, GenerationRequest, GenerationResult, BackendInfo, AppSettings + sub-settings
        │   ├── backend_catalog.py        # BACKEND_DEFINITIONS dict (loaded from YAML at composition time)
        │   ├── services.py              # ColorAdjustmentService, PaletteNormalizationService, HexValidationService, ParameterResolutionService
        │   └── exceptions.py            # ColorSchemeError hierarchy
        ├── ports/
        │   ├── __init__.py
        │   ├── palette_generator.py     # PaletteGeneratorPort (Protocol)
        │   ├── config_resolver.py       # ConfigResolverPort
        │   ├── template_renderer.py     # TemplateRendererPort
        │   ├── template_dir_resolver.py # TemplateDirResolverPort
        │   ├── processor.py             # ColorSchemeProcessorPort
        │   ├── output.py                # OutputPort
        │   ├── serializers.py           # SettingsSerializerPort
        │   ├── version_provider.py
        │   └── backend_catalog_loader.py # BackendCatalogLoaderPort
        ├── adapters/
        │   ├── __init__.py
        │   ├── assembled_config_resolver.py
        │   ├── yaml_backend_catalog_loader.py  # YamlBackendCatalogLoader
        │   ├── jinja_template_renderer.py
        │   ├── template_dir_resolver.py # uses engine's CliDirStrategy + EnvDirStrategy + XdgDirStrategy + DefaultDirStrategy
        │   ├── local_processor.py
        │   ├── container_processor.py
        │   ├── dry_run_processor.py
        │   ├── error_mapping.py
        │   ├── importlib_version_provider.py
        │   ├── backends/
        │   │   ├── __init__.py
        │   │   ├── custom.py
        │   │   ├── pywal.py
        │   │   └── wallust.py
        │   ├── schemas/
        │   │   ├── __init__.py
        │   │   ├── settings_schema.py    # Pydantic CoreSettingsSchema
        │   │   └── backends_catalog_schema.py  # Pydantic BackendsCatalogSchema
        │   ├── serializer/
        │   │   ├── __init__.py
        │   │   ├── settings_serializer.py
        │   │   └── templates_serializer.py
        │   ├── output/
        │   │   ├── __init__.py
        │   │   ├── json_output.py
        │   │   ├── rich_output.py
        │   │   └── plain_output.py
        │   └── docker/
        │       ├── __init__.py           # get_docker_dir / get_dockerfile / list_dockerfiles
        │       ├── Dockerfile.base
        │       ├── Dockerfile.custom
        │       ├── Dockerfile.pywal
        │       └── Dockerfile.wallust
        ├── defaults/
        │   ├── settings.toml
        │   ├── backends.yaml
        │   └── templates/
        │       ├── colors.css.j2
        │       ├── colors.gtk.css.j2
        │       ├── colors.json.j2
        │       ├── colors.rasi.j2
        │       ├── colors.scss.j2
        │       ├── colors.sequences.j2
        │       ├── colors.sh.j2
        │       └── colors.yaml.j2
        └── cli/
            ├── __init__.py
            ├── main.py                    # Typer app + global callback (composition) + top-level commands
            ├── generate.py
            ├── show.py
            ├── install.py
            ├── uninstall.py
            ├── info.py
            ├── dump_config.py
            ├── dump_templates.py
            ├── list_backends.py
            └── version_cmd.py
└── tests/
    ├── __init__.py
    ├── unit/
    │   ├── domain/  (test_enums, test_models, test_services, test_backend_params, test_exceptions)
    │   ├── ports/   (test_interfaces)
    │   ├── adapters/
    │   │   ├── backends/ (test_custom, test_pywal, test_wallust)
    │   │   ├── output/   (test_json_output, test_rich_output, test_plain_output)
    │   │   ├── serializer/
    │   │   ├── test_assembled_config_resolver.py
    │   │   ├── test_jinja_template_renderer.py
    │   │   ├── test_template_dir_resolver.py
    │   │   ├── test_local_processor.py
    │   │   ├── test_container_processor.py
    │   │   ├── test_dry_run_processor.py
    │   │   └── test_error_mapping.py
    │   └── cli/ (test_generate, test_show, test_install, test_uninstall, test_info, test_dump_config, test_dump_templates, test_list_backends, test_version — incl. `_parse_params` + `--param` coercion tests)
    ├── integration/  (test_local_pipeline, test_cli_generate, test_cli_show)
    ├── helpers/
    └── fixtures/
        └── test-wallpaper.jpg
```

---

## 11. Dependencies

| Dependency | Version | Purpose | Source |
|------------|---------|---------|--------|
| `config-assembler-engine` | >= 0.1.0 | settings.toml full pipeline (`AssembleConfiguration`) + templates dir path-only resolution (`CompositePathResolver`) | workspace, editable `../../shared/config-assembler-engine` |
| `oci-runtime` | >= 0.3.0 | per-backend image build/run/remove (`RuntimeFactory`, `engine.images`, `engine.containers`) | workspace, editable `../../shared/oci-runtime` |
| `pydantic` | >= 2.0 | schema validation for `settings.toml` (boundary DTO) + `PydanticTypeCoercer` for `--param` coercion | PyPI |
| `jinja2` | >= 3.1 | template rendering | PyPI |
| `typer[all]` | >= 0.9.0 | CLI framework | PyPI |
| `rich` | >= 13.0 | rich output adapter | PyPI |
| `tomli-w` | >= 1.0 | TOML serialization (`dump-config` + `ContainerProcessor` temp TOML) | PyPI |
| `pillow`, `numpy`, `scikit-learn` | — | custom backend runtime deps | PyPI, under `[project.optional-dependencies] custom` |
| `pywal` | >= 3.3.0 | host-side pywal backend (non-container) | PyPI, under `[project.optional-dependencies] pywal` |

> **`pyyaml` is NOT a direct CSG dep.** Settings are TOML, and Jinja2 emits YAML as text. config-assembler-engine may pull pyyaml transitively but CSG never imports it.

---

## 12. oci-runtime v0.3.0 API Surface (Validated)

Same as WEG `ARCHITECTURE_PLAN.md §12`. `RuntimeFactory.create(RuntimePreference(RuntimeKind.DOCKER, "docker"))`, frozen dataclasses (`RunConfig`, `VolumeMount`, `BuildContext`, `PortMapping`), exception hierarchy (`OciError → ImageNotFoundError / ImagePullAccessDeniedError / RuntimeNotAvailableError / OperationTimeoutError`), `ContainerManager.run()` dispatch matrix (TTY/Streaming/Batched/Detached). CSG consumes it identically — see WEG reference findings §4 + this plan §8.

CSG-specific usage notes:
- **One `engine.images.build(BuildContext(...), image_name)` per backend** during `install`.
- `ContainerProcessor` selects the image per `Backend` (one image per backend, D2).
- Maps `ImageNotFoundError` → `ContainerImageNotFoundError`, `ImagePullAccessDeniedError` → `ImagePullAccessError`, `RuntimeNotAvailableError` → `ContainerRuntimeUnavailableError` via `adapters/error_mapping.py`.

---

## 13. Key Architectural Decisions (ADRs)

- **ADR-001: Single-File Config Resolution (No Merging)** — replaces v2 `layered-settings` multi-file merge with config-assembler-engine single-file + opt-in overrides (deterministic, auditable).
- **ADR-002: Domain Port for Processing (Not CLI Proxy)** — replaces v2 `transparent-orchestrator` `ContainerProxyCommand` + Click/Typer monkey-patching with a `ColorSchemeProcessorPort` and three adapters (`LocalProcessor`, `ContainerProcessor`, `DryRunProcessor`). The domain decides **what** to extract; the adapter decides **where**. No CLI-framework coupling.
- **ADR-003: Pre-Resolved Config for Containers** — serialize resolved `AppSettings` as-resolved to a temp TOML mounted at `/csg-config/settings.toml`; the in-container `--runtime local` CLI flag (highest priority override) prevents recursion, not a config rewrite. Eliminates ENV forwarding and divergence. Improves on WEG ADR-003 by keeping the serialized config truthful.
- **ADR-004: Templates Dir via Path Resolver Only** — config-assembler-engine's `CompositePathResolver` resolves the templates **directory**; no `AssembleConfiguration` parser/validator (`.j2` files are content, not a schema). Thin directory-aware strategies added in CSG adapters (config-assembler-engine itself untouched).
- **ADR-005: One Container Image per Backend** — preserves v2's dependency isolation rationale. `install`/`uninstall` loop backends; `ContainerProcessor` dispatches by `Backend`.
- **ADR-006: Runtime Mode vs Container Engine (Orthogonal)** — `runtime.mode` (local/container) decides WHERE; `container.engine` (docker/podman) decides WHICH. Independent OverrideRules. Mirrors WEG ADR-006.
- **ADR-007: JSON-First Output (LLM-Friendly)** — default `--output-format json` renders structured status; `OutputPort` takes **domain objects**; each adapter renders. Inverts v2's Rich-only output.
- **ADR-008: Ephemeral In-Container Cache** — no `~/.cache` host bind mount. Each container run re-extracts via `wal`/`wallust`. Simpler mounts, no host-state coupling. Tradeoff: marginally slower repeated runs in container mode.
- **ADR-009: Optional `custom` / `pywal` Backend Deps** — `[project.optional-dependencies] custom` (pillow, numpy, scikit-learn) and `pywal` allow lean host installs. `CustomGenerator` lazily imports and raises `BackendNotAvailableError` with an install hint when missing. The `custom` container image installs the extra via `pip install .[custom]`.
- **ADR-010: No `auto` Backend — Explicit Only** — `Backend` enum is `{CUSTOM, PYWAL, WALLUST}`. The active backend is always explicit (CLI `--backend`, env `COLORSCHEME__GENERATION__BACKEND`, or the concrete default in `defaults/settings.toml`). No host-side auto-detection iteration. If unavailable, raise `BackendNotAvailableError` with an install hint. Restores determinism.
- **ADR-011: `--param key=value` Replaces Dedicated Tuning Flags + YAML Catalog** — saturation and other per-backend runtime parameters are overridden via repeatable `--param key=value`. The CLI parses (`_parse_params`, copy of WEG `cli/process.py:37-46`), coerces via `PydanticTypeCoercer` from config-assembler-engine, and resolves via the domain `ParameterResolutionService` against `BACKEND_DEFINITIONS[active].parameters`. In container mode, `--param` pairs are forwarded verbatim to the inner container command (WEG `container_processor.py:157-159` pattern). The inner `csg` re-parses and re-resolves them through the same pure domain logic. **Per-backend parameter definitions live in a `backends.yaml` catalog file** resolved via config-assembler-engine's full pipeline (`AssembleConfiguration` + `YamlConfigParser` + `BackendsCatalogSchema`), parallel to WEG `effects.yaml`. This makes backend catalog content introspectable, user-editable, and resolvable through the same deterministic machinery as settings. A `BackendCatalogLoaderPort` + `YamlBackendCatalogLoader` adapter loads the resolved catalog into the domain `BACKEND_DEFINITIONS` dict at composition time.
- **ADR-012: Frozen Domain, Pydantic at the Boundary** — `Color`/`ColorScheme`/`AppSettings`/`BackendParameterDefinition`/`BackendDefinition` are frozen dataclasses with pure methods. Pydantic `CoreSettingsSchema` lives only in `adapters/schemas/`; `_schema_to_domain()` converts. The domain never imports pydantic. Matches WEG pattern.
- **ADR-013: `BackendRegistry` Replaces v2 `BackendFactory` Switch** — `factory.py` builds `dict[Backend, PaletteGeneratorPort]` and injects it into `LocalProcessor`/`DryRunProcessor`. Adding a backend = new adapter + one registry entry + one `BackendDefinition` in `BACKEND_DEFINITIONS`; no edits to existing code paths. Replaces v2's `if backend == CUSTOM: return CustomGenerator(...)` switch in `packages/core/src/color_scheme/factory.py`. **Note:** the registry is lookup-only, never iterated for auto-detection (ADR-010).
- **ADR-014: Dockerfile Bases Preserved, Alpine-Dropped** — `python:3.14-slim` for base + per-backend ext (apt for imagemagick, cargo/Rust or prebuilt binary for wallust, pip for numpy+sklearn). `Dockerfile.custom.alpine-SLOW` removed (musl + numpy/sklearn is painful). Matches v2's pragmatic choice.
- **ADR-015: Hidden Display Flags Dropped** — v2's `--display-image-path` / `--display-output-dir` were artefacts of `transparent-orchestrator`'s proxy hook (the host-side orchestrator rewrote paths to container paths and forwarded hidden flags so the inner CLI's user-facing output could show the original host paths). In v3 the host orchestrates everything and renders output via `OutputPort` after `engine.containers.run` returns; the inner container CLI has no need to know original host paths. **Not migrated.**

---

## 14. Default Config Files

### `defaults/settings.toml` (package defaults)

```toml
version = "1.0"

[output]
verbosity = 1
directory = "/tmp/color-scheme"

[generation]
backend = "pywal"          # custom | pywal | wallust  (NO auto — ADR-010)
default_formats = ["json", "sh"]

[templates]
directory = ""           # empty -> resolve via TemplateDirResolver (env -> XDG -> package)

[runtime]
mode = "local"

[container]
engine = "docker"
image_tag = "latest"
image_registry = ""     # "" or None both treated as absent
```

> Note: per-backend parameters (saturation, algorithm, n_clusters) are NOT in `settings.toml`. They live in `defaults/backends.yaml` (resolved via `BackendCatalogLoaderPort`, ADR-011) and are overridden at the CLI via `--param`.

### `defaults/backends.yaml` (package defaults)

```yaml
custom:
  description: "PIL + scikit-learn KMeans"
  parameters:
    - key: saturation
      param_type: float
      default: 1.0
      min: 0.0
      max: 2.0
      description: "Saturation adjustment factor"
    - key: n_clusters
      param_type: int
      default: 16
      min: 1
      max: 32
      description: "Number of color clusters"
    - key: algorithm
      param_type: str
      default: kmeans
      choices: ["kmeans"]
      description: "Clustering algorithm"
pywal:
  description: "pywal (wal binary) backend"
  parameters:
    - key: saturation
      param_type: float
      default: 1.0
      min: 0.0
      max: 2.0
      description: "Saturation adjustment factor"
    - key: algorithm
      param_type: str
      default: auto
      choices: ["auto", "thief", "color", "haishoku", "colorthief", "wal"]
      description: "pywal extraction algorithm"
wallust:
  description: "wallust (Rust binary) backend"
  parameters:
    - key: saturation
      param_type: float
      default: 1.0
      min: 0.0
      max: 2.0
      description: "Saturation adjustment factor"
    - key: algorithm
      param_type: str
      default: kmeans
      choices: ["kmeans", "kmeans-new", "kmeans-old", "kmeans-improved", "fastkmeans", "kmeans-euclid", "pam", "pam-new", "pam-old"]
      description: "wallust extraction algorithm"
```

> Resolution chain: same 5-strategy pattern as `settings.toml`. Env prefix `COLORSCHEME_BACKENDS`. Default file at package `defaults/backends.yaml`. No OverrideRules — catalog content is file-source only.

### `defaults/templates/*.j2` (package defaults)

8 Jinja2 templates ported verbatim from v2 `packages/core/src/color_scheme/templates/`: `colors.{css,gtk.css,json,rasi,scss,sequences,sh,yaml}.j2`. Render context: `source_image`, `backend`, `generated_at`, `background`/`foreground`/`cursor` (`Color` with `.hex`/`.rgb`), `colors` (16-tuple of `Color`). The `sequences` format gets binary post-processing in `JinjaTemplateRenderer`.

---

## 15. Wiring & Composition Root (`factory.py`)

Mirror WEG `factory.py` + `cli/main.py` callback two-tier composition:

```python
@dataclass
class CliDependencies:
    config_resolver: ConfigResolverPort
    template_renderer: TemplateRendererPort
    version_provider: VersionProviderPort
    settings_serializer: SettingsSerializerPort
    output_adapter: OutputPort | None = None           # lazily set by --output-format
    backend_registry: dict[Backend, PaletteGeneratorPort] = field(default_factory=dict)
    container_engine: object | None = None              # oci-runtime engine, lazily created
    # caches, etc.

    def __post_init__(self): ...
```

`create_*` helpers in `factory.py`:
- `create_config_resolver(default_settings_path)` — wires `AssembledConfigResolver` (TomlConfigParser + strategies + OverrideRules).
- `create_template_renderer(default_templates_dir)` — wires `JinjaTemplateRenderer` (TemplateDirResolver + Jinja2 `Environment`).
- `create_backend_registry()` — `{Backend.CUSTOM: CustomGenerator(), Backend.PYWAL: PywalGenerator(), Backend.WALLUST: WallustGenerator()}`. **Lookup table only — no auto-detect iteration** (ADR-010).
- `create_container_engine(container_settings)` — `RuntimeFactory().create(RuntimePreference(RuntimeKind(engine), engine))`.
- `create_local_processor(backend_registry, template_renderer)`.
- `create_container_processor(container_engine, default_templates_dir)`.
- `create_dry_run_processor(backend_registry, template_renderer)`.
- `create_output_adapter(fmt)` — dispatches on `OutputFormat`.

`cli/main.py` `@app.callback()` builds `CliDependencies` (long-lived ports) and stashes on `ctx.obj["deps"]`, mirroring WEG. Per-command wiring lazily picks processor by `settings.runtime.mode` + `--dry-run` (like WEG `cli/process.py:_resolve_processor`).

### `--param` parsing in CLI

`cli/generate.py` (and `cli/show.py`) include a `_parse_params` copy of WEG `cli/process.py:37-46` (split on first `=`, last value wins, malformed silently dropped). After config resolution, the CLI:
1. Looks up `BACKEND_DEFINITIONS[settings.generation.backend]` to get the active backend's `BackendDefinition`.
2. Coerces each parsed override against the matching `BackendParameterDefinition.param_type` via `config_assembler_engine.adapters.type_coercer.PydanticTypeCoercer`.
3. Validates `min`/`max`/`choices` (raises `ConfigResolutionError` on violation).
4. Calls `ParameterResolutionService.resolve_all(definition.parameters, coerced_overrides)` to merge with defaults.
5. Builds `GeneratorConfig(backend=..., params=resolved, formats=..., output_dir=...)`.

---

## 16. Test Strategy

- `tests/unit/domain/` — pure dataclass / service tests (no I/O). Includes `ParameterResolutionService.resolve_all` against `BACKEND_DEFINITIONS`, and `_parse_params` round-trip tests (mirror of WEG `process.py:_parse_params`).
- `tests/unit/ports/` — interface compliance / runtime-checkable Protocol tests.
- `tests/unit/adapters/` — backend adapters (mock `shutil.which`/`subprocess`/PIL), `OutputPort` adapters with sample domain objects, serializers with temp files, `AssembledConfigResolver` with fixture TOMLs, `TemplateDirResolver` with temp dirs, `LocalProcessor`/`ContainerProcessor`/`DryRunProcessor` with `Mock` ports (incl. `--param` forwarding assertions in `test_container_processor.py`), `error_mapping` with parametrized oci-runtime exceptions.
- `tests/unit/cli/` — per-command Typer `CliRunner` tests with `Mock` deps on `ctx.obj`. Includes `--param` end-to-end tests: parsing → coercion → resolution → `GeneratorConfig.params`.
- `tests/integration/` — real `LocalProcessor` end-to-end with the `custom` backend (the only one needing no external binary if the extra is installed) and real template rendering to a temp dir.
- `tests/fixtures/test-wallpaper.jpg` — reuses v2 fixture.

---

## 17. Build & Packaging

- Build backend: `hatchling`, package at `src/color_scheme_generator`; console script `csg = "color_scheme_generator.cli.main:app`.
- uv workspace — root has `[tool.uv.workspace]`; editable path deps:
  ```toml
  [tool.uv.sources]
  config-assembler-engine = { path = "../../shared/config-assembler-engine", editable = true }
  oci-runtime = { path = "../../shared/oci-runtime", editable = true }
  ```
- Python `>=3.14` (matches v2 pin and oci-runtime requirement); ruff `py312` / line-length 100, selects `E,F,I,N,W,UP,B` ignoring `B905` (matches WEG + config-assembler-engine conventions).
- pytest config: `testpaths = ["tests"]`, `pythonpath = ["src", "."]`.
- Makefile targets: `test`, `test-all` (+ integration), `lint`, `format`, `check`, `build`, `clean` — same as WEG/oci-runtime.

---

## 18. v2 → v3 migration mapping (file-by-reference)

| v2 location | v3 location | Transformation |
|---|---|---|
| `packages/core/src/color_scheme/core/types.py` (`Color`, `ColorScheme`, `GeneratorConfig`) | `src/color_scheme_generator/domain/models.py` | Pydantic → frozen dataclass; `_schema_to_domain` handles Pydantic boundary |
| `packages/core/src/color_scheme/core/base.py` (`ColorSchemeGenerator` ABC) | `ports/palette_generator.py` (`PaletteGeneratorPort` Protocol) | ABC → `@runtime_checkable Protocol` |
| `packages/core/src/color_scheme/backends/{custom,pywal,wallust}.py` | `adapters/backends/{custom,pywal,wallust}.py` | Same logic, implement `PaletteGeneratorPort`; consume `GeneratorConfig.params` instead of v2 `AppConfig`; lazy heavy imports |
| `packages/core/src/color_scheme/factory.py` (`BackendFactory` switch + `auto_detect`) | `factory.py` `create_backend_registry()` + `BACKEND_DEFINITIONS` | Switch → dict registry (ADR-013); **`auto_detect` removed** (ADR-010) |
| `packages/core/src/color_scheme/output/manager.py` (`OutputManager`) | `adapters/jinja_template_renderer.py` (`JinjaTemplateRenderer`) | Same render logic; resolves dir via `TemplateDirResolver` instead of `color_scheme_templates` package |
| `packages/templates/src/color_scheme_templates/...` | `adapters/template_dir_resolver.py` + `defaults/templates/` | Replaces layered-settings-using template discovery with config-assembler-engine path resolver + bundled defaults |
| `packages/core/src/color_scheme/config/{config,defaults,enums}.py` | `adapters/schemas/settings_schema.py` + `domain/enums.py` + `defaults/settings.toml` | Pydantic schema stays at boundary; enums/defaults in domain/defaults; **`generation.saturation` removed** (became per-backend param via `BACKEND_DEFINITIONS`) |
| `packages/core/src/color_scheme/cli/{main,dry_run,dump_config,config_display,info_display}.py` | `cli/{main,generate,show,dump_config,info}.py` | Restructure into per-command modules; `OutputPort` adapter replaces inline rich/echo; **`--saturation` flag removed** (replaced by `--param saturation=...`, ADR-011) |
| `packages/orchestrator/src/.../cli/commands/{install,uninstall}.py` (use `DockerImageManager`) | `cli/{install,uninstall}.py` (use `engine.images.build/remove`) | `container-manager` → `oci-runtime` |
| `packages/orchestrator/src/.../container/manager.py` (orphan) | **Deleted** | Replaced by `adapters/container_processor.py` |
| `packages/orchestrator/src/.../cli/main.py` (`ContainerProxyCommand` + Click monkey-patching + hidden `--display-*` flags) | **Deleted** | Replaced by explicit `ColorSchemeProcessorPort` + `ContainerProcessor` (ADR-002, ADR-015) |
| `packages/orchestrator/src/.../config/{settings,unified}.py` | merged into `adapters/schemas/settings_schema.py` + `domain/models.py` (ContainerSettings) | Unification (D1) |
| `packages/orchestrator/docker/Dockerfile.*` | `adapters/docker/Dockerfile.*` | Per-backend + base; bases preserved (D9); `Dockerfile.custom.alpine-SLOW` dropped |
| `src/shared/container-manager` usage | `oci-runtime` usage | All calls rewritten to `RuntimeFactory` / `engine.images` / `engine.containers.run` |
| `src/shared/layered-settings` usage (`build_config`, `SchemaEntry`, path helpers) | `config-assembler-engine` (`AssembleConfiguration`, `OverrideRule`, `CompositePathResolver`, strategies) | Single-file resolution, opt-in overrides (ADR-001) |
| `src/shared/transparent-orchestrator` usage (`inject_config_to_all`, `ContainerProxyCommand`, `DockerContainerRunner`) | **Deleted** | No CLI proxy; explicit ports/adapters (ADR-002) |

---

## 19. Open implementation notes

These are notes for the implementation phase, not blocking architectural decisions:

1. **`--backend` and `--runtime` override plumbing**: WEG rebuilds `AppSettings` via direct dataclass reconstruction after config resolution (`cli/process.py:58-86`). For CSG, since `generation.backend`, `runtime.mode`, and `container.engine` are all covered by `OverrideRule`s, the cleaner path is to pass them via `AssembleConfiguration.execute(cli_overrides={...})` so the OverrideRules + Pydantic re-validation handle them uniformly. Document in the implementation PR which path is taken.
2. **Image naming with registry**: `image_name = f"{registry or ''}color-scheme-<backend>:<tag}"` where `registry` is e.g. `"ghcr.io/myorg/"` (trailing slash enforced via Pydantic `@field_validator`). Empty registry = local-only image.
3. **`wal` / `wallust` in-container cache paths**: backends hardcode cache locations under `$HOME/.cache/{wal,wallust}/`. The per-backend Dockerfiles ensure `HOME` is set to a writable location for the non-root `colorscheme` user (UID 1000). Architecture only needs to state: "backends manage their own cache internally; in container mode, cache is ephemeral inside the container filesystem" (ADR-008). No host mount required.
4. **Backend catalog implementation**: The `YamlBackendCatalogLoader` adapter wraps config-assembler-engine's `AssembleConfiguration` with `YamlConfigParser` + `BackendsCatalogSchema`, using the same 5-strategy resolution chain as settings. The `backends.yaml` file is file-source only (no OverrideRules) — parallel to WEG's `effects.yaml`. The `config-assembler-engine` dependency must include `pyyaml` for YAML parsing (add `pyyaml` to CSG's deps if not transitive).