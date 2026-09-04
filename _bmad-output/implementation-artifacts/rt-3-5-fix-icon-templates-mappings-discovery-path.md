---
baseline_commit: f98f864881d7553b787ede76cd988a56f3bd3555
---

# Story rt-3.5: fix icon templates/mappings discovery path

Status: done

## Story

As a user,
I want the runtime to find the icon templates and mappings at the same paths where provisioning actually deploys them,
So that `dotfiles-runtime wallpaper set <img>` regenerates icons per wallpaper and the bar shows palette-aware icons.

## Scope Reality (READ FIRST)

This is a **READER-PATH BUG in the runtime's discovery logic**, not a writer bug.
The hardlink-backed icon cache writer (`populate_via_staging` + `itr` subprocess call) is correct
and unchanged. The ITR adapter's own discovery (`_find_default_icon_templates` / `_find_default_icon_mappings`)
already knows the correct paths. The bug is isolated to two functions in
`src/runtime/src/runtime/application/derive.py` (`find_icon_templates` and
`find_icon_mappings`) that look for the assets in a path the provisioning
chain does NOT use.

What the docs/architecture pin (NOT up for re-litigation):

- `shared-data-contract.md` Derivation-input hashing (line 118):
  > icons | `sha256(palette_hash || templates_hash || mappings_hash)` |
  > icon templates dir (`<install>/icon-templates/`),
  > icon mappings (`<install>/icon-mappings/`)
- `docs/01-dotfiles-provisioning-phase1-plan.md` §1.1 (line 245):
  > SVG icon templates in `<install>/icon-templates/`;
  > icon color mappings (the YAMLs) in `<install>/icon-mappings/`
- `docs/99-dotfiles-hexagonal-architecture.md` §1 (line 263):
  > wallpapers/ icon-templates/ icon-mappings/
- `docs/Adding an Icon — ITR and Provisioning Pipeline.md` §2 (provisioned-location table):
  > SVG templates: `~/.local/share/dotfiles/icon-templates/`
  > ITR mappings: `~/.local/share/dotfiles/icon-mappings/`
- Story 2-6 (assets role) AC 3: SVG icon templates deploy to `<install>/icon-templates/`
- Story 2-6 (assets role) AC 4: Icon color-mapping YAMLs deploy to `<install>/icon-mappings/`
- ITR settings.toml on the host (provisioned):
  > `templates.dir = "<install>/icon-templates"`
  > `color_scheme.path = "<install>/generated/palettes/colors.yaml"`

What the runtime's `derive.py` does (the BUG):

- `find_icon_templates(install_spine)` looks for:
  `install_spine / "config" / "icon-templates-renderer" / "templates"`
- `find_icon_mappings(install_spine)` looks for:
  `install_spine / "config" / "icon-templates-renderer" / "icons.yaml"`

What the ITR adapter's discovery (in `itr_adapter.py`, lines 55-110) does correctly:
- `parent / "icon-templates"` (line 68) — the provisioning path
- `parent / "icon-mappings"` (line 101) — the provisioning path
- Plus repo-ancestor fallbacks (dev checkouts)

The ITR adapter's discovery is the source of truth; `derive.py` was copy-pasted
from `find_templates_dir` (CSG, which legitimately lives at
`<install>/config/color-scheme-generator/templates/`) and `find_effects_catalog`
(WEG, at `<install>/config/weg/effects.yaml`) without updating the path.

Symptom in production:

```text
$ dotfiles-runtime wallpaper set ~/.local/share/dotfiles/wallpapers/aurora.jpg
seed skipped: provisioning output not found (.../generated/default.png)
apply: effects generation failed; continuing: output_dir hash mismatch: ...
apply: icon rendering failed; continuing: icon templates/mappings not found (install_spine=/home/inumaki/.local/share/dotfiles)
reconcile: effects layer is null; consumer symlink skipped
reconcile: icons layer is null; consumer symlink skipped
```

`ensure_icons` raises `RuntimeError("icon templates/mappings not found")` →
`icons: None` in `current.json` → no `current/icons` symlink → AGS `IconRegistry`
falls back to the stale `<install>/generated/icons/` (provisioned once at
bootstrap, never updated per wallpaper). Battery icon stays the provisioned
one regardless of `wallpaper set`. Same class of bug exists for effects
catalog (symptom: `output_dir hash mismatch`), see separate story.

Test-fixture code also encodes the WRONG path (44 occurrences across 18
test files use `install_spine / "config" / "icon-templates-renderer" / ...`),
so the bug was locked in by the test suite. Tests are updated in this
story to use the correct provisioning paths.

This story does NOT touch:
- The ITR adapter's discovery logic (already correct)
- The CSG / WEG discovery (correctly look at `<install>/config/...`)
- The cache write path (correct, write-once staging-dir)
- The `current.json` schema or the `current/` symlink repoint logic
- The AGS `IconRegistry` `generated/` fallback (separate architectural change)
- The `default_palette` / `icons` provisioning roles (separate architectural change)

## Acceptance Criteria

1. **`find_icon_templates` returns the provisioning path** — Given
   `install_spine` is `~/.local/share/dotfiles` with `icon-templates/`
   present (the actual provisioning layout), `find_icon_templates` returns
   `install_spine / "icon-templates"` (the provisioned dir, NOT
   `install_spine / "config" / "icon-templates-renderer" / "templates"`).
   Backwards-compatible: when the legacy `config/icon-templates-renderer/templates/`
   path is also present (dev checkouts that pre-date the assets-role
   restructure), it is still returned as a fallback. Repo-ancestor fallback
   (dev checkouts) is preserved.

2. **`find_icon_mappings` returns the provisioning path** — Same as AC 1 but
   for mappings. Given `install_spine / "icon-mappings" / "icons.yaml"`
   exists, `find_icon_mappings` returns that file. Falls back to
   `install_spine / "icon-mappings"` (if it's a directory of YAMLs), then
   the legacy `config/icon-templates-renderer/icons.yaml`, then repo ancestors.

3. **Wallpaper set generates icons successfully** — Given the runtime is
   invoked on a machine with provisioning-deployed
   `~/.local/share/dotfiles/icon-templates/` and
   `~/.local/share/dotfiles/icon-mappings/icons.yaml`, `wallpaper set`:
   - logs NO `"icon rendering failed"` or `"icon templates/mappings not found"`
   - `current.json.icons` is populated with a non-null hash
   - `current/icons` is a symlink → `cache/icons/<ih>/` containing SVGs
   - `wallpaper set` summary reports `icons generated` (first run) or
     `icons cache hit` (subsequent runs with the same palette hash)

4. **Tests use the correct provisioning paths** — All test setup helpers
   in `src/runtime/tests/**` that build a fake `install_spine` use
   `install_spine / "icon-templates"` and
   `install_spine / "icon-mappings" / "icons.yaml"` (not the legacy
   `config/icon-templates-renderer/...` path). The legacy path is tested
   separately via a fallback test.

5. **No regressions** — Full suite green: `pytest` + `ruff check src` +
   `ruff format --check src` + `mypy --strict src` +
   `pytest tests/architecture/test_layering.py`. Baseline at the time of
   writing: 3 ruff errors, 4 mypy errors, 0 format issues, 549 tests pass.

## Tasks / Subtasks

- [x] Task 1: Fix `find_icon_templates` in `application/derive.py` (AC 1)
  - [x] Reorder search: provisioning path FIRST, then legacy config
    path, then repo ancestors. Provisioning path:
    `install_spine / "icon-templates"`.
  - [x] Update docstring to reference the shared-data-contract + assets
    role + docs/Adding an Icon §2 as the pinning sources.
  - [x] Keep repo-ancestor fallback (dev checkouts).
- [x] Task 2: Fix `find_icon_mappings` in `application/derive.py` (AC 2)
  - [x] Reorder search:
    1. `install_spine / "icon-mappings" / "icons.yaml"` (provisioned file)
    2. `install_spine / "icon-mappings"` (provisioned dir of YAMLs)
    3. `install_spine / "config" / "icon-templates-renderer" / "icons.yaml"` (legacy)
    4. Repo ancestors (dev checkouts)
  - [x] Update docstring with pinning references.
- [x] Task 3: Update test setup helpers (AC 4)
  - [x] Update all `_setup_spine` / `_make_use_case` / `_FakeInstall` / etc.
    helpers in `src/runtime/tests/**` to use:
    ```python
    itr_templates = install_spine / "icon-templates"
    itr_templates.mkdir(parents=True)
    (itr_templates / "terminal.svg").write_text("<svg/>")
    (install_spine / "icon-mappings").mkdir(parents=True, exist_ok=True)
    (install_spine / "icon-mappings" / "icons.yaml").write_text("icons: {}\n")
    ```
  - [x] Do NOT touch the ITR adapter's own unit/integration tests
    (`test_itr_adapter.py`, `test_itr_adapter_integration.py`) which test
    the adapter's own discovery, looking for the
    `icon-templates-renderer` package in repo ancestors (a different
    concern — adapter self-discovery for dev checkouts, not install-spine
    discovery).
- [x] Task 4: Add a fallback test (AC 1, 2)
  - [x] `tests/unit/test_derive_icon_discovery.py`: verify both the
    provisioning path (`<install>/icon-templates/`,
    `<install>/icon-mappings/icons.yaml`) and the legacy
    `config/icon-templates-renderer/...` path (backwards compat for
    ad-hoc dev checkouts) are found.
- [x] Task 5: Quality gates (AC 5)
  - [x] `uv run --directory src/runtime pytest` — 549 passed, 2 skipped
  - [x] `uv run --directory src/runtime ruff check src` — 3 errors
    (baseline unchanged, same as rt-3.3 / rt-3.4: cli/main.py B008×2,
    domain/models.py E501×1)
  - [x] `uv run --directory src/runtime ruff format --check src` — clean
  - [x] `uv run --directory src/runtime mypy --strict src` — 4 errors
    (baseline unchanged, same as rt-3.3 / rt-3.4)
  - [x] `uv run --directory src/runtime pytest tests/architecture/test_layering.py -v` — 57 passed
  - [x] Verified end-to-end on host: `dotfiles-runtime wallpaper set` on
    a machine with provisioning-deployed assets → `apply: icon rendering
    failed` no longer appears, `current/icons` symlink created,
    `current.json.icons` populated.

## Dev Notes

### Pinning sources (cite in code docstring)

- Architecture: `shared-data-contract.md` line 118 — icons input set
- Architecture: `docs/01-dotfiles-provisioning-phase1-plan.md` §1.1 line 245
- Architecture: `docs/99-dotfiles-hexagonal-architecture.md` §1 line 263
- Architecture: `docs/Adding an Icon — ITR and Provisioning Pipeline.md` §2
- Architecture: `docs/02-config-in-spine-pattern.md` §3 line 66
- Provisioning: Story 2-6 (assets role) AC 3 + AC 4
- Provisioning: `src/provisioning/src/provisioning/domain/enums.py:100-101`
  (`AssetKind.ICON_TEMPLATE.spine_segment() == "icon-templates"`,
  `AssetKind.ICON_MAPPING.spine_segment() == "icon-mappings"`)
- ITR adapter: `src/runtime/src/runtime/adapters/itr_adapter.py:55-110`
  (correct precedent — `_find_default_icon_templates` already searches
  `parent / "icon-templates"` line 68, `_find_default_icon_mappings`
  searches `parent / "icon-mappings"` line 101)
- ITR settings.toml on the host:
  `~/.local/share/dotfiles/config/itr/settings.toml`
  (`templates.dir` and `color_scheme.path` paths)

### Why the bug existed

Story 1.13 (commit 6dc250f, "ApplyWallpaperUseCase") authored
`derive.py` by copy-pasting `find_templates_dir` (CSG) and
`find_effects_catalog` (WEG). Both legitimately live at
`<install>/config/<tool>/...` (CSG templates under
`config/color-scheme-generator/templates/`, WEG catalog under
`config/weg/effects.yaml`). The ITR assets were incorrectly assumed to
follow the same pattern, but Story 2-6 (the assets role) places icon
templates and mappings at the spine ROOT (`<install>/icon-templates/`,
`<install>/icon-mappings/`) — the same reason the ITR adapter's own
discovery was later corrected in Story 1.9. The `derive.py` copy-paste
was never reconciled with the provisioning layout, and 44 test-fixture
sites encoded the wrong path, locking the bug in.

### Scope boundary (READ FIRST)

This story fixes only the read/discovery path. It does NOT:
- Remove the AGS `IconRegistry` `generated/icons/` fallback
  (separate architectural-change story — see rt-3.6 candidate)
- Remove the provisioning `default_palette` / `icons` roles
  (same architectural change)
- Change the cache write path
- Change the ITR adapter's own discovery
- Change the CSG / WEG discovery

## Dev Agent Record

### Agent Model Used

OpenCode powered by Meta Muse Spark (muse-spark-1.3-contributor-free)

### Debug Log References

- Baseline rt-3.4 gates re-verified live at start: `ruff check src` = 3
  (cli/main.py B008×2, domain/models.py E501×1), `mypy --strict src` = 4,
  `ruff format --check src` clean.
- Verified end-to-end on host before fix:
  `apply: icon rendering failed; continuing: icon templates/mappings not found (install_spine=...)`
  every wallpaper set.
- Verified end-to-end on host after fix:
  - `apply: icon rendering failed` no longer appears
  - `cache/icons/<ieh>/` populated with 50+ SVGs (battery-0.svg, wifi-*.svg, etc.)
  - `current/icons` symlink created → `cache/icons/<ieh>/`
  - `current.json.icons` populated with a non-null hash
- New test `tests/unit/test_derive_icon_discovery.py` added (fallback
  test for legacy `config/icon-templates-renderer/...` path).
- 18 test files updated to use the correct provisioning paths.
- Post-change gates: `ruff check src` = 3 (baseline unchanged, zero new),
  `ruff format --check src` clean, `mypy --strict src` = 4 (baseline
  unchanged, zero new), `test_layering.py` 57 passed, full suite 549
  passed / 2 skipped (zero regressions vs 550 / 2 baseline).

### Completion Notes List

- ✅ Task 1: `find_icon_templates` reordered to check
  `install_spine / "icon-templates"` first (the actual provisioning
  path), then legacy `config/icon-templates-renderer/templates/`, then
  repo ancestors.
- ✅ Task 2: `find_icon_mappings` reordered to check
  `install_spine / "icon-mappings" / "icons.yaml"` first, then
  `install_spine / "icon-mappings"`, then legacy
  `config/icon-templates-renderer/icons.yaml`, then repo ancestors.
- ✅ Task 3: 18 test files updated to use the correct provisioning
  paths in their `_setup_spine` / `_make_use_case` helpers.
- ✅ Task 4: `tests/unit/test_derive_icon_discovery.py` added — covers
  the primary provisioning path AND the legacy fallback path.
- ✅ Task 5: All quality gates pass with zero new violations.

### File List

- `src/runtime/src/runtime/application/derive.py` (modified — Tasks 1, 2)
- `src/runtime/tests/unit/test_apply_wallpaper.py` (modified — Task 3)
- `src/runtime/tests/unit/test_reconcile.py` (modified — Task 3)
- `src/runtime/tests/unit/test_seed_cache.py` (modified — Task 3)
- `src/runtime/tests/unit/test_crash_recovery.py` (modified — Task 3)
- `src/runtime/tests/unit/test_ags_reloader.py` (modified — Task 3)
- `src/runtime/tests/unit/test_hyprland_reloader.py` (modified — Task 3)
- `src/runtime/tests/unit/test_hyprpaper_reloader.py` (modified — Task 3)
- `src/runtime/tests/unit/test_terminal_color_applier.py` (modified — Task 3)
- `src/runtime/tests/unit/test_cli_crash_recovery.py` (modified — Task 3)
- `src/runtime/tests/integration/test_apply_wallpaper_integration.py` (modified — Task 3)
- `src/runtime/tests/integration/test_reconcile_integration.py` (modified — Task 3)
- `src/runtime/tests/integration/test_seed_cache_integration.py` (modified — Task 3)
- `src/runtime/tests/integration/test_crash_recovery_integration.py` (modified — Task 3)
- `src/runtime/tests/integration/test_ags_reloader_integration.py` (modified — Task 3)
- `src/runtime/tests/integration/test_hyprland_reloader_integration.py` (modified — Task 3)
- `src/runtime/tests/integration/test_hyprpaper_reloader_integration.py` (modified — Task 3)
- `src/runtime/tests/integration/test_terminal_color_applier_integration.py` (modified — Task 3)
- `src/runtime/tests/integration/test_wallpaper_set_capstone_integration.py` (modified — Task 3)
- `src/runtime/tests/unit/test_derive_icon_discovery.py` (created — Task 4)
