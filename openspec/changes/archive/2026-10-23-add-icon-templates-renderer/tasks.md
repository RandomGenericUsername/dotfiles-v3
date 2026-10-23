## 1. Scaffold

- [x] 1.1 Create `src/cli-tools/icon-templates-renderer/` with `pyproject.toml` (`name = "icon-templates-renderer"`, version `0.1.0`, `requires-python = ">=3.14"`, deps `typer>=0.12`/`pydantic>=2.0`/`pyyaml>=6.0`/`rich>=13.0`/`cli-output`/`config-assembler-engine`, `[project.scripts] itr = "icon_templates_renderer.cli.main:app"`, hatchling `packages = ["src/icon_templates_renderer"]`, `[tool.uv.sources]` editable to `../../shared/{cli-output,config-assembler-engine}`, ruff `py314`/line-length 100/lint `E,F,I,N,W,UP,B` ignore `B905`/double quotes, pytest `testpaths=["tests"]`/`pythonpath=["src","."]`/`addopts=["--strict-markers","-rxX"]`, dev group `pytest>=9.1.1`)
- [x] 1.2 Add `.python-version` = `3.14`
- [x] 1.3 Add `Makefile` with `test`/`test-all`/`lint`/`format`/`check`/`build`/`clean` (carried from v2)
- [x] 1.4 Create `src/icon_templates_renderer/__init__.py` with `__version__ = "0.1.0"`
- [x] 1.5 Create `src/icon_templates_renderer/defaults/settings.toml` placeholder (v2-style comments; optional minimal `[output]` section)
- [x] 1.6 Run `uv sync` and confirm `itr --help` wiring is reachable once `cli/main.py` exists

## 2. Domain layer

- [x] 2.1 `domain/enums.py` — `OutputFormat(str, Enum){PLAIN,JSON,RICH}` with `__str__ -> value`; `Verbosity(IntEnum){QUIET=0,NORMAL=1,VERBOSE=2,DEBUG=3}`
- [x] 2.2 `domain/exceptions.py` — `IconRendererError(Exception)` + `InvalidYamlError(reason)`/`IconNotFoundError(name,yaml_path?)`/`TemplateNotFoundError(path)`/`ColorSchemeNotFoundError(path?)`/`MissingMappingError(key)`/`ColorSchemeKeyNotFoundError(key,scheme_key)`, each storing typed attrs + building the v2 message in `__init__`; `__all__`
- [x] 2.3 `domain/models.py` — frozen dataclasses from D12: `Color(hex: str)` with `__post_init__` enforcing `^#[0-9a-fA-F]{6}$`; `ColorScheme(values)`; `Variant`; `IconGroup` (+ `resolve_mappings(variant, vocab_defaults=None)` returning `{**vocab, **group, **variant}`); `IconConfig(groups)`; `Vocabulary(defaults)`; `PathOverrides(template_dir?, color_scheme?, output_dir?)`; `RenderRequest`/`RenderedVariant`/`RenderResult`; `ListRequest`/`ListResult` (dual-shape dict|tuple); `ValidateRequest`/`ValidateResult`; `OutputSettings(verbosity)`/`AppSettings(output)`. Use `MappingProxyType` for dict fields via `__post_init__`
- [x] 2.4 `domain/services.py` — pure `PathResolutionService` (3-tier precedence + absolute passthrough, mirroring v2 `yaml_loader._resolve_*`), `MappingResolutionService.merge`, `PlaceholderSubstitutionService.substitute` (mirrors v2 `svg_renderer.render_string:34-67` verbatim including `_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")`)
- [x] 2.5 `domain/__init__.py` re-export enums/models/services/exceptions
- [x] 2.6 `errors.py` facade re-exporting `domain.exceptions` with `__all__`
- [x] 2.7 `constants.py` — `CONFIG_FILENAME="settings.toml"`, `CONFIG_XDG_SUBDIR="itr"`, `CONFIG_TRAVERSAL_DEPTH=2`, `VOCABULARY_FILENAME="defaults.yaml"`
- [x] 2.8 `tests/unit/domain/` — `test_enums.py`, `test_exceptions.py` (snapshot vs v2 message strings), `test_models.py` (`resolve_mappings` priority), `test_services.py` (exhaustive: literal `#` passthrough; scheme-key resolution; missing mapping raises vs unsafe; missing scheme key raises vs unsafe; path precedence for all three dirs; mapping merge priority)

## 3. Ports layer

- [x] 3.1 `ports/icon_config_loader.py` — `IconConfigLoaderPort`: `load(yaml_path, overrides)->IconConfig`, `load_one(yaml_path, icon, overrides)->IconGroup`, `get_resolved_path()->Path|None`
- [x] 3.2 `ports/color_scheme_loader.py` — `ColorSchemeLoaderPort`: `load(path)->ColorScheme`, `supports(path)->bool`
- [x] 3.3 `ports/vocabulary_loader.py` — `VocabularyLoaderPort`: `load(path: Path|None)->Vocabulary`
- [x] 3.4 `ports/svg_renderer.py` — `SvgRendererPort`: `render_variant(variant, scheme, unsafe, color_mappings)->Path`, `render_string(svg_body, scheme, unsafe, color_mappings)->str`
- [x] 3.5 `ports/icon_renderer.py` — `IconRendererPort`: `render(request)->RenderResult`, `list(request)->ListResult`, `validate(request)->ValidateResult`
- [x] 3.6 `ports/config_resolver.py` — `ConfigResolverPort`: `resolve(explicit_path?, cli_overrides?)->AppSettings`, `get_resolved_path()->Path|None`
- [x] 3.7 `ports/output.py` — `OutputPort`: `render_result`, `list_result`, `validate_result`, `error(exc)`, `message(msg)`
- [x] 3.8 `ports/__init__.py` re-export all ports; `from __future__ import annotations` + `TYPE_CHECKING` domain imports
- [x] 3.9 `tests/unit/ports/conftest.py` — copy sibling helpers `assert_isinstance`, `assert_signature_compatible`, `assert_interface_method_count` verbatim + scheme/settings fixtures
- [x] 3.10 `tests/unit/ports/test_interfaces.py` — per-port `isinstance(stub, Port)` compliance + negative cases
- [x] 3.11 `tests/unit/ports/test_contracts.py` — parametrize every adapter × every port through the three assertions

## 4. Adapters — parsing boundary (schemas)

- [x] 4.1 `adapters/schemas/icons_config_schema.py` — `IconsConfigSchema` (root parses as `dict[str,Any]`, pops reserved `templates_root`/`color_scheme`/`outputs_root` typed `str`, validates each remaining as `IconGroupSchema`); `IconGroupSchema` (required color_scheme/template_dir/output_dir/variants; optional unsafe/color_mappings); `VariantSchema` (required name/template/output; optional color_mappings)
- [x] 4.2 `adapters/schemas/settings_schema.py` — `OutputSettingsSchema(verbosity)`, `CoreSettingsSchema(output)`
- [x] 4.3 `tests/unit/adapters/schemas/` — schema validation tests

## 5. Adapters — loaders + renderer

- [x] 5.1 `adapters/yaml_icon_config_loader.py` — `YamlIconConfigLoader(IconConfigLoaderPort)`: PyYAML → `IconsConfigSchema` → pop roots → `IconConfig(groups)` via `PathResolutionService`+`PathOverrides`; `load_one` raises `IconNotFoundError`; v2 error message strings verbatim
- [x] 5.2 `adapters/file_color_scheme_loader.py` — `FileColorSchemeLoader(ColorSchemeLoaderPort)`: suffix dispatch (`.yaml/.yml` special+colors list→colorN; `.json` special+colors dict keys preserved; else `ColorSchemeNotFoundError`); missing file error verbatim
- [x] 5.3 `adapters/yaml_vocabulary_loader.py` — `YamlVocabularyLoader(VocabularyLoaderPort)`: None/absent→empty; `defaults` mapping enforced; k/v coerced to str; v2 error strings verbatim
- [x] 5.4 `adapters/file_svg_renderer.py` — `FileSvgRenderer(SvgRendererPort)`: existence check → `TemplateNotFoundError`; read; `render_string` delegates to `PlaceholderSubstitutionService`; mkdir parents; write; return output path
- [x] 5.5 `tests/unit/adapters/` — per-adapter unit tests with `tmp_path` (minimal `icons.yaml`/`colors.yaml`/`colors.json`/SVG/`defaults.yaml` fixtures from `tests/conftest.py`)

## 6. Adapters — use-case + output

- [x] 6.1 `adapters/icon_renderer.py` — `IconRenderer(IconRendererPort)`: constructor takes `config_loader`/`color_loader`/`vocab_loader`/`svg_renderer`/`PathResolutionService`/`MappingResolutionService`; `render` reproduces v2 `api/icon_renderer.py:51-72` (vocab default path `yaml.parent/"defaults.yaml"`; `effective_unsafe = request.unsafe if request.unsafe is not None else group.unsafe`; per-group scheme load + mkdir + per-variant resolve_mappings + render_variant; collect `RenderResult`); `list` reproduces `:74-79` dual-shape; `validate` reproduces `:81-93`
- [x] 6.2 `adapters/output/base.py` — `OutputAdapterBase(OutputPort)` holding a `cli_output` `Renderer`; each method calls a projector then dispatches (`custom`,`error`,`message`); honors `Verbosity.QUIET` no-op
- [x] 6.3 `adapters/output/projectors.py` — pure fns → `cli_output.domain.views.{CustomView,ErrorView,MessageView}`; plain projector reproduces v2 text **verbatim**: render (`Rendered: <p>`…`\n\nN icon(s) rendered.`), list-all (`<group>:\n  - <variant>`), list-icon (`Variants:\n  - <name>`), validate (`Validation passed.`), error (`Error: <exc>`)
- [x] 6.4 `adapters/output/{plain_output,json_output,rich_output}.py` — one-liner subclasses setting `_default_format` (plain default)
- [x] 6.5 `tests/unit/adapters/test_icon_renderer.py` — inject fake ports (no CliRunner, no filesystem); assert render/list/validate orchestration + `effective_unsafe` fallback + vocab-path default
- [x] 6.6 `tests/unit/adapters/output/` — per-format output tests; plain snapshot vs v2 strings

## 7. Adapter — config resolver (inert)

- [x] 7.1 `adapters/assembled_config_resolver.py` — `AssembledConfigResolver(ConfigResolverPort)`: `config-assembler-engine` `CompositePathResolver` (Cli→Env("ICON_RENDERER_CONFIG_FILE_PATH")→DirTraversal("settings.toml",3)→Xdg("icon-templates-renderer" or "itr")→DefaultFile(package defaults/settings.toml)); `TomlConfigParser`; `CoreSettingsSchema`; `ResolutionPolicy(env_prefix="ICON_RENDERER")`; maps schema→`AppSettings`; inert (only output verbosity, CLI-overridable)
- [x] 7.2 `tests/unit/adapters/test_assembled_config_resolver.py` — minimal: resolves bundled default; ENV/CLI overrides honored for verbosity

## 8. Composition root

- [x] 8.1 `factory.py` — `@dataclass CliDependencies` with `field(default_factory=YamlIconConfigLoader/FileColorSchemeLoader/YamlVocabularyLoader/FileSvgRenderer)` + `__post_init__` building `IconRenderer` from the injected ports + pure services; `create_output_adapter(fmt, verbosity)`; lazy imports for heavy adapters
- [x] 8.2 `tests/unit/test_factory.py` (or in `adapters/`) — `CliDependencies()` default-wires all ports; `__post_init__` builds the `IconRenderer`

## 9. CLI

- [x] 9.1 `cli/options.py` — module-level UPPERCASE Typer Option objects `ICON_OPT`, `UNSAFE_OPT`, `TEMPLATE_DIR`, `COLOR_SCHEME`, `OUTPUT_DIR`
- [x] 9.2 `cli/main.py` — `app = typer.Typer(name="itr", help="Render SVG icon templates with color scheme values")`; `build_deps(output_format, verbosity)->CliDependencies`; `@app.callback()` with `--output-format` (default `plain`), `-q/--quiet`, `-v/--verbose` (count); sets `ctx.obj = {"deps","output_format","verbosity"}`; registers `render_command`/`list_command`/`validate_command`
- [x] 9.3 `cli/render.py` — `render_command(yaml_file, --icon, --unsafe, --template-dir, --color-scheme, --output-dir)`: build `PathOverrides` (each `Path(x).expanduser().resolve() if x else None`); `request = RenderRequest(yaml_path.resolve(), icon, unsafe or None, overrides)`; `try: result = deps.icon_renderer.render(request); deps.output_adapter.render_result(result) except IconRendererError as exc: deps.output_adapter.error(exc); raise typer.Exit(1)`
- [x] 9.4 `cli/list_cmd.py` — `list_command(yaml_file, --icon, --template-dir)`; same try/except shape; `deps.output_adapter.list_result(result)`
- [x] 9.5 `cli/validate.py` — `validate_command(yaml_file, --icon, --template-dir, --color-scheme)`; same shape; `deps.output_adapter.validate_result(result)`
- [x] 9.6 `tests/unit/cli/` — `test_render_command.py`/`test_list_command.py`/`test_validate_command.py` using `cli_deps_with_renderer` (FakeIconRenderer recording calls) via `CliRunner`; assert exit codes, plain output verbatim, flag threading into `RenderRequest`/`ListRequest`/`ValidateRequest`

## 10. Root conftest

- [x] 10.1 `tests/conftest.py` — `runner` (CliRunner); `fake_icon_renderer` (recording dataclass returning canned `RenderResult`/`ListResult`/`ValidateResult`); `cli_deps_with_renderer` monkeypatching `icon_templates_renderer.cli.main.build_deps`; fixtures to materialize minimal `icons.yaml`, `colors.yaml`, `colors.json`, SVG templates, `defaults.yaml` in `tmp_path`

## 11. Integration tests — port v2 e2e 1:1

- [x] 11.1 `tests/integration/test_render_integration.py` — render all (battery+network output files exist; placeholders resolved `#1a1a2e`; no remaining `{{`); `--icon battery`; unknown icon exits non-zero
- [x] 11.2 `tests/integration/test_list_integration.py` — all groups (`battery`/`network`); `--icon battery` only; unknown exits non-zero
- [x] 11.3 `tests/integration/test_validate_integration.py` — valid passes; missing file exits non-zero; missing template fails
- [x] 11.4 `tests/integration/test_unsafe_integration.py` — unresolved fails by default; `--unsafe` succeeds; `unsafe:true` in YAML succeeds; `{{unknown_color}}` preserved in output
- [x] 11.5 `tests/integration/test_color_mappings_integration.py` — semantic `icon_fill`/`icon_border` resolve; output has `#1a1a2e`; no `{{` left
- [x] 11.6 `tests/integration/test_template_dir_override.py` — relative `template_dir` resolves from YAML location; output created; placeholders resolved; plus top-level `templates_root`
- [x] 11.7 `tests/integration/test_color_scheme_override.py` — top-level `color_scheme` used for all groups; alt scheme `#aabbcc` in output; no `{{` left; `--color-scheme` override
- [x] 11.8 `tests/integration/test_output_dir_override.py` — `outputs_root` drives output location; file at `outputs_root/battery/battery-0.svg`; `--output-dir` override joins root

## 12. Documentation

- [x] 12.1 `docs/ARCHITECTURE_PLAN.md` — ADR-001 single-file config; ADR-002 use-case behind domain Port; ADR-003 pure-Python only (no OCI); ADR-004 Pydantic at boundary; ADR-005 plain output default (v2 parity); ADR-006 settings.toml placeholder; ADR-007 PathOverrides threaded into loader; ADR-008 substitution extracted to pure service. Include domain/ports/adapters tables, error hierarchy, CLI surface, package tree, composition root sketch, test strategy, v2→v3 file-by-reference migration table

## 13. Verification

- [x] 13.1 `uv run ruff check src tests` — clean
- [x] 13.2 `uv run ruff format --check src tests` — clean
- [x] 13.3 `uv run pytest` — all green (unit + integration + port contracts)
- [x] 13.4 Walk the Definition of Done: every v2 behavior present; plain output verbatim; all 6 exceptions; 3-tier precedence; YAML+JSON color schemes; vocabulary absent→{}; `{{}}` substitution rules; `unsafe` semantics; `load_one`→`IconNotFoundError`; dependency-direction holds; ports are Protocols; domain frozen; `tests/unit/ports/test_contracts.py` green