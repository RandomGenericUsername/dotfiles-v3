## ADDED Requirements

### Requirement: Hexagonal layering with one-way dependency direction
The module SHALL be organized into four layers — `domain`, `ports`, `adapters`, and `cli` — plus a `factory.py` composition root. The dependency direction SHALL be one-way: `domain` imports only the standard library and siblings within `domain/`; `ports` imports only `domain.*`; `adapters` imports `ports`, `domain.*`, and external libraries; `cli` imports `ports`, `domain.*`, and `factory`; `factory` imports `ports` and `adapters`. Neither `domain` nor `ports` SHALL import `adapters` or `cli`. Neither `adapters` SHALL import `cli`.

#### Scenario: domain imports no pydantic and no outer layers
- **WHEN** the import graph of `src/icon_templates_renderer/domain/**/*.py` is inspected
- **THEN** no file imports `pydantic`, `adapters`, `ports`, or `cli`

#### Scenario: ports import only domain
- **WHEN** the import graph of `src/icon_templates_renderer/ports/**/*.py` is inspected
- **THEN** every non-stdlib import resolves to `icon_templates_renderer.domain.*` (or `TYPE_CHECKING`-guarded)

#### Scenario: adapters never import the CLI
- **WHEN** the import graph of `src/icon_templates_renderer/adapters/**/*.py` is inspected
- **THEN** no file imports `icon_templates_renderer.cli`

### Requirement: Ports are runtime-checkable Protocols, one per file
Every port SHALL be a `typing.Protocol` decorated with `@runtime_checkable`, declared in its own `ports/<role>.py` file with method bodies of `...`, importing only `domain.*` for type references. Concrete adapters SHALL rely on structural subtyping (they MAY declare the port as a base for typing convenience, but inheritance is not required for conformance).

#### Scenario: each port is a runtime-checkable Protocol
- **WHEN** each `ports/*.py` is inspected
- **THEN** it defines exactly one `@runtime_checkable Protocol` whose public methods have `...` bodies

#### Scenario: every adapter satisfies its port via isinstance
- **WHEN** `tests/unit/ports/test_contracts.py` runs
- **THEN** `isinstance(<adapter instance>, <Port>)` is asserted True for every concrete adapter × its declared port
- **AND** `assert_signature_compatible` and `assert_interface_method_count` are asserted for each pair

### Requirement: Frozen immutable domain with Pydantic only at the boundary
All `domain/models.py` classes SHALL be `@dataclass(frozen=True)`. Collection fields SHALL be `tuple[...]`; `dict` fields SHALL be wrapped in `MappingProxyType` via `__post_init__`. `pydantic` SHALL be imported only inside `adapters/schemas/`; the domain SHALL NOT import `pydantic`. An explicit mapper SHALL convert a validated Pydantic schema to domain dataclasses.

#### Scenario: domain classes are frozen
- **WHEN** `domain/models.py` is inspected
- **THEN** every dataclass is decorated with `@dataclass(frozen=True)`

#### Scenario: pydantic imports are confined to schemas
- **WHEN** the import graph of `src/icon_templates_renderer/**/*.py` excluding `adapters/schemas/**` is inspected
- **THEN** no file imports `pydantic`

### Requirement: Composition root is CliDependencies with a build_deps test seam
Dependency wiring SHALL live in `factory.py` as a `CliDependencies` dataclass holding injected ports, with concrete adapters as `field(default_factory=...)` defaults and a `__post_init__` that builds the use-case driver. `cli/main.py` SHALL expose `build_deps(...) -> CliDependencies`, stashed on `ctx.obj["deps"]`. Tests SHALL inject fake ports by monkeypatching `icon_templates_renderer.cli.main.build_deps`; no legacy `set_test_deps`/`_test_deps` hook SHALL exist.

#### Scenario: CLI stashes deps on the context object
- **WHEN** an `itr` command runs
- **THEN** `ctx.obj["deps"]` is a `CliDependencies` whose `icon_renderer` and `output_adapter` are wired

#### Scenario: tests inject a fake icon renderer
- **WHEN** `tests/unit/cli/test_render_command.py` runs
- **THEN** it monkeypatches `cli.main.build_deps` to return a `CliDependencies(icon_renderer=fake_icon_renderer)`
- **AND** the fake's recorded calls observe the request built from the CLI flags

### Requirement: Pure-Python only — no OCI runtime, no subprocess, no containers
The module SHALL NOT depend on `oci-runtime`, SHALL NOT declare `install`/`uninstall` commands, SHALL NOT spawn subprocesses, and SHALL NOT contain a `docker/` package. `pyproject.toml` SHALL omit `oci-runtime` from dependencies.

#### Scenario: no oci-runtime dependency
- **WHEN** `pyproject.toml` is inspected
- **THEN** `oci-runtime` is absent from `dependencies` and from `[tool.uv.sources]`

#### Scenario: no install/uninstall commands
- **WHEN** `itr --help` is invoked
- **THEN** only `render`, `list`, and `validate` commands are listed

### Requirement: Shared library usage is limited to cli-output and config-assembler-engine
`pyproject.toml` SHALL declare editable path dependencies to `cli-output` and `config-assembler-engine` via `[tool.uv.sources]` pointing at `../../shared/<name>`. `oci-runtime` SHALL NOT be referenced.

#### Scenario: uv.sources pin the two shared libraries
- **WHEN** `pyproject.toml` `[tool.uv.sources]` is inspected
- **THEN** `cli-output` and `config-assembler-engine` are editable path deps to `../../shared/<name>`
- **AND** `oci-runtime` is absent