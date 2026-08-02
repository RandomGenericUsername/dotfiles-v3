# Architecture Plan: icon-templates-renderer v3

## Hexagonal rewrite of v2's `icon-renderer` (SVG icon template renderer for color schemes), migrating from v2's flat `services/`+`api/`+`models/`+`cli/` package to the v3 hexagonal (ports & adapters) layout established by `wallpaper-effects-generator` (WEG) and `color-scheme-generator` (CSG). No v2 functionality is lost: every command, flag, YAML key, color-scheme format, path precedence, placeholder rule, error, and plain-text output line is preserved.

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
| D7 | `settings.toml` stays a placeholder; `ConfigResolverPort` + `AssembledConfigResolver` wired but functionally inert (clean seam, no v2 behavior shift) |
| D8 | Use-case modeled as a port (`IconRendererPort`) — not collapsed into CLI functions (differs from WEG/CSG; rationale in §4) |
| D9 | Substitution logic extracted to a pure `PlaceholderSubstitutionService` (decoupled from filesystem I/O) |
| D10 | Path override precedence (CLI → YAML root → YAML-relative) extracted to pure `PathResolutionService` |
| D11 | Test approach: pytest only (`tests/unit/{domain,ports,adapters,cli}/` mirroring src + `tests/integration/` porting all ~40 v2 bash-e2e scenarios 1:1). No bash e2e script |

---

## 1. Domain Models (pure, frozen dataclasses, zero I/O)

| Model | Purpose |
|-------|---------|
| `OutputFormat` enum | JSON / RICH / PLAIN (`__str__ -> value`; default PLAIN) |
| `Verbosity` enum | QUIET / NORMAL / VERBOSE / DEBUG (int values) |
| `ColorScheme` | `values: MappingProxyType[str, str]` (name → hex); `get(name) -> str \| None`; `from_dict` |
| `Variant` | `name`, `template: Path`, `output: Path`, `color_mappings: MappingProxyType[str, str]` |
| `IconGroup` | `name`, `color_scheme: Path`, `template_dir: Path`, `output_dir: Path`, `unsafe: bool`, `variants: tuple[Variant]`, `color_mappings`; `resolve_mappings(variant, vocab_defaults)` → `{**vocab, **group, **variant}` (v2 priority) |
| `IconConfig` | `groups: tuple[IconGroup]` |
| `Vocabulary` | `defaults: MappingProxyType[str, str]`; `as_dict()` |
| `PathOverrides` | `template_dir: Path \| None`, `color_scheme: Path \| None`, `output_dir: Path \| None` (CLI override DTO) |
| `RenderRequest` | `yaml_path`, `icon: str \| None`, `unsafe: bool \| None`, `overrides`, `vocabulary_path: Path \| None` |
| `RenderedVariant` | `variant_name`, `group_name`, `output_path: Path` |
| `RenderResult` | `success: bool`, `rendered: tuple[RenderedVariant]` |
| `ListRequest` | `yaml_path`, `icon: str \| None`, `overrides` |
| `ListResult` | `groups: tuple[(group, tuple[variant_names])]`, `single: bool` (dual-shape of v2 `list(icon=None)` vs `list(icon=X)`) |
| `ValidateRequest` | `yaml_path`, `icon: str \| None`, `overrides` |
| `ValidateResult` | `ok`, `checked_groups`, `checked_variants` |
| `OutputSettings` | `verbosity: Verbosity` |
| `AppSettings` | `output: OutputSettings` |

## 2. Domain Services (pure logic, no I/O)

| Service | Responsibility |
|---------|----------------|
| `PathResolutionService` | `resolve_template_dir` / `resolve_output_dir` / `resolve_color_scheme` / `resolve` — the v2 `yaml_loader._resolve_*` trio; precedence CLI override → YAML top-level root → YAML-relative; absolute passthrough; `color_scheme` override replaces whole path; `template_dir`/`output_dir` overrides join the YAML string |
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
└── ColorSchemeKeyNotFoundError(key, scheme_key)
```

All names preserved verbatim from v2 `exceptions.py`. `errors.py` re-exports the set with explicit `__all__`. CLI catches `IconRendererError` → `OutputPort.error` → `Error: <message>` on stderr → `typer.Exit(1)` (v2-verbatim).

## 4. Ports

| Port file | Port | Methods |
|-----------|------|---------|
| `icon_config_loader.py` | `IconConfigLoaderPort` | `load(yaml_path, overrides?) -> IconConfig`, `load_one(yaml_path, icon, overrides?) -> IconGroup`, `get_resolved_path() -> Path\|None` |
| `color_scheme_loader.py` | `ColorSchemeLoaderPort` | `load(path) -> ColorScheme`, `supports(path) -> bool` |
| `vocabulary_loader.py` | `VocabularyLoaderPort` | `load(path: Path\|None) -> Vocabulary` |
| `svg_renderer.py` | `SvgRendererPort` | `render_variant(variant, scheme, unsafe, color_mappings) -> Path`, `render_string(svg_body, scheme, unsafe, color_mappings) -> str` |
| `icon_renderer.py` | `IconRendererPort` | `render(request) -> RenderResult`, `list(request) -> ListResult`, `validate(request) -> ValidateResult` |
| `config_resolver.py` | `ConfigResolverPort` | `resolve(*, cli_overrides?, explicit_path?) -> AppSettings`, `get_resolved_path()` |
| `output.py` | `OutputPort` | `render_result`, `list_result`, `validate_result`, `error(exc)`, `message(msg)` |

All ports are `@runtime_checkable Protocol`, one per file, importing only `domain.*`. Conformance is verified by `isinstance(adapter, Port)` in `tests/unit/ports/test_contracts.py`.

## 5. Adapters

| Adapter | Port | Behavior |
|---------|------|----------|
| `YamlIconConfigLoader` | `IconConfigLoaderPort` | PyYAML → `IconsConfigSchema` (Pydantic) → pop top-level `templates_root`/`color_scheme`/`outputs_root` → `IconConfig(groups=...)` via `PathResolutionService` + `PathOverrides`. `load_one` raises `IconNotFoundError`. v2 message strings verbatim |
| `FileColorSchemeLoader` | `ColorSchemeLoaderPort` | suffix dispatch; `.yaml/.yml` → `special{background,foreground,cursor}` + `colors` list → `color0..colorN`; `.json` → `special` + `colors` dict (keys preserved); else `ColorSchemeNotFoundError` |
| `YamlVocabularyLoader` | `VocabularyLoaderPort` | `None`/absent → empty; `defaults` mapping enforced; k/v coerced to `str`; v2 error strings verbatim |
| `FileSvgRenderer` | `SvgRendererPort` | existence check → `TemplateNotFoundError`; read → `PlaceholderSubstitutionService` → mkdir parents → write; returns output path |
| `IconRenderer` | `IconRendererPort` | v2 orchestration: vocab = `yaml.parent/"defaults.yaml"`; per group `effective_unsafe = request.unsafe if request.unsafe is not None else group.unsafe`; load scheme; mkdir output; per variant `resolve_mappings` → `render_variant`; collects `RenderResult`. `list`/`validate` reproduce v2 dual-shape + first-error raise |
| `AssembledConfigResolver` | `ConfigResolverPort` | `config-assembler-engine` `CompositePathResolver` (Cli → Env `ICON_RENDERER_CONFIG_FILE_PATH` → DirTraversal `settings.toml` → Xdg `itr` → DefaultFile `defaults/settings.toml`); `CoreSettingsSchema` (minimal `[output] verbosity`); `ResolutionPolicy(env_prefix="ICON_RENDERER")`. **Inert** (D7) |
| `PlainOutput`/`JsonOutput`/`RichOutput` | `OutputPort` | `OutputAdapterBase` wrapping `cli_output` `Renderer`; `projectors.py` maps domain → `CustomView`/`ErrorView`/`MessageView`; plain default reproduces v2 text verbatim; errors always `Error: <exc>` on stderr |

## 6. Composition root

`factory.py`:
- `@dataclass CliDependencies` with `field(default_factory=YamlIconConfigLoader/FileColorSchemeLoader/YamlVocabularyLoader/FileSvgRenderer)` + `__post_init__` building `IconRenderer` from the injected ports.
- `create_output_adapter(fmt, verbosity)` dispatches to `PlainOutput`/`JsonOutput`/`RichOutput` with a `cli_output` renderer.
- Lazy imports inside `create_*` functions for heavy adapters.

`cli/main.py`:
- `app = typer.Typer(name="itr", help="Render SVG icon templates with color scheme values")`.
- `build_deps() -> CliDependencies` (test seam; tests monkeypatch it).
- `@app.callback()` — global `--output-format` (default `plain`), `-v/--verbose` (count), `-q/--quiet`; computes verbosity; sets `ctx.obj = {"deps", "output_format", "verbosity"}`; wires `output_adapter` via `create_output_adapter`.
- Registers `render`, `list`, `validate` command functions.

## 7. CLI surface

```
itr [--output-format plain|json|rich] [-v|-q] COMMAND
  render   <yaml_file> [--icon NAME] [--unsafe] [--template-dir DIR]
                     [--color-scheme FILE] [--output-dir DIR]
  list     <yaml_file> [--icon NAME] [--template-dir DIR]
  validate <yaml_file> [--icon NAME] [--template-dir DIR] [--color-scheme FILE]
```

Plain output verbatim (v2):
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
- **ADR-006 Settings.toml placeholder.** `ConfigResolverPort` present but inert; backward-compatible seam for future config-driven defaults.
- **ADR-007 PathOverrides threaded into the loader** — keeps the 3-tier override precedence testable in pure domain.
- **ADR-008 Substitution extracted to a pure service** — decouples v2's regex/literal/scheme logic from filesystem I/O.

## 9. Package structure

```
icon-templates-renderer/
├── pyproject.toml / uv.lock / Makefile / .python-version
├── docs/ARCHITECTURE_PLAN.md
├── src/icon_templates_renderer/
│   ├── __init__.py  errors.py  constants.py  factory.py
│   ├── domain/  (enums, models, services, exceptions)
│   ├── ports/   (7 Protocol files + __init__)
│   ├── adapters/
│   │   ├── yaml_icon_config_loader.py  file_color_scheme_loader.py
│   │   ├── yaml_vocabulary_loader.py   file_svg_renderer.py
│   │   ├── icon_renderer.py            assembled_config_resolver.py
│   │   ├── schemas/ (icons_config_schema, settings_schema)
│   │   └── output/  (base, projectors, plain_output, json_output, rich_output)
│   ├── defaults/settings.toml
│   └── cli/ (main, options, _helpers, render, list_cmd, validate)
└── tests/
    ├── conftest.py
    ├── unit/  (domain, ports, adapters, cli — mirror of src)
    └── integration/ (port of v2 e2e: render, list, validate, unsafe,
                      color-mappings, template-dir/color-scheme/output-dir overrides)
```

## 10. Dependencies & packaging

- `pyproject.toml`: hatchling; `[project.scripts] itr = "icon_templates_renderer.cli.main:app"`; `[tool.uv.sources] cli-output` + `config-assembler-engine` editable → `../../shared/<name>`; ruff `E,F,I,N,W,UP,B` ignore `B905`, double quotes, line-length 100; pytest `pythonpath = ["src","."]`, `addopts = ["--strict-markers","-rxX"]`; dev `pytest>=9.1.1`.
- `defaults/settings.toml`: placeholder (v2-style comments); wired but inert via `AssembledConfigResolver`.

## 11. v2 → v3 mapping (file-by-reference)

| v2 | v3 |
|----|----|
| `cli/commands/{render,list,validate}.py` | `cli/{render,list_cmd,validate}.py` + `cli/options.py` |
| `api/icon_renderer.py` | `adapters/icon_renderer.py` (port `IconRendererPort`) |
| `services/yaml_loader.py` | `adapters/yaml_icon_config_loader.py` + `domain/services.py::PathResolutionService` |
| `services/color_scheme_loader.py` | `adapters/file_color_scheme_loader.py` |
| `services/vocabulary_loader.py` | `adapters/yaml_vocabulary_loader.py` |
| `services/svg_renderer.py` | `adapters/file_svg_renderer.py` + `domain/services.py::PlaceholderSubstitutionService` |
| `models/{icon_config,color_scheme}.py` | `domain/models.py` (frozen) |
| `exceptions.py` | `domain/exceptions.py` + `errors.py` facade |
| `settings.toml` | `defaults/settings.toml` (inert resolver) |
| `tests/e2e/run-e2e-tests.sh` (~40 scenarios) | `tests/integration/*` pytest (1:1 port) |

## 12. Test strategy

- `tests/conftest.py`: `runner` (CliRunner), `FakeIconRenderer` (recording dataclass), `cli_deps_with_renderer` (monkeypatches `cli.main.build_deps`), `tmp_path` fixtures (`colors_yaml`, `colors_json`, `svg_template`, `icons_yaml`).
- `tests/unit/domain/`: services (substitution exhaustive; path precedence; mapping merge), models, exceptions (message snapshots vs v2), enums.
- `tests/unit/ports/`: `conftest.py` with `assert_isinstance`/`assert_signature_compatible`/`assert_interface_method_count`; `test_interfaces.py`; `test_contracts.py` parametrizes every adapter × port.
- `tests/unit/adapters/`: loaders, svg renderer, `IconRenderer` orchestration (fake ports), config resolver, output (plain snapshot vs v2).
- `tests/unit/cli/`: per-command via CliRunner + FakeIconRenderer.
- `tests/integration/`: real adapters + `tmp_path`; ports all v2 e2e categories.

## 13. Verification gates

- `uv run ruff check src tests` clean; `uv run ruff format --check src tests` clean; `uv run pytest` green (124 tests).
- DoD: 3 commands; every v2 flag; plain output verbatim; 3-tier precedence; YAML+JSON color schemes; vocabulary absent→{}; substitution rules; unsafe semantics (CLI override + group fallback); `load_one` → `IconNotFoundError`; dependency direction holds; ports are Protocols; domain frozen; contract tests green.
