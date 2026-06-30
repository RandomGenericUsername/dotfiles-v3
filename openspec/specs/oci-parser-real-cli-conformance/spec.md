## MODIFIED Requirements

### Requirement: parse_json_item rejects scalar JSON with ParsingError

`domain/json_parsing.py:parse_json_item()` must reject JSON that parses to `int`, `str`, `bool`, or `null` (scalar values). It raises `ParsingError(raw=raw, message="Expected dict or list, got <type>")` instead of returning the scalar and crashing later on `.get()`.

It also rejects empty arrays `[]` (inspect requires exactly one item) and arrays with >1 item (same as before). The new behavior matches the guard in `parse_json_list`.

#### Scenario: Integer JSON inspect output raises ParsingError
- **WHEN** `parse_json_item("42")` is called
- **THEN** `ParsingError` is raised with `raw="42"` and message mentioning `"int"`

#### Scenario: String JSON inspect output raises ParsingError
- **WHEN** `parse_json_item('"hello"')` is called
- **THEN** `ParsingError` is raised with message mentioning `"str"`

#### Scenario: Boolean JSON inspect output raises ParsingError
- **WHEN** `parse_json_item("true")` is called
- **THEN** `ParsingError` is raised with message mentioning `"bool"`

#### Scenario: Null JSON inspect output raises ParsingError
- **WHEN** `parse_json_item("null")` is called
- **THEN** `ParsingError` is raised with message mentioning `"NoneType"`

#### Scenario: Empty array JSON inspect output raises ParsingError
- **WHEN** `parse_json_item("[]")` is called
- **THEN** `ParsingError` is raised with message `"Empty response"`

#### Scenario: Multi-item array JSON inspect output raises ParsingError
- **WHEN** `parse_json_item("[{}, {}]")` is called
- **THEN** `ParsingError` is raised with message `"inspect expects 1 item, got 2"`

#### Scenario: Valid single-dict JSON returns the dict
- **WHEN** `parse_json_item('{"Id":"abc"}')` is called
- **THEN** returns `{"Id": "abc"}` (dict)

#### Scenario: Valid single-item array JSON returns the item dict
- **WHEN** `parse_json_item('[{"Id":"abc"}]')` is called
- **THEN** returns `{"Id": "abc"}` (dict)

### Requirement: Parser implements is_auth_error directly (no base class)

Each parser that supports auth detection defines `is_auth_error(stderr: str) -> bool` on the parser class itself. Parsers without auth (container, volume, network) also define it returning `False`, ensuring uniform interface without a shared base.

#### Scenario: Image parser returns True for auth errors
- **WHEN** `DockerImageParser.is_auth_error("pull access denied for img")` is called
- **THEN** returns `True`

#### Scenario: Container parser returns False for all input
- **WHEN** `DockerContainerParser.is_auth_error("pull access denied")` is called
- **THEN** returns `False` (no auth patterns configured)

### Requirement: ResultChecker handles auth check via injected callable

`ResultChecker.check()` receives `is_auth` as an injected callable (set to `None` for non-image managers). When `is_auth is not None` and stderr matches, `auth_error` is raised. This replaces the `CliBaseManager._check_result` conditional which relied on `getattr(self._parser, "is_auth_error", None)`.

#### Scenario: Container manager ResultChecker skips auth check
- **WHEN** ResultChecker for containers is constructed with `auth_error=None, is_auth=None`
- **THEN** `check()` never enters the auth branch
