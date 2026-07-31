## Context

CSG's `info` command currently shows three top-level blocks: `settings`, `backends`, and `sources`. The `sources` array includes a `templates:` entry with the resolved path — but no structured information about *what* templates are available at that path. Users must `ls` the directory to discover available formats.

WEG solves the identical problem for effects by loading an `EffectsCatalog` from `effects.yaml` and emitting `catalog.effects_count` / `composites_count` / `presets_count`. CSG's templates are not authored in a YAML manifest — they are the `.j2` files themselves. The catalog is derivable from directory listing + naming convention.

This change extends WEG's pattern to CSG by treating the template directory as a discoverable catalog, using the existing `ColorFormat` enum as the type system.

## Goals / Non-Goals

**Goals:**
- `csg info` emits a `templates` block analogous to WEG's `catalog` block.
- The templates catalog is derived from scanning the resolved directory, parsing the `colors.<fmt>.j2` naming convention, and mapping to `ColorFormat` enum values.
- Unknown `.j2` files (whose `fmt` does not match any `ColorFormat`) raise `TemplatesValidationError` — drift is surfaced.
- `OutputPort` protocol declares `config_info` explicitly (closing a contract gap).
- Existing template resolution + rendering is untouched — this is a read-only metadata path.
- All 3 output adapters (JSON, Plain, Rich) render the new block.

**Non-Goals:**
- Removing `TemplateDirResolver` or changing its API — still used by container processor and renderer.
- Adding `version` field to CSG info output (separate concern).
- Creating a `templates.yaml` manifest (the files ARE the catalog).
- Any WEG code changes.

## Decisions

### D1: Catalog derivation via naming convention, not YAML manifest

**Choice:** `TemplateCatalogService.derive(dir_path)` scans `*.j2` files, strips the `colors.` prefix and `.j2` suffix, maps the remainder to `ColorFormat`. Files like `README.md` are ignored. Files with unknown format keys raise `TemplatesValidationError`.

**Alternatives considered:**
- *Author a `templates.yaml` manifest:* Strict WEG parity but adds a second source of truth; the manifest would drift from the actual files.
- *Parse Jinja2 AST for output format hints:* Too fragile and complex.

**Why naming convention:** The `colors.<fmt>.j2` pattern is already the existing convention (8 bundled templates follow it exactly). No new config file needed; the catalog is always consistent with what's on disk.

### D2: Validate unknown formats strictly

**Choice:** `derive()` raises `TemplatesValidationError` if any `.j2` file's format key is not a member of `ColorFormat`. This surfaces typos, stray generated files, or forgotten enum additions early.

### D3: Cache by key in the loader

**Choice:** `DirectoryTemplateCatalogLoader` caches the catalog by key (`str(explicit_dir)` or `"__resolved__"` for the auto-resolved path). Multiple `load()` calls with the same key return the same cached catalog. A different key triggers a re-scan.

**Rationale:** The only consumer is `info` (single call per invocation), but caching is cheap and mirrors WEG's `CatalogCache` pattern conceptually. If future commands also need catalog info, the cache avoids redundant directory scans.

### D4: `config_info` declared on `OutputPort` Protocol

**Choice:** Add `config_info(self, settings, backends, sources, templates)` to the `OutputPort` protocol. Currently all 3 concrete adapters implement it but the protocol doesn't declare it — a contract gap. Drop the previously-dead `catalog` parameter (was passed but never consumed by any adapter).

### D5: No changes to `TemplateDirResolver` port

**Choice:** The existing `TemplateDirResolverPort.resolve()` signature (and its mismatch with the concrete resolver's `settings_dir` kwarg) is left untouched. The new `DirectoryTemplateCatalogLoader` wraps the concrete resolver and calls `.resolve()` with no args. The explicit-dir override (`--templates-dir`) is handled by the loader's `explicit_dir` parameter, bypassing the resolver entirely.

## Risks / Trade-offs

- **[New dependency on directory contents]** If a user has custom templates that don't follow the `colors.<fmt>.j2` naming, they'll get a `TemplatesValidationError`. **Mitigation:** The naming convention is already the established convention for CSG templates; `dump-templates` produces files that match it. Custom templates following different naming would need adjustment. The error message clearly states which files are problematic.
- **[No backward compat for the dead `catalog` arg]** `config_info` signature changed: dropped the unused `catalog` parameter, added `templates`. The only caller (`info_cmd.py:92`) is updated atomically in this change.
- **[Test churn]** The info command tests needed fixture updates (added `template_catalog_loader` mock, `templates` key assertions).

## Migration Plan

1. Implement domain models + service + exception.
2. Implement ports + update `OutputPort` protocol.
3. Implement `DirectoryTemplateCatalogLoader` adapter.
4. Update all 3 output adapters (`config_info` signature + templates rendering).
5. Update factory (`create_template_catalog_loader`, `CliDependencies`, `build_deps`).
6. Update `info_cmd.py` (rewire to use catalog loader).
7. Update / create tests.
8. Run full suite + ruff + mypy.

### Rollback strategy

`git revert` the change. All changes are confined to the CSG module (`src/cli-tools/color-scheme-generator/`) and its tests; no shared infrastructure is touched.
