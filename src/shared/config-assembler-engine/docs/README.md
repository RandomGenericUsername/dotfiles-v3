# `config-assembler-engine`

A reusable, stateless, hexagonal configuration resolution engine for Python >= 3.12.

## What it does

Given a **policy** (where to find the config file), a **schema** (what the config should look like), and **override rules** (which fields can be overridden via env vars / CLI args), the engine runs a 7-phase pipeline:

1. Find the config file on disk (CLI path → env var → cwd walk → XDG → default)
2. Parse it (TOML/YAML/JSON — you pick the parser)
3. Validate against a Pydantic schema
4. Read matching environment variables
5. Match env/CLI overrides against registered rules
6. Coerce strings to proper types and merge them into the config
7. Re-validate the final result

Returns a validated config model, the resolved file path, and a list of every override that was applied.

## Quickstart

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
from config_assembler_engine.domain.models import ResourceKind


class AppConfig(BaseModel):
    engine: str = Field(default="docker")
    timeout: int = Field(default=30)
    mounts: list[str] = Field(default_factory=list)


# Build the resolution chain — order matters, first hit wins
# Every strategy requires an explicit `kind` — FILE for config files, DIRECTORY for directories
strategies = [
    CliPathStrategy(kind=ResourceKind.FILE),
    EnvPathStrategy(var="CONFIG_FILE_PATH", kind=ResourceKind.FILE),
    DirectoryTraversalStrategy(filename="config.yaml", max_levels=2, kind=ResourceKind.FILE),
    XdgStrategy(xdg_subdir="my-app", filename="config.yaml", kind=ResourceKind.FILE),
    DefaultFileStrategy(path=Path("defaults.yaml"), kind=ResourceKind.FILE),
]

assembler = create_standard_assembler(parser=YamlConfigParser(), strategies=strategies)

result = assembler.execute(
    policy=ResolutionPolicy(env_prefix="MY_APP"),
    rules=[
        OverrideRule(field_path="timeout", sources={"env", "cli"}),
        OverrideRule(field_path="mounts", sources={"env"}),
        OverrideRule(field_path="engine", sources={"cli"}),
    ],
    schema=AppConfig,
    cli_overrides={"engine": "podman"},
)

config = result.config        # validated AppConfig instance
src = result.resolved_path     # where the file was found
overrides = result.applied_overrides  # what was overridden
```

## Directory Resolution

The engine also provides `AssembleDir` for resolving directories rather than files:

```python
from pathlib import Path

from config_assembler_engine import ResolutionPolicy
from config_assembler_engine.adapters.factories import create_directory_assembler
from config_assembler_engine.adapters.strategies import (
    CliDirStrategy, EnvDirStrategy, XdgDirStrategy, DefaultDirStrategy,
)


strategies = [
    CliDirStrategy(),                                      # --templates /path
    EnvDirStrategy(var="TEMPLATES_DIR"),                    # APP_TEMPLATES_DIR
    XdgDirStrategy(xdg_subdir="my-app", dirname="templates"),  # ~/.config/my-app/templates
    DefaultDirStrategy(path=Path("defaults/templates")),    # fallback
]

assembler = create_directory_assembler(strategies=strategies, file_pattern="*.j2")
result = assembler.execute(ResolutionPolicy(env_prefix="MY_APP"))

directory = result.directory  # resolved Path
files = result.files          # sorted list of matching Paths
source = result.source        # PathSource enum
```

Each file strategy has a directory counterpart (`CliDirStrategy`, `EnvDirStrategy`, `DirTraversalStrategy`, `XdgDirStrategy`, `DefaultDirStrategy`) that presets `kind=DIRECTORY` and validates with `is_dir()` instead of `is_file()`.

## File discovery priority

The resolution chain is built from ordered strategies. Default order:

```
1.  --config /explicit/path.yaml         CliPathStrategy
2.  MY_APP_CONFIG_FILE_PATH=/x.yaml      EnvPathStrategy (single underscore)
3.  ./config.yaml → ../config.yaml       DirectoryTraversalStrategy
4.  ~/.config/my-app/config.yaml         XdgStrategy
5.  /fallback/defaults.yaml              DefaultFileStrategy
```

You can reorder, skip, or replace strategies freely.

## Override precedence

CLI overrides win over env overrides. For the same field, whichever is processed last wins (CLI is sorted after ENV). Within the same source, order is preserved.

## Document index

| Document | What's in it |
|----------|-------------|
| [SPEC.md](./SPEC.md) | Source of truth — contracts, protocols, models, formal algorithms |
| [PROTOTYPE.md](./PROTOTYPE.md) | Reference implementation that validated the spec decisions |
| [ADR.md](./ADR.md) | Architecture Decision Records — why every design choice was made |

## When to use this

Your app needs config files with a multi-location discovery chain (cwd → parents → XDG → default) + env/CLI overrides with provenance tracking. You want it stateless, testable, and with no framework lock-in beyond Pydantic.

## When not to use this

- You only need `pydantic-settings` (env-only, no file discovery)
- You want a global singleton config object
- Your config is a single hardcoded file with no overrides
