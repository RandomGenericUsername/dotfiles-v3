---
baseline_commit: d99517b198334f305fb525d560c9d121482dd5af
---

# Story 1.2: Config Resolution & CLI Wiring

Status: in-progress

## Story

As a developer,
I want the full settings and effects resolution chain wired via CLI,
So that config file discovery, override application, and source attribution work from the command line.

## Acceptance Criteria

### AC1: Default path resolution
Given a settings file at a default path
When the CLI runs without `--config` or env overrides
Then it resolves settings via traversal/XDG/default strategy
And `info` shows the resolved source path and attribution

### AC2: CLI explicit path wins
Given a `--config /path/to/custom.yaml` CLI flag
When the CLI runs
Then the explicit path wins resolution over all other strategies
And the resolved source attribution reports `CLI_PATH`

### AC3: ENV path resolution
Given an ENV var `WEG_CONFIG_FILE_PATH=/env/path/config.yaml`
When the CLI runs without `--config`
Then the ENV path wins over traversal/XDG/default
And the resolved source attribution reports `ENV_PATH`

### AC4: Effects file-source immutability
Given an effects file at a resolved path
When effects are loaded
Then the content matches the file exactly (no ENV/CLI scalar overrides applied)
And `dump-effects` outputs the resolved effects catalog

### AC5: ENV override coercion
Given an override rule declared for `settings.timeout`
When `WEG__SETTINGS__TIMEOUT=60` is set
Then the ENV override is applied and coerced to `int`
And the final config has `timeout=60`

### AC6: CLI override precedence
Given an override rule declared for `settings.timeout`
When `--param settings.timeout=30` is passed via CLI
Then the CLI override is applied and takes precedence over any ENV value for the same field

## Tasks / Subtasks

- [ ] Implement Pydantic schemas for settings and effects (AC: 1-6)
  - [ ] CoreSettingsSchema for settings.toml validation
  - [ ] EffectsConfigSchema for effects.yaml validation
- [ ] Implement AssembledConfigResolver adapter (AC: 1-3, 5-6)
  - [ ] Uses config-assembler-engine's AssembleConfiguration
  - [ ] TomlConfigParser for settings
  - [ ] ResolutionPolicy with WALLPAPER prefix
  - [ ] OverrideRules for all declared settings fields
  - [ ] Implements ConfigResolverPort
- [ ] Implement YamlEffectLoader adapter (AC: 4)
  - [ ] Uses config-assembler-engine with YamlConfigParser
  - [ ] No override rules (effects are file-source only)
  - [ ] YamlConfigParser for effects
  - [ ] Converts parsed data to domain EffectsCatalog
  - [ ] Implements EffectLoaderPort
- [ ] Set up CLI framework with Typer (AC: 1-6)
  - [ ] Global flags: --config, --effects, --output, --runtime
  - [ ] Global flags: -q/--quiet, -v/--verbose
  - [ ] info command showing resolved config source paths
  - [ ] dump-config command showing full resolved config
  - [ ] dump-effects command showing resolved effects catalog
- [ ] Wire CLI to adapters (AC: 1-6)
  - [ ] CLI --config maps to AssembledConfigResolver explicit_path
  - [ ] CLI --effects maps to YamlEffectLoader explicit_path
  - [ ] Override rules wired to env reader and CLI params

## Dev Notes

### Previous Story Learnings (Story 1.1)
- Domain models are frozen dataclasses (not Pydantic BaseModel). Exception: AppSettings domain models use frozen dataclasses too.
- Pydantic schemas live in `adapters/schemas/` layer, not domain.
- EffectProcessorPort has 4 separate methods (process_effect, process_composite, process_preset, process_batch) — runtime-agnostic.
- Config-assembler-engine's AssembleConfiguration.execute() API: `execute(policy, rules, schema, cli_overrides, explicit_path)` returns `AssemblyResult`.
- ResolutionPolicy takes env_prefix: str (settings use "WALLPAPER", effects use "WALLPAPER_EFFECTS").
- OverrideSource.ENV < OverrideSource.CLI (CLI wins in sorting).
- Escape shell values in domain services (shell injection guard applied in 1.1).
- All existing tests: 63 unit tests pass after code review.

### Adapter Architecture (from ARCHITECTURE_PLAN.md §5)

**AssembledConfigResolver** (implements ConfigResolverPort):
```
ConfigResolverPort.resolve(explicit_path=None) -> AppSettings
```
- Uses config-assembler-engine with TomlConfigParser
- ResolutionPolicy(env_prefix="WALLPAPER")
- Strategies: CliPath -> EnvPath -> XdgStrategy("weg") -> DefaultFileStrategy
- OverrideRules: execution.parallel, execution.strict, execution.max_workers, output.verbosity, output.directory, backend.binary, runtime.mode, container.engine, container.image_tag, container.image_registry
- Sources for all rules: {ENV, CLI}
- Returns domain AppSettings (frozen dataclass, converted from pydantic schema)

**YamlEffectLoader** (implements EffectLoaderPort):
```
EffectLoaderPort.load(path=None) -> EffectsCatalog
```
- Uses config-assembler-engine with YamlConfigParser
- ResolutionPolicy(env_prefix="WALLPAPER_EFFECTS")
- Strategies: CliPath -> EnvPath -> XdgStrategy("weg") -> DefaultFileStrategy
- NO override rules (effects are file-source only)
- Returns domain EffectsCatalog (frozen dataclass)

### Config System Details (from ARCHITECTURE_PLAN.md §7)

Settings (TOML):
- Prefix: WALLPAPER
- Default file: package-bundled settings.toml
- Parser: TomlConfigParser
- Schema: CoreSettingsSchema (Pydantic)
- ENV path var: WALLPAPER_CONFIG_FILE_PATH
- ENV separator: WALLPAPER__ (double underscore), remaining __ becomes . in field path
  - WALLPAPER__CONTAINER__ENGINE=podman → container__engine → container.engine
- OverrideRules for all declared fields

Effects (YAML):
- Prefix: WALLPAPER_EFFECTS
- Default file: package-bundled effects.yaml
- Parser: YamlConfigParser
- Schema: EffectsConfigSchema (Pydantic)
- ENV path var: WALLPAPER_EFFECTS_CONFIG_FILE_PATH
- No override rules — effects content is not overridable via ENV

Two separate AssembleConfiguration instances: one for settings, one for effects.

### Pydantic Schemas (from ARCHITECTURE_PLAN.md §7)

CoreSettingsSchema (TOML):
- version: str
- execution.parallel: bool, execution.strict: bool, execution.max_workers: int
- output.verbosity: int, output.directory: str
- processing.temp_dir: str
- backend.binary: str
- runtime.mode: str (local|container)
- container.engine: str (docker|podman), container.image_tag: str, container.image_registry: Optional[str]

EffectsConfigSchema (YAML):
- version: str
- parameter_types: dict[str, ParameterTypeSchema]
- effects: list[EffectSchema]
- composites: list[CompositeSchema]
- presets: list[PresetSchema]

ContainerSettings validation: @field_validator on engine (docker|podman), strip trailing slashes from image_registry.

### Package Structure Changes
```
src/cli-tools/wallpaper-effects-generator/
  src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/
    adapters/
      __init__.py                       — (NEW)
      schemas/
        __init__.py                     — (NEW)
        effects_schema.py               — (NEW) EffectsConfigSchema (Pydantic)
        settings_schema.py              — (NEW) CoreSettingsSchema (Pydantic)
      yaml_effect_loader.py             — (NEW) implements EffectLoaderPort
      assembled_config_resolver.py      — (NEW) implements ConfigResolverPort
    defaults/
      effects.yaml                      — (NEW) package-bundled effects defaults
      settings.toml                     — (NEW) package-bundled settings defaults
    cli/
      __init__.py                       — (NEW)
      main.py                           — (NEW) Typer app entry point
      info.py                           — (NEW) info command
      dump_config.py                    — (NEW) dump-config command
      dump_effects.py                   — (NEW) dump-effects command
    factory.py                          — (NEW) adapter wiring / DI composition
  tests/
    unit/adapters/
      test_assembled_config_resolver.py  — (NEW)
      test_yaml_effect_loader.py         — (NEW)
      test_schemas.py                    — (NEW)
    integration/
      test_config_resolution.py          — (NEW) full resolution chain
```

### Dependency Changes
None beyond what was declared in Story 1.1. The adapters use:
- `config-assembler-engine` (AssembleConfiguration, TomlConfigParser, YamlConfigParser, strategies)
- `pydantic` (schema validation)
- `typer[all]` (CLI framework)

### Default Config Files (from ARCHITECTURE_PLAN.md §15)

settings.toml defaults:
```toml
version = "1.0"
[execution]
parallel = true
strict = true
max_workers = 0
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

### Testing Standards
- Unit tests for schema validation (valid configs, invalid configs, edge cases)
- Unit tests for AssembledConfigResolver (mock config-assembler-engine, verify path resolution and override application)
- Unit tests for YamlEffectLoader (mock config-assembler-engine, verify effects loading)
- Integration tests for full resolution chain (use real config-assembler-engine with temp files)
- Use pytest. Follow existing patterns in tests/ directory from Story 1.1.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/__init__.py` — (NEW)
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/schemas/__init__.py` — (NEW)
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/schemas/settings_schema.py` — (NEW) CoreSettingsSchema
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/schemas/effects_schema.py` — (NEW) EffectsConfigSchema
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/yaml_effect_loader.py` — (NEW) YamlEffectLoader
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/assembled_config_resolver.py` — (NEW) AssembledConfigResolver
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/factory.py` — (NEW) wiring/composition
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/__init__.py` — (NEW)
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/main.py` — (NEW) Typer app
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/info.py` — (NEW) info command
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/dump_config.py` — (NEW) dump-config command
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/dump_effects.py` — (NEW) dump-effects command
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/defaults/settings.toml` — (NEW) package defaults
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/defaults/effects.yaml` — (NEW) package defaults
- `tests/unit/adapters/test_assembled_config_resolver.py` — (NEW)
- `tests/unit/adapters/test_yaml_effect_loader.py` — (NEW)
- `tests/unit/adapters/test_schemas.py` — (NEW)
- `tests/integration/test_config_resolution.py` — (NEW)
