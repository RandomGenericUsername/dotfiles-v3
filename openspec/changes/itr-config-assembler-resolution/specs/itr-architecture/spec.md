## ADDED Requirements

### Requirement: Real settings resolution via config-assembler
`ConfigResolverPort` SHALL be implemented by an `AssembledConfigResolver` that resolves `settings.toml` via 5 FILE strategies (`CliPathStrategy` from `--config`, `EnvPathStrategy` `ICON_RENDERER_CONFIG_FILE_PATH`, `DirectoryTraversalStrategy` `settings.toml`, `XdgStrategy` `itr/settings.toml`, bundled `defaults/settings.toml`), with OverrideRules for `output.output_dir`, `output.verbosity`, `templates.dir`, `color_scheme.path` (each `{CLI, ENV}`), producing `AppSettings(output, templates, color_scheme)`.

#### Scenario: bundled default settings
- **WHEN** no settings file is found via flag/env/traversal/XDG
- **THEN** the bundled `defaults/settings.toml` is used and `output_dir` resolves to `/tmp/icon-templates-renderer`

### Requirement: TemplateDirResolver and ColorSchemeResolver ports
Two new `@runtime_checkable Protocol` ports SHALL provide discovery-only resolution returning `Path | None`: `TemplateDirResolverPort` (DirTraversal `templates` + Xdg `itr/templates`) and `ColorSchemeResolverPort` (traversal `colors.yaml` + Xdg `itr/colors.yaml`). They SHALL NOT consult env or CLI.

#### Scenario: every adapter satisfies its port
- **WHEN** `tests/unit/ports/test_contracts.py` runs
- **THEN** `isinstance`/signature/method-count assertions pass for both new adapters

#### Scenario: discovery returns None when nothing found
- **WHEN** no `templates/` dir and no XDG `itr/templates` exist
- **THEN** `TemplateDirResolverPort.resolve()` returns `None`

### Requirement: ResolvedRoots replaces PathOverrides
The domain SHALL carry a frozen `ResolvedRoots(template_root, color_scheme, output_root: Path | None)`, populated by the CLI orchestrator after settings + discovery. Requests SHALL carry `ResolvedRoots` (not `PathOverrides`). `PathResolutionService` SHALL be a pure joiner (`root / sub` then resolve; absolute passthrough); the 3-tier precedence SHALL live in the orchestrator, not the domain.

#### Scenario: render request carries resolved roots
- **WHEN** a render runs
- **THEN** `RenderRequest.roots` is a `ResolvedRoots` and the loader joins each group's relative dir under the corresponding root
