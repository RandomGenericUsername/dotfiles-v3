# Architecture Plan: wallpaper-effects-generator v3

## Hexagonal architecture redesign of the wallpaper effects processing CLI tool.

---

## 1. Domain Models (pure, frozen dataclasses, zero I/O)

| Model | Purpose |
|-------|---------|
| `ItemType` enum | EFFECT / COMPOSITE / PRESET, with `subdir_name` |
| `Verbosity` enum | QUIET / NORMAL / VERBOSE / DEBUG |
| `RuntimeMode` enum | LOCAL / CONTAINER |
| `OutputFormat` enum | JSON / RICH / PLAIN (default: JSON) |
| `ParameterType` | Reusable param type definition (type, pattern, min/max, default) |
| `ParameterDefinition` | Effect param definition (type ref, cli_flag, default, description) |
| `EffectDefinition` | Atomic effect: name, description, command template, parameters |
| `ChainStep` | Composite chain step: effect name + params |
| `CompositeDefinition` | Composite: name, description, chain |
| `PresetDefinition` | Preset: name, description, XOR composite/effect, params |
| `EffectsCatalog` | Root aggregate: version, parameter_types, effects, composites, presets |
| `ProcessingRequest` | input_path, output_path, params (CLI --param overrides) |
| `ProcessingResult` | success, command, stdout, stderr, return_code, duration |
| `BatchRequest` | input_path, output_dir, item_types, flat, explicit_output, parallel, strict, max_workers |
| `BatchResult` | total, succeeded, failed, results map, output_dir |
| `AppSettings` | version, execution, output, processing, backend, runtime, container |
| `ExecutionSettings` | parallel, strict, max_workers |
| `OutputSettings` | verbosity, directory |
| `ProcessingSettings` | temp_dir |
| `BackendSettings` | binary |
| `RuntimeSettings` | mode (local/container) -- WHERE to process |
| `ContainerSettings` | engine (docker/podman), image_tag, image_registry -- WHICH runtime |

> **NOTE**: `RuntimeSettings.mode` and `ContainerSettings.engine` are orthogonal. `mode` decides WHERE to process (local or container). `engine` decides WHICH OCI runtime (docker or podman). See ADR-006.

---

## 2. Domain Services (pure logic, @staticmethod, zero I/O)

| Service | Responsibility |
|---------|----------------|
| `CommandSubstitutionService` | Substitute `$INPUT`, `$OUTPUT`, `$PARAM` in command templates |
| `ParameterResolutionService` | Resolve param values: explicit CLI --param overrides -> effect defaults -> parameter_type defaults |
| `OutputPathService` | Compute output file paths from base_dir, item name, type, flat flag, explicit_output flag |
| `CatalogValidationService` | Validate cross-refs (composites -> effects, presets -> effects/composites) |

---

## 3. Error Hierarchy

```
WallpaperEffectsError (base)
+-- EffectsLoadError (file_path, reason)
+-- EffectsValidationError (message)
+-- CommandExecutionError (command, return_code, stderr)
+-- CatalogError
|   +-- EffectNotFoundError (name)
|   +-- CompositeNotFoundError (name)
|   +-- PresetNotFoundError (name)
+-- BinaryNotFoundError (binary)
+-- ContainerImageNotFoundError (image)
+-- ContainerRuntimeUnavailableError (runtime)
+-- ImagePullAccessError (image, registry)
+-- ConfigResolutionError
```

---

## 4. Ports (Protocol/ABC interfaces)

| Port | Methods | Direction |
|------|---------|-----------|
| `EffectLoaderPort` | `load(path=None) -> EffectsCatalog`, `get_default_path() -> Path`, `get_resolved_path() -> Path \| None` | Inbound |
| `ConfigResolverPort` | `resolve(explicit_path=None) -> AppSettings`, `get_resolved_path() -> Path \| None` | Inbound |
| `CommandRunnerPort` | `is_available(binary=None) -> bool`, `get_binary() -> str`, `execute(command, timeout=None) -> CommandResult` | Outbound |
| `EffectProcessorPort` | `process_effect(name, request) -> ProcessingResult`, `process_composite(name, request) -> ProcessingResult`, `process_preset(name, request) -> ProcessingResult`, `process_batch(request) -> BatchResult` | Core |
| `ImageManagerPort` | `build(context, image_name) -> str`, `remove(image, force) -> None`, `exists(image) -> bool`, `pull(image) -> str` | Outbound |
| `OutputPort` | `process_result(result)`, `batch_result(result)`, `catalog_list(catalog, item_type)`, `config_info(settings, catalog, sources)`, `dry_run(...)`, `error(exc)`, `message(msg)`, `progress_start(total, desc)`, `progress_advance(name)`, `progress_done()` | Outbound |
| `SettingsSerializerPort` | `serialize(settings: AppSettings) -> str` | Outbound |
| `EffectsSerializerPort` | `serialize(catalog: EffectsCatalog) -> str` | Outbound |

> **NOTE**: `OutputPort` is restructured for structured output. Instead of `info(str)` / `error(str)`, it takes **domain objects** and each adapter renders them differently (JSON / Rich / Plain). See ADR-007.

---

## 5. Adapters

| Adapter | Implements | Key Behavior |
|---------|------------|-------------|
| `YamlEffectLoader` | `EffectLoaderPort` | Uses config-assembler-engine with `YamlConfigParser` + strategies to resolve effects.yaml. Parses YAML, validates via `EffectsConfigSchema` (Pydantic), converts to domain `EffectsCatalog`. Returns resolved path. |
| `AssembledConfigResolver` | `ConfigResolverPort` | Uses config-assembler-engine with `TomlConfigParser` + strategies to resolve settings.toml. Applies OverrideRules for ENV+CLI. Returns domain `AppSettings`. Also returns resolved path (needed for container mount). |
| `LocalProcessor` | `EffectProcessorPort` | Runs ImageMagick via `CommandRunnerPort`. Single effects, chains via temp files, batch via ThreadPoolExecutor. Accepts CLI param overrides. |
| `ContainerProcessor` | `EffectProcessorPort` | Serializes resolved `AppSettings` -> temp TOML, resolves effects file path, builds mount plan (input, output, config, effects), constructs RunConfig (tuples, VolumeMountType.BIND), runs via `oci-runtime`'s `ContainerEngine.containers.run()`. Checks image availability first (ImageNotFoundError vs ImagePullAccessDeniedError). Cleans up temp files after. chmod output dir for container user. |
| `DryRunProcessor` | `EffectProcessorPort` | Records what would be executed, outputs to `OutputPort` without running anything. Validates: input exists, binary found, effect/composite/preset in catalog, output dir writable, container engine available, container image exists. |
| `SubprocessCommandRunner` | `CommandRunnerPort` | `subprocess.run()` with auto-detection of `magick`/`convert` (ImageMagick v6/v7). |
| `DryRunCommandRunner` | `CommandRunnerPort` | Records commands without executing. |
| `OciImageManager` | `ImageManagerPort` | Delegates to `oci-runtime`'s `ContainerEngine.images` (build, remove, exists, pull). Maps oci-runtime exceptions to wallpaper domain exceptions. |
| `JsonOutput` | `OutputPort` | **DEFAULT**. All output is structured JSON. Process result -> `{"success": true, "command": "...", "output_path": "..."}`. Batch result -> `{"total": 10, "succeeded": 8, "failed": 2, "results": [...]}`. Errors -> `{"error": {"type": "...", "message": "..."}}`. LLM-friendly. |
| `RichOutput` | `OutputPort` | Rich library for styled console output. Tables, progress bars, colored text. Human-friendly. |
| `PlainOutput` | `OutputPort` | Simple text lines. No colors, no tables. Pipe-friendly. |
| `TomlSettingsSerializer` | `SettingsSerializerPort` | Converts `AppSettings` -> TOML string. Used by dump-config and ContainerProcessor. |
| `YamlEffectsSerializer` | `EffectsSerializerPort` | Converts `EffectsCatalog` -> YAML string. Used by dump-effects. |

---

## 6. Application Use Cases

| Use Case | Flow |
|----------|------|
| `ProcessEffect` | Resolve catalog -> resolve params (CLI --param overrides via ParameterResolutionService) -> select processor by runtime mode -> delegate to LocalProcessor or ContainerProcessor -> return ProcessingResult |
| `ProcessComposite` | Resolve catalog -> validate chain is non-empty -> select processor -> delegate (processor handles chain internally) -> return ProcessingResult |
| `ProcessPreset` | Resolve catalog -> determine if preset references effect or composite -> delegate accordingly -> return ProcessingResult |
| `ProcessBatch` | Resolve catalog -> enumerate items by type -> compute output paths (with explicit_output) -> execute parallel/sequential -> aggregate BatchResult |
| `InstallImage` | Resolve settings -> locate Dockerfile -> build BuildContext (build_file_path) -> build via OciImageManager -> report. Support --dump-config, --dump-effects post-build. |
| `UninstallImage` | Resolve settings -> if --yes not provided, prompt for confirmation -> remove via OciImageManager -> report. |
| `ShowCatalog` | Resolve catalog -> list effects/composites/presets via OutputPort.catalog_list() |
| `DumpConfig` | Resolve settings -> serialize via SettingsSerializerPort -> output to file or stdout |
| `DumpEffects` | Load catalog -> serialize via EffectsSerializerPort -> output to file or stdout |
| `ShowInfo` | Resolve settings + effects -> display via OutputPort.config_info() (resolved paths, applied overrides, runtime mode, container image availability) |

---

## 7. Config System (config-assembler-engine)

### Design Principle: Single-File Resolution, No Merging

Config-assembler-engine resolves **one** config file through a priority chain and applies opt-in overrides on top. It does NOT merge multiple files. The resolution order is:

**CLI explicit path > ENV path > Directory traversal > XDG > Package default**

Once a file is resolved, all ENV and CLI overrides are applied on top via `OverrideRule`s.

The `__` separator is the universal nesting separator in ENV vars. ENV var names are case-sensitive (must be uppercase). After the prefix `WALLPAPER__` is stripped, any remaining `__` becomes a `.` in the field path:

| ENV Var | After strip | After `__` -> `.` | Matches Rule |
|---------|-------------|---------------------|--------------|
| `WALLPAPER__CONTAINER__ENGINE=podman` | `container__engine` | `container.engine` | `OverrideRule("container.engine", {ENV})` |
| `WALLPAPER__VERSION=2.0` | `version` | `version` | `OverrideRule("version", {ENV})` |
| `WALLPAPER__OUTPUT__DIRECTORY=/tmp/out` | `output__directory` | `output.directory` | `OverrideRule("output.directory", {ENV})` |

Flat field names use single underscore `_`:
| `WALLPAPER__CONTAINER_ENGINE=podman_flat` | `container_engine` | `container_engine` | `OverrideRule("container_engine", {ENV})` |

Config file path env vars use single `_` between prefix and `CONFIG_FILE_PATH`:
- Settings: `WALLPAPER_CONFIG_FILE_PATH`
- Effects: `WALLPAPER_EFFECTS_CONFIG_FILE_PATH`

### Settings (TOML)

```
Prefix: WALLPAPER
Default file: package-bundled settings.toml
Strategies: CliPath -> EnvPath(WALLPAPER_CONFIG_FILE_PATH) -> XdgStrategy(weg) -> DefaultFileStrategy(package defaults)
Parser: TomlConfigParser
Schema: CoreSettingsSchema (Pydantic)

OverrideRules:
  - execution.parallel        -> ENV, CLI
  - execution.strict          -> ENV, CLI
  - execution.max_workers    -> ENV, CLI
  - output.verbosity          -> ENV, CLI
  - output.directory          -> ENV, CLI
  - backend.binary            -> ENV, CLI
  - runtime.mode               -> ENV, CLI   (local | container); Pydantic @field_validator enforces these values
  - container.engine           -> ENV, CLI   (docker | podman); Pydantic @field_validator enforces these values
  - container.image_tag       -> ENV, CLI
  - container.image_registry  -> ENV, CLI

ENV vars (examples):
  WALLPAPER__EXECUTION__PARALLEL=false
  WALLPAPER__RUNTIME__MODE=container
  WALLPAPER__CONTAINER__ENGINE=podman
  WALLPAPER_CONFIG_FILE_PATH=/custom/path.toml
```

### Effects (YAML)

```
Prefix: WALLPAPER_EFFECTS
Default file: package-bundled effects.yaml
Strategies: CliPath -> EnvPath(WALLPAPER_EFFECTS_CONFIG_FILE_PATH) -> XdgStrategy(weg) -> DefaultFileStrategy(package defaults)
Parser: YamlConfigParser
Schema: EffectsConfigSchema (Pydantic)

No override rules -- effects content is not overridable via ENV.
Effects are defined in YAML files, not via env vars.

ENV vars:
  WALLPAPER_EFFECTS_CONFIG_FILE_PATH=/custom/effects.yaml
```

### Two Separate Assembler Instances

Settings and effects each get their own `AssembleConfiguration` instance:

| Aspect | Settings | Effects |
|--------|----------|---------|
| Parser | `TomlConfigParser` | `YamlConfigParser` |
| Prefix | `WALLPAPER` | `WALLPAPER_EFFECTS` |
| File path env var | `WALLPAPER_CONFIG_FILE_PATH` | `WALLPAPER_EFFECTS_CONFIG_FILE_PATH` |
| XDG subdir | `weg` | `weg` |
| Default filename | `settings.toml` | `effects.yaml` |
| Override rules | Scalar settings (parallel, runtime mode, engine, etc.) | None |
| Schema | `CoreSettingsSchema` | `EffectsConfigSchema` |

---

## 8. Container Execution Flow

### Design Principle: Pre-Resolved Config, No Double Resolution

Config resolution happens **once** on the host. The container receives the final, resolved result. This avoids ENV forwarding, ENV divergence between host and container, and complex path rewriting.

### Why we serialize settings but not effects

**Settings (TOML):** The host resolves a path, reads the file, then **applies ENV + CLI overrides on top**. The final `AppSettings` is a *computed* result that doesn't exist as a file anywhere on disk. We serialize it to a temp TOML so the container can read the final values via `--config` (which hits `CliPathStrategy` -> highest priority).

**Effects (YAML):** The host only **resolves which file to read** (path resolution via config-assembler-engine). No ENV/CLI overrides are applied to effects content. The resolved path points to an **existing file on disk** that's complete as-is. We mount it directly.

### Flow

```
HOST:
  1. Resolve settings via AssembledConfigResolver -> AppSettings + resolved settings path
  2. Resolve effects via YamlEffectLoader -> EffectsCatalog + resolved effects path
  3. If RuntimeMode.CONTAINER:
     a. Check image availability via engine.images.exists(image_name)
        - If not found: raise ContainerImageNotFoundError (suggest: run install)
        - Use RuntimeFactory.create(RuntimePreference(kind, binary)) to get engine
        - Note: `exists()` then `run()` is not atomic. Handle `ImageNotFoundError`
          from `run()` by pulling and retrying once, or letting it propagate as
          `ContainerImageNotFoundError`.
     b. Serialize AppSettings -> temp TOML file
     c. chmod output dir to 0o777 (for container non-root user)
      d. Build mount plan:
         - Input parent dir       -> /input                      (RO, VolumeMountType.BIND)
           Note: `os.path.realpath()` resolves input path first. If parent dir is `/`,
           error out — mounting the entire root filesystem is unsafe.
         - Output dir             -> /output                     (RW, VolumeMountType.BIND)
           Note: create dir via `Path.mkdir(parents=True, exist_ok=True)` if absent.
           `os.path.realpath()` resolves before mounting to prevent symlink escapes.
         - Temp settings TOML    -> /weg-config/settings.toml   (RO, VolumeMountType.BIND)
         - Resolved effects dir  -> /weg-effects                (RO, VolumeMountType.BIND)
     e. Build RunConfig:
        - image: wallpaper-effects:latest
        - command: ("process", "effect", "blur", "/input/photo.jpg",
                    "--config", "/weg-config/settings.toml",
                    "--effects", "/weg-effects/effects.yaml",
                    "-o", "/output")
        - volumes: tuple of VolumeMount objects (NOT list)
        - ports: () (no port mappings needed)
        - remove: True
        - detach: False
        - stream_output: False (JSON mode prints final result only; use True only for Rich output)
        - timeout: 3600 (configurable, default 1h prevents infinite hangs)
     f. engine.containers.run(run_config)
     g. Clean up temp TOML (use try/finally or context manager to ensure cleanup on exception)
  4. If RuntimeMode.LOCAL:
     a. Use LocalProcessor with resolved AppSettings and EffectsCatalog
```

No ENV forwarding. No double-resolution divergence. The container receives pre-resolved config and original effects file.

### Mount Table

| Host Resource | Container Path | Mode | When |
|---------------|---------------|------|------|
| Input file's parent dir | `/input` | RO | Always |
| Output directory | `/output` | RW | Always (chmod 0o777 first) |
| Pre-resolved settings TOML | `/weg-config/settings.toml` | RO | Always |
| Resolved effects file | `/weg-effects/effects.yaml` | RO | Always |

### Which Commands Run Where

| Command | Runs where | Reason |
|---------|-----------|--------|
| `process` (effect/composite/preset) | Local OR Container | Only thing that needs ImageMagick |
| `batch` (effects/composites/presets/all) | Local OR Container | Only thing that needs ImageMagick |
| `show` | Always local | Just reads the effects catalog |
| `dump-config` | Always local | Just reads settings |
| `dump-effects` | Always local | Just reads effects.yaml |
| `info` | Always local | Just reads config |
| `version` | Always local | Just prints version |
| `install` | Always local | Runs `docker build` on host |
| `uninstall` | Always local | Runs `docker rmi` on host |

The runtime mode (`--runtime local|container`) only affects `process` and `batch`. It is resolved via `runtime.mode` in AppSettings (default: "local").

---

## 9. CLI Structure

```
wallpaper-effects-generator
  process
    effect <name> <input> [-e effect] [-o output] [--flat] [--dry-run] [--param key=value...]
    composite <name> <input> [-c composite] [-o output] [--flat] [--dry-run]
    preset <name> <input> [-p preset] [-o output] [--flat] [--dry-run]
  batch
    effects <input> [-o dir] [--flat] [--parallel|--sequential] [--strict|--no-strict] [--dry-run]
    composites <input> ...
    presets <input> ...
    all <input> ...
  show
    effects
    composites
    presets
    all
  install [--engine docker|podman] [--dry-run] [--dump-config] [--dump-effects]
  uninstall [--engine docker|podman] [--yes] [--dry-run]
  dump-config
  dump-effects
  info
  version

Global: -q/--quiet, -v/--verbose, --output json|rich|plain, --effects PATH, --config PATH, --runtime local|container
```

- `--output json|rich|plain` (default: `json`) — controls output format. JSON is default for LLM-friendliness.
- `--runtime local|container` maps to `runtime.mode` in AppSettings via CLI override.
- `--param key=value` is repeatable and passes effect parameter overrides to ParameterResolutionService.
  - Duplicate keys: last value wins (no merge).
  - Value containing `=`: split on first `=` only.
  - Non-existent parameter: gracefully ignored with a warning (not an error, for forward compat).
  - Coercion failure (e.g., `--param radius=abc` when `radius` expects `float`): raises `ConfigValidationError` with a clear message.
- `-q`/`-v` control verbosity, mapped to `output.verbosity` via CLI override or handled in CLI adapter directly.

---

## 10. Package Structure

```
wallpaper-effects-generator/
  pyproject.toml
  Makefile
  .python-version
  src/wallpaper_effects_generator/
    __init__.py
    errors.py
    factory.py
    domain/
      __init__.py
      enums.py
      models.py
      services.py
      exceptions.py
    ports/
      __init__.py
      effect_loader.py
      config_resolver.py
      command_runner.py
      processor.py
      image_manager.py
      output.py
      serializers.py
    application/
      __init__.py
      use_cases.py
    adapters/
      __init__.py
      schemas/
        __init__.py
        effects_schema.py
        settings_schema.py
      yaml_effect_loader.py
      assembled_config_resolver.py
      local_processor.py
      container_processor.py
      dry_run_processor.py
      subprocess_runner.py
      dry_run_runner.py
      oci_image_manager.py
      output/
        __init__.py
        json_output.py
        rich_output.py
        plain_output.py
      serializers/
        __init__.py
        toml_settings_serializer.py
        yaml_effects_serializer.py
      docker/
        __init__.py
        Dockerfile.imagemagick
    defaults/
      effects.yaml
      settings.toml
    cli/
      __init__.py
      main.py
      process.py
      batch.py
      show.py
      install.py
      uninstall.py
      dump_config.py
      dump_effects.py
      info.py
      version.py
  tests/
    unit/domain/
    unit/ports/
    unit/application/
    unit/adapters/
    integration/
    helpers/
    fixtures/
```

---

## 11. Dependencies

| Dependency | Purpose | Source |
|------------|---------|--------|
| `config-assembler-engine` | Settings + effects file resolution (single-file + overrides) | workspace |
| `oci-runtime` >= 0.3.0 | Container image build/run/remove | workspace |
| `pydantic` >= 2.0 | Schema validation for effects.yaml and settings.toml | PyPI |
| `pyyaml` >= 6.0 | Effects YAML parsing | PyPI |
| `typer[all]` >= 0.9.0 | CLI framework | PyPI |
| `rich` >= 13.0 | Terminal output (rich output adapter only) | PyPI |
| `tomli-w` or manual | TOML serialization for dump-config and ContainerProcessor | PyPI |

---

## 12. oci-runtime v0.3.0 API Surface (Validated)

### Engine Creation

```python
from oci_runtime import RuntimeFactory, RuntimePreference, RuntimeKind

factory = RuntimeFactory()
available = factory.available()  # list[RuntimePreference] (informational only)
engine = factory.create(RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"))
# No fallback. Raises RuntimeNotAvailableError if binary not found.
# Call engine.is_available() to probe.
```

### Key Types (all frozen dataclasses)

| Type | Key Fields | Constraints |
|------|-----------|-------------|
| `VolumeMount` | source, target, type, read_only | `type` must be `VolumeMountType` enum (BIND/VOLUME/TMPFS). Non-TMPFS requires `source`. |
| `PortMapping` | container_port, host_ip, host_port, protocol | `host_ip` is **required** (pass None explicitly). `container_port` 1-65535. |
| `BuildContext` | build_file_path XOR build_file_content, context_path XOR files, build_args, labels, build_contexts, target, no_cache, pull, rm | Mutually exclusive pairs enforced in `__post_init__`. |
| `RunConfig` | image, command (tuple), volumes (tuple), ports (tuple), environment (dict), network, restart_policy, detach, remove, stream_output, timeout, runtime_flags (tuple), tty, auto_tty, stdin_open, user, working_dir, hostname, labels, log_driver, privileged, read_only, memory_limit, cpu_limit | `detach=True` mutually exclusive with `tty`/`auto_tty`. `timeout` must be positive. All sequences frozen to tuples. |

### Exception Hierarchy

```
OciError (message, command, exit_code, stderr)
+-- ContainerError
|   +-- ContainerNotFoundError (container_id)
|   +-- ContainerRuntimeError
+-- ImageError
|   +-- ImageNotFoundError (image_name)
|   +-- ImagePullAccessDeniedError (image_name, registry)
|   +-- ImageRuntimeError
+-- VolumeError / NetworkError / etc.
+-- RuntimeNotAvailableError (runtime)
+-- OperationTimeoutError (command, timeout)
+-- ProviderNotRegisteredError (kind)
+-- ParsingError (raw)
```

### ContainerManager.run() Dispatch

| Mode | Flag Combination | Transport | Returns |
|------|------------------|-----------|---------|
| TTY | `effective_tty=True` | `PtyTransport.execute_pty()` | `""` (output goes to OutputStream) |
| Streaming | `stream_output=True`, no TTY | `StreamingTransport.stream()` with callbacks | Stripped stdout |
| Batched | `stream_output=False`, no TTY, `detach=False` | `StreamingTransport.stream()` no callbacks | Stripped stdout |
| Detached | `detach=True` | `Transport.execute()` | Container ID |

### H3, Q1, C3: All Resolved

- **H3**: `TestImagePullAuthErrors` in `tests/unit/boundary/test_error_conditions.py` — real `DockerImageParser` + "pull access denied" stderr -> `ImagePullAccessDeniedError`. FIXED.
- **Q1**: GIL-dependent concurrency tests removed. Replaced with `test_concurrent_factory_create` testing factory thread-safety. `RecordingTransport` documents it's not thread-safe. FIXED.
- **C3**: `stream_output=True` always takes streaming branch. Internal `_write` closure with None-check. No outer guard. Matches design. FIXED.

---

## 13. Key Architectural Decisions

### ADR-001: Single-File Config Resolution (No Merging)

The old tool used `layered-settings` to merge multiple config files (package defaults, project-level, user-level). The new tool uses `config-assembler-engine` for single-file resolution with opt-in overrides. Rationale: merging creates ambiguity about which value wins and makes debugging harder. Single-file resolution with explicit override rules is deterministic and auditable.

### ADR-002: Domain Port for Processing (Not CLI Proxy)

The old tool used `transparent-orchestrator` to intercept CLI commands and re-route them into containers via mount hooks and Click proxy groups. The new tool defines an `EffectProcessorPort` with two implementations: `LocalProcessor` (host) and `ContainerProcessor` (OCI). Rationale: the domain decides *what* to process; the adapter decides *where* to process it. No coupling to CLI frameworks.

### ADR-003: Pre-Resolved Config for Containers

Instead of forwarding ENV vars and hoping the container resolves identically, we serialize the resolved `AppSettings` to a temp TOML and mount it. The container's `--config` flag uses `CliPathStrategy` (highest priority), guaranteeing identical configuration. Rationale: eliminates an entire class of ENV divergence bugs and removes the need for ENV forwarding/filtering logic.

### ADR-004: Original Effects File Mounted As-Is

Effects files are not overridden via ENV vars, so the resolved effects.yaml on disk is complete and unmodified. We mount it directly rather than serializing a copy. Rationale: avoids unnecessary temp files and preserves the exact effects content.

### ADR-005: Explicit ContainerProcessor Commands

Each command the `ContainerProcessor` handles has typed domain inputs/outputs. There is no "run any CLI command in a container" capability. Rationale: explicit is better than implicit. No fragile CLI string interception or Typer/Click internals coupling. New container commands are added deliberately to the adapter.

### ADR-006: Runtime Mode vs Container Engine (Orthogonal Settings)

`runtime.mode` (local/container) decides WHERE to process. `container.engine` (docker/podman) decides WHICH OCI runtime. These are separate settings in AppSettings, each with their own OverrideRule. The old tool conflated these into a single `container.engine` field. Rationale: a user might want podman as their engine but still process locally, or use docker while processing in a container.

### ADR-007: JSON-First Output (LLM-Friendly Default)

The default output format is **structured JSON**, not Rich human-friendly output. A `--output json|rich|plain` flag selects the format. Rationale: the primary consumer of CLI output in modern workflows includes LLMs and automation tools that need structured data. The `OutputPort` takes domain objects (not strings) and each adapter renders them. This inverts the old tool's design where Rich was the only output mode.

### ADR-008: oci-runtime v0.3.0 as Foundation

The wallpaper tool depends on `oci-runtime` >= 0.3.0 which has resolved all known issues (H3, Q1, C3). The factory pattern, frozen dataclass types, and explicit error hierarchy are fully adopted. No workarounds or custom wiring needed beyond the standard `RuntimeFactory.create()` flow.

---

## 14. Resolved Decisions

All open items have been discussed and decided:

1. **Dry-run**: Full validation + commands. Pre-flight checks (input exists, binary found, effect in catalog, container engine available, container image exists) AND resolved command rendering (ImageMagick commands, chain commands, batch table, container run command with mounts). All via OutputPort.

2. **`--param` coercion**: Reuse `PydanticTypeCoercer` from config-assembler-engine. The CLI adapter passes raw string values; the coercer converts to the target type from `ParameterType` in the effects schema. Consistent with ENV override coercion. No changes to config-assembler-engine needed.

3. **`--show-config` flag**: DROPPED. The `info` command covers config attribution display. No per-command `--show-config` flag. Users who want config details run `info` separately.

4. **Verbosity flags**: Through config-assembler-engine as an `OverrideRule("output.verbosity", {ENV, CLI})`. The CLI flag `-v` (count) maps to `cli_overrides={"output.verbosity": "2"}`, `-q` maps to `"0"`. No changes to config-assembler-engine needed — OverrideRules + CLI overrides + type coercion already exist.

5. **ContainerSettings validation**: Pydantic `@field_validator` on `ContainerSettingsSchema` in `adapters/schemas/settings_schema.py`. Validates `engine` is "docker" or "podman". Strips trailing slashes from `image_registry`. Invalid values fail at config resolution time as `ConfigValidationError`.

6. **`image_registry` default**: `None` (not empty string). `image_registry: str | None = None` in both the Pydantic schema and the domain dataclass. Truthy check `if settings.container.image_registry:` works for both None and "".

7. **TOML serializer**: Use `tomli-w` library. Added as a dependency. Handles nested dicts, arrays, booleans, None values. Used by `dump-config` command and `ContainerProcessor` (temp TOML for pre-resolved config).

8. **Container dry-run**: Show full `docker run` command with volumes and flags AND the inner command. Also render mount mappings as a structured table/list. Most useful for debugging.

9. **Timeout handling**: Batch operations use `RunConfig.timeout` (configurable via settings, default None = no timeout). `OperationTimeoutError` from oci-runtime is caught and rendered via `OutputPort.error()` with command + timeout details.

10. **JSON progress**: Final result only, no streaming. Batch operations print nothing during processing. After completion, a single JSON object with full results is printed. `RunConfig.stream_output=False` in JSON mode. `stream_output=True` only for `--output rich` mode._PROGRESS bars only appear in `--output rich` mode._

11. **Chain execution in ContainerProcessor**: Confirmed — the container handles chains internally via `process composite <name>`. No special temp-file handling from the host. The container's own CLI manages the chain through temp files inside the container filesystem.

12. **`explicit_output` flag**: Keep old behavior. `flat=True + explicit_output=True` -> `output_dir/item_name.ext` (no stem subdir). `flat=True + explicit_output=False` -> `output_dir/input_stem/item_name.ext`. `flat=False` -> `output_dir/input_stem/type_subdir/item_name.ext`. `explicit_output=True` is only valid when `-o` is provided; otherwise, `ProcessingRequest.output_path` is `None` and `explicit_output` is ignored (treated as `False`).

13. **Container Dockerfile**: `python:3.14-alpine` base + ImageMagick via `apk`. Non-root `wallpaper` user (UID 1000). `/input` and `/output` mount points. Install wallpaper-effects-generator via `uv pip install --system`.

14. **install --dump-config / --dump-effects**: Keep both flags. After building the image, optionally write default settings.toml and effects.yaml to the user's XDG config directory (`~/.config/weg/`). Creates the directory via `Path.mkdir(parents=True, exist_ok=True)` if absent. Requires `--overwrite` to replace existing files.

---

## 15. Default Config Files

### settings.toml (package defaults)

```toml
version = "1.0"

[execution]
parallel = true
strict = true
max_workers

[output]
verbosity = 1
directory = "/tmp/wallpaper-effects"

[processing]
temp_dir = "/tmp/.wallpaper-effects-tmp"

[backend]
binary = "magick"

[runtime]
mode = "local"

[container]
engine = "docker"
image_tag = "latest"
image_registry = ""
```

### effects.yaml (package defaults)

Same effect definitions as old tool (blur, blackwhite, negate, brightness, contrast, saturation, sepia, vignette, color_overlay, composites, presets). See section 1 for the full schema.

---

## 16. Dependency Versions

| Dependency | Version Constraint | Purpose |
|------------|-------------------|---------|
| `config-assembler-engine` | workspace (>= 0.1.0) | Config resolution |
| `oci-runtime` | workspace (>= 0.3.0) | Container management |
| `pydantic` | >= 2.0 | Schema validation |
| `pyyaml` | >= 6.0 | YAML parsing |
| `typer[all]` | >= 0.9.0 | CLI framework |
| `rich` | >= 13.0 | Rich output adapter |
| `tomli-w` | >= 1.0 | TOML serialization |