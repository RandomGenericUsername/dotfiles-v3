# `config-assembler-engine` — Prototype / Reference Implementation

**Implements:** [SPEC.md](./SPEC.md)
**Design rationale:** [ADR.md](./ADR.md)

> **Purpose of this document:** Reference implementation that was built to validate the decisions in SPEC.md. If any code here contradicts SPEC.md, SPEC.md is authoritative.

---

## 1. Domain Services

Implements: SPEC.md §7 (Override Algorithm)

### `OverrideMatchingService`

```python
from typing import ClassVar

from config_assembler_engine.domain.models import (
    OverrideRule,
    OverrideSource,
    OverrideValue,
)


class OverrideMatchingService:
    """Pure logic: match raw env/cli dicts against registered OverrideRules."""

    ENV_SEPARATOR: ClassVar[str] = "__"

    @staticmethod
    def match(
        env_vars: dict[str, str],
        cli_overrides: dict[str, str],
        rules: list[OverrideRule],
    ) -> list[OverrideValue]:
        values: list[OverrideValue] = []
        registered_paths = {r.field_path for r in rules}

        for raw_key, raw_val in env_vars.items():
            dotted = raw_key.replace(OverrideMatchingService.ENV_SEPARATOR, ".")
            if dotted in registered_paths:
                rule = next(r for r in rules if r.field_path == dotted)
                if OverrideSource.ENV in rule.sources:
                    values.append(
                        OverrideValue(
                            field_path=dotted,
                            raw_value=raw_val,
                            source=OverrideSource.ENV,
                        )
                    )

        for key, raw_val in cli_overrides.items():
            if key in registered_paths:
                rule = next(r for r in rules if r.field_path == key)
                if OverrideSource.CLI in rule.sources:
                    values.append(
                        OverrideValue(
                            field_path=key,
                            raw_value=raw_val,
                            source=OverrideSource.CLI,
                        )
                    )

        return values
```

### `ConfigMergeService`

```python
from copy import deepcopy
from typing import Any

from config_assembler_engine.domain.models import OverrideValue


class ConfigMergeService:
    """Pure logic: apply typed overrides to a baseline dict."""

    @staticmethod
    def apply(base: dict[str, Any], override: OverrideValue, coerced_value: Any) -> dict[str, Any]:
        result = deepcopy(base)
        parts = override.field_path.split(".")
        current = result

        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            elif not isinstance(current[part], dict):
                raise TypeError(
                    f"Cannot set '{override.field_path}': "
                    f"'{part}' is {type(current[part]).__name__}, not a dict"
                )
            current = current[part]

        current[parts[-1]] = coerced_value
        return result
```

---

## 1.5 Domain Type Utilities

Implements: SPEC.md §4.4, §8 (Optional unwrapping for get_field_info and coercion)

```python
# domain/type_utils.py
from typing import Any, get_args, get_origin


def unwrap_optional(tp: Any) -> Any:
    """Unwrap Optional[T] → T and Annotated[T, ...] → T.

    Returns the unwrapped type if it's a simple Optional or Annotated,
    otherwise returns the type unchanged.
    """
    if tp is None:
        return tp

    origin = get_origin(tp)
    args = get_args(tp)

    # Optional[T] → T (Union[T, None] with exactly one non-None type)
    if origin is not None and type(None) in args:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return unwrap_optional(non_none[0])

    # Annotated[T, ...] → T (Pydantic v2 stores constraints in Annotated)
    if origin is Annotated:
        return unwrap_optional(args[0]) if args else tp

    return tp
```

---

## 2. Application Use Case

Implements: SPEC.md §6-7 (Resolution + Override Algorithms, 7-phase pipeline)

```python
from typing import Any

from pydantic import BaseModel

from config_assembler_engine.domain.models import (
    AppliedOverride,
    AssemblyResult,
    OverrideRule,
    OverrideSource,
    ResolutionPolicy,
)
from config_assembler_engine.domain.services import ConfigMergeService, OverrideMatchingService
from config_assembler_engine.errors import (
    ConfigValidationError,
    OverrideCoercionError,
    PathResolutionError,
)
from config_assembler_engine.ports.config_parser import ConfigParserPort
from config_assembler_engine.ports.config_validator import ConfigValidatorPort
from config_assembler_engine.ports.env_reader import EnvironmentReaderPort
from config_assembler_engine.ports.path_resolver import PathResolverPort
from config_assembler_engine.ports.type_coercer import TypeCoercerPort


class AssembleConfiguration:
    """Orchestrate the 7-phase configuration assembly pipeline."""

    def __init__(
        self,
        path_resolver: PathResolverPort,
        parser: ConfigParserPort,
        env_reader: EnvironmentReaderPort,
        validator: ConfigValidatorPort,
        coercer: TypeCoercerPort,
    ) -> None:
        self._path_resolver = path_resolver
        self._parser = parser
        self._env_reader = env_reader
        self._validator = validator
        self._coercer = coercer

    def execute(
        self,
        policy: ResolutionPolicy,
        rules: list[OverrideRule],
        schema: type[BaseModel],
        *,
        cli_overrides: dict[str, str] | None = None,
        explicit_path: str | None = None,
    ) -> AssemblyResult:
        # Phase 1: Resolve file path
        resolved = self._path_resolver.resolve(policy, explicit_path)

        # Phase 2: Parse file
        raw = self._parser.parse(resolved.path)

        # Phase 3: Validate baseline
        baseline = self._validator.validate(raw, schema)

        # Phase 4: Read env vars
        env_vars = self._env_reader.read(policy.env_prefix)

        # Phase 5: Discover and match overrides
        overrides = OverrideMatchingService.match(
            env_vars, cli_overrides or {}, rules
        )

        # Phase 6: Coerce and merge overrides
        merged_dict = baseline.model_dump()
        applied: list[AppliedOverride] = []

        sorted_overrides = sorted(
            overrides, key=lambda o: 0 if o.source == OverrideSource.ENV else 1
        )

        for ov in sorted_overrides:
            field_type = self._validator.get_field_info(schema, ov.field_path)
            try:
                coerced = self._coercer.coerce(ov, field_type)
            except OverrideCoercionError:
                raise  # already has full context (field_path, raw_value, reason)
            except Exception as e:
                raise OverrideCoercionError(
                    field_path=ov.field_path,
                    raw_value=ov.raw_value,
                    target_type=str(field_type),
                    reason=str(e),
                ) from e

            merged_dict = ConfigMergeService.apply(merged_dict, ov, coerced)
            applied.append(
                AppliedOverride(
                    field_path=ov.field_path,
                    raw_value=ov.raw_value,
                    coerced_value=coerced,
                    source=ov.source,
                )
            )

        # Phase 7: Final validation
        try:
            final = self._validator.validate(merged_dict, schema)
        except ConfigValidationError as e:
            e.applied_overrides = applied  # attach partial provenance
            raise

        return AssemblyResult(
            config=final,
            resolved_path=resolved,
            applied_overrides=applied,
        )
```

---

## 3. Adapters

### 3.1 Strategies

Implements: SPEC.md §4.2 (ResolutionStrategy), §6 (Algorithm)

Each strategy is a self-contained handler. Strategies carry their own configuration and return `ResolvedPath | None`.

```python
# adapters/strategies/cli_path.py
import os
from pathlib import Path

from config_assembler_engine.domain.models import ResolutionPolicy, ResolvedPath, PathSource
from config_assembler_engine.ports.path_resolver import ResolutionStrategy


class CliPathStrategy:
    """Returns the explicit CLI path if provided and exists."""

    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        if not explicit_path:
            return None
        path = Path(explicit_path).expanduser().resolve()
        if path.exists():
            return ResolvedPath(path=path, source=PathSource.CLI_PATH)
        return None
```

```python
# adapters/strategies/env_path.py
import os
from pathlib import Path

from config_assembler_engine.domain.models import ResolutionPolicy, ResolvedPath, PathSource
from config_assembler_engine.ports.path_resolver import ResolutionStrategy


class EnvPathStrategy:
    """Reads a specific env var to find the config file path.

    Uses single underscore separator (PREFIX_VAR) — outside the PREFIX__* namespace
    used by config overrides. See ADR-006.
    """

    def __init__(self, var: str = "CONFIG_FILE_PATH") -> None:
        self._var = var

    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        env_key = f"{policy.env_prefix}_{self._var}"
        file_path = os.environ.get(env_key)
        if not file_path:
            return None
        path = Path(file_path).expanduser().resolve()
        if path.exists():
            return ResolvedPath(path=path, source=PathSource.ENV_PATH)
        return None
```

```python
# adapters/strategies/directory.py
from pathlib import Path

from config_assembler_engine.domain.models import ResolutionPolicy, ResolvedPath, PathSource
from config_assembler_engine.ports.path_resolver import ResolutionStrategy


class DirectoryTraversalStrategy:
    """Walks up from cwd looking for the config file. Closest match wins."""

    def __init__(self, filename: str, max_levels: int = 3) -> None:
        self._filename = filename
        self._max_levels = max_levels

    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        cwd = Path.cwd()
        for level in range(self._max_levels + 1):
            check_dir = cwd.parents[level - 1] if level > 0 else cwd
            candidate = check_dir / self._filename
            if candidate.exists():
                return ResolvedPath(path=candidate.resolve(), source=PathSource.DIRECTORY)
        return None
```

```python
# adapters/strategies/xdg.py
import os
from pathlib import Path

from config_assembler_engine.domain.models import ResolutionPolicy, ResolvedPath, PathSource
from config_assembler_engine.ports.path_resolver import ResolutionStrategy


class XdgStrategy:
    """Checks ~/.config/<subdir>/<filename> (or $XDG_CONFIG_HOME)."""

    def __init__(self, xdg_subdir: str, filename: str) -> None:
        self._xdg_subdir = xdg_subdir
        self._filename = filename

    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        if not self._xdg_subdir:
            return None
        xdg_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        candidate = xdg_home / self._xdg_subdir / self._filename
        if candidate.exists():
            return ResolvedPath(path=candidate.resolve(), source=PathSource.XDG)
        return None
```

```python
# adapters/strategies/default_file.py
from pathlib import Path

from config_assembler_engine.domain.models import ResolutionPolicy, ResolvedPath, PathSource
from config_assembler_engine.ports.path_resolver import ResolutionStrategy


class DefaultFileStrategy:
    """Falls back to a hardcoded default path."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath | None:
        if self._path.exists():
            return ResolvedPath(path=self._path.resolve(), source=PathSource.DEFAULT)
        return None
```

### 3.2 `CompositePathResolver`

Implements: SPEC.md §4.1 (PathResolverPort), §6 (Algorithm)

```python
from config_assembler_engine.domain.models import ResolutionPolicy, ResolvedPath
from config_assembler_engine.errors import PathResolutionError
from config_assembler_engine.ports.path_resolver import PathResolverPort, ResolutionStrategy


class CompositePathResolver(PathResolverPort):
    """Runs an ordered list of strategies. First hit wins."""

    def __init__(self, strategies: list[ResolutionStrategy]) -> None:
        self._strategies = strategies

    def resolve(
        self,
        policy: ResolutionPolicy,
        explicit_path: str | None = None,
    ) -> ResolvedPath:
        for strategy in self._strategies:
            result = strategy.resolve(policy, explicit_path)
            if result is not None:
                return result
        raise PathResolutionError("No strategy found a config file")
```

### 3.2 `OsEnvironmentReader`

Implements: SPEC.md §4.3 (EnvironmentReaderPort contract)

```python
import os
from typing import ClassVar

from config_assembler_engine.ports.env_reader import EnvironmentReaderPort


class OsEnvironmentReader(EnvironmentReaderPort):
    SEPARATOR: ClassVar[str] = "__"

    def read(self, prefix: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for key, value in os.environ.items():
            if not key.startswith(prefix + self.SEPARATOR):
                continue
            config_key = key[len(prefix) + len(self.SEPARATOR):].lower()
            result[config_key] = value
        return result
```

### 3.3 `PydanticValidator`

Implements: SPEC.md §4.4 (ConfigValidatorPort contract)

```python
from typing import Any, get_type_hints

from pydantic import BaseModel, ValidationError

from config_assembler_engine.domain.type_utils import unwrap_optional
from config_assembler_engine.errors import ConfigValidationError
from config_assembler_engine.ports.config_validator import ConfigValidatorPort


class PydanticValidator(ConfigValidatorPort):
    def validate(self, raw: dict[str, Any], schema: type[BaseModel]) -> BaseModel:
        try:
            return schema.model_validate(raw)
        except ValidationError as e:
            raise ConfigValidationError(str(e), errors=e.errors()) from e

    def get_field_info(self, schema: type[BaseModel], field_path: str) -> Any:
        from typing import get_origin, get_args

        parts = field_path.split(".")
        current_type = schema

        for i, part in enumerate(parts):
            # Unwrap Optional and Annotated before any navigation
            current_type = unwrap_optional(current_type)

            if isinstance(current_type, type) and issubclass(current_type, BaseModel):
                if part not in current_type.model_fields:
                    path_so_far = ".".join(parts[: i + 1])
                    raise ConfigValidationError(
                        f"Field '{path_so_far}' not found in schema {current_type.__name__}"
                    )
                field_info = current_type.model_fields[part]
                current_type = field_info.annotation
                continue

            origin = get_origin(current_type)
            args = get_args(current_type)

            if origin is dict:
                if len(args) > 1:
                    current_type = args[1]
                else:
                    current_type = Any
                continue

            if origin is list:
                list_field = ".".join(parts[: i + 1])
                raise ConfigValidationError(
                    f"Cannot navigate into '{list_field}': '{parts[i - 1]}' is a list. "
                    f"Element-wise overrides for list fields are not supported. "
                    f"Override the entire list field instead (e.g. <prefix>__{parts[i - 1].upper()}=val1,val2)."
                )

            if i < len(parts) - 1:
                path_so_far = ".".join(parts[: i + 1])
                raise ConfigValidationError(
                    f"Cannot navigate beyond '{path_so_far}': type {current_type} is not a BaseModel, Dict, or list"
                )

        return current_type
```

### 3.4 `PydanticTypeCoercer`

Implements: SPEC.md §8 (Type Coercion Rules table)

```python
import json
from pathlib import Path
from typing import Any, get_args, get_origin

from config_assembler_engine.domain.models import OverrideValue, OverrideSource
from config_assembler_engine.domain.type_utils import unwrap_optional
from config_assembler_engine.errors import OverrideCoercionError
from config_assembler_engine.ports.type_coercer import TypeCoercerPort


class PydanticTypeCoercer(TypeCoercerPort):
    def coerce(self, override: OverrideValue, field_type: Any) -> Any:
        raw = override.raw_value

        # Unwrap Optional[T] → T and Annotated[T, ...] → T
        field_type = unwrap_optional(field_type)

        origin = get_origin(field_type)
        args = get_args(field_type)

        if field_type is str or (isinstance(field_type, type) and issubclass(field_type, str)):
            return raw

        if field_type is int or (isinstance(field_type, type) and issubclass(field_type, int)):
            try:
                return int(raw)
            except ValueError:
                raise OverrideCoercionError(override.field_path, raw, "int", "not a valid integer")

        if field_type is float or (isinstance(field_type, type) and issubclass(field_type, float)):
            try:
                return float(raw)
            except ValueError:
                raise OverrideCoercionError(override.field_path, raw, "float", "not a valid float")

        if field_type is bool:
            return raw.lower() in ("true", "1", "yes", "on")

        if isinstance(field_type, type) and issubclass(field_type, Path):
            return Path(raw)

        if origin is list or (isinstance(field_type, type) and issubclass(field_type, list)):
            if not raw:
                return []
            item_type = args[0] if args else str
            items = [item.strip() for item in raw.split(",")]
            return [self._coerce_item(item, item_type) for item in items]

        if origin is dict or (isinstance(field_type, type) and issubclass(field_type, dict)):
            if not raw:
                return {}
            key_type = args[0] if len(args) > 0 else str
            val_type = args[1] if len(args) > 1 else str
            result: dict[Any, Any] = {}
            entries = raw.split(";")
            for entry in entries:
                if ":" not in entry:
                    raise OverrideCoercionError(
                        override.field_path, raw, "dict",
                        f"malformed entry '{entry}' — expected 'key:value'"
                    )
                k, v = entry.split(":", 1)
                result[self._coerce_item(k.strip(), key_type)] = self._coerce_item(v.strip(), val_type)
            return result

        if hasattr(field_type, "__members__"):
            try:
                return field_type[raw]
            except KeyError:
                for member in field_type:
                    if member.name.lower() == raw.lower():
                        return member
                raise OverrideCoercionError(override.field_path, raw, "enum", f"not a valid member")

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        return raw

    def _coerce_item(self, raw: str, item_type: Any) -> Any:
        return self.coerce(OverrideValue(field_path="", raw_value=raw, source=OverrideSource.ENV), item_type)
```

### 3.5 Parsers

Implements: SPEC.md §4.2 (ConfigParserPort contract)

```python
# adapters/parsers/toml_parser.py
import tomllib
from pathlib import Path
from typing import Any

from config_assembler_engine.errors import ConfigParseError
from config_assembler_engine.ports.config_parser import ConfigParserPort


class TomlConfigParser(ConfigParserPort):
    def parse(self, path: Path) -> dict[str, Any]:
        try:
            with path.open("rb") as f:
                return tomllib.load(f)
        except Exception as e:
            raise ConfigParseError(f"Failed to parse TOML {path}: {e}") from e
```

```python
# adapters/parsers/yaml_parser.py
from pathlib import Path
from typing import Any

import yaml

from config_assembler_engine.errors import ConfigParseError
from config_assembler_engine.ports.config_parser import ConfigParserPort


class YamlConfigParser(ConfigParserPort):
    def parse(self, path: Path) -> dict[str, Any]:
        try:
            with path.open(encoding="utf-8") as f:
                result = yaml.safe_load(f)
                return result if result is not None else {}
        except Exception as e:
            raise ConfigParseError(f"Failed to parse YAML {path}: {e}") from e
```

```python
# adapters/parsers/json_parser.py
import json
from pathlib import Path
from typing import Any

from config_assembler_engine.errors import ConfigParseError
from config_assembler_engine.ports.config_parser import ConfigParserPort


class JsonConfigParser(ConfigParserPort):
    def parse(self, path: Path) -> dict[str, Any]:
        try:
            with path.open(encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise ConfigParseError(f"Failed to parse JSON {path}: {e}") from e
```

### 3.6 Factory

````python
from pathlib import Path

from config_assembler_engine.application.use_cases import AssembleConfiguration
from config_assembler_engine.ports.config_parser import ConfigParserPort
from config_assembler_engine.ports.config_validator import ConfigValidatorPort
from config_assembler_engine.ports.path_resolver import ResolutionStrategy
from config_assembler_engine.ports.type_coercer import TypeCoercerPort

from .config_validator import PydanticValidator
from .env_reader import OsEnvironmentReader
from .path_resolver import CompositePathResolver
from .strategies.cli_path import CliPathStrategy
from .strategies.env_path import EnvPathStrategy
from .strategies.directory import DirectoryTraversalStrategy
from .strategies.xdg import XdgStrategy
from .strategies.default_file import DefaultFileStrategy
from .type_coercer import PydanticTypeCoercer


_DEFAULT_STRATEGIES = [
    CliPathStrategy(),
    EnvPathStrategy(),
    DirectoryTraversalStrategy(filename="config.yaml", max_levels=3),
    XdgStrategy(xdg_subdir="", filename="config.yaml"),
    DefaultFileStrategy(path=Path("config.yaml")),
]


def create_standard_assembler(
    parser: ConfigParserPort,
    *,
    strategies: list[ResolutionStrategy] | None = None,
    validator: ConfigValidatorPort | None = None,
    coercer: TypeCoercerPort | None = None,
) -> AssembleConfiguration:
    """Wires standard OS-level adapters for common use cases.

    Args:
        parser: The config format parser.
        strategies: Ordered list of resolution strategies. Defaults to
            [CliPath, EnvPath, DirectoryTraversal, Xdg, DefaultFile].
            Pass a custom list to reorder, skip, or add strategies.
        validator: Pydantic validator (default: PydanticValidator).
        coercer: Type coercer (default: PydanticTypeCoercer).
    """
    env_reader = OsEnvironmentReader()
    return AssembleConfiguration(
        path_resolver=CompositePathResolver(
            strategies if strategies is not None else _DEFAULT_STRATEGIES
        ),
        parser=parser,
        env_reader=env_reader,
        validator=validator or PydanticValidator(),
        coercer=coercer or PydanticTypeCoercer(),
    )
````

---

## 4. Consumer Examples

### ABC Project (Single Config)

```python
from pathlib import Path
from pydantic import BaseModel, Field

from config_assembler_engine import ResolutionPolicy, OverrideRule
from config_assembler_engine.adapters.factories import create_standard_assembler
from config_assembler_engine.adapters.parsers import YamlConfigParser
from config_assembler_engine.adapters.strategies import (
    CliPathStrategy,
    EnvPathStrategy,
    DirectoryTraversalStrategy,
    XdgStrategy,
    DefaultFileStrategy,
)


class AbcConfig(BaseModel):
    engine: str = Field(default="docker")
    mounts: list[str] = Field(default_factory=list)
    map: dict[str, str] = Field(default_factory=dict)


# Build custom resolution chain
strategies = [
    CliPathStrategy(),
    EnvPathStrategy(var="CONFIG_FILE_PATH"),
    DirectoryTraversalStrategy(filename="config.yaml", max_levels=2),
    XdgStrategy(xdg_subdir="abc-project", filename="config.yaml"),
    DefaultFileStrategy(path=Path(__file__).parent / "config-defaults.yaml"),
]

assembler = create_standard_assembler(parser=YamlConfigParser(), strategies=strategies)

result = assembler.execute(
    policy=ResolutionPolicy(env_prefix="ABC_PROJECT"),
    rules=[
        OverrideRule(field_path="mounts", sources={"env", "cli"}),
        OverrideRule(field_path="map", sources={"env", "cli"}),
        OverrideRule(field_path="engine", sources={"cli"}),
    ],
    schema=AbcConfig,
    cli_overrides={"engine": "podman"} if args.engine else None,
)

config = result.config  # AbcConfig instance
```

### Wallpaper Effects Generator (Two Instances)

```python
from pathlib import Path

from config_assembler_engine import ResolutionPolicy
from config_assembler_engine.adapters.factories import create_standard_assembler
from config_assembler_engine.adapters.parsers import TomlConfigParser, YamlConfigParser
from config_assembler_engine.adapters.strategies import (
    CliPathStrategy,
    EnvPathStrategy,
    DirectoryTraversalStrategy,
    XdgStrategy,
    DefaultFileStrategy,
)

WALLPAPER_STRATEGIES = [
    CliPathStrategy(),
    EnvPathStrategy(),
    DirectoryTraversalStrategy(filename="settings.toml", max_levels=2),
    XdgStrategy(xdg_subdir="wallpaper-effects-generator", filename="settings.toml"),
    DefaultFileStrategy(path=Path(__file__).parent / "settings.toml"),
]

EFFECTS_STRATEGIES = [
    CliPathStrategy(),
    EnvPathStrategy(),
    DirectoryTraversalStrategy(filename="effects.yaml", max_levels=2),
    XdgStrategy(xdg_subdir="wallpaper-effects-generator", filename="effects.yaml"),
    DefaultFileStrategy(path=Path(__file__).parent / "effects.yaml"),
]

# Settings assembler
settings_assembler = create_standard_assembler(
    parser=TomlConfigParser(), strategies=WALLPAPER_STRATEGIES
)
settings_result = settings_assembler.execute(
    policy=ResolutionPolicy(env_prefix="WALLPAPER"),
    rules=[...],
    schema=CoreSettings,
)

# Effects assembler (skips XDG)
custom_strategies = [
    CliPathStrategy(),
    EnvPathStrategy(),
    DirectoryTraversalStrategy(filename="effects.yaml", max_levels=2),
    DefaultFileStrategy(path=Path(__file__).parent / "effects.yaml"),
]

effects_assembler = create_standard_assembler(
    parser=YamlConfigParser(), strategies=custom_strategies
)
effects_result = effects_assembler.execute(
    policy=ResolutionPolicy(env_prefix="WALLPAPER"),
    rules=[...],
    schema=EffectsConfig,
)
```
