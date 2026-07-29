## MODIFIED Requirements

### Requirement: Templates directory is isolated from settings assembly

**Previous:** CSG's `--templates-dir` flowed through `cli_overrides["template.templates_dir"]` → `OverrideRule("template.templates_dir", ...)` → `settings.template.templates_dir` → `renderer.update_templates_dir()`. Templates resolution was entangled with the settings assembly subsystem.

**Updated:** Templates directory resolution SHALL be managed exclusively by `TemplateDirResolver` (path resolution subsystem). The settings assembly subsystem SHALL NOT have any knowledge of templates directory.

- `TemplateSettings` dataclass and `TemplateSettingsSchema` SHALL be deleted.
- `AppSettings` SHALL NOT have a `template` field.
- `CoreSettingsSchema` SHALL NOT have a `template` field.
- `AssembledConfigResolver` SHALL NOT register `OverrideRule("template.*", ...)`.
- `SettingsSerializer.serialize` SHALL NOT emit a `[template]` section.
- `ContainerProcessor._serialize_settings` SHALL NOT emit a `[template]` section.

#### Scenario: --templates-dir flag reaches renderer directly

- **WHEN** `csg generate img.png --templates-dir /custom/templates` is run
- **THEN** the renderer's `update_templates_dir("/custom/templates")` is called
- **THEN** the config assembler never sees `template.templates_dir` in `cli_overrides`
- **THEN** `settings.template` does not exist

#### Scenario: Env var COLORSCHEME_TEMPLATES_TEMPLATES_DIR continues working

- **WHEN** `COLORSCHEME_TEMPLATES_TEMPLATES_DIR=/custom/templates csg generate img.png` is run (no `--templates-dir`)
- **THEN** `TemplateDirResolver.EnvDirStrategy` resolves `/custom/templates`
- **THEN** the renderer uses templates from `/custom/templates`

#### Scenario: Singular env var COLORSCHEME_TEMPLATE_TEMPLATES_DIR no longer overrides

- **WHEN** `COLORSCHEME_TEMPLATE_TEMPLATES_DIR=/custom/templates csg generate img.png` is run
- **THEN** the singular env var has no effect (override rule was removed)
- **THEN** templates resolution falls back to the discovery chain (CWD traversal, XDG, bundled default)

#### Scenario: dump-config output omits template section

- **WHEN** `csg dump-config` is run
- **THEN** the output does not contain `[template]` section
- **THEN** the output does not contain `templates_dir` or `custom_templates_dir` keys

#### Scenario: info shows template path from resolver chain only

- **WHEN** `csg info` is run
- **THEN** the templates source path shown is resolved by `TemplateDirResolver.resolve()` (env/CWD/XDG/default chain)
- **THEN** the resolver receives no `settings_dir` argument (no settings templates field to pass)

#### Scenario: Container mode mounts templates without settings field read

- **WHEN** `csg generate img.png --runtime container` is run
- **THEN** `ContainerProcessor.process_generate` calls `self._template_dir_resolver.resolve()` with no args
- **THEN** the in-container TOML delivered to the container does not contain a `[template]` section
- **THEN** the container's inner csg uses `COLORSCHEME_TEMPLATES_TEMPLATES_DIR` (from `_CONTAINER_ENV`) for templates resolution

#### Scenario: Settings.toml with template section is silently ignored

- **WHEN** user has `[template]\ntemplates_dir = "/x"` in their `settings.toml` and runs `csg generate img.png`
- **THEN** the `[template]` section is silently ignored (no field in schema)
- **THEN** templates resolution falls back to the discovery chain (env/CWD/XDG/default)

## ADDED Requirements

### Requirement: TemplateDirResolver remains single source of truth

`TemplateDirResolver` SHALL be the only mechanism for resolving the templates directory in CSG. Its strategy chain (CliDirStrategy → EnvDirStrategy → DirTraversalStrategy → XdgDirStrategy → DefaultDirStrategy) SHALL be unchanged.

#### Scenario: CliDirStrategy receives --templates-dir value (post cli-flag-scope-completion)

- **WHEN** `csg generate img.png --templates-dir /custom` is run (after `cli-flag-scope-completion` lands)
- **THEN** the `--templates-dir` value reaches `TemplateDirResolver.resolve(explicit_path="/custom")` either via `renderer.update_templates_dir("/custom")` (this change) or via direct resolver call (subsequent flag-scope change)
- **THEN** `CliDirStrategy` returns `/custom` as the resolved path

#### Scenario: Renderer keeps update_templates_dir API

- **WHEN** any caller invokes `renderer.update_templates_dir(path)`
- **THEN** the renderer re-initializes its Jinja environment from the given path
- **THEN** the renderer does not consult any settings object