## 1. Improve parse_json_list error message

- [ ] 1.1 In `src/oci_runtime/domain/json_parsing.py:60-63`, append to the `message=` kwarg of `ParsingError`: `". If the output is pretty-printed (multi-line), invoke the runtime with --format '{{json .}}' to emit single-line NDJSON."`.
- [ ] 1.2 Add `test_parse_json_list_pretty_printed_raises_informative` to `tests/unit/domain/test_json_parsing.py` (new file or extend existing): feed `'{"id":\n  "abc"\n}'`, assert `ParsingError` raised and `str(exc.value)` contains `"pretty-printed"` and `"--format"`.
- [ ] 1.3 Add `test_parse_json_list_ndjson_still_works` to the same file: feed `'{"id":"a"}\n{"id":"b"}'`, assert returns two-item list.
- [ ] 1.4 Run `uv run pytest -q tests/unit/domain/test_json_parsing.py` — green.
- [ ] 1.5 Run `uv run ruff check src/oci_runtime/domain/json_parsing.py` — green.