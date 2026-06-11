# `config-assembler-engine` — Specification (Source of Truth)

**Version:** 1.0.0
**Target:** Python >= 3.12, Pydantic >= 2.0
**Status:** Approved

> **Purpose of this document:** Defines WHAT the system does — contracts, protocols, models, and algorithms. Implementation code is in [`PROTOTYPE.md`](./PROTOTYPE.md). Design rationale is in [`ADR.md`](./ADR.md).

---

## 1. Goal

A reusable, stateless, strictly hexagonal configuration resolution engine. Each application instantiates its own engine with explicit policies. The engine does not assume anything about file formats, filesystem layout, or environment conventions unless explicitly injected.

**Key constraints:**

| # | Constraint |
|---|------------|
| 1 | No global state. No module-level caches. No `configure()`/`_reset()` anti-patterns. |
| 2 | One engine instance per config file. |
| 3 | Explicit parser injection: the consumer declares the format, never the engine. |
| 4 | Per-application policy: layer order, override rules, and schema are consumer-defined. |
| 5 | All I/O (filesystem, environment variables, parsing, validation) is behind explicit ports. |

---

## 2. Hexagonal Layering

```
----------------------------------------------
               Infrastructure
  Adapters: CompositePathResolver,
            CliPathStrategy, EnvPathStrategy,
            DirectoryTraversalStrategy,
            XdgStrategy, DefaultFileStrategy,
            OsEnvironmentReader,
            TomlConfigParser, YamlConfigParser,
            JsonConfigParser,
            PydanticValidator,
            PydanticTypeCoercer,
            create_standard_assembler
----------------------------------------------
                   ^
                   | depends on
----------------------------------------------
                Application
  Use Case: AssembleConfiguration
  Orchestrates ports + domain services
----------------------------------------------
                   ^
                   | depends on
----------------------------------------------
                  Domain
  Services: OverrideMatchingService
            ConfigMergeService
  Models: ResolutionPolicy, OverrideRule,
          ResolvedPath, AssemblyResult,
          OverrideValue, PathSource,
          OverrideSource
----------------------------------------------
                   ^
                   | implements
----------------------------------------------
                   Ports
  PathResolverPort, ResolutionStrategy,
  ConfigParserPort,
  EnvironmentReaderPort, ConfigValidatorPort,
  TypeCoercerPort
----------------------------------------------
```

---

## 3. Domain Models

### `PathSource` — identifies how a config file path was discovered

| Member | Meaning |
|--------|---------|
| `DEFAULT` | Found at `policy.default_file_path` |
| `XDG` | Found at `~/.config/<xdg_subdir>/<filename>` |
| `DIRECTORY` | Found via directory traversal (cwd or parent) |
| `ENV_PATH` | Provided via `<env_prefix>__FILE_PATH` env var |
| `CLI_PATH` | Provided via `explicit_path` argument |

### `OverrideSource` — identifies where an override came from

| Member | Meaning |
|--------|---------|
| `ENV` | Override from environment variable |
| `CLI` | Override from CLI argument dict |

### `ResolutionPolicy` — shared context for resolution strategies

| Field | Type | Description |
|-------|------|-------------|
| `env_prefix` | `str` | Namespace prefix for env var filtering (e.g. `"ABC_PROJECT"`). Used by the use case's env reader. Strategies may also reference this. |

### `OverrideRule` — defines which schema field can be overridden and from which sources

| Field | Type | Description |
|-------|------|-------------|
| `field_path` | `str` | Dotted path into the config schema (e.g. `"mounts"`, `"map.host_dir"`) |
| `sources` | `set[OverrideSource]` | Which sources are allowed (`ENV`, `CLI`, or both) |

### `ResolvedPath` — result of Phase 1 path resolution

| Field | Type | Description |
|-------|------|-------------|
| `path` | `Path` | Absolute path to the resolved config file |
| `source` | `PathSource` | How the path was discovered |

### `OverrideValue` — a discovered raw override before type coercion

| Field | Type | Description |
|-------|------|-------------|
| `field_path` | `str` | Dotted path into the config schema |
| `raw_value` | `str` | The raw string value |
| `source` | `OverrideSource` | Where this override came from |

### `AppliedOverride` — an override that was applied with its coerced value

| Field | Type | Description |
|-------|------|-------------|
| `field_path` | `str` | Dotted path that was overridden |
| `raw_value` | `str` | Original raw string value |
| `coerced_value` | `Any` (from `typing.Any`) | Value after type coercion. Can be `str`, `int`, `Path`, `list`, `dict`, etc. |
| `source` | `OverrideSource` | Where this override came from |

### `AssemblyResult` — final validated configuration with provenance

| Field | Type | Description |
|-------|------|-------------|
| `config` | `BaseModel` (from `pydantic.BaseModel`) | Final validated Pydantic model instance |
| `resolved_path` | `ResolvedPath` | Which file was loaded and how it was found |
| `applied_overrides` | `list[AppliedOverride]` | All overrides that were applied in order |

---

## 4. Ports (Contracts)

All ports are `Protocol` classes. Implementations live in adapters.

### 4.1 `PathResolverPort`

```
resolve(policy: ResolutionPolicy, explicit_path: str | None = None) -> ResolvedPath
```

Discovers which config file to load by iterating through an ordered list of `ResolutionStrategy` handlers. The first strategy that returns a `ResolvedPath` wins. Raises `PathResolutionError` if no strategy succeeds.

### 4.2 `ResolutionStrategy`

```
resolve(policy: ResolutionPolicy, explicit_path: str | None = None) -> ResolvedPath | None
```

A single step in the resolution chain. Returns a `ResolvedPath` if it finds the file, or `None` to pass to the next strategy. Strategies are self-contained — they carry their own configuration (filename, max levels, subdirectory, etc.) and do not depend on `ResolutionPolicy` for strategy-specific fields.

### 4.3 `ConfigParserPort`

```
parse(path: Path) -> dict[str, Any]
```

Reads and parses a configuration file into a raw Python dict. The engine never inspects file extensions or guesses formats.

Raises `ConfigParseError` if the file cannot be read or is malformed.

### 4.4 `EnvironmentReaderPort`

```
read(prefix: str) -> dict[str, str]
```

Returns all environment variables matching the namespace prefix. The prefix is stripped from keys and all keys are lowercased. Both flat and nested fields are accepted.

Format: `PREFIX__FIELD` or `PREFIX__NESTED__KEY`

Examples:
- `read("ABC_PROJECT")` with `ABC_PROJECT__TIMEOUT=30` → `{"timeout": "30"}`
- `read("ABC_PROJECT")` with `ABC_PROJECT__MAP__HOST=localhost` → `{"map__host": "localhost"}`
- `read("ABC_PROJECT")` with `ABC_PROJECT__FILE_PATH=/etc/config.yaml` → `{"file_path": "/etc/config.yaml"}`

### 4.5 `ConfigValidatorPort`

```
validate(raw: dict[str, Any], schema: type[BaseModel]) -> BaseModel
```

Validates a raw dict against a Pydantic schema and returns a model instance.

Raises `ConfigValidationError` if validation fails.

```
get_field_info(schema: type[BaseModel], field_path: str) -> Any
```

Returns the type annotation for a dotted field path in the schema. Used by the type coercer to determine the target type. `Optional[T]` and `Annotated[T, ...]` are unwrapped before navigation. See `unwrap_optional()` in `domain/type_utils.py`.

**Limitation:** `list[T]` fields cannot be navigated into for element-wise overrides. An override targeting a path through a list field (e.g. `mounts.target`) raises `ConfigValidationError`. Override the entire list field instead: `<prefix>__MOUNTS=val1,val2`.

### 4.6 `TypeCoercerPort`

```
coerce(override: OverrideValue, field_type: Any) -> Any
```

Converts a raw string override value to the target type defined by the schema.

Raises `OverrideCoercionError` if coercion fails.

---

## 5. Error Hierarchy

| Exception | Parent | Raised When |
|-----------|--------|-------------|
| `ConfigAssemblerError` | `Exception` | Base for all config assembler errors |
| `PathResolutionError` | `ConfigAssemblerError` | No config file found across all resolution layers |
| `ConfigParseError` | `ConfigAssemblerError` | Config file cannot be read or parsed |
| `ConfigValidationError` | `ConfigAssemblerError` | Raw dict fails schema validation |
| `OverrideCoercionError` | `ConfigAssemblerError` | Single override value cannot be coerced to its target type |

`OverrideCoercionError` carries these fields:
- `field_path: str` — the dotted path that failed
- `raw_value: str` — the raw string that failed coercion
- `target_type: str` — the intended type name
- `reason: str` — description of what went wrong

`ConfigValidationError` carries optional fields (defaults to `None` — check with `is not None`):
- `errors: list[dict[str, Any]] | None` — structured validation errors from the validator (e.g. Pydantic `ValidationError.errors()`). Populated by the validator adapter.
- `applied_overrides: list[AppliedOverride] | None` — partial list of overrides that were successfully applied before validation failed. Populated by the use case.

---

## 6. Formal Algorithm — Resolution

**Given:**
- `strategies`: an ordered list of `ResolutionStrategy` instances
- `policy`: `ResolutionPolicy`
- `explicit_path`: `str | None`

**Algorithm:**
1. For each `strategy` in `strategies` (in order):
   - `result = strategy.resolve(policy, explicit_path)`
   - If `result` is not `None`: return `result`
2. Raise `PathResolutionError`

**Key behavior:** The first strategy to return a `ResolvedPath` wins. A strategy returns `None` to pass control to the next strategy. Strategies are independent — they carry their own configuration and do not share state.

---

## 7. Formal Algorithm — Override Resolution

**Given:**
- `rules`: list of `OverrideRule`
- `env_vars`: dict from `EnvironmentReaderPort.read(prefix)`
- `cli_overrides`: dict from consumer

**Algorithm:**
1. Initialize `values = []`
2. For each `(key, val)` in `env_vars`:
   - `dotted = key.replace("__", ".")`
   - Find matching `rule` where `rule.field_path == dotted` and `OverrideSource.ENV in rule.sources`
   - If found: append `OverrideValue(dotted, val, ENV)`
3. For each `(key, val)` in `cli_overrides`:
   - Find matching `rule` where `rule.field_path == key` and `OverrideSource.CLI in rule.sources`
   - If found: append `OverrideValue(key, val, CLI)`
4. Sort `values` by source (ENV before CLI)
5. For each `ov` in sorted `values`:
   - `field_type = validator.get_field_info(schema, ov.field_path)`
   - `coerced = coercer.coerce(ov, field_type)`
   - `merged_dict = ConfigMergeService.apply(merged_dict, ov, coerced)`
   - Record `AppliedOverride`
6. Validate final `merged_dict` against schema. Return `AssemblyResult`.

**Precedence:** CLI overrides override ENV overrides for the same field. CLI is processed after ENV in the sorted order, so its value overwrites the dict key.

---

## 8. Type Coercion Rules

| Schema Type | Raw Input Example | Coerced Output | Rule |
|-------------|-------------------|----------------|------|
| `str` | `"hello"` | `"hello"` | As-is |
| `int` | `"42"` | `42` | `int()` |
| `float` | `"3.14"` | `3.14` | `float()` |
| `bool` | `"true"`/`"1"`/`"yes"` → `True`; anything else → `False` | Case-insensitive. Any value not in truthy set returns `False` with no error. |
| `Path` | `"/tmp/foo"` | `Path("/tmp/foo")` | `Path()` |
| `list[str]` | `"a,b,c"` | `["a", "b", "c"]` | Split on `,` |
| `list[int]` | `"1,2,3"` | `[1, 2, 3]` | Split + coerce each item |
| `dict[str, int]` | `"a:1;b:2"` | `{"a": 1, "b": 2}` | Split on `;`, then `:`; malformed entries raise error |
| `Enum` | `"docker"` | `Engine.DOCKER` | Name lookup (case-insensitive fallback) |

**Optional unwrapping:** `Optional[T]` is unwrapped to `T` before coercion. `Union` types other than `Optional` have undefined behavior.

**List limitation:** `list[BaseModel]` fields must be overridden as a whole (comma-separated string values). Element-wise overrides through list fields are not supported. See `ConfigValidatorPort.get_field_info()`.

---

## 9. Package Configuration

```toml
[project]
name = "config-assembler-engine"
version = "0.1.0"
description = "Strictly hexagonal configuration resolution engine"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.0",
]

[project.optional-dependencies]
yaml = ["pyyaml>=6.0"]
all = ["pyyaml>=6.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/config_assembler_engine"]
```

---

## 10. File Structure

```
config-assembler-engine/
├── pyproject.toml
└── src/
    └── config_assembler_engine/
        ├── __init__.py              # re-exports: ResolutionPolicy, OverrideRule,
        │                           #   OverrideSource, PathSource, AssemblyResult,
        │                           #   ConfigAssemblerError
        ├── errors.py
        ├── domain/
        │   ├── __init__.py
        │   ├── models.py
        │   ├── services.py
        │   └── type_utils.py
        ├── ports/
        │   ├── __init__.py
        │   ├── config_parser.py
        │   ├── path_resolver.py
        │   ├── env_reader.py
        │   ├── config_validator.py
        │   └── type_coercer.py
        ├── application/
        │   ├── __init__.py
        │   └── use_cases.py
        └── adapters/
            ├── __init__.py
            ├── path_resolver.py          # CompositePathResolver
            ├── env_reader.py
            ├── config_validator.py
            ├── type_coercer.py
            ├── factories.py
            ├── parsers/
            │   ├── __init__.py
            │   ├── toml_parser.py
            │   ├── yaml_parser.py
            │   └── json_parser.py
            └── strategies/
                ├── __init__.py
                ├── cli_path.py            # CliPathStrategy
                ├── env_path.py            # EnvPathStrategy
                ├── directory.py           # DirectoryTraversalStrategy
                ├── xdg.py                 # XdgStrategy
                └── default_file.py        # DefaultFileStrategy
```

---

## 11. Testing Strategy

| Layer | Approach | Example |
|-------|----------|---------|
| Domain services | Pure pytest, no mocks | `test_override_matching_service.py` |
| Use case | Fake port stubs | `FakePathResolver`, `FakeEnvReader`, `FakeValidator` |
| Adapters | `tmp_path` + real files | `test_file_system_path_resolver.py` |
| Parsers | Real files in `tests/fixtures/` | `test_toml_parser.py`, `test_yaml_parser.py` |
| Integration | End-to-end with `create_standard_assembler` | `test_full_pipeline.py` |

**Key fixtures:**
- `fake_path_resolver`: Returns a predetermined `ResolvedPath`
- `fake_env_reader`: Returns a predetermined dict
- `tmp_config_file`: Creates a temp config file in a temp dir

---

## 12. Migration Path (from `layered-settings`)

| Current | New |
|---------|-----|
| `configure()` globals | Per-instance `AssembleConfiguration` |
| `SchemaEntry` + `build_config()` | `ResolutionPolicy` + `execute()` |
| `LayerDiscovery` (hardcoded) | `FileSystemPathResolver` (injected) |
| `FileLoader` (auto-detect format) | Explicit `ConfigParserPort` injection |
| `parse_env_vars()` | `OsEnvironmentReader` (injected) |
| Winner-takes-all files | Closest-match directory traversal + XDG + default |
| Attribution re-reads files | Provenance tracked during execution |
