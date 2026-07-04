## Context

The line-by-line NDJSON fallback in `parse_json_list` raises a misleading error on pretty-printed JSON. The message needs to guide the user, not just report the failure.

## Goals / Non-Goals

**Goals:** The `ParsingError` message suggests using `--format '{{json .}}'` when line-by-line parsing fails.
**Non-Goals:** Detecting pretty-printed JSON automatically (brittle heuristic). The improved message is sufficient.

## Decisions

Update the `raise ParsingError(...)` message at `json_parsing.py:60-63` to include `". If the output is pretty-printed (multi-line), invoke the runtime with --format '{{json .}}' to emit single-line NDJSON."` appended to the existing text.

## Risks / Trade-offs

- None. Only error text changes.