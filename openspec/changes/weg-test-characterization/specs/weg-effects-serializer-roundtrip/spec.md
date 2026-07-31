# WEG Effects Serializer Round-Trip

## Why

The `EffectsSerializer` converts domain `EffectsCatalog` ↔ dict ↔ YAML. The serialize path preserves all fields including parameter bounds (`min`, `max`, `required`, `type`). The deserialize path (`_dict_to_parameter_definition`) ignores `min`, `max`, `required`, and `type` — they are silently dropped on round-trip. The existing round-trip tests only assert `name`/`command`/`count`, so the data loss is invisible.

When the container processor re-loads a serialized effects catalog inside the container, parameter bounds are lost — effects with bounded parameters lose their validation.

This spec defines the round-trip contract for `EffectsSerializer`.

## ADDED Requirements

### Requirement: Full EffectsCatalog round-trip preserves parameter bounds
An `EffectsCatalog` serialized to dict and back SHALL produce an equivalent catalog with identical parameter `min`, `max`, `required`, and `type` values.

#### Scenario: Parameter min and max survive round-trip
- **WHEN** an `EffectDefinition` has a parameter with `min=0`, `max=100`
- **AND** the catalog is serialized via `EffectsSerializer.serialize()`
- **AND** the resulting string is parsed via `EffectsSerializer.deserialize()`
- **THEN** the deserialized parameter SHALL have `min=0` and `max=100`

#### Scenario: Parameter type survives round-trip
- **WHEN** an `EffectDefinition` has a parameter with `type="float"`
- **AND** the catalog is serialized and deserialized
- **THEN** the deserialized parameter SHALL have `type="float"`

#### Scenario: Parameter required flag survives round-trip
- **WHEN** an `EffectDefinition` has a parameter with `required=True`
- **AND** the catalog is serialized and deserialized
- **THEN** the deserialized parameter SHALL have `required=True`

#### Scenario: Effects with zero configurable parameters round-trip
- **WHEN** an `EffectDefinition` has an empty `parameters` dict
- **AND** the catalog is serialized and deserialized
- **THEN** the deserialized effect SHALL have an empty `parameters` dict

### Requirement: EffectsSerializer.serialize produces valid YAML
The serialized output SHALL be parseable by `yaml.safe_load` and conform to the effects YAML schema structure.

#### Scenario: Serialized output is valid YAML with expected keys
- **WHEN** a minimal `EffectsCatalog` (version, one effect) is serialized
- **THEN** `yaml.safe_load(result)` returns a dict with keys `version`, `effects`, `composites`, `presets`, `parameter_types`

### Requirement: EffectsSerializer.deserialize rejects missing required fields
The deserializer SHALL raise `EffectsValidationError` when required fields (`name`, `command` for effects) are missing from the input dict.

#### Scenario: Missing effect name raises error
- **WHEN** `EffectsSerializer.deserialize()` is called with a dict containing an effect without a `name` key
- **THEN** `EffectsValidationError` is raised
