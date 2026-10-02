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

## 5. Verification

- [ ] 5.1 `uv run --directory src/runtime pytest` green
- [ ] 5.2 `python tests/architecture/test_layering.py` green
- [ ] 5.3 `make contracts-check` green
- [ ] 5.4 On-host: `dotfiles-runtime wallpaper set <img>` then confirm all three `current/colors.btop-*.theme` symlinks exist and resolve into the new cache entry
- [ ] 5.5 Confirm a pre-existing palette entry was evicted and re-derived (first converge does real work by design)
