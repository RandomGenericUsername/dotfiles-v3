# Shared Data Contract — Runtime Core

Companion to `ARCHITECTURE-SPINE.md`. Pins the on-disk shapes the runtime core owns. Every writer (seeder, ApplyWallpaperUseCase, ReconcileDesktopStateUseCase, InspectStateUseCase, adapters) MUST write exactly these shapes. A field rename or re-nest is a spine change, not an implementation detail.

## current.json (manifest — single current derivation projection)

```json
{
  "schema_version": 2,
  "wallpaper": { "hash": "<sha256-hex>", "source_path": "<abs-or-empty>", "applied_at": "<ISO-8601-UTC>" },
  "monitors": {
    "<monitor-name>": {
      "backend": "hyprpaper|swaybg|swww|mpvpaper",
      "source_hash": "<sha256-hex>",
      "fit_mode": "cover|contain|fill|tile|center|stretch",
      "mpv_options": "<string-or-null>",
      "ipc_socket": "<abs-path-or-null>"
    }
  },
  "palette":   { "hash": "<sha256-hex>", "generated_at": "<ISO-8601-UTC>" },
  "effects":   { "hash": "<sha256-hex>", "generated_at": "<ISO-8601-UTC>" },
  "icons":     { "hash": "<sha256-hex>", "generated_at": "<ISO-8601-UTC>" },
  "applied_at": "<ISO-8601-UTC>"
}
```

Rules:
- `schema_version`: 2 (v1 had flat wallpaper only; v2 adds per-monitor `monitors` object).
- `wallpaper.hash` names `cache/wallpapers/<hash>/`; `palette.hash` names `cache/palettes/<hash>/`, etc.
- `monitors` object keys are monitor names (e.g., `DP-1`, `HDMI-1`). Each monitor config specifies its wallpaper backend and parameters. Names are determined once at seed/apply by the injected `IMonitorSource` adapter (`HyprlandMonitorSource` — `hyprctl monitors -j`; enabled, non-mirrored outputs); `DEFAULT_MONITOR` (`DP-1`) is only the fallback when detection is unavailable (headless/CI).
- `backend`: one of `hyprpaper`, `swaybg`, `swww`, `mpvpaper`. Required.
- `source_hash`: wallpaper content hash (names `cache/wallpapers/<hash>/`). Required.
- `fit_mode`: scaling mode for static backends. Default `cover`. Ignored by `mpvpaper`.
- `mpv_options`: mpv passthrough options string (e.g., `"no-audio --loop-playlist"`). Only for `mpvpaper`.
- `ipc_socket`: absolute path to mpv IPC socket (e.g., `$XDG_RUNTIME_DIR/mpvpaper-<monitor>.sock`). Only for `mpvpaper`.
- Any of palette/effects/icons may be absent (`null`) only when that layer was never derived for the current wallpaper; wallpaper is always present once seeded.
- Written atomically (tmp + `os.replace`).
- Migration: on read, if `monitors` absent (v1), derive single-monitor config from legacy `wallpaper` for all detected monitors using default backend `hyprpaper`.

## history.jsonl (append-only, must-not-lose)

One JSON object per line, append-only, never rewritten, never truncated. Newest on the last line.

```json
{"ts": "<ISO-8601-UTC>", "trigger": "seed|set|reconcile|force|regenerate|doctor|prune", "wallpaper": "<sha256-hex>", "palette": "<sha256-hex|null>", "effects": "<sha256-hex|null>", "icons": "<sha256-hex|null>", "source_path": "<abs-or-empty>"}
```

Optional per-trigger payload (R-1): a line may carry a `details` object (string
keys, JSON values). A real `prune` execution appends exactly one line with
`trigger="prune"` and `details={"removed": <int>, "layers": {<layer>: <int>}}`,
plus `"failed": <int>` when a removal errored; `--dry-run` appends nothing. The
field is absent on all other lines. The machine definition is
`contracts/schemas/history.schema.json` (embedded in the runtime package and
enforced by the history reader); this prose is descriptive.

Rules:
- Appended BEFORE desktop reload is considered complete (AD-4).
- A line is immutable once written; correction of a mistake is a NEW line, never an edit.
- The trigger enum and the `details` shape are defined once in code and
  machine-checked (AD-44); this prose is descriptive. A change to either is a
  shared-contract change, not an implementation detail.
- `force` is a reserved (currently unwritten) value; `reactive` is added by the
  Phase 5 daemon (AD-42).

## meta.json (one per cache entry, co-located in the entry dir)

### cache/wallpapers/<hash>/meta.json

```json
{
  "hash_algorithm": "sha256",
  "kind": "wallpaper",
  "content_hash": "<sha256-hex>",
  "source_path": "<abs-or-null>",
  "imported_at": "<ISO-8601-UTC>"
}
```

### cache/palettes/<hash>/meta.json

```json
{
  "hash_algorithm": "sha256",
  "kind": "palette",
  "entry_hash": "<sha256-hex>",
  "source_wallpaper_hash": "<sha256-hex>",
  "input_template_hash": "<sha256-hex>",
  "artifact_hashes": { "colors.yaml": "<sha256-hex>", "colors.conf": "<sha256-hex>", "colors.gtk.css": "<sha256-hex>", "colors.adw.css": "<sha256-hex>", "colors.sequences": "<sha256-hex>", "colors.rasi": "<sha256-hex>" },
  "generated_at": "<ISO-8601-UTC>"
}
```

### cache/effects/<hash>/meta.json

```json
{
  "hash_algorithm": "sha256",
  "kind": "effects",
  "entry_hash": "<sha256-hex>",
  "source_wallpaper_hash": "<sha256-hex>",
  "input_catalog_hash": "<sha256-hex>",
  "artifact_hashes": { "<filename>.png": "<sha256-hex>" },
  "generated_at": "<ISO-8601-UTC>"
}
```

### cache/icons/<hash>/meta.json

```json
{
  "hash_algorithm": "sha256",
  "kind": "icons",
  "entry_hash": "<sha256-hex>",
  "source_palette_hash": "<sha256-hex>",
  "input_templates_hash": "<sha256-hex>",
  "input_mappings_hash": "<sha256-hex>",
  "artifact_hashes": { "<name>.svg": "<sha256-hex>" },
  "generated_at": "<ISO-8601-UTC>"
}
```

## Derivation-input hashing (cache keys)

Cache keys are the SHA-256 of the canonicalized derivation input set:

| Layer | entry_hash = | Inputs (read from provisioning-owned spine, READ-ONLY) |
| --- | --- | --- |
| wallpaper | `sha256(file_bytes)` | the wallpaper file itself |
| palette | `sha256(wallpaper_hash \|\| template_set_hash)` | CSG templates dir (`<install>/config/color-scheme-generator/templates/`), canonicalized: sorted file list of `(relpath, file_hash)` |
| effects | `sha256(wallpaper_hash \|\| catalog_hash)` | effects catalog (`<install>/config/weg/effects.yaml`) |
| icons | `sha256(palette_hash \|\| templates_hash \|\| mappings_hash)` | icon templates dir (`<install>/icon-templates/`), icon mappings (`<install>/icon-mappings/`) |

`input_template_hash`, `input_catalog_hash`, `input_templates_hash`, `input_mappings_hash` in `meta.json` are the canonicalized-set hashes of the corresponding spine inputs. Canonicalization: sorted list of `(relative_path, sha256(file))`, then `sha256` of the joined list.

## Env-override protocol (AD-7, literal keys)

| Tool | Output-dir override | Notes |
| --- | --- | --- |
| csg | `COLORSCHEME__OUTPUT__DIRECTORY` | runs in container mode (podman/docker via oci-runtime); the override must be passed INTO the container environment, not just the host process |
| weg | `WALLPAPER__OUTPUT__DIRECTORY` | temp is also env-overridable: `WALLPAPER__PROCESSING__TEMP_DIR` (env reader is generic `PREFIX__SECTION__KEY` → `section.key`, verified in config-assembler-engine env_reader + weg env_prefix WALLPAPER) |
| itr | `ICON_RENDERER__OUTPUT__OUTPUT_DIR` | note: key is `output_dir`, not `directory` |
| itr | `ICON_RENDERER__COLOR_SCHEME__PATH` | input redirection for palette chaining |

Precedence per tool's config-assembler chain: CLI `--config`/flag > env override > settings.toml > bundled default. Runtime relies on env override alone; it MUST NOT edit the rendered settings.toml.

## Swap sequence (AD-6 ownership)

Owner: `ReconcileDesktopStateUseCase` (the only writer of the swap). `SeedCacheUseCase` performs the identical sequence once at seed time. `ApplyWallpaperUseCase` updates desired state and delegates the actual swap to Reconcile.

Order:
1. Ensure all cache entries exist (populate via staging-dir, AD-9).
2. Repoint `current/` symlinks (each atomic: tmp symlink + `os.replace`).
   - Repoint wallpaper symlink(s): for each monitor in `current.json.monitors`, create `current/wallpaper-<monitor>.png` → `cache/wallpapers/<hash>/wallpaper.png`.
   - Repoint palette symlinks: `current/colors.conf`, `current/colors.gtk.css`, `current/colors.yaml`, `current/colors.adw.css`, `current/colors.sequences`, `current/colors.rasi` → `cache/palettes/<ph>/...`.
   - Repoint effects dir: `current/effects/` → `cache/effects/<eh>/`.
   - Repoint icons dir: `current/icons/` → `cache/icons/<ih>/`.
3. Write `current.json` (atomic tmp + `os.replace`).
4. Append `history.jsonl`.
5. Trigger desktop reloads per monitor:
   - For each monitor, invoke its backend's reload (hyprctl reload, ags restart, hyprctl hyprpaper wallpaper, mpvpaper IPC, swww img, swaybg restart).
   - Terminal palette applied once from `current/colors.sequences`.

Crash recovery: on next run, `ReconcileDesktopStateUseCase` reads `current.json` and re-derives the `current/` symlinks from it (idempotent repair). If a symlink target is missing (evicted/partial), the entry is treated as a cache miss and regenerated. The desktop is never left pointing at a half-swapped state because each symlink resolves independently to a complete write-once entry.

Login restore: Hyprland session start runs `dotfiles-runtime reconcile` (staggered, fail-open hook in `config/hypr/autostart.lua`, after the hyprpaper IPC socket is ready) so a reboot converges to `current.json` instead of the static `default.png` from `hyprpaper.conf`. This is the same `reconcile` primitive — no separate restore path.

## Consumer-pointer table (gt-2-2, AD-11 exception class)

Consumer *pointers* are the only writes the runtime may make under the
install spine (AD-11 exception, spec'd as data — adding a consumer is a
table entry, never bespoke code):

| Pointer | Target | Owning writer |
| --- | --- | --- |
| `<install>/config/ags/colors.css` | `current/colors.gtk.css` | runtime seeder + reconcile loop |
| `<install>/config/gtk-3.0/colors.css` | `current/colors.gtk.css` | runtime seeder + reconcile loop |
| `<install>/config/gtk-4.0/colors.css` | `current/colors.adw.css` | runtime seeder + reconcile loop |
| `<install>/config/rofi/colors.rasi` | `current/colors.rasi` | runtime seeder + reconcile loop |

Rules (pinned, implemented once in `CacheSeeder.repoint_consumer_symlinks`):
palette null → pointer removed (`missing_ok`); regular file at destination →
replaced with symlink (one-run migration); missing destination parent →
skip+warn (never mkdir into the spine); missing target artifact → skip+warn
(never a dangling consumer link). Health of all pointers is projected by
`inspect status` from the same spec.

Palette artifact set (gt-2-1 / add-rofi-app-launcher): `colors.yaml`, `colors.conf`, `colors.gtk.css`,
`colors.adw.css`, `colors.sequences`, `colors.rasi` — all sha256-addressed in per-entry
`meta.json`; keys unchanged (`sha256(ph‖templates)`). Terminal palette is
applied from `current/colors.sequences`; the rofi root pointer
(`config/rofi/colors.rasi`) feeds every rofi tool via `@import "../colors.rasi"`;
the two-channel GTK mechanism and the `GTK_THEME` hazard are recorded in
`consumer-wiring.md`.
