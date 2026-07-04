## ADDED Requirements

### Requirement: Frozen domain mappings are copied before wrapping

`_freeze_mapping` SHALL copy the source dict before wrapping it in `MappingProxyType`: `object.__setattr__(self, name, MappingProxyType(dict(value)))`. A caller that retains the original dict reference MUST NOT be able to mutate the "frozen" dataclass instance by mutating that dict. This restores the deep-immutability guarantee for every `Mapping`-typed domain field (`BuildContext.files/build_args/labels/build_contexts`, `RunConfig.environment/labels`, and every `*.labels` on info objects).

#### Scenario: Mutating the source dict does not affect a frozen instance
- **WHEN** `RunConfig(image="x", environment={"A": "1"})` is constructed and the original `{"A": "1"}` dict is mutated to `{"A": "1", "B": "MUTATED"}` after construction
- **THEN** `config.environment` is unchanged (`{"A": "1"}`); no `"B"` key is visible

#### Scenario: BuildContext files dict is isolated
- **WHEN** `BuildContext(build_file_content="FROM alpine", files={"Dockerfile": b"..."})` is constructed and the caller's files dict gains a new entry after construction
- **THEN** `ctx.files` reflects only the entries present at construction time

### Requirement: PortMapping validates port range and protocol

`PortMapping.__post_init__` SHALL reject invalid ports and protocols at construction: `0 < container_port <= 65535`, `host_port is None or 0 < host_port <= 65535`, and `protocol in ("tcp", "udp", "sctp")`. Invalid values raise `ValueError`. This matches the validation pattern already established by `VolumeMount` and `RunConfig`.

#### Scenario: Container port out of range raises
- **WHEN** `PortMapping(container_port=70000, host_ip=None)` is constructed
- **THEN** `ValueError` is raised

#### Scenario: Negative host port raises
- **WHEN** `PortMapping(container_port=80, host_port=-1, host_ip=None)` is constructed
- **THEN** `ValueError` is raised

#### Scenario: Invalid protocol raises
- **WHEN** `PortMapping(container_port=80, host_ip=None, protocol="foo")` is constructed
- **THEN** `ValueError` is raised

#### Scenario: Valid tcp mapping accepted
- **WHEN** `PortMapping(container_port=80, host_port=8080, host_ip="127.0.0.1")` is constructed
- **THEN** no exception is raised and `protocol == "tcp"`

### Requirement: RuntimeCapabilities enforces tuple fields at construction

`RuntimeCapabilities.__post_init__` SHALL coerce each `tuple[str, ...]`-typed field (`list_format_flags`, `default_build_flags`, and any other sequence-typed field) via `tuple(...)` so that a list passed by the caller is converted to a tuple on the frozen instance. The stored sequence MUST NOT be a mutable `list`.

#### Scenario: List passed as list_format_flags is coerced to tuple
- **WHEN** `RuntimeCapabilities(list_format_flags=["--format", "{{json .}}"])` is constructed
- **THEN** `isinstance(caps.list_format_flags, tuple)` is `True` and `caps.list_format_flags == ("--format", "{{json .}}")`

#### Scenario: Mutating the source list does not affect the capabilities
- **WHEN** a list `flags = ["--format"]` is passed to `RuntimeCapabilities(list_format_flags=flags)` and `flags.append("x")` is called after construction
- **THEN** `caps.list_format_flags == ("--format",)` (unchanged)
