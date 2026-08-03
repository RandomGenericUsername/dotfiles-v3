## Context

ITR (`add-icon-templates-renderer` change) shipped with an inert `AssembledConfigResolver` (resolves only `output.verbosity`, unused by commands) and a `PathResolutionService` that resolves per-group `template_dir`/`output_dir`/`color_scheme` from CLI override → YAML top-level root → YAML-relative. Every render today requires the three CLI flags because no settings discovery fills them. WEG resolves settings.toml + effects.yaml via config-assembler; CSG resolves settings.toml + a templates DIR via config-assembler (`TemplateDirResolver`, 5 Dir strategies). ITR should adopt the same engine, but with a cleaner single-axis model: settings field is the top priority for all three paths (user request), with discovery (traversal/XDG) only as the fallback when the settings field is absent.

## Goals / Non-Goals

**Goals:** real settings.toml holding `[output] output_dir`, `[templates] dir`, `[color_scheme] path`; OverrideRules for each (CLI+ENV) feeding config-assembler; new `TemplateDirResolver` + `ColorSchemeResolver` (discovery-only, no env/cli); unified precedence CLI > env > settings > discovery > error; icons YAML simplified (relative dirs default `.`, no per-group color_scheme, no top-level roots); `PathOverrides` → `ResolvedRoots`; clean fail-fast errors.

**Non-Goals:** bundled default templates dir / color scheme (assets are the user's dotfiles/CSG output — not package-bundled); per-group color_scheme (removed — one global scheme); backward compat with the old top-level roots (breakage accepted).

## Decisions

### D1. Settings field first; discovery only as fallback
All three paths are settings.toml fields. CLI flags and env feed the OverrideRule flow (config-assembler standard), so env is the single env mechanism. The discovery chain (templates dir, color_scheme file) reads NO env and NO CLI — those are already resolved at the settings tier. This removes the sibling-style double-env-var (CSG has both `_CONFIG_FILE_PATH` path env and `__SECTION__KEY` override env); ITR has only the latter.

### D2. Precedence (one axis)
- `templates_dir`: `--template-dir` > `ICON_RENDERER__TEMPLATES__DIR` > `[templates] dir` > discovery (`templates/` traversal + XDG `itr/templates`) > None → error.
- `color_scheme`: `--color-scheme` > `ICON_RENDERER__COLOR_SCHEME__PATH` > `[color_scheme] path` > discovery (`colors.yaml` traversal + XDG `itr/colors.yaml`) > None → error.
- `output_dir`: `--output-dir` > `ICON_RENDERER__OUTPUT__OUTPUT_DIR` > `[output] output_dir` > bundled default (`/tmp/icon-templates-renderer`). (Output is a write target, not a discovery concern — no traversal/XDG; bundled default only.)

### D3. Two new resolver ports (discovery-only)
`TemplateDirResolverPort.resolve() -> Path | None` — `CompositePathResolver([DirTraversalStrategy("templates", max_levels=3), XdgDirStrategy("itr","templates")])`; catch `PathResolutionError` → None.
`ColorSchemeResolverPort.resolve() -> Path | None` — `CompositePathResolver([DirectoryTraversalStrategy("colors.yaml", max_levels=3), XdgStrategy("itr","colors.yaml")])`; catch `PathResolutionError` → None.
Both use a `ResolutionPolicy(env_prefix=...)` only to satisfy the resolver API; no path env var is consulted. Adapters wrap `PathResolutionError` → None (not a domain error; the orchestrator decides whether None is fatal).

### D4. ConfigResolverPort made real
`AssembledConfigResolver`: 5 FILE strategies (`CliPathStrategy` from `--config`, `EnvPathStrategy` `ICON_RENDERER_CONFIG_FILE_PATH`, `DirectoryTraversalStrategy` `settings.toml`, `XdgStrategy` `itr/settings.toml`, `DefaultFileStrategy` bundled `defaults/settings.toml`). OverrideRules: `output.output_dir`, `output.verbosity`, `templates.dir`, `color_scheme.path` — each `{CLI, ENV}`. `ResolutionPolicy(env_prefix="ICON_RENDERER")`. Maps validated `CoreSettingsSchema` → `AppSettings(output=OutputSettings(output_dir, verbosity), templates=TemplatesSettings(dir), color_scheme=ColorSchemeSettings(path))`.

### D5. Icons YAML simplified
`IconGroupSchema`: remove `color_scheme` (no per-group); `template_dir`/`output_dir` become `str = "."` (relative subpaths); `unsafe`/`color_mappings`/`variants` kept. The YAML loader joins: `group_template_dir = template_root / group.template_dir`; `group_output_dir = output_root / group.output_dir`; `group_color_scheme = global color_scheme`. `PathResolutionService` becomes a pure joiner (`root / sub` then resolve; absolute passthrough) — the 3-tier precedence is gone from the domain (it lives in the orchestrator).

### D6. ResolvedRoots replaces PathOverrides
New frozen `ResolvedRoots(template_root: Path | None, color_scheme: Path | None, output_root: Path | None)`. Requests (Render/List/Validate) carry `ResolvedRoots`. The loader/`load_one` takes `ResolvedRoots`. For `list`, roots may be None (names only). For render/validate, a None required root triggers a clear `ConfigResolutionError` from the orchestrator before any load.

### D7. Orchestrator (`_resolve_roots`)
`cli/_helpers.resolve_roots(deps, config_flag, template_dir_flag, color_scheme_flag, output_dir_flag) -> ResolvedRoots`:
1. Build `cli_overrides` from non-None flags (`templates.dir` / `color_scheme.path` / `output.output_dir`).
2. `settings = deps.config_resolver.resolve(explicit_path=config_flag, cli_overrides=cli_overrides)`.
3. `templates_dir = settings.templates.dir`; if None → `deps.template_dir_resolver.resolve()`.
4. `color_scheme = settings.color_scheme.path`; if None → `deps.color_scheme_resolver.resolve()`.
5. `output_root = settings.output.output_dir` (always set: settings value + bundled default guarantee non-None).
6. For render/validate: if `templates_dir` is None or `color_scheme` is None → raise `ConfigResolutionError` naming the missing root + the levers (`--template-dir` / `ICON_RENDERER__TEMPLATES__DIR` / `[templates] dir` / discovery).
7. Return `ResolvedRoots`.

### D8. Naming
Prefix `ICON_RENDERER` (kept). XDG subdir `itr`. Env overrides: `ICON_RENDERER__OUTPUT__OUTPUT_DIR`, `ICON_RENDERER__TEMPLATES__DIR`, `ICON_RENDERER__COLOR_SCHEME__PATH`, `ICON_RENDERER__OUTPUT__VERBOSITY`. Settings file env: `ICON_RENDERER_CONFIG_FILE_PATH`. Sections: `[output]`, `[templates]`, `[color_scheme]`.

### D9. Bundled default settings.toml
`defaults/settings.toml` ships `[output] output_dir = "/tmp/icon-templates-renderer"` and `verbosity = 1`; `[templates]` and `[color_scheme]` commented out (absent → discovery). `output_dir` always resolves (settings value or bundled default); `templates`/`color_scheme` resolve to None when neither settings nor discovery finds them.

## Risks / Trade-offs
- Breakage of icons YAML top-level roots / per-group color_scheme (accepted).
- Discovery returns None when nothing is configured → clear error; no silent fallback to a wrong path.
- Discovery chain shares `CompositePathResolver` but reads no env (slightly unusual use of the engine) — accepted for the clean single-env-axis model.
- `list` with optional roots means it cannot verify template existence; that's already true today.

## Migration Plan
Net refactor inside the module (no data migration). Update the user's 7 mapping yamls + `icons.yaml` to the simplified shape (drop boilerplate). Rollback: revert commit; previous flag-required behavior returns.
