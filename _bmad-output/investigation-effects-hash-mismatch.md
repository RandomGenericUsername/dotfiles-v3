# Effects Hash Mismatch — Full Investigation Report (v2)

## TL;DR (REVISED)

The runtime's `WegAdapter._find_default_effects_catalog` duplicates WEG's
config-discovery logic with WRONG paths. The provisioning IS correct
(Story 2-6 assets role writes the catalog, Story 3.4 config_links role
creates the `~/.config/weg` symlink to `<install>/config/weg`). WEG's own
config-assembler XDG discovery (via `constants.py` `EFFECTS_XDG_SUBDIR="weg"`,
`EFFECTS_FILENAME="effects.yaml"`) correctly finds the catalog at
`~/.config/weg/effects.yaml` (following the symlink).

**The bug is in the runtime's adapter, not the provisioning.** The
adapter's hand-rolled discovery (lines 51-122 of `weg_adapter.py`) looks
at `~/.local/share/wallpaper/...` and `~/.config/wallpaper-effects-generator/...`
— paths that match a different XDG layout (`wallpaper/...` not `dotfiles/...`).
These paths were correct for an earlier project layout but were never
updated when the install spine was pinned to `dotfiles/`.

**Fix:** Replace the hand-rolled discovery with the same XDG strategy WEG
itself uses. Specifically: look for `$XDG_CONFIG_HOME/weg/effects.yaml`
(the project's `~/.config/weg` is a symlink to `<install>/config/weg`,
created by the `config_links` provisioning role).

## User's Hypothesis (validated)

> "WEG and CSG both use a config assembler engine that performs discovery
> of settings file per a configured strategy that uses XDG, investigate
> that i dont want you to label that as a bug while its a feature that
> might be possible be interfering, the provision doesnt account for
> those files to be presetn (this is a posibility)"

**Validated partially:** The config-assembler-engine's XDG strategy IS
the feature. The provisioning DOES account for the symlink (via
`config_links` role, Story 3.4). WEG's XDG discovery works correctly
on this host — when the WEG binary is invoked from the shell, it finds
the catalog at `~/.config/weg/effects.yaml` (symlink-resolved).

The bug is NOT in the provisioning or in WEG's discovery. The bug is in
the **runtime's hand-rolled duplication** of WEG's discovery with the
wrong paths.

## WEG's Config-Discovery Stack (the "feature")

WEG uses `config-assembler-engine`'s `CompositePathResolver` with these
strategies (in order) for the effects catalog
(`yaml_effect_loader.py:113-120`):

```python
_STRATEGIES = [
    CliPathStrategy(kind=ResourceKind.FILE),      # 1. --config flag
    EnvPathStrategy(kind=ResourceKind.FILE),      # 2. WALLPAPER_EFFECTS_CONFIG_FILE_PATH env
    DirectoryTraversalStrategy(                   # 3. effects.yaml in CWD or up to 2 parents
        filename=EFFECTS_FILENAME,
        max_levels=EFFECTS_TRAVERSAL_DEPTH,
    ),
    XdgStrategy(                                 # 4. XDG default
        xdg_subdir=EFFECTS_XDG_SUBDIR,            # "weg"
        filename=EFFECTS_FILENAME,                # "effects.yaml"
    ),
]
```

WEG's XDG constants (`constants.py`):
- `EFFECTS_XDG_SUBDIR = "weg"`
- `EFFECTS_FILENAME = "effects.yaml"`
- XDG base: `$XDG_CONFIG_HOME` (default `~/.config`)
- **Result: WEG looks for `~/.config/weg/effects.yaml`**

## Provisioning's Intent (the symlink)

`src/provisioning/ansible/roles/assets/vars/main.yml:76-79`:
> `<install>/config/weg/effects.yaml` (WEG's effects catalog is TOOL CONFIG —
> `~/.config/weg` is symlinked to `<install>/config/weg`, so weg's native XDG
> discovery of `~/.config/weg/effects.yaml` finds it through the link).

`src/provisioning/ansible/roles/config_links/vars/main.yml:65`:
- `config_links_managed_dirs: [..., weg, ...]` — `~/.config/weg` is symlinked

Verified on host:
```text
lrwxrwxrwx 1 inumaki inumaki 46 ago 16 20:04 ~/.config/weg -> /home/inumaki/.local/share/dotfiles/config/weg
# /home/inumaki/.config/weg/effects.yaml and ~/.local/share/dotfiles/config/weg/effects.yaml share inode 3869517
```

## Verified End-to-End Discovery

When the WEG binary is invoked from the shell (no env var, no CLI flag):
- Step 1 (CLI): no `--config` flag → skip
- Step 2 (env): `WALLPAPER_EFFECTS_CONFIG_FILE_PATH` not set → skip
- Step 3 (dir traversal): no `effects.yaml` in CWD or 2 parents → skip
- Step 4 (XDG): `~/.config/weg/effects.yaml` → symlink → `~/.local/share/dotfiles/config/weg/effects.yaml` ✓

So WEG CORRECTLY finds the catalog at `<install>/config/weg/effects.yaml`
via the XDG symlink. The runtime's `WegAdapter.generate()` subprocess
call would also get the right file (same XDG strategy inside WEG).

## The Runtime's Bug

`src/runtime/src/runtime/adapters/weg_adapter.py:51-122` —
`_find_default_effects_catalog` was written before the project's
install-spine layout was pinned. It hardcodes paths for a different
XDG layout:

```python
# CURRENT (buggy) — looks for wallpaper/... and wallpaper-effects-generator/...
xdg_data/wallpaper/config/weg/effects.yaml
xdg_config/wallpaper/config/weg/effects.yaml
home/.local/share/wallpaper/config/weg/effects.yaml
home/.config/wallpaper/config/weg/effects.yaml
home/.config/wallpaper-effects-generator/effects.yaml  ← FOUND HERE on this host
```

On this host, `~/.config/wallpaper-effects-generator/effects.yaml` exists
(probably from a prior install), so the WEG adapter finds the WRONG file
(hash `df8d25b1...`). Meanwhile, WEG's own XDG discovery finds the
CORRECT file at `~/.config/weg/effects.yaml` (hash `11d0df00...`).

The runtime's adapter and WEG compute DIFFERENT `eeh` values because they
load DIFFERENT catalog files → `_validate_output_dir` fails with
`output_dir hash mismatch`.

## Fix

Update `_find_default_effects_catalog` to check the same XDG path WEG's
config-assembler uses (the project's `~/.config/weg/effects.yaml`,
which is a symlink to `<install>/config/weg/effects.yaml`):

```python
# NEW — matches WEG's config-assembler XDG strategy
xdg_config_home / "weg" / "effects.yaml"  # → symlink → <install>/config/weg/effects.yaml
```

Also keep:
- `WALLPAPER_EFFECTS_CONFIG_FILE_PATH` env var (via `EnvPathStrategy` semantics)
- `effects.yaml` in CWD or up to 2 parent levels (`DirectoryTraversalStrategy`)
- Repo ancestor fallback (dev checkouts) — but this is not strictly needed
  since the XDG path now works on both provisioned and dev machines

The new discovery priority:
1. `WALLPAPER_EFFECTS_CONFIG_FILE_PATH` env var (explicit override)
2. `$XDG_CONFIG_HOME/weg/effects.yaml` (XDG default — the project's
   symlink-resolved catalog)
3. Repo ancestor fallback (dev checkouts only)
4. NO `wallpaper/...` paths (those are a different project)

This is the **opposite** of the `derive.py` `find_effects_catalog`
(currently looks at `<install>/config/weg/effects.yaml` — the install
spine path). Both will resolve to the same file via different paths
(derive goes direct, WegAdapter follows the symlink). They're consistent.

The cleanest fix: make `_find_default_effects_catalog` look at
`$XDG_CONFIG_HOME/weg/effects.yaml` (matching WEG), and remove the
`wallpaper/...` paths entirely. If the runtime needs to know the
catalog path for hash computation, it can resolve the symlink to get
the actual file, or it can just use the symlink path directly (the
file's content is the same).

## Secondary Issue (Still Open)

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

**Not addressed by the WEG discovery fix.** This will surface after
fixing the primary hash mismatch. Two options:
- (a) Make the runtime use a different output dir strategy (e.g., pass
  the wallpaper's parent dir, let WEG create the subdir, then flatten)
- (b) Update `drain_work_dir` in `seeder.py` to move `<eeh>/<stem>/*` up
  to `<eeh>/*` after WEG returns

## CSG / ITR (NOT affected)

For comparison:
- **CSG**: `_find_default_templates_dir` only searches repo ancestors.
  `derive.py` finds the templates at
  `<install>/config/color-scheme-generator/templates/` and passes them
  via the `templates_dir` constructor arg. CSG's discovery is bypassed
  in the runtime's flow. Hash matches because provisioning copies
  templates verbatim.
- **ITR**: Already fixed in rt-3-5 (added provisioning paths to
  `_find_default_icon_templates` / `_find_default_icon_mappings`).

## Why This Wasn't Caught Earlier

- Story 1.8 (WEG adapter) was written before the project's install
  spine layout was pinned to `dotfiles/`. The adapter's discovery
  assumed a different XDG layout (`wallpaper/...`).
- The test suite for the WEG adapter probably mocks the catalog
  discovery, so the real-world path mismatch was never tested.
- On this host, `~/.config/wallpaper-effects-generator/effects.yaml`
  happens to exist (probably from a prior install or from a different
  package), so the WEG adapter finds SOMETHING — just the wrong thing.
- Effects generation is a "graceful degradation" path in `apply_wallpaper`
  (effects: null on failure), so the error didn't crash the command —
  it just silently dropped the effects layer. The user only noticed
  because of the noisy log line.

## Files Affected by the Fix

- `src/runtime/src/runtime/adapters/weg_adapter.py` — update
  `_find_default_effects_catalog` to use WEG's XDG strategy
- `src/runtime/tests/**` — update test fixtures that create the WEG
  catalog to use the correct path (`~/.config/weg/effects.yaml` or
  via the install spine `<install>/config/weg/effects.yaml`)

## Suggested Story Name

`rt-3-6-fix-weg-catalog-discovery-path` (or `rt-3-6-align-weg-adapter-with-config-assembler-xdg-strategy`)
