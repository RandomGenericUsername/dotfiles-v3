## ADDED Requirements

### Requirement: parse_json_list produces informative error for pretty-printed JSON

`parse_json_list` SHALL produce an informative error message when line-by-line NDJSON parsing fails, suggesting the user invoke the runtime with `--format '{{json .}}'` if the output is pretty-printed (multi-line). The message SHALL include both the failing line number/content AND the format-flag guidance.

#### Scenario: Pretty-printed JSON raises informative error
- **WHEN** `parse_json_list` receives `'{"id":\n  "abc"\n}'` (pretty-printed single object)
- **THEN** the raised `ParsingError.message` contains both `"line 1"` and `"pretty-printed"` and `"--format"`

#### Scenario: Valid NDJSON still parses
- **WHEN** `parse_json_list` receives `'{"id":"a"}\n{"id":"b"}'`
- **THEN** it returns `[{"id":"a"}, {"id":"b"}]` with no error