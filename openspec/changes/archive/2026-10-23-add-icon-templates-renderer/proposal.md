## Why

The v2 `icon-renderer` (`dotfiles-repo-v2/src/cli-tools/icon-renderer`) is a flat, single-layer Python package: CLI commands, a `YamlLoader`, a `ColorSchemeLoader`, a `VocabularyLoader`, an `SvgRenderer`, and an `IconRenderer` API facade all sit in a `services/` + `api/` + `models/` + `cli/` structure with no ports, no pure-domain extraction, no structural-subtyping contracts, and a mostly-empty placeholder `settings.toml`. Its behaviour is fully captured by an 879-line bash e2e script (~40 tests) and a handful of unit tests, but the architecture diverges sharply from the v3 repo's established hexagonal (ports & adapters) philosophy that `wallpaper-effects-generator` (WEG) and `color-scheme-generator` (CSG) already follow.

v3 has no `icon-renderer` at all. The module must be rebuilt in `src/cli-tools/icon-templates-renderer/` matching the sibling architecture (frozen domain, `@runtime_checkable Protocol` ports, Pydantic-at-the-boundary, `CliDependencies` composition root, `OutputPort` taking domain objects, port-contract tests) so that the three CLI tools share one maintainable, scalable shape. The rewrite must not lose a single v2 capability: every command, flag, override, color-scheme format, placeholder rule, error message, and plain-text output line must be reproduced, and the entire v2 e2e behavioral spec must be carried over as pytest integration tests.

## What Changes

### New module (`src/cli-tools/icon-templates-renderer/`)

A standalone uv-managed Python package mirroring WEG/CSG layout:
- `pyproject.toml` — `name = "icon-templates-renderer"`, `requires-python = ">=3.14"`, `[project.scripts] itr = "icon_templates_renderer.cli.main:app"`, hatchling build, deps `typer>=0.12`, `pydantic>=2.0`, `pyyaml>=6.0`, `rich>=13.0`, `cli-output`, `config-assembler-engine` (editable via `[tool.uv.sources]` → `../../shared/<name>`), **no `oci-runtime`**; ruff `py314` / line-length 100 / double quotes; pytest `--strict-markers -rxX`; dev group `pytest>=9.1.1`.
- `Makefile` — `test`/`test-all`/`lint`/`format`/`check`/`build`/`clean` (carried over from v2 for dev ergonomics).
- `.python-version` — `3.14`.
- `docs/ARCHITECTURE_PLAN.md` — ADRs mirroring siblings.
- `uv.lock`.

### Source layout (`src/icon_templates_renderer/`)

```
__init__.py            # __version__ = "0.1.0"
errors.py              # re-export of domain.exceptions (public facade) + __all__
constants.py           # CONFIG_FILENAME, CONFIG_XDG_SUBDIR="itr", CONFIG_TRAVERSAL_DEPTH, VOCABULARY_FILENAME
factory.py             # CliDependencies dataclass + create_* factories
domain/
  enums.py             # OutputFormat (PLAIN/JSON/RICH), Verbosity
  models.py            # frozen dataclasses (see Decisions)
  services.py          # pure services: PathResolutionService, MappingResolutionService, PlaceholderSubstitutionService
  exceptions.py        # IconRendererError + 6 subclasses (v2 names preserved)
ports/
  icon_config_loader.py    # IconConfigLoaderPort
  color_scheme_loader.py   # ColorSchemeLoaderPort
  vocabulary_loader.py     # VocabularyLoaderPort
  svg_renderer.py          # SvgRendererPort
  icon_renderer.py         # IconRendererPort  (use-case driver; renders/lists/validates)
  config_resolver.py       # ConfigResolverPort
  output.py                # OutputPort
adapters/
  yaml_icon_config_loader.py    # YamlIconConfigLoader  (PyYAML + Pydantic + PathResolutionService)
  file_color_scheme_loader.py   # FileColorSchemeLoader (yaml/json dispatch)
  yaml_vocabulary_loader.py     # YamlVocabularyLoader
  file_svg_renderer.py          # FileSvgRenderer (read→substitute→write)
  icon_renderer.py              # IconRenderer (implements IconRendererPort; orchestrates ports + services)
  assembled_config_resolver.py # AssembledConfigResolver (config-assembler-engine; minimal/inert)
  schemas/
    icons_config_schema.py      # IconsConfigSchema + group/variant sub-schemas (Pydantic)
    settings_schema.py          # CoreSettingsSchema (minimal)
  output/
    base.py                     # OutputAdapterBase (cli-output Renderer)
    projectors.py               # domain → cli_output Views; plain reproduces v2 text verbatim
    plain_output.py             # PlainOutput (default)
    json_output.py
    rich_output.py
defaults/
  settings.toml          # placeholder (v2-style comments); architecturally present but inert
cli/
  main.py                # app = typer.Typer("itr"); build_deps(); global options
  options.py             # reusable Typer Option objects (ICON_OPT, UNSAFE_OPT, TEMPLATE_DIR, COLOR_SCHEME, OUTPUT_DIR)
  render.py              # render_command
  list_cmd.py            # list_command
  validate.py            # validate_command
```

### Tests (`tests/`)

- `conftest.py` — `runner`, `fake_icon_renderer` (recording dataclass), `cli_deps_with_renderer` (monkeypatches `cli.main.build_deps`), `tmp_path` fixtures to materialize minimal `icons.yaml`, `colors.yaml`, `colors.json`, SVG templates, `defaults.yaml`.
- `tests/unit/{domain,ports,adapters,cli}/` mirroring `src/` — including `ports/conftest.py` with `assert_isinstance`/`assert_signature_compatible`/`assert_interface_method_count` and `ports/test_contracts.py` parametrizing every adapter × its port.
- `tests/integration/` — port all ~40 v2 bash-e2e scenarios 1:1 into pytest. **No bash e2e script.**

### Behavior preserved from v2 (verbatim / exact)

- **Commands**: `render`, `list`, `validate` (no `version`/`info`/`dump-config`/`dump-templates`).
- **`render` flags**: `--icon`, `--unsafe`, `--template-dir`, `--color-scheme`, `--output-dir`.
- **`list` flags**: `--icon`, `--template-dir`.
- **`validate` flags**: `--icon`, `--template-dir`, `--color-scheme`.
- **App help**: "Render SVG icon templates with color scheme values".
- **Plain output text (verbatim)**: `Rendered: <path>` (one per variant), blank line, `<N> icon(s) rendered.`; `Validation passed.`; `<group>:\n  - <variant>` lines; `Variants:\n  - <name>` lines; `Error: <exc>` to stderr + exit 1.
- **Icons YAML**: top-level optional `templates_root`/`color_scheme`/`outputs_root` keys; each group requires `color_scheme`/`template_dir`/`output_dir`/`variants`, optional `color_mappings`/`unsafe`; each variant requires `name`/`template`/`output`, optional `color_mappings`. Missing required keys raise `InvalidYamlError` with v2 message strings.
- **Path resolution precedence** (per dir kind): CLI override > YAML top-level root > YAML-relative; absolute passthrough. `color_scheme` override replaces the whole path; `template_dir`/`output_dir` overrides join the override root with the YAML string.
- **ColorScheme loader**: `.yaml`/`.yml` → `special{background,foreground,cursor}` + `colors` list → `color0..colorN`; `.json` → `special` + `colors` dict (keys preserved); other suffix → `ColorSchemeNotFoundError`. Missing file → `ColorSchemeNotFoundError`.
- **Vocabulary loader**: `defaults.yaml` next to icons YAML; `{}` when absent or unset; must contain a `defaults` mapping; k/v coerced to `str`; malformed → `InvalidYamlError`.
- **Mapping merge priority**: variant > group > vocab_defaults.
- **Placeholder substitution**: regex `\{\{(\w+)\}\}`; missing mapping → `MissingMappingError` unless `unsafe`; value starts with `#` → literal; else `scheme.get(value)` → `None` ⇒ `ColorSchemeKeyNotFoundError` unless `unsafe`; `unsafe` leaves the token as-is.
- **`unsafe` semantics**: effective = `request.unsafe if request.unsafe is not None else group.unsafe` (v2 `unsafe or None` pattern).
- **`validate`**: per group check `color_scheme.exists()` and each `variant.template.exists()`; first failure raises.
- **`load_one` by icon name**: `IconNotFoundError` if absent (`list --icon unknown` and `render --icon unknown` exit non-zero with `Error: ...`).
- **Errors**: `IconRendererError`, `InvalidYamlError`, `IconNotFoundError`, `TemplateNotFoundError`, `ColorSchemeNotFoundError`, `MissingMappingError`, `ColorSchemeKeyNotFoundError` (names preserved).

### Additive surface (open decision, flagged for veto)

Adopting the sibling `OutputPort` requires a format selector. To preserve v2 UX: **plain is the default**; additive global flags `--output-format {plain,json,rich}`, `-q/--quiet`, `-v/--verbose` (count). Nothing v2 is removed. If the flags are vetoed, the fallback is to keep v2's plain `typer.echo` output and drop the `OutputPort`/`cli-output` dependency — but that diverges from the sibling output architecture. **Default plan proceeds assuming the flags are included.**

## Capabilities

### New Capabilities
- `itr-cli` — `itr` binary exposing `render`/`list`/`validate` commands with v2-flag surfaces, plain-default output verbatim with v2 text, optional `--output-format`/`-q`/`-v`, and `Error: <exc>` + exit 1 on `IconRendererError`.
- `itr-config-loading` — loading of the icons YAML config (top-level roots + groups/variants), color-scheme files (YAML/JSON), and vocabulary defaults (`defaults.yaml`), with the 3-tier path override precedence and the exact error messages.
- `itr-substitution` — SVG `{{placeholder}}` substitution semantics (regex, literal `#`, scheme-key lookup, `unsafe` fallback leaving tokens) and mapping merge priority variant > group > vocab.
- `itr-architecture` — hexagonal layering (domain/ports/adapters/cli), frozen domain dataclasses, `@runtime_checkable Protocol` ports, Pydantic-at-the-boundary, `CliDependencies` composition root with `build_deps` monkeypatch test seam, port-contract tests via `isinstance`.

### Modified Capabilities
- (none — no existing v3 spec covers icon rendering; this is a new module.)

## Impact

- **New source tree**: `src/cli-tools/icon-templates-renderer/**` (full structure above) — entirely new; the v2 module at `dotfiles-repo-v2/src/cli-tools/icon-renderer/**` is the reference being migrated, not modified.
- **Shared libraries used**: `cli-output` (OutputPort adapters), `config-assembler-engine` (AssembledConfigResolver; inert). No `oci-runtime`. Workspace editable deps already declared by siblings; the new `pyproject.toml` adds the same `[tool.uv.sources]` entries.
- **Repo-level**: no root workspace pyproject exists (each cli-tool owns its own `pyproject.toml`/`uv.lock`); no change to root files. The new module is discovered by running `uv sync` inside its folder.
- **CLI surface**: a new `itr` binary is installed via `uv sync` in the new module; no existing binaries change.
- **Tests**: pure addition under `src/cli-tools/icon-templates-renderer/tests/`; the full v2 e2e behavioral contract is re-encoded as integration tests so behavior stays locked.
- **Behavior**: identical user-facing behavior to v2 for `render`/`list`/`validate` and all flags; the only additions are the opt-in `--output-format`/`-q`/`-v` flags (plain default preserves v2 output).
- **Documentation**: new `docs/ARCHITECTURE_PLAN.md` inside the module with ADRs mirroring siblings.