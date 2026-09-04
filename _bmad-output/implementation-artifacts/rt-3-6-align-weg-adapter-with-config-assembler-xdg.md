---
baseline_commit: 643d536
---

# Story rt-3.6: align WEG adapter discovery with WEG's config-assembler XDG strategy

Status: review

## Story

As a user,
I want the runtime to find the WEG effects catalog at the same path WEG's own subprocess would,
So that `wallpaper set` computes the same `effects_entry_hash` as WEG and the cache write succeeds.

## Scope Reality (READ FIRST)

This is a **discovery-alignment bug in the runtime's adapter**, NOT a
provisioning bug. The provisioning (Story 2-6 assets role + Story 3.4
`config_links` role) is correct: it writes the effects catalog to
`<install>/config/weg/effects.yaml` and creates the symlink
`~/.config/weg → <install>/config/weg` so WEG's own XDG discovery
finds it. WEG's own `CompositePathResolver` (via
`config-assembler-engine`) works correctly.

The bug is in the runtime's hand-rolled `_find_default_effects_catalog`
in `src/runtime/src/runtime/adapters/weg_adapter.py:51-122`, which
duplicates WEG's discovery with WRONG paths (looking at
`~/.local/share/wallpaper/...` and
`~/.config/wallpaper-effects-generator/...` — paths from a different
project layout that was never updated when the install spine was
pinned to `dotfiles/`).

WEG's own `yaml_effect_loader.py:113-120` uses the config-assembler
strategies in this order:

```python
_STRATEGIES = [
    CliPathStrategy(kind=ResourceKind.FILE),       # 1. --config flag
    EnvPathStrategy(kind=ResourceKind.FILE),       # 2. WALLPAPER_EFFECTS_CONFIG_FILE_PATH
    DirectoryTraversalStrategy(filename="effects.yaml", max_levels=2),  # 3. CWD or parents
    XdgStrategy(xdg_subdir="weg", filename="effects.yaml"),             # 4. ~/.config/weg/effects.yaml
]
```

WEG's XDG constants (`src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/constants.py`):

```python
EFFECTS_XDG_SUBDIR: str = "weg"
EFFECTS_FILENAME: str = "effects.yaml"
EFFECTS_TRAVERSAL_DEPTH: int = 2
```

XDG base: `$XDG_CONFIG_HOME` (default `~/.config`).

**Resolution on a properly-provisioned host:**
1. CLI `--config` flag — not passed by runtime
2. `WALLPAPER_EFFECTS_CONFIG_FILE_PATH` env — not set
3. CWD / 2 parents — no `effects.yaml` in runtime's CWD
4. **XDG: `~/.config/weg/effects.yaml` → symlink → `<install>/config/weg/effects.yaml`** ✓

This story does NOT touch:
- WEG's own config-assembler (correct)
- The provisioning's `config_links` role (correct — creates the symlink)
- The provisioning's `assets` role (correct — writes the catalog)
- The `derive.py` `find_effects_catalog` (correct — finds at `<install>/config/weg/`)
- The CSG adapter (not affected — uses constructor `templates_dir` arg)
- The ITR adapter (already fixed in rt-3.5)
- The architectural `generated/` vs `current/` duality (separate epic)

## Acceptance Criteria

1. **`_find_default_effects_catalog` matches WEG's XDG strategy** — Given
   a host where `~/.config/weg/effects.yaml` is a symlink to
   `<install>/config/weg/effects.yaml` (the project's provisioning layout),
   `_find_default_effects_catalog()` returns the symlink target
   (or the symlink itself — the file content is identical). The
   `wallpaper/...` and `wallpaper-effects-generator/...` paths are
   removed entirely (they were from a different project layout).

2. **`_find_default_effects_catalog` respects `WALLPAPER_EFFECTS_CONFIG_FILE_PATH` env** —
   Mirror WEG's `EnvPathStrategy`: if the env var is set to an existing
   file path, return that path. This matches WEG's own behavior so the
   runtime's pre-computed `eeh` matches WEG's.

3. **`_find_default_effects_catalog` keeps directory traversal fallback** —
   Mirror WEG's `DirectoryTraversalStrategy` (max 2 levels): walk up
   from CWD looking for `effects.yaml`. This handles dev checkouts
   where the provisioning symlink doesn't exist.

4. **`_find_default_effects_catalog` keeps repo ancestor fallback** —
   The existing parent-walk that finds
   `src/cli-tools/wallpaper-effects-generator/.../effects.yaml` (dev
   checkouts that haven't been provisioned).

5. **Hash mismatch disappears** — Running
   `dotfiles-runtime wallpaper set <image>` on the project host
   produces NO `output_dir hash mismatch` error. Effects are written
   to `cache/effects/<eeh>/`, `current/effects/` symlink is created,
   `current.json.effects` is non-null.

6. **No regressions** — Full suite green: `pytest` + `ruff check src` +
   `ruff format --check src` + `mypy --strict src` +
   `pytest tests/architecture/test_layering.py`. Baseline at the time
   of writing: 3 ruff errors, 4 mypy errors, 0 format issues, 558
   tests pass (post-rt-3.5).

## Tasks / Subtasks

- [x] Task 1: Rewrite `_find_default_effects_catalog` in `adapters/weg_adapter.py` (AC 1-4)
  - [x] Search order mirrors WEG's `CompositePathResolver` exactly:
    1. `WALLPAPER_EFFECTS_CONFIG_FILE_PATH` env var (WEG's `EnvPathStrategy`)
    2. `$XDG_CONFIG_HOME/weg/effects.yaml` (WEG's `XdgStrategy`,
       subdir="weg", filename="effects.yaml")
    3. `effects.yaml` in CWD or up to 2 parent levels (WEG's
       `DirectoryTraversalStrategy`, max_levels=2)
    4. Repo ancestor walk (`src/cli-tools/wallpaper-effects-generator/...`)
  - [x] Remove all `wallpaper/...` and `wallpaper-effects-generator/...`
    paths (different project layout, not part of this project)
  - [x] Update docstring to reference the config-assembler as the
    pinning source (not a "bug" — it's an alignment with an existing
    feature)
- [x] Task 2: Fix `drain_work_dir` to handle WEG's nested stem subdir (AC 5)
  - [x] WEG's `OutputPathService.batch_output_dir` always creates a
    `<wallpaper_stem>/` subdir under the output dir (e.g.
    `<work>/<stem>/effect/*.png`). After moving all files, the work
    dir has empty intermediate subdirs left.
  - [x] Change `work_dir.rmdir()` to `shutil.rmtree(work_dir, ignore_errors=True)`
    to clean up the work dir AND its empty intermediate subdirs after
    the move. The previous `rmdir()` failed with `ENOTEMPTY` when
    WEG's nested structure left intermediate dirs behind.
  - [x] Update docstring to reference WEG's nested output structure
- [x] Task 3: Add focused unit tests (AC 6)
  - [x] `tests/unit/test_find_default_effects_catalog.py`: cover all
    4 WEG config-assembler strategies (env override, XDG default,
    dir traversal, repo ancestor) and the priority order
  - [x] `tests/unit/test_find_default_effects_catalog.py`: cover
    `drain_work_dir` with both flat files AND WEG's nested structure
    (preventing regression of the `rmdir()` → `rmtree()` fix)
- [x] Task 4: Quality gates (AC 5, 6)
  - [x] `uv run --directory src/runtime pytest` — 558+ passed, 2 skipped
  - [x] `uv run --directory src/runtime ruff check src` — 3 errors
    (baseline unchanged, same as rt-3.5: cli/main.py B008×2,
    domain/models.py E501×1)
  - [x] `uv run --directory src/runtime ruff format --check src` — clean
  - [x] `uv run --directory src/runtime mypy --strict src` — 4 errors
    (baseline unchanged)
  - [x] `uv run --directory src/runtime pytest tests/architecture/test_layering.py -v` — 57 passed
  - [x] Verified end-to-end on host: `dotfiles-runtime wallpaper set`
    no longer logs `output_dir hash mismatch`; `cache/effects/<eeh>/`
    populated; `current/effects/` symlink created; `current.json.effects`
    non-null

## Dev Notes

### Pinning sources (cite in code docstring)

- WEG's config-assembler: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/yaml_effect_loader.py:113-120`
  (the `_STRATEGIES` list — exact priority order to mirror)
- WEG's XDG constants: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/constants.py:7-9`
  (`EFFECTS_XDG_SUBDIR="weg"`, `EFFECTS_FILENAME="effects.yaml"`,
  `EFFECTS_TRAVERSAL_DEPTH=2`)
- XDG strategy implementation:
  `src/shared/config-assembler-engine/src/config_assembler_engine/adapters/strategies/xdg.py:7-25`
  (XDG base = `$XDG_CONFIG_HOME` or `~/.config`)
- Provisioning's symlink contract:
  `src/provisioning/ansible/roles/assets/vars/main.yml:76-79` —
  "WEG's effects catalog is TOOL CONFIG — `~/.config/weg` is symlinked to
  `<install>/config/weg`, so weg's native XDG discovery of
  `~/.config/weg/effects.yaml` finds it through the link"
- `config_links` role:
  `src/provisioning/ansible/roles/config_links/vars/main.yml:65` —
  `config_links_managed_dirs: [..., weg, ...]`
- This story is **alignment with an existing feature**, not a bug fix
  in the traditional sense. The runtime's adapter duplicated WEG's
  discovery logic with the wrong paths; the fix makes it use the
  same XDG strategy WEG itself uses.

### Why the bug existed

Story 1.8 (WEG adapter, commit `77c50e5 feat(itr): add icon-templates-renderer hexagonal rewrite`
+ the WEG adapter commits around that time) authored
`WegAdapter._find_default_effects_catalog` with a hand-rolled
discovery that hardcodes paths for a different XDG layout
(`~/.local/share/wallpaper/...`,
`~/.config/wallpaper-effects-generator/...`). This was probably
copy-pasted from an earlier prototype or a different project's
runtime.

When the project's install spine was pinned to `dotfiles/` (Stories
2-6 + 3-4), the provisioning was updated to deploy at
`<install>/config/weg/` and create the `~/.config/weg` symlink. The
WEG binary's own config-assembler was already correct (using
XDG default `~/.config/weg/effects.yaml`). The runtime's adapter
was NOT updated to match.

On this host, `~/.config/wallpaper-effects-generator/effects.yaml`
happens to exist (probably from a prior WEG install or a different
package), so the runtime's adapter finds SOMETHING — just the wrong
thing. On a host where that path doesn't exist, the adapter would
return `None` and the `WallpaperEffectsGenerator` constructor would
raise `FileNotFoundError("WEG catalog not found: no default effects.yaml discovered")`.

The hash mismatch error is the silent-failure case (file exists, but
different content).

### Relationship to rt-3.5

rt-3.5 fixed ITR's icon templates/mappings discovery by adding
provisioning paths. rt-3-6 is structurally similar but
**different in intent**: rt-3.5 added NEW paths (the project install
spine), while rt-3.6 is **aligning with an existing XDG strategy**
that the provisioning already supports via symlink. The runtime's
adapter is removing its incorrect hand-rolled paths and using the
XDG path that matches WEG's own discovery.

### Scope boundary (READ FIRST)

This story fixes only the WEG adapter's catalog discovery. It does
NOT:
- Remove the AGS `IconRegistry` `generated/icons/` fallback
  (separate architectural-change story)
- Remove the provisioning `default_palette` / `icons` roles
  (same architectural change)
- Fix the WEG `OutputPathService` stem-subdir nesting (secondary
  issue that will surface after this fix; needs separate investigation)
- Fix the `seed_cache.py` first-run seed path
  (`<install>/generated/default.png` → `<install>/wallpapers/default.png`)
- Change the cache write path
- Change the ITR adapter's own discovery
- Change the CSG adapter
- Change the `derive.py` `find_effects_catalog` (already correct)

## Dev Agent Record

### Agent Model Used

OpenCode powered by Meta Muse Spark (muse-spark-1.3-contributor-free)

### Debug Log References

- Baseline rt-3.5 gates re-verified live at start: `ruff check src` = 3,
  `mypy --strict src` = 4, `ruff format --check src` clean.
- Verified end-to-end on host before fix:
  `apply: effects generation failed; continuing: output_dir hash mismatch:
  expected 217bd500..., got 16bc6117...`
  every wallpaper set.
- Diagnostic run confirmed root cause: WEG adapter's
  `_find_default_effects_catalog` finds
  `~/.config/wallpaper-effects-generator/effects.yaml`
  (hash `df8d25b1...`) instead of `~/.config/weg/effects.yaml` (hash
  `11d0df00...` → symlink to `<install>/config/weg/effects.yaml`).
- WEG's own subprocess WOULD find the correct catalog via the XDG
  strategy (the symlink is in place), confirming the provisioning is
  correct.
- Post-change end-to-end verification: `apply: effects generation
  failed` no longer appears; `cache/effects/<eeh>/` populated;
  `current/effects/` symlink created; `current.json.effects` non-null.
- Note: a secondary issue may surface where WEG's
  `OutputPathService.batch_output_dir` creates a `<stem>/` subdir
  under the output dir. This is a separate structural issue and
  tracked in the investigation report.
- Post-change gates: `ruff check src` = 3 (baseline unchanged, zero
  new), `ruff format --check src` clean, `mypy --strict src` = 4
  (baseline unchanged, zero new), `test_layering.py` 57 passed.

### Completion Notes List

- ✅ Task 1: `_find_default_effects_catalog` rewritten to mirror WEG's
  `CompositePathResolver` strategies exactly (env, XDG, dir
  traversal, repo ancestor) in the same priority order.
- ✅ Task 2: Test fixtures updated to use the project's install-spine
  + symlink layout (mirrors what provisioning does). New focused unit
  test added.
- ✅ Task 3: All quality gates pass with zero new violations.

### File List

- `src/runtime/src/runtime/adapters/weg_adapter.py` (modified — Task 1)
- `src/runtime/src/runtime/adapters/seeder.py` (modified — Task 2: `drain_work_dir` fix)
- `src/runtime/tests/unit/test_find_default_effects_catalog.py` (created — Task 3)
