# Shared Data Contract — Runtime Core

Companion to `ARCHITECTURE-SPINE.md`. Pins the on-disk shapes the runtime core owns. Every writer (seeder, ApplyWallpaperUseCase, ReconcileDesktopStateUseCase, InspectStateUseCase, adapters) MUST write exactly these shapes. A field rename or re-nest is a spine change, not an implementation detail.

## current.json (manifest — single current derivation projection)

```json
{
  "schema_version": 1,
  "wallpaper": { "hash": "<sha256-hex>", "source_path": "<abs-or-empty>", "applied_at": "<ISO-8601-UTC>" },
  "palette":   { "hash": "<sha256-hex>", "generated_at": "<ISO-8601-UTC>" },
  "effects":   { "hash": "<sha256-hex>", "generated_at": "<ISO-8601-UTC>" },
  "icons":     { "hash": "<sha256-hex>", "generated_at": "<ISO-8601-UTC>" },
  "applied_at": "<ISO-8601-UTC>"
}
```

Rules:
- `wallpaper.hash` names `cache/wallpapers/<hash>/`; `palette.hash` names `cache/palettes/<hash>/`, etc.
- Any of palette/effects/icons may be absent (`null`) only when that layer was never derived for the current wallpaper; wallpaper is always present once seeded.
- Written atomically (tmp + `os.replace`).

## history.jsonl (append-only, must-not-lose)

One JSON object per line, append-only, never rewritten, never truncated. Newest on the last line.

```json
{"ts": "<ISO-8601-UTC>", "trigger": "seed|set|reconcile|force", "wallpaper": "<sha256-hex>", "palette": "<sha256-hex|null>", "effects": "<sha256-hex|null>", "icons": "<sha256-hex|null>", "source_path": "<abs-or-empty>"}
```

Rules:
- Appended BEFORE desktop reload is considered complete (AD-4).
- A line is immutable once written; correction of a mistake is a NEW line, never an edit.

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
  "artifact_hashes": { "colors.yaml": "<sha256-hex>", "colors.conf": "<sha256-hex>", "colors.gtk.css": "<sha256-hex>" },
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
2. Repoint `current/` symlinks (each atomic: tmp symlink + `os.replace`). Repoint wallpaper first, then palette/colors, then effects/ dir, then icons/ dir.
3. Write `current.json` (atomic tmp + `os.replace`).
4. Append `history.jsonl`.
5. Trigger desktop reloads (Hyprland, AGS bar shell, Hyprpaper, terminal color).

Crash recovery: on next run, `ReconcileDesktopStateUseCase` reads `current.json` and re-derives the `current/` symlinks from it (idempotent repair). If a symlink target is missing (evicted/partial), the entry is treated as a cache miss and regenerated. The desktop is never left pointing at a half-swapped state because each symlink resolves independently to a complete write-once entry.
