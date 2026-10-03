## 1. Request and hash the artifacts

- [ ] 1.1 `adapters/csg_adapter.py` — add `--format btop-minimal.theme`, `--format btop-balanced.theme`, `--format btop-full.theme` to the requested formats
- [ ] 1.2 `adapters/csg_adapter.py` — add all three to the existence assert on produced outputs
- [ ] 1.3 `adapters/csg_adapter.py` — add all three to the `PaletteArtifacts` construction
- [ ] 1.4 `domain/models.py` — add `colors_btop_minimal`, `colors_btop_balanced`, `colors_btop_full` fields to the `PaletteArtifacts` dataclass
- [ ] 1.5 `adapters/seeder.py:485-493` — `load_palette_entry` populates the three new fields from `artifact_hashes`
- [ ] 1.6 `adapters/seeder.py:657-665` — add all three to the `current/` artifact loop

## 2. Completeness oracle + reconcile lists

- [ ] 2.1 `application/derive.py` — add the three to `PALETTE_ARTIFACT_NAMES` (this is what triggers self-healing of existing entries)
- [ ] 2.2 `application/derive.py` — add the three to the `artifact_hashes` map written on population
- [ ] 2.3 `application/reconcile.py` — add all three to the expected-symlink skip list, the stale-prune set, and `_build_expected_targets` (three separate hardcoded lists; verify all three were found)

## 3. Contracts (SAME COMMIT as section 1-2)

- [ ] 3.1 `contracts/schemas/meta.schema.json` — add the three keys to the `artifact_hashes` `required` array **and** the `properties` map
- [ ] 3.2 `make contracts-check` green — the schema is closed with `additionalProperties: false`, so a one-sided change (runtime without schema, or schema without runtime) fails the build in opposite directions
- [ ] 3.3 Confirm no other strict reader of `artifact_hashes` needs updating

## 4. Tests

- [ ] 4.1 Assert a six-artifact palette entry (the pre-change shape) is evicted by `ensure_palette_entry_complete` — extend the existing self-heal test
- [ ] 4.2 `PaletteArtifacts` construction/serialization round-trip covers the three new fields
- [ ] 4.3 `load_palette_entry` reads all three from a `meta.json` fixture
- [ ] 4.4 `repoint_current_symlinks` creates all three `current/` symlinks; a missing source artifact is skipped with a warning and no dangling link
- [ ] 4.5 Contract schema conformance test covers a `meta.json` with all ten artifacts

## 5. Verification — all machine-checkable

- [ ] 5.1 `uv run --directory src/runtime pytest` green
- [ ] 5.2 `python tests/architecture/test_layering.py` green
- [ ] 5.3 `make contracts-check` green
- [ ] 5.4 Assert the CSG invocation carries all three `--format` flags: a test on `csg_adapter`'s argv construction asserts each flag is present (not a log read)
- [ ] 5.5 Assert `PALETTE_ARTIFACT_NAMES` membership directly
- [ ] 5.6 Integration: after `wallpaper set` against a temp state root, assert all three `current/colors.btop-*.theme` symlinks exist AND `Path.resolve()` lands inside the new palette entry (`assert (cur / name).resolve().is_relative_to(entry_dir)`)
- [ ] 5.7 Self-heal: assert a pre-existing six-artifact entry is evicted and re-derived by `ensure_palette_entry_complete` (unit-level, no host needed)
- [ ] 5.8 Round-trip: `meta.json` written with all ten artifacts validates against the palette schema; one missing any of the three fails — proving the schema is the forcing function, not decoration

Note: on-host steps are intentionally omitted. Everything above is assertable in
CI against a temp state root, so no verification depends on a provisioned machine
or a person's eyes.
