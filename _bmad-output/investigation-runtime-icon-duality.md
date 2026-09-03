# Investigation: Runtime Icon/Palette Symlink Duality

## User Intent

The user wants to investigate and fix issues with the dotfiles-runtime where
**icons do not change according to the color schema when the wallpaper is set**.
The user suspects:

1. The bar (AGS) is loading icons from the wrong directory
2. The `wallpaper set` command may not be properly generating the color scheme
3. The cache may not be used correctly
4. Icons may not be regenerated when required
5. Symlinks may not be properly switched to the proper locations

The user is driving an **architectural change** to eliminate the duality between
the provisioning-side `generated/` directory and the runtime-side `current/`
directory. The goal: the runtime should be the single source of truth for all
generated artifacts (palette, effects, icons), eliminating the fallback chain
that causes staleness.

## Investigation Methodology

- Execute actual commands (`dotfiles-runtime wallpaper set ...`) and read the
  logs/output — do NOT rely solely on code analysis
- Check actual filesystem state (`~/.local/state/dotfiles/`,
  `~/.local/share/dotfiles/`) after commands
- Cross-reference findings against architecture docs (`shared-data-contract.md`,
  `docs/99`, `docs/01`, `docs/Adding an Icon`, `cache-model.md`,
  `consumer-wiring.md`, `provisioning-delta.md`) and bmad stories
- Fix bugs with minimal scope, write bmad story for each fix
- After fixes, verify end-to-end on the host

## What Was Fixed (committed as `a738733`, story `rt-3-5`)

### Bug: `find_icon_templates` / `find_icon_mappings` looked at wrong paths

**Symptom (before fix):**
```text
apply: icon rendering failed; continuing: icon templates/mappings not found
  (install_spine=/home/inumaki/.local/share/dotfiles)
reconcile: icons layer is null; consumer symlink skipped
```

**Root cause:**
`src/runtime/src/runtime/application/derive.py` searched:
- `install_spine/config/icon-templates-renderer/templates` (WRONG)
- `install_spine/config/icon-templates-renderer/icons.yaml` (WRONG)

But provisioning's assets role (Story 2-6 AC 3/4) places them at:
- `install_spine/icon-templates/` (per `shared-data-contract.md` line 118,
  `docs/01` §1.1, `docs/99` §1, `docs/Adding an Icon` §2)
- `install_spine/icon-mappings/icons.yaml`

The ITR adapter's own discovery (`itr_adapter.py:55-110`) already knew the
correct paths. The bug originated in Story 1.13 (commit 6dc250f) where
`derive.py` was copy-pasted from `find_templates_dir` (CSG, correctly at
`config/color-scheme-generator/templates/`) and `find_effects_catalog` (WEG,
correctly at `config/weg/effects.yaml`) without updating the path for ITR.
The test suite locked the bug in (44 occurrences across 18 test files).

**Fix:** Reorder search to provisioning path first, legacy config path second,
repo ancestors (dev checkouts) third. Update test fixtures to use the correct
paths. Add `test_derive_icon_discovery.py` covering both paths.

**Verified end-to-end:** `wallpaper set` no longer logs the icon error,
`cache/icons/<ieh>/` populated with 50+ SVGs, `current/icons` symlink created,
`current.json.icons` non-null. Battery icon visibly changes between wallpaper
sets.

## What Was Discovered But NOT Yet Fixed

### 1. Effects generation: `output_dir hash mismatch` — **ROOT CAUSE IDENTIFIED**

**Symptom:**
```text
apply: effects generation failed; continuing: output_dir hash mismatch:
  expected 217bd500c3b53c58fe49f0a5429774f7dcbf0bb1044718bdb295b24cb0a15fc9, got
  16bc6117643b40c275565d6428507a3096523bd9f993b91dade9929b4243155b
reconcile: effects layer is null; consumer symlink skipped
```

**Root cause (confirmed by diagnostic run):**

The WEG adapter's `_find_default_effects_catalog` (in
`src/runtime/src/runtime/adapters/weg_adapter.py:51-122`) hardcodes
discovery paths that don't match the project's install spine layout:

```python
# WEG adapter searches:
$XDG_DATA_HOME/wallpaper/config/weg/effects.yaml
$XDG_CONFIG_HOME/wallpaper/config/weg/effects.yaml
$HOME/.local/share/wallpaper/config/weg/effects.yaml
$HOME/.config/wallpaper/config/weg/effects.yaml
$HOME/.config/wallpaper-effects-generator/effects.yaml   ← FOUND HERE on this host
```

But the actual project install spine is `~/.local/share/dotfiles/` (per
`XDG_DATA_HOME` + provisioning's `dotfiles` subdir). The WEG adapter
finds the wrong catalog at `~/.config/wallpaper-effects-generator/effects.yaml`
(hash `df8d25b1...`) instead of the correct one at
`~/.local/share/dotfiles/config/weg/effects.yaml` (hash `11d0df00...`).

Diagnostic output:
```text
=== derive.py find_effects_catalog ===
  catalog: /home/inumaki/.local/share/dotfiles/config/weg/effects.yaml
  hash:   11d0df00729505055766193100151527cbd0d39d360eb37108149c2dfb353c15

=== WEG adapter _find_default_effects_catalog ===
  catalog: /home/inumaki/.config/wallpaper-effects-generator/effects.yaml
  hash:   df8d25b118243b8a8de6ccbc56c8d9324d1ee4d6218517707278b94e53740e03

=== effects_entry_hash (derive) ===
  eeh:    16bc6117643b40c275565d6428507a3096523bd9f993b91dade9929b4243155b  ← got

=== effects_entry_hash (WEG adapter) ===
  eeh:    217bd500c3b53c58fe49f0a5429774f7dcbf0bb1044718bdb295b24cb0a15fc9  ← expected
```

**Same class of bug as rt-3-5 (icon templates/mappings):** the WEG adapter
was written before the project's install spine layout was pinned. The
adapter assumes a different XDG layout (`wallpaper/...` not `dotfiles/...`).

## Full Knowledge of the Effects Bug

**Confirmed root cause:** Same class of bug as rt-3.5 (icon templates/mappings
path mismatch). The WEG adapter's `_find_default_effects_catalog` in
`src/runtime/src/runtime/adapters/weg_adapter.py:51-122` was hardcoded to
discover the catalog at:
- `$XDG_DATA_HOME/wallpaper/config/weg/effects.yaml`
- `$XDG_DATA_HOME/wallpaper/config/wallpaper/effects.yaml`
- `$XDG_CONFIG_HOME/wallpaper/config/weg/effects.yaml`
- `$XDG_CONFIG_HOME/wallpaper/config/wallpaper/effects.yaml`
- `$HOME/.local/share/wallpaper/config/weg/effects.yaml`
- `$HOME/.local/share/wallpaper/config/wallpaper/effects.yaml`
- `$HOME/.config/wallpaper/config/weg/effects.yaml`
- `$HOME/.config/wallpaper/config/wallpaper/effects.yaml`
- `$HOME/.config/wallpaper-effects-generator/effects.yaml` ← FOUND HERE

But the project's actual install spine is `~/.local/share/dotfiles/`,
not `~/.local/share/wallpaper/`. The catalog is at
`~/.local/share/dotfiles/config/weg/effects.yaml`, which the WEG
adapter never checks.

When the WEG adapter calls `generate(wallpaper_path, output_dir)`, it:
1. Re-hashes the wallpaper (`wallpaper_hash`)
2. Finds the catalog at the WRONG path (`~/.config/wallpaper-effects-generator/`)
3. Computes `eeh_weg = effects_entry_hash(wallpaper_hash, catalog_hash_weg)`
4. Validates `output_dir.name == eeh_weg` → fails because `derive.py`
   passed `output_dir.name = eeh_derive` (a different hash computed from
   the correct catalog)

**Fix plan (mirrors rt-3.5):**
- Update `_find_default_effects_catalog` to add:
  `$HOME/.local/share/dotfiles/config/weg/effects.yaml` (primary)
  plus XDG equivalents (`$XDG_DATA_HOME/dotfiles/...`)
- Keep the existing `wallpaper/...` paths as legacy fallbacks
- Keep repo ancestor as final fallback (dev checkouts)
- Update 18 test files that create the WEG catalog at the wrong path

**Secondary WEG structural issue (separate from the hash mismatch):**

WEG's `OutputPathService.batch_output_dir` (`domain/services.py:81-93`)
always creates a subdirectory named after the input file's stem:
`<output_dir>/<wallpaper_stem>/effect/*.png`. The runtime's
cache layout (per `shared-data-contract.md`) expects
`<output_dir>/effect/*.png` (no stem subdir).

The WEG adapter handles this in its verification step (line 414-424,
`rglob("*")`), but the runtime's `derive.py` `ensure_effects` passes
`work = staging/<eeh>/` and the populate callback drains the work dir
into staging. The current flow:

```python
work = staging / eeh                                    # staging/<eeh>/
generated = self._weg.generate(wallpaper_path, work)    # WEG writes to <eeh>/<stem>/effect/*.png
# _validate_output_dir checks work.name == eeh → fails (WEG's eeh != derive's eeh)
```

After fixing the hash mismatch, the next issue would be that WEG writes
to `<eeh>/<stem>/` but the cache expects files directly in `<eeh>/`.
The `drain_work_dir` in `seeder.py` would need to move the contents
from `<eeh>/<stem>/effect/*.png` up to `<eeh>/effect/*.png`, OR the
runtime needs to use a different output dir strategy.

This is a pre-existing structural issue with how the runtime wires
WEG's output, NOT introduced by the hash mismatch fix. It needs to be
addressed in a follow-up story (or as part of the same story if
small enough).

## Stories To Write

Based on full investigation, here are the stories to write:

### Story rt-3-6: Fix WEG catalog discovery path
- **Class:** Same as rt-3.5 (path mismatch, not architectural change)
- **Scope:** `_find_default_effects_catalog` in `weg_adapter.py` + test files
- **Status:** Bug identified with diagnostic data, fix is straightforward

### Story rt-3-7 (or follow-up to rt-3-6): Handle WEG's wallpaper subdir nesting
- **Class:** Pre-existing structural issue (WEG always creates stem subdir)
- **Scope:** `derive.py` `ensure_effects` + `seeder.py` `drain_work_dir`
- **Status:** May surface after rt-3-6 fix; needs investigation

### Story rt-3-8: Fix first-run seed path (`<install>/generated/default.png` → `<install>/wallpapers/default.png`)
- **Class:** Path mismatch
- **Scope:** `seed_cache.py:145` + `cli/main.py:93`
- **Status:** Discovered during investigation, needs to be fixed regardless of architectural change

### Epic 4 (or new epic): Eliminate `generated/` vs `current/` duality
- **Class:** Architectural change
- **Scope:** Provisioning (`default_palette`, `icons` roles), AGS
  (`icon-registry.ts`), runtime (`seed_cache.py` flow), docs
- **Status:** Larger, needs separate planning

## Diagnostic Data Captured

```text
=== derive.py find_effects_catalog ===
  catalog: /home/inumaki/.local/share/dotfiles/config/weg/effects.yaml
  hash:   11d0df00729505055766193100151527cbd0d39d360eb37108149c2dfb353c15

=== WEG adapter _find_default_effects_catalog ===
  catalog: /home/inumaki/.config/wallpaper-effects-generator/effects.yaml
  hash:   df8d25b118243b8a8de6ccbc56c8d9324d1ee4d6218517707278b94e53740e03

=== effects_entry_hash (derive) ===
  eeh:    16bc6117643b40c275565d6428507a3096523bd9f993b91dade9929b4243155b  ← got

=== effects_entry_hash (WEG adapter) ===
  eeh:    217bd500c3b53c58fe49f0a5429774f7dcbf0bb1044718bdb295b24cb0a15fc9  ← expected
```

```text
=== CSG templates (working correctly) ===
derive.py find_templates_dir: ~/.local/share/dotfiles/config/color-scheme-generator/templates
CSG adapter _find_default_templates_dir: ./src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates
both hash: 894b08c5cf445c4f3b5bbaf49ccf5964f1a04b4a22ab1257aeadba1e2f6d9c0e
palette_entry_hash: 4d6f3b48fdf29e13d2e74f60913800e9b9769d38b1611537fae555767e1e269e (match)
```

```text
=== WEG output structure (from test run with WALLPAPER__OUTPUT__DIRECTORY=/tmp/weg-staging/<hash>) ===
/tmp/weg-staging/<hash>/wave/preset/dark_blur.png
/tmp/weg-staging/<hash>/wave/effect/color_overlay.png
/tmp/weg-staging/<hash>/wave/composite/blur-brightness80.png
(NOTE: WEG always creates <stem>/ subdir under output_dir)
```

### 2. First-run seed path mismatch: `install_spine/generated/default.png`

**Symptom:**
```text
seed skipped: provisioning output not found
  (/home/inumaki/.local/share/dotfiles/generated/default.png);
  run provisioning to enable first-run seeding
```

**Root cause:** `seed_cache.py:145` and `main.py:93` look for
`<install>/generated/default.png`, but provisioning's assets role deploys
`default.png` at `<install>/wallpapers/default.png`. The seeder never finds
the file and silently skips, so a freshly provisioned machine never
auto-seeds the default wallpaper.

**The default wallpaper is never set on a fresh install** (user's observation).
This is a separate path-bug from the icons fix.

**Status:** NOT YET FIXED. Part of the bigger architectural change (see below).

### 3. Architectural duality: `generated/` vs `current/`

**The core architectural problem:**

```
PROVISIONING (Phase 1)                          RUNTIME (Phase 2)
─────────────────────                          ─────────────────
~/.local/share/dotfiles/                        ~/.local/state/dotfiles/
├── wallpapers/  (assets role)                 ├── current/
├── generated/                                  │   ├── wallpaper.png → cache/...
│   ├── palettes/ (default_palette role)       │   ├── colors.yaml → cache/...
│   ├── effects/                                │   ├── colors.conf → cache/...
│   └── icons/ (icons role)                     │   └── icons/ → cache/...
├── icon-templates/ (assets role)              ├── cache/
├── icon-mappings/ (assets role)               │   ├── palettes/  (sha256(wh || templates))
├── config/itr/settings.toml                    │   ├── effects/   (sha256(wh || catalog))
└── [consumer symlinks to generated/]           │   └── icons/     (sha256(ph || t || m))
                                               ├── current.json
                                               └── history.jsonl
```

Two systems do the same job:
- **Provisioning** generates palette/effects/icons at bootstrap, writes to
  `<install>/generated/` (NEVER updated per wallpaper)
- **Runtime** generates palette/effects/icons per wallpaper, writes to
  `cache/<layer>/<hash>/`, symlinks to `current/`

AGS `IconRegistry` (`dotfiles/config/ags/lib/icon-registry.ts:48-52`) has a
fallback chain that is the root cause of staleness:

```typescript
const runtimePath = `${RUNTIME_ICONS_DIR}/${variantEntry.output}`   // current/
if (GLib.file_test(runtimePath, GLib.FileTest.EXISTS)) return runtimePath

const provisionPath = `${PROVISION_ICONS_DIR}/${variantEntry.output}`  // generated/
if (GLib.file_test(provisionPath, GLib.FileTest.EXISTS)) return provisionPath

return null
```

If `current/icons/<file>` exists, the runtime version wins. If not (e.g. the
icons symlink points to a different cache dir, or the file name doesn't match
the expected `<output>` from the manifest), AGS silently falls back to the
stale `generated/icons/` which was rendered once at bootstrap against the
DEFAULT palette, not the current wallpaper's palette.

**The user's proposed architectural change:**

- Provisioning deploys **inputs only** (wallpapers, templates, catalog, mappings,
  settings.toml) — no generation
- Runtime is the **single source of truth** for all generated artifacts
- AGS `IconRegistry` looks ONLY at `current/icons/` — no `generated/` fallback
- First-run seed is triggered by a single command (e.g. a systemd unit or the
  user's first `wallpaper set`)
- The default wallpaper is set by the runtime's first-run seed reading from
  `<install>/wallpapers/default.png` (the actual provisioning path)

**Scope of the architectural change (if approved):**
1. **Provisioning**: remove `default_palette` role + `icons` role, update
   bootstrap order, update `verify` criteria
2. **Runtime**: change `seed_cache.py` to use `<install>/wallpapers/default.png`
   (not `<install>/generated/default.png`), use the same derivation pipeline
   as `apply_wallpaper` (consistency)
3. **AGS** (`icon-registry.ts`): remove the `generated/` fallback
4. **ITR settings.toml**: repoint `color_scheme.path` to `<install>/cache/palettes/<ph>/colors.yaml`
   or `<install>/current/colors.yaml` (runtime-managed)
5. **Docs**: update `cache-model.md`, `consumer-wiring.md`, `provisioning-delta.md`,
   `docs/99`, `docs/Adding an Icon`
6. **verify role**: criterion 6 ("either generated/palettes/colors.yaml exists
   OR current/colors.yaml exists") becomes "current/colors.yaml exists"
   (no more OR)

**Benefits:**
- Single source of truth (runtime)
- No staleness (every wallpaper set updates everything via one path)
- AGS is simpler (one path to check)
- Provisioning is simpler (only deploys static inputs)
- First-run seeding uses the same code path as `wallpaper set` (consistency)

**Risks:**
- Fresh-machine bootstrap: after provisioning, the user must run
  `wallpaper set` to set the default wallpaper (or a systemd unit does it)
- Any current consumer relying on `<install>/generated/` paths must be
  updated (ITR settings.toml, AGS icons.json path references, etc.)
- The `verify` role's criterion 6 must change

## File/Folder Map of the Fix

```
~/Development/dotfiles-new-architectures/dotfiles-repo-v3/
├── _bmad-output/
│   ├── implementation-artifacts/
│   │   └── rt-3-5-fix-icon-templates-mappings-discovery-path.md  [NEW]
│   └── sprint-status.yaml  [update for rt-3-5]
├── src/runtime/
│   ├── src/runtime/application/derive.py  [MODIFIED — fix find_* paths]
│   ├── tests/unit/
│   │   ├── test_derive_icon_discovery.py  [NEW]
│   │   └── [18 test files — fixtures updated to use correct paths]
└── (no other changes — minimal scope)
```

## Current State on Host (after fix)

- `~/.local/state/dotfiles/cache/icons/<ieh>/` — populated with 50+ SVGs
- `~/.local/state/dotfiles/current/icons` — symlink → `cache/icons/<ieh>/`
- `~/.local/state/dotfiles/current.json` — has `icons: {hash, generated_at}`
- AGS `IconRegistry` now resolves icons from `current/icons/` (works for
  the icons the runtime generated; the `generated/` fallback is still
  there for the manifest's `<output>` names that don't match the
  cache's SVG names)
- `~/.local/share/dotfiles/config/weg/effects.yaml` exists
- `~/.local/share/dotfiles/csg-templates/` does NOT exist
  (CSG templates are at `config/color-scheme-generator/templates/`)
- `~/.local/share/dotfiles/weg-effects.yaml` does NOT exist
  (WEG catalog is at `config/weg/effects.yaml`)
- `~/.local/share/dotfiles/generated/palettes/` — has files (from old
  provisioning run, BEFORE the icon fix)
- `~/.local/share/dotfiles/generated/icons/` — has files (from old
  provisioning run)

## Quality Gates Baseline (unchanged by this story)

- `pytest`: 558 passed / 2 skipped (was 549 / 2; +9 from new discovery tests)
- `ruff check src`: 3 errors (cli/main.py B008×2, domain/models.py E501×1)
- `ruff format --check src`: clean
- `mypy --strict src`: 4 errors (3 cli_output import-untyped + 1 pre-existing
  domain typing)
- `test_layering.py`: 57 passed

## Next Steps (pending user direction)

1. **Write bmad story for the architectural change** (rt-3.6 or new epic)
2. **Investigate the effects hash mismatch** (separate bug, may have a
   similar path-mismatch root cause)
3. **Fix the `seed_cache.py` path bug** (`<install>/generated/default.png`
   → `<install>/wallpapers/default.png`) as a standalone story
4. **Update AGS `icon-registry.ts`** to remove `generated/` fallback
   (as part of the architectural change)
5. **Update provisioning** to remove `default_palette` and `icons` roles
   (as part of the architectural change)
6. **Update docs** (`cache-model.md`, `consumer-wiring.md`,
   `provisioning-delta.md`, `docs/99`, `docs/Adding an Icon`)

## Key References (pinning sources)

- **Architecture**: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md` line 118
- **Specs**: `_bmad-output/specs/spec-dotfiles-runtime-phase2/cache-model.md`,
  `consumer-wiring.md`, `provisioning-delta.md`
- **Docs**: `docs/01-dotfiles-provisioning-phase1-plan.md` §1.1,
  `docs/99-dotfiles-hexagonal-architecture.md` §1, `docs/02-config-in-spine-pattern.md`,
  `docs/Adding an Icon — ITR and Provisioning Pipeline.md` §2 + §6
- **Epics**: `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md` Epic 3
- **Stories**: 2-6 (assets), 1-11 (first-run seed), 1-13 (apply_wallpaper),
  1-9 (ITR adapter), rt-3-4 (inspect cache list)
- **AGS**: `dotfiles/config/ags/lib/icon-registry.ts:48-52` (the fallback)
- **Runtime code**:
  - `src/runtime/src/runtime/application/derive.py` (FIXED in rt-3.5)
  - `src/runtime/src/runtime/application/seed_cache.py` (has the wrong path bug)
  - `src/runtime/src/runtime/cli/main.py:93` (has the wrong path bug)
  - `src/runtime/src/runtime/adapters/itr_adapter.py:55-110` (correct precedent)
- **Provisioning code**:
  - `src/provisioning/ansible/roles/default_palette/` (to be removed)
  - `src/provisioning/ansible/roles/icons/` (to be removed)
  - `src/provisioning/ansible/roles/assets/` (AC 3 + AC 4 = correct)
