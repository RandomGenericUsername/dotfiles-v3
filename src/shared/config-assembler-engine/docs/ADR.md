# Architecture Decision Records — `config-assembler-engine`

---

## ADR-001: No Global State — One Engine Instance Per Config File

**Status:** Accepted

**Context:** The predecessor (`layered-settings`) used a global `configure()` + `_reset()` pattern that made testing and parallel usage error-prone.

**Decision:** Each config file gets its own `AssembleConfiguration` instance. No module-level state, no singletons, no caches.

**Consequences:**
- Testing is fully isolated — create a new instance per test case
- Multiple config files in the same process (e.g. effects + settings for wallpaper app) each have independent pipelines
- Zero shared mutable state between instances

---

## ADR-002: Explicit Parser Injection (Never Inspect File Extensions)

**Status:** Accepted

**Context:** Guessing format from file extensions is fragile. A `config.yaml` file might contain TOML, or a file without an extension could be valid YAML.

**Decision:** The consumer must provide the parser explicitly. The engine never calls `path.suffix` or any format-detection logic.

**Consequences:**
- Slightly more boilerplate for the consumer (must pass a parser)
- Zero ambiguity about what parser is used
- Consumers can provide custom parsers (e.g. for `.env` files, HCL, etc.)

---

## ADR-003: Ports Are `Protocol` Classes, Not ABCs

**Status:** Accepted

**Context:** Adapters must be swappable for testing. ABCs enforce an inheritance hierarchy that couples the port to the implementation.

**Decision:** All ports are `typing.Protocol` classes with structural subtyping. Any object with the right method signatures satisfies the port.

**Consequences:**
- Adapters don't need to inherit from port classes (though they can for self-documentation)
- Fakes for testing are trivial — any object with matching method signatures works
- Protocols are strictly behavioral contracts, not implementation hierarchies

---

## ADR-004: Domain Services Are Static Methods

**Status:** Accepted

**Context:** `OverrideMatchingService` and `ConfigMergeService` are pure functions — they take inputs, return outputs, have no state, and no side effects.

**Decision:** All domain service methods are `@staticmethod`. No instance state, no dependency injection at the domain layer.

**Consequences:**
- Trivially testable — just call the method with test data
- Stateless by construction — no risk of mutable state leaking between calls
- The `ENV_SEPARATOR` constant lives on the service rather than being scattered

---

## ADR-005: Env Var Keys Are Lowercased After Prefix Stripping

**Status:** Accepted

**Context:** Environment variable names are conventionally uppercase (`ABC_PROJECT__TIMEOUT`), but field paths on Pydantic models are lowercase (`timeout`).

**Decision:** `OsEnvironmentReader.read()` lowercases the key after stripping the prefix. Field paths in `OverrideRule` must be lowercase to match.

**Consequences:**
- `ABC_PROJECT__TIMEOUT=30` → `{"timeout": "30"}` — natural mapping
- If a consumer has uppercase field names, they must use lowercase `OverrideRule.field_path`
- Case-insensitive matching by design — no surprises when env vars differ in case

---

## ADR-006: Engine Control Env Vars Use Single Underscore (Outside `PREFIX__*` Namespace)

**Status:** Accepted

**Context:** The consumer needs a way to override the config file path via environment variables (e.g. `ABC_PROJECT_CONFIG_FILE_PATH=/path/to/custom.yaml`). This must not collide with config field overrides that use `PREFIX__*` (double underscore).

**Decision:** Engine control parameters (like the config file path) live outside the `PREFIX__*` namespace. They use a single underscore `_` between prefix and parameter name. `FileSystemPathResolver` reads them directly from `os.environ`, not through `EnvironmentReaderPort`.

Format: `{env_prefix}_{env_file_path_var}` — e.g. `ABC_PROJECT_CONFIG_FILE_PATH=/x.yaml`

`OsEnvironmentReader` only matches `PREFIX__*` (double underscore), so it never sees engine control vars. Zero collision by construction.

**Consequences:**
- `EnvironmentReaderPort` has one responsibility: serving `PREFIX__*` vars for config overrides
- `FileSystemPathResolver` reads `os.environ` directly (acceptable for an adapter — it already calls `os.path.exists()`, `Path.cwd()`, `os.environ.get("XDG_CONFIG_HOME")`)
- The env reader is called once per `execute()`, not twice
- The engine control var name is configurable via `ResolutionPolicy.env_file_path_var`
- The naming convention `_` (engine) vs `__` (config) is a visual signal of the architectural boundary

---

## ADR-007: Bool Coercion Silently Returns `False` for Unknown Values

**Status:** Accepted

**Context:** The type coercion table lists `"true"`, `"1"`, `"yes"` as truthy and `"false"`, `"0"`, `"no"` as falsy. There are three possible behaviors for unknown values: raise an error, return `False`, or return `None`.

**Decision:** Any value not in the explicit truthy set returns `False`. No error is raised.

**Consequences:**
- A typo like `ABC_PROJECT__ENABLED=ture` would silently result in `False` instead of raising an error
- This was chosen because strict bool coercion (raise on unknown) would break consumers that pass env vars like `ENABLED=0` or `ENABLED=off` without needing to special-case them
- If strict validation is desired, the consumer should handle it via Pydantic validators in Phase 7

---

## ADR-008: CLI Overrides Take Precedence Over ENV (Sorted ENV → CLI)

**Status:** Accepted

**Context:** When both an env var and a CLI argument override the same field, there must be a deterministic winner.

**Decision:** Overrides are sorted by source: ENV first, then CLI. Because `ConfigMergeService.apply` uses `deepcopy` + key assignment, CLI overrides processed later overwrite ENV values for the same field path.

**Consequences:**
- CLI always wins for the same field — standard CLI convention
- If the same field is overridden by two CLI args, the last one wins (dict merge order)
- The sort is stable for same-source values, so order within each source is preserved

---

## ADR-009: Directory Traversal Walks cwd First, Then Parents

**Status:** Accepted

**Context:** A project might have its config file in the current directory, a parent directory, or a grandparent. The search range is bounded by `parent_lookup_levels`.

**Decision:** Start at cwd (level 0), then walk up parents up to `parent_lookup_levels`. First found file wins. `parent_lookup_levels=0` means cwd only. Iteration `level` maps to `cwd.parents[level - 1]` (since `parents` is 0-indexed: `parents[0]` is the immediate parent).

**Consequences:**
- Config file in cwd takes priority over parent directories — standard monorepo convention
- A flat project with a single directory uses `parent_lookup_levels=0`
- Walking up exactly `parent_lookup_levels` levels means `parent_lookup_levels=1` checks cwd + `parents[0]` (immediate parent)

---

## ADR-010: `OverrideCoercionError` Includes Full Context

**Status:** Accepted

**Context:** When coercion fails, the consumer needs to know which field, what value, what type, and why — not just a generic "coercion failed" message.

**Decision:** `OverrideCoercionError` carries `field_path`, `raw_value`, `target_type`, and `reason` as structured fields, and formats them into a human-readable message.

**Consequences:**
- Error messages are self-diagnostic: `Cannot coerce override 'timeout'=abc to int: not a valid integer`
- Programmatic callers can catch the error and inspect structured fields
- The use case re-wraps all coercion exceptions through this type, so the provenance chain is never lost

---

## ADR-011: `_coerce_item` Uses Empty `field_path` for List/Dict Elements

**Status:** Acknowledged limitation

**Context:** When coercing individual elements of a list (`list[int]` items) or dict values, `_coerce_item` creates an `OverrideValue` with `field_path=""`.

**Decision:** The empty string is a placeholder. Error messages for individual elements will not include a meaningful dotted path.

**Consequences:**
- If `ABC_PROJECT__MOUNTS=bad` fails coercion (not applicable for `str` but could for `list[int]` with malformed items), the error message reports `field_path=""` instead of `"mounts"`
- The caller (`coerce` → `_coerce_item`) doesn't pass the parent field path
- This is acceptable because the consumer sees the original override error first, and element errors are wrapped by the parent coercion

---

## ADR-012: Ports Include `get_field_info` in the Validator (Not a Separate Port)

**Status:** Accepted

**Context:** The type coercer needs to know the target type for a given field path. This could be a separate port (`TypeInfoPort`) or a method on the validator.

**Decision:** `get_field_info` lives on `ConfigValidatorPort`. The validator already knows the schema structure, so it's the natural owner of type introspection.

**Consequences:**
- Single port interface for all schema-related operations
- The coercer depends on the validator port for type info (inter-port dependency within the application layer)
- If the validator is swapped (e.g. for a non-Pydantic schema), `get_field_info` must be implemented in the replacement

---

## ADR-013: Environment Prefix Is Matched With `__` Separator

**Status:** Accepted

**Context:** Environment variables follow the convention `PREFIX__FIELD`. The prefix itself may or may not contain underscores.

**Decision:** The separator is always `__` (double underscore). Matching uses `key.startswith(prefix + "__")`. If the prefix contains `__`, the behavior is ambiguous.

**Consequences:**
- `ABC_PROJECT__TIMEOUT=30` with prefix `ABC_PROJECT` matches correctly
- If a prefix is `ABC__PROJECT` (contains `__`), then `ABC__PROJECT__TIMEOUT` matches but the key after stripping becomes `TIMEOUT` — the internal `__` in the prefix is consumed. This is a documented limitation.
- Consumers should avoid `__` in their prefix

---

## ADR-014: Re-validation (Phase 7) Runs Against Original Schema

**Status:** Accepted

**Context:** After merging overrides into the baseline config, the result might violate schema constraints (e.g. a numeric field out of range, or a string that doesn't match a regex pattern). Type coercion catches type mismatches but not validation constraints.

**Decision:** The final merged dict is validated against the same Pydantic schema in Phase 7. If it fails, `ConfigValidationError` is raised and no `AssemblyResult` is returned.

**Consequences:**
- Invalid overrides (e.g. `timeout=-1` when the field has `ge=0`) are caught at the final validation step
- The `applied_overrides` list has been partially populated at this point but is not returned — the error is raised instead
- This is intentional: partial results could mask the failure. If provenance is needed for debugging, the consumer can catch `ConfigValidationError` and inspect the error message

---

## ADR-015: Resolution Strategies Are Independent, Consumer-Built Handlers

**Status:** Accepted

**Context:** The original resolution chain was a hardcoded 5-step priority list inside a monolithic `FileSystemPathResolver`. Consumers couldn't reorder layers, skip XDG, or add custom resolution sources (e.g. a database, a network endpoint, a legacy path format).

**Decision:** Replace the monolithic resolver with a `CompositePathResolver` that runs an ordered list of `ResolutionStrategy` handlers. Each strategy is a self-contained class with its own constructor parameters. The consumer builds the list — picking, ordering, and configuring strategies as needed. A factory provides a sensible default list.

**Consequences:**
- Consumers can reorder layers: put XDG before directory traversal, or skip it entirely by omitting it from the list
- Custom strategies are trivial: implement the `ResolutionStrategy` protocol (single `resolve()` method)
- `ResolutionPolicy` is now minimal — only `env_prefix` (used by the env reader in the use case). Strategy-specific config (filenames, max levels, subdirectories) lives in each strategy's constructor
- The formal algorithm is simple: iterate strategies; first non-None result wins
- Testing is isolated — each strategy can be tested independently with its own config
