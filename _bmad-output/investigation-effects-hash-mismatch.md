# Effects Hash Mismatch — Full Investigation Report

## TL;DR

The runtime's `WegAdapter` (in `src/runtime/src/runtime/adapters/weg_adapter.py`)
finds the effects catalog at the WRONG path. The catalog is at
`~/.config/wallpaper-effects-generator/effects.yaml` (WEG's own bundled
default) instead of the correct `~/.local/share/dotfiles/config/weg/effects.yaml`
(the project's provisioned catalog). This produces a different `effects_entry_hash`
than what `derive.py` computes, so `wallpaper set` fails with
`output_dir hash mismatch: expected 217bd500..., got 16bc6117...`.

**Same class of bug as rt-3.5 (icon templates/mappings).** Fix: add the
project's actual install spine path (`~/.local/share/dotfiles/config/weg/effects.yaml`)
to the WEG adapter's discovery.

## Reproduction

```bash
$ uv run --directory src/runtime dotfiles-runtime wallpaper set ~/.local/share/dotfiles/wallpapers/wave.png
seed skipped: provisioning output not found (...).generated/default.png
apply: effects generation failed; continuing: output_dir hash mismatch:
  expected 217bd500c3b53c58fe49f0a5429774f7dcbf0bb1044718bdb295b24cb0a15fc9, got
  16bc6117643b40c275565d6428507a3096523bd9f993b91dade9929b4243155b
reconcile: effects layer is null; consumer symlink skipped
```

## Diagnostic Run (definitive proof)

```python
from pathlib import Path
from runtime.adapters.hashing import hash_file, effects_entry_hash
from runtime.adapters.weg_adapter import _find_default_effects_catalog
from runtime.application.derive import find_effects_catalog

install_spine = Path("/home/inumaki/.local/share/dotfiles")
wallpaper = install_spine / "wallpapers" / "wave.png"
wallpaper_hash = hash_file(wallpaper)
# wallpaper hash: 3efcd6faa704ab48e53c5fab1945441275a7a0b1d8e2583b44157abcce373c7d

# derive.py finds the catalog at the CORRECT provisioning path
derive_catalog = find_effects_catalog(install_spine)
#   catalog: ~/.local/share/dotfiles/config/weg/effects.yaml
#   hash:    11d0df00729505055766193100151527cbd0d39d360eb37108149c2dfb353c15

# WEG adapter's _find_default_effects_catalog finds it at the WRONG path
weg_catalog = _find_default_effects_catalog()
#   catalog: ~/.config/wallpaper-effects-generator/effects.yaml
#   hash:    df8d25b118243b8a8de6ccbc56c8d9324d1ee4d6218517707278b94e53740e03

# These produce different effects_entry_hash:
# derive.py eeh:  16bc6117643b40c275565d6428507a3096523bd9f993b91dade9929b4243155b  ← matches "got"
# WEG adapter eeh: 217bd500c3b53c58fe49f0a5429774f7dcbf0bb1044718bdb295b24cb0a15fc9  ← matches "expected"
```

## Root Cause

`WegAdapter._find_default_effects_catalog` (weg_adapter.py:51-122) hardcodes
discovery paths that don't match the project's `dotfiles` install spine:

| What WEG adapter searches for | What project actually uses |
|-------------------------------|---------------------------|
| `~/.local/share/wallpaper/...` | `~/.local/share/dotfiles/...` |
| `~/.config/wallpaper/...` | `~/.config/dotfiles/...` (none) |
| `~/.config/wallpaper-effects-generator/effects.yaml` ← FOUND HERE | `~/.local/share/dotfiles/config/weg/effects.yaml` |

The WEG adapter was written for a different XDG layout (`wallpaper/...`)
that doesn't match the project's actual install spine (`dotfiles/...`).
The catalog at `~/.config/wallpaper-effects-generator/effects.yaml` is
WEG's own bundled default (or a user-installed copy from a different
package), not the project's provisioned catalog.

## Fix

Mirror the rt-3.5 approach. Update `_find_default_effects_catalog` to add
the project's actual install spine paths as the primary candidates:

```python
# NEW: install-spine candidates for the dotfiles project (primary)
xdg_data / "dotfiles" / "config" / "weg" / "effects.yaml"
xdg_config / "dotfiles" / "config" / "weg" / "effects.yaml"
$HOME/.local/share/dotfiles/config/weg/effects.yaml
$HOME/.config/dotfiles/config/weg/effects.yaml

# KEEP: existing wallpaper/ paths (legacy)
# KEEP: repo ancestor fallback (dev checkouts)
```

Also update the test suite to use the correct provisioning path (the
tests probably encode the legacy `wallpaper/...` path or don't test
catalog discovery at all).

## Secondary Issue (Discovered During Investigation)

WEG's `OutputPathService.batch_output_dir` (in
`src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/services.py:81-93`)
always creates a subdirectory named after the input file's stem:

```text
WALLPAPER__OUTPUT__DIRECTORY=<hash>/
├── wave/                       ← created by WEG from wallpaper stem
│   ├── effect/color_overlay.png
│   ├── composite/blur-brightness80.png
│   └── preset/dark_blur.png
```

The cache layout (per `shared-data-contract.md`) expects
`cache/effects/<eh>/effect/*.png` (no stem subdir). The WEG adapter
handles this in its verification step (rglob finds nested files), but
the runtime's `derive.py` `ensure_effects` doesn't account for it when
draining the work dir.

After fixing the primary hash mismatch, this secondary issue will
surface. Two options:
- (a) Make the runtime use a different output dir strategy (e.g., pass
  the wallpaper's parent dir, let WEG create the subdir, then flatten)
- (b) Update `drain_work_dir` in `seeder.py` to move `<eeh>/<stem>/*` up
  to `<eeh>/*` after WEG returns

## Why This Wasn't Caught Earlier

- Story 1.8 (WEG adapter) was written before the project's install
  spine layout was pinned (Stories 2-6, 2-7, 2-11). The adapter's
  discovery assumed a different XDG layout.
- The test suite for the WEG adapter probably mocks the catalog
  discovery entirely, so the real-world path mismatch was never
  tested.
- On this host, the `~/.config/wallpaper-effects-generator/effects.yaml`
  file happens to exist (probably from a prior WEG install or from a
  different package), so the WEG adapter found SOMETHING — just the
  wrong thing.
- Effects generation is a "graceful degradation" path in `apply_wallpaper`
  (effects: null on failure), so the error didn't crash the command —
  it just silently dropped the effects layer. The user only noticed
  because of the noisy log line.

## CSG/ITR (NOT affected)

For comparison, CSG and ITR have the correct behavior:

- **CSG**: `_find_default_templates_dir` only searches repo ancestors
  (no install spine path), but `derive.py` correctly finds the templates
  at `<install>/config/color-scheme-generator/templates/` and passes
  them via the `templates_dir` constructor arg. The templates in both
  locations happen to have the same hash (894b08c5...) because the
  provisioning role copies them verbatim.

- **ITR**: `_find_default_icon_templates` and
  `_find_default_icon_mappings` were correctly updated (rt-3.5) to
  check the provisioning paths.

Only WEG needs the path-discovery fix.

## Files Affected by the Fix

- `src/runtime/src/runtime/adapters/weg_adapter.py` — add project
  install spine paths to `_find_default_effects_catalog`
- `src/runtime/tests/**` — update test fixtures that create the WEG
  catalog to use the correct path (similar to what rt-3.5 did for ITR)

## Suggested Story Name

`rt-3-6-fix-weg-catalog-discovery-path` (or similar)
