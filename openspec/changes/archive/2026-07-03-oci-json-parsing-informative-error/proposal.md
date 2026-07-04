## Why

`domain/json_parsing.py:60-63` raises `ParsingError` with `"Invalid JSON on line N: {"` when the input is pretty-printed (multi-line) JSON. The NDJSON line-by-line fallback treats each line as standalone JSON, fails on the first opening brace, and the error message gives no hint that the user should invoke the runtime with `--format '{{json .}}'` to emit single-line NDJSON. v4 #19 made the branch stricter but didn't improve the message.

## What Changes

- Improve the error message at `domain/json_parsing.py:60-63` to suggest `--format '{{json .}}'` when line-by-line parsing fails. No behavioral change for valid input.

## Capabilities

### Modified Capabilities

- `oci-parser-real-cli-conformance`: `ParsingError` message for pretty-printed output SHALL suggest the `--format '{{json .}}'` flag.

## Impact

- **Code**: one message string in `domain/json_parsing.py:62`.
- **Tests**: one test asserting the message mentions "pretty-printed" and "--format".
- **Risk**: none — only the error text changes.