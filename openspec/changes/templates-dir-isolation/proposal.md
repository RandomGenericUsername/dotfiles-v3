## Why

CSG entangles templates directory resolution with the settings assembly subsystem. `TemplateSettings` carries `templates_dir` and `custom_templates_dir` fields, two `OverrideRule("template.*", ...)` entries treat them as settings override fields, and `--templates-dir` flows through `cli_overrides` → `OverrideMatchingService` → `settings.template.templates_dir` → `renderer.update_templates_dir()` — a roundabout path that duplicates what `TemplateDirResolver` already does independently.

WEG's architecture for the parallel concern (`effects.yaml`) is cleaner: the effects path is **never a settings field**, never an `OverrideRule`, and `YamlEffectLoader` resolves it directly via config-assembler-engine path strategies with `rules=[]`. CSG's current architecture is asymmetric and produces three concrete defects:

1. **Two env var names for the same concern** — `COLORSCHEME_TEMPLATE_TEMPLATES_DIR` (singular, override route — being removed) and `COLORSCHEME_TEMPLATES_TEMPLATES_DIR` (plural, `TemplateDirResolver.EnvDirStrategy`). Users cannot predict which wins.
2. **`TemplateSettings` exists solely to launder a path** through the settings assembler. It carries no domain meaning; `dump-config` serializes an empty `[template]` section as a result.
3. **`TemplateDirResolver`'s `CliDirStrategy` is dead code for `--templates-dir`** — the CLI value is laundered through the settings field instead of reaching the strategy directly.

## What Changes

Decouple CSG templates directory resolution from the settings assembly subsystem, mirroring WEG's isolated secondary-resource pattern.

1. **Remove `TemplateSettings` dataclass** from `domain/models.py`.
2. **Remove `template: TemplateSettings` field** from `AppSettings`.
3. **Remove `TemplateSettingsSchema`** from `adapters/settings/schema.py`.
4. **Remove `template: TemplateSettingsSchema = ...` field** from `CoreSettingsSchema`.
5. **Remove two `OverrideRule("template.*", ...)` entries** from `AssembledConfigResolver`.
6. **Remove `template=TemplateSettings(...)` kwarg** from `_convert_to_app_settings` and `default_app_settings()`.
7. **Route `--templates-dir` directly to the renderer** — store the flag value in `ctx.obj["templates_dir"]` and have `generate`/`show` call `renderer.update_templates_dir(ctx.obj["templates_dir"])` instead of reading `settings.template.templates_dir`.
8. **Drop `[template]` section** from `SettingsSerializer.serialize` output.
9. **Drop `[template]` block** from `ContainerProcessor._serialize_settings` (in-container TOML no longer has a `[template]` section).
10. **Simplify `process_generate`** in `ContainerProcessor`: drop `settings_dir = settings.template.templates_dir` lookup; call `self._template_dir_resolver.resolve()` with no args.
11. **Simplify `info`** command: drop `settings_dir = settings.template.templates_dir` lookup; call `template_dir_resolver.resolve()` with no args.

After this change:
- `COLORSCHEME_TEMPLATES_TEMPLATES_DIR` (plural, via `TemplateDirResolver.EnvDirStrategy`) is the **single** env var for templates.
- `--templates-dir` flows directly to the renderer (still at root callback in this change; relocation to leaves happens in `cli-flag-scope-completion`).
- `dump-config` output no longer contains an empty `[template]` section.
- `TemplateDirResolver` is the single source of truth for templates directory resolution.
- The `CliDirStrategy` (explicit path) inside `TemplateDirResolver` finally reaches `--templates-dir`'s value directly rather than through a settings-laundry roundtrip.

## Capabilities

### New Capabilities
*(none — this change removes an entanglement; it does not add new behavior)*

### Modified Capabilities
- `cli-runtime-engine-scope`: Refines flag-consumer relationships — `--templates-dir` now flows directly to a standalone resolver (like WEG's `--effects`), not through `cli_overrides`. Strengthened alignment with WEG's pattern.

## Impact

- **CSG domain layer**: `TemplateSettings` class deleted from `models.py`; `AppSettings` loses a field.
- **CSG schema layer**: `TemplateSettingsSchema` deleted from `schema.py`; `CoreSettingsSchema` loses a field. `_convert_to_app_settings` simplified.
- **CSG override rules**: `AssembledConfigResolver` loses two `OverrideRule` entries and the `TemplateSettings` import.
- **CSG serializer**: `SettingsSerializer.serialize` no longer emits `[template]` section. `dump-config` output is cleaner.
- **CSG container adapter**: `ContainerProcessor._serialize_settings` no longer emits `[template]` section. On-the-wire TOML delivered into the container loses the redundant section. `process_generate` no longer reads `settings.template.templates_dir`.
- **CSG CLI**: `generate`, `show`, `info` no longer read `settings.template.templates_dir`; they read `ctx.obj["templates_dir"]` (CLI flag) or `template_dir_resolver.resolve()` (fallback chain).
- **CSG `_helpers.default_app_settings()`**: no longer instantiates `TemplateSettings`.
- **Tests (14 files)**: every test fixture that constructs `AppSettings` drops the `template=` kwarg; `TestTemplateSettings` deleted from `test_models.py`; `[template]` section assertions removed from `test_settings_serializer.py`; `isinstance(result.template, TemplateSettings)` assertion removed from `test_config_resolver.py`.
- **WEG**: **no changes.** WEG is already on the target architecture.
- **No changes**: `JinjaTemplateRenderer` API (`update_templates_dir()` and `_init_env()` remain — still useful). `TemplateDirResolver.resolve(settings_dir=None)` API unchanged. `_CONTAINER_ENV` in `container_processor.py:34` continues injecting `COLORSCHEME_TEMPLATES_TEMPLATES_DIR` for the in-container `csg` invocation. The `CliDependencies.template_dir_resolver` field stays.