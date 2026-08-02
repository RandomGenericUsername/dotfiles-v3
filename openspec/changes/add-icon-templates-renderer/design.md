## Context

The v2 `icon-renderer` lives at `dotfiles-repo-v2/src/cli-tools/icon-renderer/`. It is a flat Python package (`src/icon_templates_renderer/{__init__,exceptions}.py`, `models/{color_scheme,icon_config}.py`, `api/icon_renderer.py`, `services/{yaml_loader,color_scheme_loader,vocabulary_loader,svg_renderer}.py`, `cli/__init__.py`, `cli/commands/{render,list,validate}.py`) plus `pyproject.toml` (deps `typer`, `pyyaml`), a placeholder `settings.toml`, a `Makefile`, and an 879-line `tests/e2e/run-e2e-tests.sh` encoding ~40 behavior assertions across 10 categories: environment, CLI help, validate, list, render, unsafe mode, color mappings, template-dir override, color-scheme override, output-dir override.

The v3 repo (`dotfiles-repo-v3/`) has two sibling CLI tools implemented in a strict hexagonal (ports & adapters) style:
- `src/cli-tools/wallpaper-effects-generator` (binary `weg`, package `wallpaper_effects_generator`, Python ≥3.12): `domain` (frozen dataclasses, pure services, exceptions) ← `ports` (`@runtime_checkable Protocol`, one per file) ← `adapters` (loaders, processors, output/ with `base.py`+`projectors.py`+`{plain,json,rich}_output.py`, schemas/) ← `cli` (main.py with `build_deps`+`@app.callback`, per-group files, `options.py`, `_params.py`) + `factory.py` (`CliDependencies` + `create_*`) + `errors.py` facade + `constants.py` + `defaults/`. Tests: `tests/unit/{domain,ports,adapters,cli}/` mirroring src, `tests/unit/ports/conftest.py` with `assert_isinstance`/`assert_signature_compatible`/`assert_interface_method_count` and `test_contracts.py`, plus `tests/integration/`. Pyproject: hatchling, `[tool.uv.sources]` editable to `../../shared/{cli-output,config-assembler-engine,oci-runtime}`, ruff `E,F,I,N,W,UP,B` ignore `B905`, double quotes.
- `src/cli-tools/color-scheme-generator` (binary `csg`, package `color_scheme_generator`, Python ≥3.14): same shape; richer ADRs in `docs/ARCHITECTURE_PLAN.md` (ADR-001 single-file config, ADR-002 domain Port for processing, ADR-007 JSON-first output, ADR-010 no auto, ADR-012 frozen domain + Pydantic-at-boundary). Collapses "application/use-case" layer into CLI functions + factory.

There is no icon-renderer in v3. The `docs/99-dotfiles-hexagonal-architecture.md` tree lists `icon-renderer/` as a planned sibling; `docs/01-functional-testing-infra.md` confirms it is **native-only pure Python** — no `magick`, no Docker, no `oci-runtime` (unlike WEG/CSG which have containerized variants).

The v2 `IconRenderer` (`api/icon_renderer.py`) orchestrates: load icons YAML (`YamlLoader`) → per group load color scheme (`ColorSchemeLoader`) + mkdir output → per variant resolve mappings (variant > group > vocab) → `SvgRenderer.render_variant` (read template, regex-substitute `{{\w+}}`, write). The regex/literal/scheme logic is glued inside `SvgRenderer`, coupled to filesystem I/O — not unit-testable in isolation. `settings.toml` is a placeholder; nothing depends on it.

Shared libraries available in v3: `src/shared/cli-output` and `src/shared/config-assembler-engine`. `oci-runtime` exists but is deliberately unused here.

## Goals / Non-Goals

**Goals:**
- A new `src/cli-tools/icon-templates-renderer/` module whose folder tree, layering, naming, tooling, and test conventions match WEG/CSG exactly.
- Binary `itr`; project name `icon-templates-renderer`; package `icon_templates_renderer` (project name preserved from v2).
- Commands `render`/`list`/`validate` only — no `version`/`info`/`dump-config`/`dump-templates` (user-locked scope).
- Every v2 command, flag, override, format, precedence, rule, error, and plain-text output reproduced verbatim. Behavior parity is provable by the integration tests.
- All ~40 v2 bash-e2e scenarios ported 1:1 to pytest integration tests.
- Pure-domain extraction (`PathResolutionService`, `MappingResolutionService`, `PlaceholderSubstitutionService`) so the v2 substitution logic is unit-testable without files.
- Use-case modeled as a port (`IconRendererPort`) so orchestration is unit-testable with fake ports (no CliRunner, no filesystem).
- Python ≥3.14 (match CSG).

**Non-Goals:**
- No new commands beyond `render`/`list`/`validate`.
- No `oci-runtime`, no Docker, no `install`/`uninstall`, no subprocess.
- No behavior change to the user-facing surface (other than the additive, opt-in `--output-format`/`-q`/`-v` flags pending veto).
- No real settings behavior: `settings.toml` stays a placeholder; `ConfigResolverPort` is wire-architecturally present but functionally inert (keeps a clean seam for future growth without shifting v2 behavior).
- No modification to v2 code (it is the reference, not edited).
- No shared test-infra package changes; the new module owns its own `conftest.py` fixtures.

## Decisions

### D1. Module identity: `icon-templates-renderer` / `itr` / `icon_templates_renderer`

Folder `src/cli-tools/icon-templates-renderer/` (folder = project kebab-name, sibling convention). `pyproject.toml` `[project] name = "icon-templates-renderer"`, `[project.scripts] itr = "icon_templates_renderer.cli.main:app"`, package `src/icon_templates_renderer`. Rationale: project name preserved from v2 (`icon-templates-renderer`), short binary `itr` follows the `weg`/`csg` short-binary convention. Alternative considered: keep the long binary `icon-templates-renderer` — rejected (user chose `itr`); keep the v2 folder's `icon-renderer` short name as project — rejected (project name is preserved; folder follows project name).

### D2. No OCI / pure Python

`pyproject.toml` deps omit `oci-runtime`. No `adapters/docker/`, no `install`/`uninstall` commands, no `RuntimeMode`/`ContainerEngine` enums, no `--runtime`/`--container-engine` flags. Rationale: matches `docs/01-functional-testing-infra.md` (icon-renderer runs *none*: native only, no subprocess). Alternatives considered: mirroring siblings' container machinery — rejected as dead code with no v2 counterpart.

### D3. Hexagonal layout: domain → ports → adapters → cli + factory

Layer dependency direction is one-way, enforced by convention (no `import-linter`):
- `domain/` imports only stdlib + siblings within `domain/` (no pydantic, no `ports/`/`adapters/`/`cli/`).
- `ports/` imports only `domain.*` (under `TYPE_CHECKING` where possible).
- `adapters/` imports `ports/`, `domain.*`, external libs (`pydantic`, `yaml`, `cli-output`, `config-assembler-engine`); never `cli/`.
- `cli/` imports `ports/`, `domain.*`, `factory`, `typer`.
- `factory.py` imports `ports` + `adapters` (wires them).
Mirror WEG/CSG exactly. Rationale: siblings' verified pattern; gives pure-domain unit tests, fake-port adapter tests, and fake-processor CLI tests.

### D4. Frozen domain; Pydantic at the boundary only

All `domain/models.py` classes are `@dataclass(frozen=True)`; collection fields are `tuple[...]`; `dict` fields are wrapped in `MappingProxyType` via `__post_init__` (mirror CSG `GenerationSettings`). `domain/services.py` are pure (no I/O). `domain/enums.py` holds `OutputFormat` (PLAIN/JSON/RICH with `__str__ -> value`) and `Verbosity` (IntEnum QUIET=0..DEBUG=3). Pydantic `BaseModel`s live only in `adapters/schemas/` (`icons_config_schema.py`, `settings_schema.py`); an explicit mapper converts the validated schema to domain dataclasses. Rationale: ADR-012 from CSG; enables structural immutability and keeps the domain test-pure. `from __future__ import annotations` at the top of every file.

### D5. Ports are `@runtime_checkable Protocol`, one per file

Seven ports (`IconConfigLoaderPort`, `ColorSchemeLoaderPort`, `VocabularyLoaderPort`, `SvgRendererPort`, `IconRendererPort`, `ConfigResolverPort`, `OutputPort`), each `@runtime_checkable Protocol` in its own `ports/<name>.py` with `...` method bodies, importing only `domain.*`. Adapters rely on structural subtyping (duck typing via Protocol), NOT explicit inheritance (though they may declare the port as base for typing convenience — harmless; Protocol bases are ignored at runtime, same as siblings). Verified by `isinstance(adapter, Port)` in `tests/unit/ports/test_contracts.py`. Rationale: WEG/CSG signature idiom; enables the contract tests. Alternative considered: `abc.ABC` + `@abstractmethod` — rejected (siblings use Protocols; structural subtyping is the repo standard).

### D6. Use-case behind a Domain Port (`IconRendererPort`) — not collapsed into CLI

Unlike WEG (which collapses use-cases into CLI command functions), icon-renderer models its orchestration as a port + adapter (`ports/icon_renderer.py::IconRendererPort`, `adapters/icon_renderer.py::IconRenderer`). The adapter is exactly v2's `IconRenderer` reshaped to depend on injected ports (`IconConfigLoaderPort`, `ColorSchemeLoaderPort`, `VocabularyLoaderPort`, `SvgRendererPort`) plus the pure `PathResolutionService`/`MappingResolutionService`. Rationale: icon-renderer has non-trivial orchestration but no local/container/dry-run strategy split; a port makes the orchestration unit-testable with fake ports (no CliRunner, no filesystem) — matching the testing role WEG's `EffectProcessorPort` plays. Alternatives considered: putting orchestration directly in CLI command functions — rejected (loses fake-port unit testability; WEG collapsed because of the strategy split, which icon-renderer lacks).

### D7. Pure services extract v2's logic from I/O

`domain/services.py` contains three pure classes (no I/O, no filesystem):
- `PathResolutionService` — the v2 `_resolve_template_dir`/`_resolve_color_scheme`/`_resolve_output_dir`/`_resolve` trio (`yaml_loader.py:147-190`). Exposes the 3-tier precedence (CLI override → YAML root → YAML-relative) and absolute passthrough as pure functions of `(base_dir, path_str, overrides, root)`.
- `MappingResolutionService` — `merge(vocab_defaults, group_mappings, variant_mappings) -> dict[str,str]` implementing v2 `resolve_mappings` priority `{**vocab, **group, **variant}` (`icon_config.py:23-31`).
- `PlaceholderSubstitutionService` — the entire v2 `svg_renderer.render_string` core (`svg_renderer.py:34-67`): regex `\{\{(\w+)\}\}`, missing mapping → `MissingMappingError` unless unsafe, value `#…` → literal, `scheme.get(value)` → `None` ⇒ `ColorSchemeKeyNotFoundError` unless unsafe, unsafe leaves token as-is. `substitute(svg_body, scheme, unsafe, color_mappings) -> str`.
Rationale: v2 glued the regex logic to file I/O; extracting it to a pure service makes the trickiest behavior exhaustively unit-testable without files. This is the central maintainability upgrade.

### D8. Adapters re-implement v2 exact semantics

- `YamlIconConfigLoader` (`IconConfigLoaderPort`): PyYAML parse → `IconsConfigSchema` (Pydantic) validation → pop top-level `templates_root`/`color_scheme`/`outputs_root` → build `IconConfig(groups=...)` using `PathResolutionService` + `PathOverrides`. `load_one(name)` → find by name else `IconNotFoundError`. Error message strings verbatim from v2 (`yaml_loader.py`): `"YAML file not found: {path}"`, `"Failed to parse YAML: {e}"`, `"YAML root must be a mapping of icon group keys"`, `"Icon '{name}' is missing required field: '{field}'"`, `"A variant in icon '{group_name}' is missing required field: '{field}'"`.
- `FileColorSchemeLoader` (`ColorSchemeLoaderPort`): suffix dispatch; `.yaml/.yml` → `special{background,foreground,cursor}` + `colors` list → `color0..colorN`; `.json` → `special` + `colors` dict (keys preserved, NOT re-indexed); else `ColorSchemeNotFoundError(f"Unsupported color scheme format: {suffix}. Use .yaml or .json")`. Missing file → `ColorSchemeNotFoundError(f"Color scheme file not found: {path}")`. (Verbatim from v2 `color_scheme_loader.py`.)
- `YamlVocabularyLoader` (`VocabularyLoaderPort`): `None`/absent → empty `Vocabulary`; parse YAML; not dict OR missing `defaults` → `InvalidYamlError("Vocabulary file must contain a 'defaults' mapping: {path}")`; falsy → empty; not a dict → `InvalidYamlError("'defaults' must be a mapping of placeholder names to tokens")`; coerce k/v to `str`. (Verbatim from v2 `vocabulary_loader.py`.)
- `FileSvgRenderer` (`SvgRendererPort`): `render_variant` — `variant.template.exists()` else `TemplateNotFoundError(f"Template not found: {variant.template}")`; read text; `render_string` (delegate to `PlaceholderSubstitutionService`); mkdir `variant.output.parent`; write; return `variant.output`.
- `IconRenderer` (`IconRendererPort`): v2 `render`/`list`/`validate` orchestration (`api/icon_renderer.py:51-93`) reproduced. `render`: vocab = `vocab_loader.load(request.vocabulary_path or yaml_path.parent/"defaults.yaml")`; `effective_unsafe = request.unsafe if request.unsafe is not None else group.unsafe`; load scheme; `mkdir output_dir`; per variant `group.resolve_mappings(variant, vocab.defaults)` → `svg_renderer.render_variant`; collect `RenderedVariant`. Vocabulary default path lives in the adapter caller (preserves v2 `api/icon_renderer.py:44-49`).
- `AssembledConfigResolver` (`ConfigResolverPort`): uses `config-assembler-engine` `CompositePathResolver` (`CliPathStrategy` → `EnvPathStrategy("ICON_RENDERER_CONFIG_FILE_PATH")` → `DirectoryTraversalStrategy("settings.toml", 3)` → `XdgStrategy("icon-templates-renderer" or "itr")` → `DefaultFileStrategy(package defaults/settings.toml)`), `TomlConfigParser`, `CoreSettingsSchema` (minimal `[output] verbosity` only), `ResolutionPolicy(env_prefix="ICON_RENDERER")`. **Inert**: no command behavior depends on it beyond output verbosity/format (which are also CLI-overridable). Kept for architectural consistency + future-growth seam.

### D9. CLI / composition root mirrors WEG/CSG

- `factory.py`: `@dataclass CliDependencies` with `field(default_factory=ConcreteAdapter)` defaults + `__post_init__` wiring the `IconRenderer` from injected ports; free `create_*` factories (`create_output_adapter(fmt, verbosity)`, etc.); lazy imports for heavy adapters.
- `cli/main.py`: `app = typer.Typer(name="itr", help="Render SVG icon templates with color scheme values")`; `build_deps(output_format, verbosity) -> CliDependencies`; `@app.callback()` sets `ctx.obj = {"deps", "output_format", "verbosity"}`; `app.command()(render_command)` and same for `list_command`/`validate_command`.
- `cli/options.py`: reusable module-level UPPERCASE Typer Option objects (`ICON_OPT`, `UNSAFE_OPT`, `TEMPLATE_DIR`, `COLOR_SCHEME`, `OUTPUT_DIR`) — sibling convention.
- Each command: build `PathOverrides` (each flag `Path(x).expanduser().resolve() if x else None`), build the request DTO, `try: ...except IconRendererError as exc: deps.output_adapter.error(exc); raise typer.Exit(1)`.
- `render` uses `unsafe=unsafe or None` (preserves v2 `api/icon_renderer.py:33` semantics where `False` falls back to group value).
- Test seam: monkeypatch `icon_templates_renderer.cli.main.build_deps` (the universal sibling pattern — there is an explicit WEG test asserting no legacy `set_test_deps` hook exists).

### D10. Output: plain default, verbatim v2 text; additive opt-in flags

`OutputPort` takes domain objects (`RenderResult`/`ListResult`/`ValidateResult`/`IconRendererError`). `adapters/output/projectors.py` maps to `cli_output.domain.views` (`CustomView`/`ErrorView`/`MessageView`). `plain_output.py`/`json_output.py`/`rich_output.py` are one-liner subclasses setting `_default_format` (strategy pattern via class attribute; mirror siblings). **Plain is the default** (diverges from CSG's JSON default — recorded as ADR-005). Plain projector reproduces v2 text **verbatim**:
- render: `Rendered: <p1>\nRendered: <p2>\n\n2 icon(s) rendered.`
- list (all): `<group>:\n  - <variant>\n...`
- list (--icon): `Variants:\n  - <name>\n...`
- validate: `Validation passed.`
- error: `Error: <exc>` (to stderr).
Global flags `--output-format {plain,json,rich}` (default `plain`), `-q/--quiet`, `-v/--verbose` (count) are **additive** (plain default = v2 output). Rationale: adopting the sibling output architecture requires a format selector; plain default preserves user-facing v2 behavior. **Open decision flagged for veto** — if vetoed, drop `OutputPort`/`cli-output` and keep v2 `typer.echo`, diverging from siblings' output architecture.

### D11. Settings.toml placeholder (v2 behavior)

`defaults/settings.toml` carries v2-style commented-out sections (plus a minimal `[output] verbosity = "normal"` if needed). `ConfigResolverPort` + `AssembledConfigResolver` are wired but inert (D8). No command behavior depends on resolved settings; nothing in v2 relied on `settings.toml`. Rationale: user-locked "keep placeholder"; architecturally consistent seam for future config-driven defaults without breaking v2 today.

### D12. Domain model catalogue (frozen dataclasses)

`Color(hex)` (validates `^#[0-9a-fA-F]{6}$`), `ColorScheme(values: MappingProxyType[str, Color] | dict[str,str] view)`, `Variant(name, template, output, color_mappings)`, `IconGroup(name, color_scheme, template_dir, output_dir, unsafe=False, variants=(), color_mappings=...) + resolve_mappings(variant, vocab_defaults=None) -> dict[str,str]`, `IconConfig(groups)`, `Vocabulary(defaults)`, `PathOverrides(template_dir?, color_scheme?, output_dir?)`, `RenderRequest(yaml_path, icon?, unsafe: bool|None, overrides, vocabulary_path?)`, `RenderedVariant(variant_name, group_name, output_path)`, `RenderResult(success, rendered: tuple, error?)`, `ListRequest(...)`, `ListResult(groups: dict[str,tuple[str,...]] | tuple[str,...])` (v2 dual-shape preserved), `ValidateRequest(...)`, `ValidateResult(ok, checked_groups, checked_variants)`, `OutputSettings(verbosity)`, `AppSettings(output)`.

### D13. Schemas (Pydantic, parsing boundary)

`IconsConfigSchema` parses root as `dict[str, Any]`, pops reserved top-level keys (`templates_root`/`color_scheme`/`outputs_root` typed `str`), validates each remaining as `IconGroupSchema`. `IconGroupSchema`: required `color_scheme:str`/`template_dir:str`/`output_dir:str`/`variants:list[VariantSchema]`; optional `unsafe:bool=False`/`color_mappings:dict[str,str]={}`. `VariantSchema`: required `name:str`/`template:str`/`output:str`; optional `color_mappings:dict[str,str]={}`. `SettingsSchema`: `OutputSettingsSchema(verbosity)`, `CoreSettingsSchema(output)`. Path resolution semantics live in `PathResolutionService` (pure domain — testable).

### D14. Error model preserved

`domain/exceptions.py` defines `IconRendererError(Exception)` + 6 subclasses with the **same names as v2**, each storing typed attributes and building a human-readable message in `__init__` (sibling pattern, used by `projectors.project_error`): `InvalidYamlError(reason)`, `IconNotFoundError(name, yaml_path?)`, `TemplateNotFoundError(path)`, `ColorSchemeNotFoundError(path?)`, `MissingMappingError(key)`, `ColorSchemeKeyNotFoundError(key, scheme_key)`. `errors.py` re-exports with explicit `__all__`.

### D15. Testing strategy

- `tests/conftest.py`: `runner` (CliRunner), `fake_icon_renderer` (recording dataclass), `cli_deps_with_renderer` (monkeypatch `cli.main.build_deps`), `tmp_path` fixtures to build minimal `icons.yaml`, `colors.yaml`, `colors.json`, SVG templates, `defaults.yaml`.
- `tests/unit/{domain,ports,adapters,cli}/` mirroring `src/`. `ports/conftest.py` + `test_contracts.py` + `test_interfaces.py` copy sibling helpers verbatim and parametrize every adapter × every port.
- `tests/integration/`: port all 40 v2 bash-e2e scenarios 1:1 — real adapters + `tmp_path` (YAML/color/template content generated in pytest, same approach as v2 e2e heredocs). Categories: render, list, validate, unsafe mode, color mappings, template-dir override, color-scheme override, output-dir override. **No bash e2e script.**

### D16. Tooling

`pyproject.toml`: hatchling; `packages = ["src/icon_templates_renderer"]`; `[tool.uv.sources] cli-output = {path = "../../shared/cli-output", editable = true}` and `config-assembler-engine = {path = "../../shared/config-assembler-engine", editable = true}`; ruff `target-version = "py314"`, `line-length = 100`, lint `E,F,I,N,W,UP,B` ignore `B905`, format double quotes; pytest `testpaths = ["tests"]`, `pythonpath = ["src", "."]`, `addopts = ["--strict-markers", "-rxX"]`; `[dependency-groups] dev = ["pytest>=9.1.1"]`. `.python-version` = `3.14`. `Makefile` target set carried from v2 for dev ergonomics.

## Risks / Trade-offs

- **Open decision: additive `--output-format`/`-q`/`-v` flags** → Mitigation: plain default preserves v2 user-facing output; flags are opt-in. If vetoed, fallback D10-alt drops `OutputPort`/`cli-output` and keeps v2 `typer.echo`.
- **`IconRendererPort` diverges from WEG's collapsed-into-CLI use-cases** → Accepted: icon-renderer has no strategy split (local/container/dry-run) so removing it from the CLI enables fake-port unit tests of the orchestration; reasoned per-module.
- **`ConfigResolverPort` is wired but inert** → Accepted: small extra surface; clean seam for future config-driven defaults without a later refactor; honors user "keep placeholder" decision.
- **MiPy / `import-linter` not enforced** → Mitigation: dependency-direction is conventional; port-contract `isinstance` tests + the DoD checklist guard layering. Siblings also rely on convention.
- **Sibling test-layout inconsistency** (flat `tests/test_*.py` coexist with nested `tests/unit/...`) → Mitigation: new module follows the newer, nested mirror convention exclusively.
- **Folder name `icon-templates-renderer` longer than `weg`/`csg` folders'** → Accepted: folder = project kebab-name; short binary `itr` is the user-facing artifact.
- **Vocabulary default path (`yaml_path.parent/"defaults.yaml"`) lives inside `IconRenderer`** → Mitigation: explicitly relocated there (not the CLI) to preserve v2 behavior exactly; documented.
- **`MappingProxyType` wrapping in frozen dataclasses** → Mitigation: mirror CSG `GenerationSettings` `__post_init__` pattern.

## Migration Plan

Net-new module; no data migration, no removal. Rollback is deleting `src/cli-tools/icon-templates-renderer/`. No deployment surface beyond running `uv sync` in the new folder to install `itr`. v2 module is untouched. The v2 e2e script serves as the behavioral checklist during implementation; its scenarios become the integration tests, after which it is no longer referenced.