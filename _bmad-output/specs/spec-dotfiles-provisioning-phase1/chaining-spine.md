# Chaining Spine — Install Dir Layout & Settings Contract

Load-bearing companion to `SPEC.md` (CAP-5, Constraints). Holds the install-dir subtree and the exact per-tool settings contract that provisioning must render.

## Install dir

`$XDG_DATA_HOME/dotfiles/` (default `~/.local/share/dotfiles/`). Provisioning resolves it at plan time and bakes absolute paths into the rendered settings files.

```
$XDG_DATA_HOME/dotfiles/
├── wallpapers/                          # unpacked from dotfiles/assets/wallpapers/wallpapers.tar.gz (default.png included)
├── icon-templates/                      # deployed from dotfiles/assets/icon-templates/
├── icon-mappings/*.yaml                # deployed from dotfiles/config/icon-template-color-scheme-mappings/
├── csg-templates/                       # bundled CSG Jinja templates (from CSG defaults/templates)
├── weg-effects.yaml                     # deployed via `weg dump-effects --output`
└── generated/
    ├── palettes/                        # CSG writes colors.yaml + colors.conf + formats here
    ├── effects/                         # WEG writes effect images here
    ├── icons/                           # ITR writes rendered SVGs here
    └── .weg-tmp/                        # WEG temp dir (processing.temp_dir)
```

**Default palette:** generated at apply time by the `default_palette` role via `csg generate <install>/wallpapers/default.png -f conf` (plus standard formats) into `generated/palettes/`. The `overwrite=true` semantic is scoped to that one task via `environment: COLORSCHEME__OUTPUT__OVERWRITE: "true"` — never written into the rendered `~/.config/color-scheme-generator/settings.toml` (which keeps `overwrite = false`).

## Data-flow chain

- CSG: reads wallpaper (positional CLI arg) → writes palette to `<install>/generated/palettes/` (`output.directory`). Reads Jinja templates from `<install>/csg-templates/` via `--templates-dir` (Phase 2 runtime passes it per invocation). Emits Hyprland `colors.conf` via the `conf` format.
- WEG: reads wallpaper (positional CLI arg) → writes effects to `<install>/generated/effects/` (`output.directory`), temps to `<install>/generated/.weg-tmp/` (`processing.temp_dir`). Reads its effects catalog from the deployed `<install>/weg-effects.yaml`.
- ITR: reads SVG templates from `<install>/icon-templates/` (`templates.dir`), reads color scheme from `<install>/generated/palettes/colors.yaml` (`color_scheme.path` — **chains to CSG output**), writes rendered SVGs to `<install>/generated/icons/` (`output.output_dir`).

## Settings files provisioning renders

All resolve through the shared `config-assembler-engine`: CLI `--config` > ENV path var > directory traversal > XDG `$XDG_CONFIG_HOME/<subdir>/` > bundled default. Env override naming `<PREFIX>__SECTION__KEY`; config-file env `<PREFIX>_CONFIG_FILE_PATH`.

### CSG — `~/.config/color-scheme-generator/settings.toml`

Env prefix `COLORSCHEME`; config file env `COLORSCHEME_CONFIG_FILE_PATH`.

```toml
[output]
directory = "<install>/generated/palettes"
verbosity = 1
default_formats = ["json", "sh"]
overwrite = false

[generation]
backend = "pywal"

[runtime]
mode = "container"

[container]
engine = "podman"
image_prefix = "csg"
image_tag = "latest"
timeout_seconds = 300
memory_limit = "512m"
mount_timeout_seconds = 30
```

Templates dir is **not** a settings field — separate resolver chain (CLI `--templates-dir` → env `COLORSCHEME_TEMPLATES_TEMPLATES_DIR` → traversal `templates/` → XDG `~/.config/color-scheme/templates/` → bundled). Decision: provisioning deploys the bundled templates to `<install>/csg-templates/` and the Phase 2 runtime invokes CSG with `--templates-dir <install>/csg-templates/`.

The rendered settings file keeps `overwrite = false` (CSG's safe default). The `default_palette` role's single `csg generate` call overrides it per-task via `environment: COLORSCHEME__OUTPUT__OVERWRITE: "true"` — the override exists only for that one process and never mutates this file.

### WEG — `~/.config/weg/settings.toml`

Env prefix `WALLPAPER`; config file env `WALLPAPER_CONFIG_FILE_PATH`. A custom effects catalog **is** deployed to `<install>/weg-effects.yaml` (emitted via `weg dump-effects --output`), and the WEG effects chain points at it (env `WALLPAPER_EFFECTS_CONFIG_FILE_PATH` or `--effects`).

```toml
version = "1.0"

[execution]
parallel = true
strict = false
max_workers = 0

[output]
verbosity = 1
directory = "<install>/generated/effects"

[processing]
temp_dir = "<install>/generated/.weg-tmp"

[backend]
binary = "magick"

[runtime]
mode = "container"

[container]
engine = "podman"
image_name = "weg"
image_tag = "latest"
image_registry = ""
```

### ITR — `~/.config/itr/settings.toml`

Env prefix `ICON_RENDERER`; config file env `ICON_RENDERER_CONFIG_FILE_PATH`. Resolver is active; ITR has no dump command, so this file is provisioning-authored directly.

```toml
[output]
output_dir = "<install>/generated/icons"
verbosity = 1

[templates]
dir = "<install>/icon-templates"

[color_scheme]
path = "<install>/generated/palettes/colors.yaml"
```

## Dump commands (user-facing only; not used by provisioning)

- `csg dump-config` / `csg dump-templates` — bundled default settings.toml / bundled `.j2` templates.
- `weg dump-config` / `weg dump-effects` — bundled default settings.toml / effects.yaml.
- ITR: none.

## Compositor color fragments (first-boot theming)

The compositor configs provisioning places are static skeletons; the colors they reference are the **default palette fragments** generated from `default.png`:

| Fragment | Source | Target |
|---|---|---|
| Hyprland `colors.conf` | `csg generate -f conf` → `<install>/generated/palettes/colors.conf` | `~/.config/hypr/colors.conf` (copied by `compositor_configs` role) |
| Waybar `colors.css` | CSG `gtk.css` format → `<install>/generated/palettes/colors.gtk.css` (review finding 2026-08-12: corrected from the browser-CSS `css` format; `gtk.css` emits `@define-color` the skeleton consumes) | `~/.config/waybar/colors.css` (copied) |
| Hyprpaper wallpaper ref | `<install>/wallpapers/default.png` | baked into flat static `hyprpaper.conf` |

Skeletons: `dotfiles/config/hypr/hyprland.conf` starts with `source = ~/.config/hypr/colors.conf`; `dotfiles/config/waybar/style.css` starts with `@import "colors.css";`; `dotfiles/config/hyprpaper/hyprpaper.conf` is flat static pointing at the default wallpaper. Phase 2 overwrites only the fragment files on palette change; the skeletons provisioning placed never change.
