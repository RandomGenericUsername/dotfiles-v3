## ADDED Requirements

### Requirement: Empty list result is valid
The `list()` methods of `ImageManager`, `ContainerManager`, `VolumeManager`, and `NetworkManager` SHALL return an empty list `[]` when the runtime reports zero items (JSON `[]`). An empty result MUST NOT raise `ParsingError`. The parser helper `_parse_json_list` SHALL return `[]` for an empty JSON array.

#### Scenario: Empty container list returns []
- **WHEN** `ContainerManager.list()` is called and the transport returns `RawExecResult(returncode=0, stdout=b"[]", ...)`
- **THEN** the method returns `[]` without raising

#### Scenario: Empty image list returns []
- **WHEN** `ImageManager.list()` is called and the transport returns `RawExecResult(returncode=0, stdout=b"[]", ...)`
- **THEN** the method returns `[]` without raising

#### Scenario: Empty volume list returns []
- **WHEN** `VolumeManager.list()` is called and the transport returns `RawExecResult(returncode=0, stdout=b"[]", ...)`
- **THEN** the method returns `[]` without raising

#### Scenario: Empty network list returns []
- **WHEN** `NetworkManager.list()` is called and the transport returns `RawExecResult(returncode=0, stdout=b"[]", ...)`
- **THEN** the method returns `[]` without raising

### Requirement: Inspect still raises on empty
The parser helper `_parse_json_item` (used by all `inspect()` methods) SHALL raise `ParsingError` when the runtime returns an empty JSON array `[]`, because inspect requires exactly one item.

#### Scenario: Container inspect on empty array raises
- **WHEN** `ContainerManager.inspect("ctr1")` is called and the transport returns `RawExecResult(returncode=0, stdout=b"[]", ...)`
- **THEN** the method raises `ParsingError`

#### Scenario: Empty string is still malformed
- **WHEN** `_parse_json_list("")` is called
- **THEN** it raises `ParsingError` (an empty string is malformed JSON, distinct from a valid empty array)
