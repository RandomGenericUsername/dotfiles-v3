# Architecture Plan: wallpaper-effects-generator v3

## Hexagonal architecture redesign of the wallpaper effects processing CLI tool.

---

## 1. Domain Models (pure, frozen dataclasses, zero I/O)

| Model | Purpose |
|-------|---------|
| `ItemType` enum | EFFECT / COMPOSITE / PRESET, with `subdir_name` |
| `Verbosity` enum | QUIET / NORMAL / VERBOSE / DEBUG |
| `RuntimeMode` enum | LOCAL / CONTAINER |
| `ParameterType` | Reusable param type definition (type, pattern, min/max, default) |
| `ParameterDefinition` | Effect param definition (type ref, cli_flag, default, description) |
| `EffectDefinition` | Atomic effect: name, description, command template, parameters |
| `ChainStep` | Composite chain step: effect name + params |
| `CompositeDefinition` | Composite: name, description, chain |
| `PresetDefinition` | Preset: name, description, XOR composite/effect, params |
| `EffectsCatalog` | Root aggregate: version, parameter_types, effects, composites, presets |
| `ProcessingRequest` | input_path, output_path, runtime_mode |
| `ProcessingResult` | success, command, stdout, stderr, return_code, duration |
| `BatchRequest` | input_path, output_dir, item_types, flat, parallel, strict, max_workers, runtime_mode |
| `BatchResult` | total, succeeded, failed, results map, output_dir |
| `AppSettings` | version, execution, output, processing, backend, container |
| `ExecutionSettings` | parallel, strict, max_workers |
| `OutputSettings` | verbosity, directory |
| `ProcessingSettings` | temp_dir |
| `BackendSettings` | binary |
| `ContainerSettings` | engine, image_tag, image_registry |

---

## 2. Domain Services (pure logic, @staticmethod, zero I/O)

| Service | Responsibility |
|---------|----------------|
| `CommandSubstitutionService` | Substitute `$INPUT`, `$OUTPUT`, `$PARAM` in command templates |
| `ParameterResolutionService` | Resolve param values: explicit overrides -> effect defaults -> parameter_type defaults |
| `OutputPathService` | Compute output file paths from base_dir, item name, type, flat flag |
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
+-- ConfigResolutionError
```

---

## 4. Ports (Protocol classes)

| Port | Methods | Direction |
|------|---------|-----------|
| `EffectLoaderPort` | `load(path=None) -> EffectsCatalog`, `get_default_path() -> Path` | Inbound |
| `ConfigResolverPort` | `resolve(explicit_path=None) -> AppSettings` | Inbound |
| `CommandRunnerPort` | `is_available(binary=None) -> bool`, `get_binary() -> str`, `execute(command, timeout=None) -> CommandResult` | Outbound |
| `EffectProcessorPort` | `process_effect()`, `process_composite()`, `process_preset()`, `process_batch()` | Core |
| `ImageManagerPort` | `build()`, `remove()`, `exists() -> bool` | Outbound |
| `OutputPort` | `info()`, `error()`, `debug()`, `command()`, `progress()` | Outbound |

---

## 5. Adapters

| Adapter | Implements | Key Behavior |
|---------|------------|-------------|
| `YamlEffectLoader` | `EffectLoaderPort` | Uses config-assembler-engine with `YamlConfigParser` + strategies to resolve effects.yaml. Parses YAML, validates via `EffectsConfigSchema` (Pydantic), converts to domain `EffectsCatalog`. Returns resolved path. |
| `AssembledConfigResolver` | `ConfigResolverPort` | Uses config-assembler-engine with `TomlConfigParser` + strategies to resolve settings.toml. Applies OverrideRules for ENV+CLI. Returns domain `AppSettings`. Also returns resolved path (needed for container mount). |
| `LocalProcessor` | `EffectProcessorPort` | Runs ImageMagick via `CommandRunnerPort`. Single effects, chains via temp files, batch via ThreadPoolExecutor. |
| `ContainerProcessor` | `EffectProcessorPort` | Serializes resolved `AppSettings` -> temp TOML, resolves effects file path, builds mount plan (input, output, config, effects), constructs container command, runs via `oci-runtime`'s `ContainerEngine.containers.run()`. Cleans up temp files after. |
| `DryRunProcessor` | `EffectProcessorPort` | Records what would be executed, outputs to `OutputPort` without running anything. |
| `SubprocessCommandRunner` | `CommandRunnerPort` | `subprocess.run()` with auto-detection of `magick`/`convert`. |
| `DryRunCommandRunner` | `CommandRunnerPort` | Records commands without executing. |
| `OciImageManager` | `ImageManagerPort` | Delegates to `oci-runtime`'s `ContainerEngine.images` (build, remove, exists). |
| `RichOutput` | `OutputPort` | Rich library for styled console output. |
| `QuietOutput` | `OutputPort` | Suppresses all non-error output. |
| `DryRunOutput` | `OutputPort` | Captures output for dry-run display. |

---

## 6. Application Use Cases

| Use Case | Flow |
|----------|------|
| `ProcessEffect` | Resolve catalog -> resolve params -> check runtime mode -> delegate to LocalProcessor or ContainerProcessor |
| `ProcessComposite` | Resolve catalog -> iterate chain -> pipe via temp files -> delegate to processor |
| `ProcessPreset` | Resolve catalog -> delegate to ProcessEffect or ProcessComposite based on preset type |
| `ProcessBatch` | Resolve catalog -> enumerate items -> compute output paths -> execute parallel/sequential -> aggregate results |
| `InstallImage` | Resolve settings -> locate Dockerfile -> build via OciImageManager -> report |
| `UninstallImage` | Resolve settings -> remove via OciImageManager -> report |
| `ShowCatalog` | Resolve catalog -> list effects/composites/presets |
| `DumpConfig` | Resolve settings -> serialize to TOML |
| `DumpEffects` | Load catalog -> serialize to YAML |

---

## 7. Config System (config-assembler-engine)

### Design Principle: Single-File Resolution, No Merging

Config-assembler-engine resolves **one** config file through a priority chain and applies opt-in overrides on top. It does NOT merge multiple files. The resolution order is:

**CLI explicit path > ENV path > Directory traversal > XDG > Package default**

Once a file is resolved, all ENV and CLI overrides are applied on top via `OverrideRule`s.

The `__` separator is the universal nesting separator in ENV vars. After the prefix `WALLPAPER__` is stripped, any remaining `__` becomes a `.` in the field path:

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
  - execution.parallel     -> ENV, CLI
  - execution.strict       -> ENV, CLI
  - execution.max_workers  -> ENV, CLI
  - output.verbosity       -> ENV, CLI
  - output.directory       -> ENV, CLI
  - backend.binary         -> ENV, CLI
  - container.engine        -> ENV, CLI
  - container.image_tag    -> ENV, CLI
  - container.image_registry -> ENV, CLI

ENV vars (examples):
  WALLPAPER__EXECUTION__PARALLEL=false
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
| Override rules | Scalar settings (parallel, engine, etc.) | None |
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
     a. Serialize AppSettings -> temp TOML file
     b. Build mount plan:
        - Input parent dir       -> /input                      (RO)
        - Output dir             -> /output                     (RW)
        - Temp settings TOML    -> /weg-config/settings.toml   (RO)
        - Resolved effects dir  -> /weg-effects                (RO)
     c. Build RunConfig:
        - image: wallpaper-effects:latest
        - command: ["process", "effect", "blur", "/input/photo.jpg",
                    "--config", "/weg-config/settings.toml",
                    "--effects", "/weg-effects/effects.yaml",
                    "-o", "/output"]
        - mounts: above
        - remove: True, detach: False
     d. engine.containers.run(run_config)
     e. Clean up temp TOML
  4. If RuntimeMode.LOCAL:
     a. Use LocalProcessor with resolved AppSettings and EffectsCatalog
```

No ENV forwarding. No double-resolution divergence. The container receives pre-resolved config and original effects file.

### Mount Table

| Host Resource | Container Path | Mode | When |
|---------------|---------------|------|------|
| Input file's parent dir | `/input` | RO | Always |
| Output directory | `/output` | RW | Always |
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

The runtime mode (`--runtime local|container`) only affects `process` and `batch`. It is resolved via `container.engine` in AppSettings (default: "local").

---

## 9. CLI Structure

```
wallpaper-effects-generator
  process
    effect <name> <input> [-o output] [--flat] [--dry-run]
    composite <name> <input> [-o output] [--flat] [--dry-run]
    preset <name> <input> [-o output] [--flat] [--dry-run]
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

Global: -q/--quiet, -v/--verbose, --effects PATH, --config PATH, --runtime local|container
```

`--runtime` maps to `container.engine` in AppSettings as a CLI override. When `local`, uses `LocalProcessor`. When `container`, uses `ContainerProcessor`.

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
    application/
      __init__.py
      use_cases.py
    adapters/
      __init__.py
      schemas/
        __init__.py
        effects_schema.py
      yaml_effect_loader.py
      assembled_config_resolver.py
      local_processor.py
      container_processor.py
      dry_run_processor.py
      subprocess_runner.py
      dry_run_runner.py
      oci_image_manager.py
      rich_output.py
      quiet_output.py
      serializers/
        __init__.py
        settings_serializer.py
        effects_serializer.py
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
| `oci-runtime` | Container image build/run/remove | workspace |
| `pydantic` >= 2.0 | Schema validation for effects.yaml and settings.toml | PyPI |
| `pyyaml` >= 6.0 | Effects YAML parsing | PyPI |
| `typer[all]` >= 0.9.0 | CLI framework | PyPI |
| `rich` >= 13.0 | Terminal output | PyPI |

---

## 12. Key Architectural Decisions

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

### ADR-006: Runtime Mode as AppSettings Field

`--runtime local|container` is not a separate concept. It maps to the `container.engine` setting (values: "local", "container") via an OverrideRule. Rationale: unified configuration pipeline. The runtime mode can be set via settings.toml, ENV var (`WALLPAPER__CONTAINER__ENGINE=container`), or CLI flag, all going through config-assembler-engine.