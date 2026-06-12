# TDD Status
Plan: `src/shared/oci-runtime/docs/LIST_FORMAT_REMEDIATION.md`

## Done
- [x] Cycle 1: Replace `supported_output_formats` with `list_format_flags` (2026-06-11)
- [x] Cycle 2: Update manager `list()` commands to use `list_format_flags` (2026-06-11)
- [x] Cycle 3: Add NDJSON fallback to `_parse_json_list()` (2026-06-11)
- [x] Cycle 4: Normalize Docker parser `parse_list()` key names (2026-06-11)
- [x] Cycle 5: Normalize Podman parser `parse_list()` key names (2026-06-11)
- [x] Cycle 6: `container.list()` uses capabilities (covered by Cycle 2) (2026-06-11)
- [x] Cycle 7: Update all tests (2026-06-11)

## Next
- None — all cycles complete

## Decisions Made
- Default for `list_format_flags` is `[]` (empty list). Existing call sites (Docker/Podman providers) pass explicit values.
- Empty list `[]` now raises `ParsingError("Empty response")` instead of returning empty list. This is deliberate per prototype validation.
- Docker `VirtualSize` strings (e.g. `"8.454MB"`) are parsed via `parse_size_to_bytes` when `Size` is not available.

## Deviations
- None

## Final Verification
- `grep -rn "supported_output_formats" src/ tests/` — **0 hits** ✅
- `grep -rn "\-\-format.*json" src/oci_runtime/adapters/managers/` — **only inspect commands** ✅
- `grep -rn "list_format_flags" src/oci_runtime/adapters/managers/` — **4 hits** (all managers) ✅
- All **694 tests pass** ✅
