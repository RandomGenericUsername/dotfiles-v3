## 1. Constants & schema

- [x] 1.1 `constants.py`: add `TEMPLATES_TRAVERSAL_DIRNAME="templates"`, `TEMPLATES_TRAVERSAL_DEPTH=3`, `TEMPLATES_XDG_SUBDIR="itr"`, `COLOR_SCHEME_FILENAME="colors.yaml"`, `COLOR_SCHEME_TRAVERSAL_DEPTH=3`, `COLOR_SCHEME_XDG_SUBDIR="itr"`; keep `CONFIG_*`
- [x] 1.2 `adapters/schemas/settings_schema.py`: `OutputSettingsSchema` += `output_dir: Path` (`mode="before"` empty-string reject) + keep `verbosity`; new `TemplatesSettingsSchema` (`dir: Path | None = None`), `ColorSchemeSettingsSchema` (`path: Path | None = None`); `CoreSettingsSchema` nests `output`/`templates`/`color_scheme`
- [x] 1.3 `adapters/schemas/icons_config_schema.py`: `IconGroupSchema` remove `color_scheme`; `template_dir`/`output_dir` → `str = "."`

## 2. Domain

- [x] 2.1 `domain/models.py`: `OutputSettings` += `output_dir: Path | None`; new `TemplatesSettings(dir: Path | None)`, `ColorSchemeSettings(path: Path | None)`; `AppSettings(output, templates, color_scheme)`. New `ResolvedRoots(template_root, color_scheme, output_root: Path | None)`. `IconGroup`: remove `color_scheme` field; `template_dir`/`output_dir` → `Path | None`. Requests carry `ResolvedRoots` (replace `PathOverrides`)
- [x] 2.2 `domain/services.py`: `PathResolutionService` → pure joiner (`resolve(root, sub) -> Path | None`; absolute passthrough; root None → None). Remove the 3-tier precedence methods
- [x] 2.3 `domain/exceptions.py`: `ConfigResolutionError(name, levers)` with clear message
- [ ] 2.4 `tests/unit/domain/` tests for the above

## 3. Ports & adapters: resolvers

- [ ] 3.1 `ports/template_dir_resolver.py`: `TemplateDirResolverPort.resolve() -> Path | None`
- [ ] 3.2 `ports/color_scheme_resolver.py`: `ColorSchemeResolverPort.resolve() -> Path | None`
- [ ] 3.3 `adapters/template_dir_resolver.py`: discovery-only `CompositePathResolver`; `PathResolutionError` → None
- [ ] 3.4 `adapters/color_scheme_resolver.py`: discovery-only; `PathResolutionError` → None
- [ ] 3.5 tests; `tests/unit/ports/test_contracts.py` covers both

## 4. Settings resolver (real)

- [ ] 4.1 `adapters/assembled_config_resolver.py`: add OverrideRules (`output.output_dir`, `output.verbosity`, `templates.dir`, `color_scheme.path`); map to `AppSettings(output, templates, color_scheme)`
- [ ] 4.2 `defaults/settings.toml`: `[output]` `output_dir` + `verbosity`; `[templates]`/`[color_scheme]` commented
- [ ] 4.3 tests: settings/env/CLI/bundled for `output_dir`; `templates.dir`/`color_scheme.path` from settings

## 5. Config loader & icon renderer

- [ ] 5.1 `adapters/yaml_icon_config_loader.py`: `load(yaml_path, roots: ResolvedRoots | None = None)`; remove top-level roots popping; per-group join (`root / sub`); remove per-group `color_scheme` resolution (global only)
- [ ] 5.2 `adapters/icon_renderer.py`: thread `request.roots` into `load`/`load_one`; `list` tolerates None roots; render/validate require roots
- [ ] 5.3 tests: join precedence; None roots behavior

## 6. Composition root & CLI

- [ ] 6.1 `factory.py`: `CliDependencies` += `template_dir_resolver`, `color_scheme_resolver`; `create_*` factories; `build_deps` wires all three
- [ ] 6.2 `cli/options.py`: `CONFIG_OPT` (`--config`, exists/file/resolve)
- [ ] 6.3 `cli/_helpers.py`: `resolve_roots(...) -> ResolvedRoots` (D7); clear `ConfigResolutionError` on missing required root
- [ ] 6.4 `cli/main.py`: `build_deps` wires resolvers; app help documents the discovery chains + env override format
- [ ] 6.5 `cli/render.py`, `cli/list_cmd.py`, `cli/validate.py`: add `--config`; call `resolve_roots`; build `ResolvedRoots`; pass into request
- [x] 6.6 tests: orchestrator precedence; flag > env > settings > discovery; fail-fast error

## 7. Integration & assets

- [x] 7.1 integration tests: no-flag render works when env set; flag wins; settings.toml honored; missing-root error
- [x] 7.2 simplify user's 7 mapping `*.yaml` + `icons.yaml` (drop `template_dir: .`, `output_dir: .`, `color_scheme: ~`)
- [x] 7.3 `docs/ARCHITECTURE_PLAN.md`: new ADRs (settings-first; discovery-only resolvers; single env axis; `ResolvedRoots`; removed per-group scheme)

## 8. Verification

- [x] 8.1 `uv run ruff check src tests` + `uv run ruff format --check src tests` clean; `uv run pytest` green (incl. new resolver/port/settings/precedence/discovery-fallback tests)
- [x] 8.2 `uv run itr render icons.yaml` (no flags) works once env/settings set
