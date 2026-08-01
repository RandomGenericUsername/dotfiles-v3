## ADDED Requirements

### Requirement: JsonRenderer serializes unknown objects as strings

`JsonRenderer` SHALL serialize `pathlib.Path` objects as their string form and `Enum` members as their value. For any other non-primitive object encountered during serialization, `JsonRenderer` SHALL fall back to its string form (`str(object)`) rather than raising `TypeError`.

#### Scenario: JsonRenderer stringifies an unknown object

- **WHEN** `JsonRenderer().result(ResultView(success=True, fields={"extra": object()}))` is invoked with stdout captured
- **THEN** stdout contains a valid JSON object where `"extra"` is a string
- **AND** no exception is raised

#### Scenario: JsonRenderer still special-cases Path and Enum

- **WHEN** a view field holds a `Path("/out/x.png")` and an enum member
- **THEN** the serialized JSON uses the path string and the enum's value
