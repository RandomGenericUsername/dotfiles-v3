# Architecture Plan: icon-templates-renderer v3

## Hexagonal rewrite of v2's `icon-renderer` (SVG icon template renderer for color schemes), migrating from v2's flat `services/`+`api/`+`models/`+`cli/` package to the v3 hexagonal (ports & adapters) layout established by `wallpaper-effects-generator` (WEG) and `color-scheme-generator` (CSG). The original v2 functionality is preserved; this plan is superseded for path resolution by the `itr-config-assembler-resolution` change (see §8 ADRs 009–013): flags are now optional, settings.toml is real, and discovery is a fallback.

---

## 0. Resolved decisions

| # | Decision |
|---|---|
| D1 | Commands are exactly `render`, `list`, `validate` — no `version`/`info`/`dump-config`/`dump-templates` (user-locked; v2 scope preserved) |
| D2 | Binary `itr`; project name `icon-templates-renderer`; package `icon_templates_renderer` (project name preserved from v2; short binary follows `weg`/`csg`) |
| D3 | **Pure Python — no `oci-runtime`, no Docker, no subprocess.** Deps: `typer>=0.12`, `pydantic>=2.0`, `pyyaml>=6.0`, `rich>=13.0`, `cli-output`, `config-assembler-engine` (editable `[tool.uv.sources]` → `../../shared/<name>`) |
| D4 | Python `>=3.14` (matches CSG); ruff `target-version = "py314"` |
| D5 | Frozen domain dataclasses; Pydantic only in `adapters/schemas/` (boundary DTO) |
| D6 | `OutputPort` takes domain objects; plain is the **default** output format (v2 UX parity); JSON/RICH opt-in via global `--output-format` (additive, flagged as open decision) |
| D7 | `settings.toml` resolved via config-assembler (5 FILE strategies + OverrideRules); `ConfigResolverPort` + `AssembledConfigResolver` **real** (replaces the inert placeholder) |
| D8 | Use-case modeled as a port (`IconRendererPort`) — not collapsed into CLI functions (differs from WEG/CSG; rationale in §4) |
| D9 | Substitution logic extracted to a pure `PlaceholderSubstitutionService` (decoupled from filesystem I/O) |
| D10 | Path precedence lives in the CLI orchestrator (`resolve_roots`); `PathResolutionService` is a pure joiner (root None → None; absolute passthrough) |
| D11 | Test approach: pytest only (`tests/unit/{domain,ports,adapters,cli}/` mirroring src + `tests/integration/`). No bash e2e script |

---

## 1. Domain Models (pure, frozen dataclasses, zero I/O)

| Model | Purpose |
|-------|---------|
| `OutputFormat` enum | JSON / RICH / PLAIN (`__str__ -> value`; default PLAIN) |
| `Verbosity` enum | QUIET / NORMAL / VERBOSE / DEBUG (int values) |
| `ColorScheme` | `values: MappingProxyType[str, str]` (name → hex); `get(name) -> str \| None`; `from_dict` |
| `Variant` | `name`, `template: Path`, `output: Path`, `color_mappings: MappingProxyType[str, str]` |
| `IconGroup` | `name`, `template_dir: Path \| None`, `output_dir: Path \| None`, `unsafe: bool`, `variants: tuple[Variant]`, `color_mappings`; `resolve_mappings(variant, vocab_defaults)` → `{**vocab, **group, **variant}` |
| `IconConfig` | `groups: tuple[IconGroup]` |
| `Vocabulary` | `defaults: MappingProxyType[str, str]`; `as_dict()` |
| `ResolvedRoots` | `template_root: Path \| None`, `color_scheme: Path \| None`, `output_root: Path \| None` (frozen; populated by the CLI orchestrator from settings + discovery; replaces `PathOverrides`) |
| `RenderRequest` | `yaml_path`, `icon: str \| None`, `unsafe: bool \| None`, `roots: ResolvedRoots`, `vocabulary_path: Path \| None` |
| `RenderedVariant` | `variant_name`, `group_name`, `output_path: Path` |
| `RenderResult` | `success: bool`, `rendered: tuple[RenderedVariant]` |
| `ListRequest` | `yaml_path`, `icon: str \| None`, `roots: ResolvedRoots` |
| `ListResult` | `groups: tuple[(group, tuple[variant_names])]`, `single: bool` |
| `ValidateRequest` | `yaml_path`, `icon: str \| None`, `roots: ResolvedRoots` |
| `ValidateResult` | `ok`, `checked_groups`, `checked_variants` |
| `OutputSettings` | `output_dir: Path \| None`, `verbosity: Verbosity` |
| `TemplatesSettings` | `dir: Path \| None` |
| `ColorSchemeSettings` | `path: Path \| None` |
| `AppSettings` | `output: OutputSettings`, `templates: TemplatesSettings`, `color_scheme: ColorSchemeSettings` |

## 2. Domain Services (pure logic, no I/O)

| Service | Responsibility |
|---------|----------------|
| `PathResolutionService` | `resolve(root, sub) -> Path \| None` — pure joiner; root None → None; absolute `sub` passes through. No precedence logic (that lives in the orchestrator) |
| `MappingResolutionService` | `merge(vocab, group, variant)` — v2 `resolve_mappings` priority |
| `PlaceholderSubstitutionService` | `substitute(svg, scheme, unsafe, color_mappings)` — the v2 `svg_renderer.render_string` core: regex `\{\{(\w+)\}\}`; missing mapping → `MissingMappingError` unless unsafe (leave token); value `#…` → literal; `scheme.get(value)` → `None` ⇒ `ColorSchemeKeyNotFoundError` unless unsafe |

## 3. Error hierarchy

```
IconRendererError(Exception)
├── InvalidYamlError(reason)
├── IconNotFoundError(name, yaml_path?)
├── TemplateNotFoundError(path)
├── ColorSchemeNotFoundError(message)
├── MissingMappingError(key)
├── ColorSchemeKeyNotFoundError(key, scheme_key)
└── ConfigResolutionError(name, levers)   — required root unresolved; names the levers
```

All names preserved verbatim from v2 `exceptions.py`. `errors.py` re-exports the set with explicit `__all__`. CLI catches `IconRendererError` → `OutputPort.error` → `Error: <message>` on stderr → `typer.Exit(1)` (v2-verbatim).

## 4. Ports

| Port file | Port | Methods |
|-----------|------|---------|
| `icon_config_loader.py` | `IconConfigLoaderPort` | `load(yaml_path, roots?) -> IconConfig`, `load_one(yaml_path, icon, roots?) -> IconGroup`, `get_resolved_path() -> Path\|None` |
| `color_scheme_loader.py` | `ColorSchemeLoaderPort` | `load(path) -> ColorScheme`, `supports(path) -> bool` |
| `vocabulary_loader.py` | `VocabularyLoaderPort` | `load(path: Path\|None) -> Vocabulary` |
| `svg_renderer.py` | `SvgRendererPort` | `render_variant(variant, scheme, unsafe, color_mappings) -> Path`, `render_string(svg_body, scheme, unsafe, color_mappings) -> str` |
| `icon_renderer.py` | `IconRendererPort` | `render(request) -> RenderResult`, `list(request) -> ListResult`, `validate(request) -> ValidateResult` |
| `config_resolver.py` | `ConfigResolverPort` | `resolve(*, cli_overrides?, explicit_path?) -> AppSettings`, `get_resolved_path()` |
| `template_dir_resolver.py` | `TemplateDirResolverPort` | `resolve() -> Path\|None` (discovery-only) |
| `color_scheme_resolver.py` | `ColorSchemeResolverPort` | `resolve() -> Path\|None` (discovery-only) |
| `output.py` | `OutputPort` | `render_result`, `list_result`, `validate_result`, `error(exc)`, `message(msg)` |

All ports are `@runtime_checkable Protocol`, one per file, importing only `domain.*`. Conformance is verified by `isinstance(adapter, Port)` in `tests/unit/ports/test_contracts.py`.

## 5. Adapters

| Adapter | Port | Behavior |
|---------|------|----------|
| `YamlIconConfigLoader` | `IconConfigLoaderPort` | PyYAML → `IconsConfigSchema` (Pydantic) → joins each group's relative `template_dir`/`output_dir` under the global `ResolvedRoots` roots via `PathResolutionService`; `variants` are the only required group field (`template_dir`/`output_dir` default `"."`). No top-level roots, no per-group `color_scheme` |
| `FileColorSchemeLoader` | `ColorSchemeLoaderPort` | suffix dispatch; `.yaml/.yml` → `special{background,foreground,cursor}` + `colors` list → `color0..colorN`; `.json` → `special` + `colors` dict (keys preserved); else `ColorSchemeNotFoundError` |
| `YamlVocabularyLoader` | `VocabularyLoaderPort` | `None`/absent → empty; `defaults` mapping enforced; k/v coerced to `str` |
| `FileSvgRenderer` | `SvgRendererPort` | existence check → `TemplateNotFoundError`; read → `PlaceholderSubstitutionService` → mkdir parents → write; returns output path |
| `IconRenderer` | `IconRendererPort` | orchestrates against `request.roots`: global scheme loaded once; `list` tolerates None roots; render/validate require roots (raise `ConfigResolutionError` otherwise) |
| `AssembledConfigResolver` | `ConfigResolverPort` | `config-assembler-engine` `CompositePathResolver` (Cli `--config` → Env `ICON_RENDERER_CONFIG_FILE_PATH` → DirTraversal `settings.toml` → Xdg `itr` → DefaultFile `defaults/settings.toml`); OverrideRules `output.output_dir`/`output.verbosity`/`templates.dir`/`color_scheme.path`; maps to `AppSettings` |
| `TemplateDirResolver` | `TemplateDirResolverPort` | discovery-only `CompositePathResolver([DirTraversal("templates", 3), XdgDir("itr","templates")])`; `PathResolutionError` → None |
| `ColorSchemeResolver` | `ColorSchemeResolverPort` | discovery-only `CompositePathResolver([DirectoryTraversal("colors.yaml", 3), Xdg("itr","colors.yaml")])`; `PathResolutionError` → None |
| `PlainOutput`/`JsonOutput`/`RichOutput` | `OutputPort` | `OutputAdapterBase` wrapping `cli_output` `Renderer`; `projectors.py` maps domain → `CustomView`/`ErrorView`/`MessageView`; plain default reproduces v2 text; errors always `Error: <exc>` on stderr |

## 6. Composition root

`factory.py`:
- `@dataclass CliDependencies` with `field(default_factory=YamlIconConfigLoader/FileColorSchemeLoader/YamlVocabularyLoader/FileSvgRenderer)` + `__post_init__` building `IconRenderer` from the injected ports. Carries `config_resolver`, `template_dir_resolver`, `color_scheme_resolver`.
- `build_deps() -> CliDependencies` wires `AssembledConfigResolver` + `TemplateDirResolver` + `ColorSchemeResolver` (test seam; tests monkeypatch it).
- `create_*` factories (`create_config_loader`, `create_color_loader`, `create_vocab_loader`, `create_svg_renderer`, `create_config_resolver`, `create_template_dir_resolver`, `create_color_scheme_resolver`).
- `create_output_adapter(fmt, verbosity)` dispatches to `PlainOutput`/`JsonOutput`/`RichOutput` with a `cli_output` renderer.
- Lazy imports inside `create_*` functions for heavy adapters.

`cli/main.py`:
- `app = typer.Typer(name="itr", ...)` with help documenting the discovery chains + env override format.
- `@app.callback()` — global `--output-format` (default `plain`), `-v/--verbose` (count), `-q/--quiet`; computes verbosity; sets `ctx.obj = {"deps", "output_format", "verbosity"}`; wires `output_adapter` via `create_output_adapter`.
- Registers `render`, `list`, `validate` command functions.

`cli/_helpers.py`:
- `resolve_roots(deps, config_flag, template_dir_flag, color_scheme_flag, output_dir_flag, *, required) -> ResolvedRoots` — orchestrates settings → discovery → `ResolvedRoots` (D7 of the change); when `required`, raises `ConfigResolutionError` naming the missing root + its levers.

## 7. CLI surface

```
itr [--output-format plain|json|rich] [-v|-q] COMMAND
  render   <yaml_file> [--icon NAME] [--unsafe] [--template-dir DIR]
                     [--color-scheme FILE] [--output-dir DIR] [--config PATH]
  list     <yaml_file> [--icon NAME] [--template-dir DIR] [--config PATH]
  validate <yaml_file> [--icon NAME] [--template-dir DIR] [--color-scheme FILE] [--config PATH]
```

All three flags (`--template-dir`, `--color-scheme`, `--output-dir`) are optional. Root precedence (single axis): CLI flag > `ICON_RENDERER__<SECTION>__<KEY>` env override > settings.toml field > discovery (templates/color_scheme) / bundled default (output_dir) > error.

Plain output (v2):
- render: `Rendered: <path>` per variant, blank line, `<N> icon(s) rendered.`
- list (all): `<group>:` + `  - <variant>`; list (`--icon`): `Variants:` + `  - <name>`
- validate: `Validation passed.`
- errors: `Error: <exc>` to stderr, exit 1

## 8. ADRs

- **ADR-001 Single-file config resolution, no merging.** One resolved `settings.toml`; no merge across sources.
- **ADR-002 Use-case behind a domain Port** (`IconRendererPort`) — orchestrates loaders + `SvgRendererPort`; unit-testable with fake ports (no CliRunner, no filesystem). Rationale: icon-renderer has non-trivial orchestration but no local/container/dry-run strategy split, so it fills the role WEG's `EffectProcessorPort` plays while keeping orchestration reusable.
- **ADR-003 Pure-Python only — no OCI / subprocess.** Deliberate absence of `oci-runtime` and install/uninstall commands; matches v2 docs.
- **ADR-004 Pydantic at the boundary only** (`adapters/schemas/`); domain is frozen dataclasses.
- **ADR-005 Plain output is default (v2 parity).** JSON/RICH opt-in via `--output-format` (diverges from CSG's JSON-default ADR-007, recorded intentionally).
- **ADR-006 Settings.toml placeholder.** *Superseded by ADR-009* (config resolution is now real).
- **ADR-007 PathOverrides threaded into the loader.** *Superseded by ADR-012* (`ResolvedRoots` replaces `PathOverrides`; precedence lives in the orchestrator).
- **ADR-008 Substitution extracted to a pure service** — decouples v2's regex/literal/scheme logic from filesystem I/O.
- **ADR-009 Settings-first path resolution.** Each of `templates_dir`/`color_scheme`/`output_dir` is a settings.toml field. CLI flags and env feed config-assembler's OverrideRules (`{CLI, ENV}`); the settings tier is the single env axis (`ICON_RENDERER__…`). Precedence: CLI flag > env > settings field > discovery (templates/color_scheme) / bundled default (output_dir) > error.
- **ADR-010 Discovery-only resolvers.** `TemplateDirResolver` + `ColorSchemeResolver` are discovery chains (`DirTraversal` + XDG) reading NO env and NO CLI — those are already handled at the settings tier. Return `Path | None`; adapters wrap `PathResolutionError` → None (not a domain error; the orchestrator decides whether None is fatal).
- **ADR-011 Single env axis.** Unlike CSG's double-env-var (path env + `__SECTION__KEY` overrides), ITR uses only OverrideRule env (`ICON_RENDERER__OUTPUT__OUTPUT_DIR`, `ICON_RENDERER__TEMPLATES__DIR`, `ICON_RENDERER__COLOR_SCHEME__PATH`, `ICON_RENDERER__OUTPUT__VERBOSITY`) plus `ICON_RENDERER_CONFIG_FILE_PATH` for the settings file.
- **ADR-012 `ResolvedRoots` replaces `PathOverrides`.** A frozen `ResolvedRoots(template_root, color_scheme, output_root)` is populated by the CLI orchestrator after settings + discovery and carried by every request. `list` tolerates None roots; render/validate fail fast with `ConfigResolutionError` when a required root is None.
- **ADR-013 Per-group `color_scheme` removed.** One global scheme per render (from settings/env/flag/discovery). Icons YAML simplified: no top-level `templates_root`/`color_scheme`/`outputs_root`; per-group `template_dir`/`output_dir` are relative subpaths defaulting to `"."`.

## 9. Package structure

```
icon-templates-renderer/
├── pyproject.toml / uv.lock / Makefile / .python-version
├── docs/ARCHITECTURE_PLAN.md
├── src/icon_templates_renderer/
│   ├── __init__.py  errors.py  constants.py  factory.py
│   ├── domain/  (enums, models, services, exceptions)
│   ├── ports/   (9 Protocol files + __init__)
│   ├── adapters/
│   │   ├── yaml_icon_config_loader.py  file_color_scheme_loader.py
│   │   ├── yaml_vocabulary_loader.py   file_svg_renderer.py
│   │   ├── icon_renderer.py            assembled_config_resolver.py
│   │   ├── template_dir_resolver.py    color_scheme_resolver.py
│   │   ├── schemas/ (icons_config_schema, settings_schema)
│   │   └── output/  (base, projectors, plain_output, json_output, rich_output)
│   ├── defaults/settings.toml
│   └── cli/ (main, options, _helpers, render, list_cmd, validate)
└── tests/
    ├── conftest.py
    ├── unit/  (domain, ports, adapters, cli — mirror of src)
    └── integration/ (render, list, validate, unsafe, color-mappings,
                      template-dir/color-scheme/output-dir overrides)
```

## 10. Dependencies & packaging

- `pyproject.toml`: hatchling; `[project.scripts] itr = "icon_templates_renderer.cli.main:app"`; `[tool.uv.sources] cli-output` + `config-assembler-engine` editable → `../../shared/<name>`; ruff `E,F,I,N,W,UP,B` ignore `B905`, double quotes, line-length 100; pytest `pythonpath = ["src","."]`, `addopts = ["--strict-markers","-rxX"]`; dev `pytest>=9.1.1`.
- `defaults/settings.toml`: `[output] output_dir = "/tmp/icon-templates-renderer"` + `verbosity = 1`; `[templates]`/`[color_scheme]` commented (absent → discovery). `output_dir` always resolves; `templates`/`color_scheme` resolve to None when neither settings nor discovery finds them.

## 11. v2 → v3 mapping (file-by-reference)

| v2 | v3 |
|----|----|
| `cli/commands/{render,list,validate}.py` | `cli/{render,list_cmd,validate}.py` + `cli/options.py` |
| `api/icon_renderer.py` | `adapters/icon_renderer.py` (port `IconRendererPort`) |
| `services/yaml_loader.py` | `adapters/yaml_icon_config_loader.py` + `domain/services.py::PathResolutionService` |
| `services/color_scheme_loader.py` | `adapters/file_color_scheme_loader.py` |
| `services/vocabulary_loader.py` | `adapters/yaml_vocabulary_loader.py` |
| `services/svg_renderer.py` | `adapters/file_svg_renderer.py` + `domain/services.py::PlaceholderSubstitutionService` |
| `models/{icon_config,color_scheme}.py` | `domain/models.py` (frozen; `ResolvedRoots` replaces `PathOverrides`) |
| `exceptions.py` | `domain/exceptions.py` + `errors.py` facade (+ `ConfigResolutionError`) |
| `settings.toml` | `defaults/settings.toml` (real resolver, ADR-009) |
| `tests/e2e/run-e2e-tests.sh` (~40 scenarios) | `tests/integration/*` pytest (adapted to simplified YAML + settings/discovery roots) |

## 12. Test strategy

- `tests/conftest.py`: `runner` (CliRunner), `FakeIconRenderer` (recording dataclass), `cli_deps_with_renderer` (monkeypatches `cli.main.build_deps` + sets env roots), `tmp_path` fixtures (`colors_yaml`, `colors_json`, `svg_template`, `icons_yaml`).
- `tests/unit/domain/`: services (substitution exhaustive; pure joiner; mapping merge), models (`ResolvedRoots`, settings), exceptions (message snapshots + `ConfigResolutionError`), enums.
- `tests/unit/ports/`: `conftest.py` with `assert_isinstance`/`assert_signature_compatible`/`assert_interface_method_count`; `test_interfaces.py`; `test_contracts.py` parametrizes every adapter × port (incl. the two discovery resolvers).
- `tests/unit/adapters/`: loaders, svg renderer, `IconRenderer` orchestration (fake ports), config resolver, `TemplateDirResolver`/`ColorSchemeResolver`, output.
- `tests/unit/cli/`: per-command via CliRunner + FakeIconRenderer; `test_resolve_roots.py` covers orchestrator precedence (flag > settings > discovery) + fail-fast.
- `tests/integration/`: real adapters + `tmp_path` + env roots; no-flag render from env/settings, flag-wins, missing-root fail-fast, list without roots.

## 13. Verification gates

- `uv run ruff check src tests` clean; `uv run ruff format --check src tests` clean; `uv run pytest` green.
- DoD: 3 commands; every v2 flag optional; plain output verbatim; unified settings-first precedence (flag > env > settings > discovery/bundled); YAML+JSON color schemes; vocabulary absent→{}; substitution rules; unsafe semantics (CLI override + group fallback); `load_one` → `IconNotFoundError`; missing required root → clear `ConfigResolutionError`; `list` works without roots; dependency direction holds; ports are Protocols; domain frozen; contract tests green.
