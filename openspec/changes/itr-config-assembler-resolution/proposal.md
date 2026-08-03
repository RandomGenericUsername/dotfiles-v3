## Why

ITR's `AssembledConfigResolver` is wired but inert, and every render requires `--template-dir`, `--color-scheme`, and `--output-dir` on the CLI (or the icons YAML's top-level roots). The siblings (WEG, CSG) resolve analogous paths via config-assembler-engine so they are configured once (settings/env) and optional on the CLI. ITR should do the same: a single, clean, no-workaround resolution axis — settings field first, then discovery — with the inert-resolver ghost removed.

## What Changes

- **Real settings.toml resolution.** `AssembledConfigResolver` is no longer inert: 5 FILE strategies incl. bundled `defaults/settings.toml`; OverrideRules for `output.output_dir`, `output.verbosity`, `templates.dir`, `color_scheme.path` (each `{CLI, ENV}`) → `AppSettings(output, templates, color_scheme)`.
- **New TemplateDirResolver** (port + adapter): discovery-only chain `[DirTraversalStrategy("templates"), XdgDirStrategy("itr","templates")]` returning `Path | None`. No env, no CLI (handled at the settings tier).
- **New ColorSchemeResolver** (port + adapter): discovery-only chain `[DirectoryTraversalStrategy("colors.yaml"), XdgStrategy("itr","colors.yaml")]` returning `Path | None`. Resolves a single scheme FILE.
- **Unified precedence** (one axis, no redundancy): CLI flag > env (`ICON_RENDERER__…`) > settings.toml field > discovery (templates/color_scheme) / bundled default (output_dir) > clear error. The discovery chain reads no env and no CLI, eliminating the siblings' double-env-var.
- **Icons YAML simplified.** Remove top-level `templates_root`/`color_scheme`/`outputs_root`. Per-group `template_dir`/`output_dir` become relative subpaths under the global root, default `"."` (boilerplate drops). Remove per-group `color_scheme` (one global scheme per render). `PathResolutionService` shrinks to a dumb joiner (3-tier precedence leaves the domain).
- **CLI:** `--template-dir`/`--color-scheme`/`--output-dir`/`--config` all optional overrides. New `--config` selects settings.toml. A `_resolve_roots` helper orchestrates settings → discovery → `ResolvedRoots`; raises a clear `ConfigResolutionError` naming the missing root when a required root is None. `list` keeps roots optional (names only); render/validate fail fast.

## Capabilities

### Modified
- `itr-cli` — flags optional; new `--config`; fail-fast root-missing error.
- `itr-config-loading` — icons YAML shape (no roots, relative dirs, no per-group color_scheme); unified precedence; settings/discovery as the lower tiers.
- `itr-architecture` — `ConfigResolverPort` made real; new resolver ports + adapters; domain `ResolvedRoots` replaces `PathOverrides`.

### Removed
- Per-group `color_scheme` field; top-level `templates_root`/`color_scheme`/`outputs_root` keys; the inert `AssembledConfigResolver` ghost; `PathOverrides` (superseded by `ResolvedRoots`).

## Impact

- **Source**: new ports + adapters; modified domain models, services, config loader, icon renderer, factory, CLI. `settings.toml` filled. The existing inert resolver's `ICON_RENDERER` prefix kept; XDG subdir `itr`.
- **Assets/configs**: the user's 7 mapping `*.yaml` + `icons.yaml` are simplified (drop `template_dir: .`, `output_dir: .`, `color_scheme: ~`).
- **Behavior**: `uv run itr render icons.yaml` works with zero flags once settings/env is set; flags override. No functionality lost otherwise.
- **Tests**: new resolver/port/settings/precedence/discovery-fallback tests; port-contract tests cover 2 new ports; integration tests updated; ruff + pytest green.
