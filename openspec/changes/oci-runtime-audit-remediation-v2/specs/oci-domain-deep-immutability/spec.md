## ADDED Requirements

### Requirement: Domain value objects are deeply immutable

All domain dataclasses in `domain/types.py` SHALL hold only immutable container types. `dict` fields SHALL be stored as `MappingProxyType` (from `types`), and `list` fields SHALL be stored as `tuple`. This extends `frozen=True` (which prevents attribute reassignment) to also prevent mutation of held container contents. The zero-dependency constraint SHALL be preserved — only stdlib (`types.MappingProxyType`, `collections.abc.Mapping`) is used.

#### Scenario: Dict field cannot be mutated after construction
- **WHEN** a `RunConfig` is constructed with `environment={"KEY": "val"}` and code attempts `config.environment["NEW"] = "x"`
- **THEN** `TypeError` is raised (mappingproxy does not support item assignment)

#### Scenario: List field is a tuple after construction
- **WHEN** an `ImageInfo` is constructed with `tags=["alpine:latest"]`
- **THEN** `info.tags` is a `tuple`, not a `list`, and `isinstance(info.tags, tuple)` is `True`

#### Scenario: Empty dict field equals empty dict
- **WHEN** a `RunConfig` is constructed with default `environment`
- **THEN** `config.environment == {}` is `True` (MappingProxyType delegates `__eq__` to underlying dict)

#### Scenario: Frozen attribute reassignment still blocked
- **WHEN** code attempts `config.image = "new"`
- **THEN** `dataclasses.FrozenInstanceError` is raised (unchanged from current behavior)

#### Scenario: None command stays None
- **WHEN** a `RunConfig` is constructed with `command=None`
- **THEN** `config.command is None` (not converted to empty tuple)

#### Scenario: Adapter code works unchanged
- **WHEN** adapters iterate `config.environment.items()`, `config.volumes`, `config.ports`, or call `cmd.extend(config.runtime_flags)`
- **THEN** no errors occur (tuple and MappingProxyType support iteration, `.items()`, and `extend()`)
