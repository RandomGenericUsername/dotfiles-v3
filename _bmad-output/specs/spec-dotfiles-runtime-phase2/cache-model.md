# Cache Model — dotfiles-runtime-phase2

Companion to SPEC-dotfiles-runtime-phase2. Holds the layered content-addressed cache shape that the kernel's CAP-2/CAP-3 reference. The pinned on-disk schemas (meta.json per layer, current.json, history.jsonl) and the literal env-override keys live in the adopted `shared-data-contract.md`; this file holds the *structure* and the *flow*.

## Cache layout

```
$XDG_STATE_HOME/dotfiles/                ← state_root (runtime-owned, AD-5)
├── current.json                         ← manifest: current derivation projection
├── history.jsonl                        ← append-only, must-not-lose (AD-4)
├── current/                             ← directory of symlinks (consumers read here)
│   ├── wallpaper.png   → cache/wallpapers/<wh>/wallpaper.png
│   ├── colors.yaml     → cache/palettes/<ph>/colors.yaml
│   ├── colors.conf     → cache/palettes/<ph>/colors.conf
│   ├── colors.gtk.css  → cache/palettes/<ph>/colors.gtk.css
│   ├── effects/        → cache/effects/<eh>/           (dir symlink)
│   └── icons/          → cache/icons/<ih>/              (dir symlink)
└── cache/
    ├── wallpapers/<wh>/{wallpaper.png, meta.json}
    ├── palettes/<ph>/{colors.yaml, colors.conf, colors.gtk.css, meta.json}
    ├── effects/<eh>/{*.png, meta.json}
    └── icons/<ih>/{*.svg, meta.json}
```

## Derivation layers and cache keys

| Layer | entry dir | entry_hash = | Inputs (read-only from spine) |
| --- | --- | --- | --- |
| wallpapers | `cache/wallpapers/<wh>/` | sha256(file bytes) | the wallpaper file |
| palettes | `cache/palettes/<ph>/` | sha256(wh \|\| template_set_hash) | csg templates dir |
| effects | `cache/effects/<eh>/` | sha256(wh \|\| catalog_hash) | effects catalog (`config/weg/effects.yaml`) |
| icons | `cache/icons/<ih>/` | sha256(ph \|\| templates_hash \|\| mappings_hash) | icon templates + icon mappings |

Canonicalized input-set hashing is pinned in `shared-data-contract.md` (Derivation-input hashing).

## First-run seeding (CAP-5, Epic 4 single-source)

Trigger: any runtime command when `current.json` is absent (the
`<install>/wallpapers/default.png` source must exist — the assets role
deploys it; rt-3-8).

1. Hash `<install>/wallpapers/default.png` → `wh`.
2. Create `cache/wallpapers/<wh>/` (hardlink default.png, write meta.json).
3. Hash csg templates dir → template_set_hash; compute `ph`; DERIVE via the
   shared pipeline (`csg generate` with `COLORSCHEME__OUTPUT__DIRECTORY`
   override) into `cache/palettes/<ph>/` (write meta.json). Provisioning
   renders no palette — the runtime is the single producer.
4. Hash effects catalog → catalog_hash; compute `eh`; DERIVE via the shared
   pipeline (`weg batch all` with `WALLPAPER__OUTPUT__DIRECTORY` override)
   into `cache/effects/<eh>/` (write meta.json).
5. Hash icon templates + mappings → templates_hash, mappings_hash; compute
   `ih`; DERIVE via the shared pipeline (`itr render` with
   `ICON_RENDERER__OUTPUT__OUTPUT_DIR` + `ICON_RENDERER__COLOR_SCHEME__PATH`
   overrides) into `cache/icons/<ih>/` (write meta.json).
6. Write `current.json` (all four hashes).
7. Create `current/` symlinks.
8. **R2 consumer paths (rt-4-2):** replace
   `<install>/config/ags/colors.css` with a symlink → `current/colors.gtk.css`
   (remove it when the palette is null). Hyprland needs no consumer path
   (nothing sources `colors.conf`); hyprpaper uses IPC with the resolved
   `current/` path; ITR reads `current/colors.yaml` via its settings path.
9. Append `history.jsonl` line with `trigger: seed`.

After seeding, runtime WRITES nothing under the install spine except the
single documented R2 symlink (AD-11 exception). It still READS spine inputs
(templates, catalog, icon templates/mappings) for regeneration — those are part of the cache key.

## Cache population (AD-9, staging-dir)

Generate into `cache/.staging-<pid>/`, then `os.rename` to the final `cache/<layer>/<hash>/`. An existing final entry is never overwritten; staging is discarded if the target already exists. Prevents concurrent-population races and partial entries.

## Cache-hit flow (CAP-2)

`dotfiles wallpaper set <img>`:
1. Hash img → `wh`.
2. `cache/wallpapers/<wh>/` exists? No → hardlink + meta.json. Yes → skip.
3. Compute `ph` from (wh, template_set_hash). `cache/palettes/<ph>/` exists? No → run csg with `COLORSCHEME__OUTPUT__DIRECTORY=<state>/cache/palettes/<ph>/`, write meta.json. Yes → skip.
4. Compute `eh`. `cache/effects/<eh>/` exists? No → run weg with `WALLPAPER__OUTPUT__DIRECTORY=<state>/cache/effects/<eh>/`, write meta.json. Yes → skip.
5. Compute `ih`. `cache/icons/<ih>/` exists? No → run itr with `ICON_RENDERER__OUTPUT__OUTPUT_DIR=<state>/cache/icons/<ih>/` + `ICON_RENDERER__COLOR_SCHEME__PATH=<state>/cache/palettes/<ph>/colors.yaml`, write meta.json. Yes → skip.
6. Repoint `current/` symlinks (wallpaper → palette → effects → icons).
7. Write `current.json`.
8. Append `history.jsonl`.
9. Reload desktop (CAP-6).

On a full cache hit, steps 2-5 are all skips — the command is just symlink repoint + JSON + reload.
