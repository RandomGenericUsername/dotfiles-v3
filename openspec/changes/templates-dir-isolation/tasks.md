## 1. Remove TemplateSettings and TemplateSettingsSchema

- [ ] 1.1 Delete `TemplateSettings` dataclass from `src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/models.py` (lines 119-122)
- [ ] 1.2 Remove `template: TemplateSettings` field from `AppSettings` in domain/models.py
- [ ] 1.3 Remove `TemplateSettings` from `domain/__init__.py` exports (lines 40, 82)
- [ ] 1.4 Delete `TemplateSettingsSchema` class from `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/settings/schema.py` (lines 45-54)
- [ ] 1.5 Remove `template` field from `CoreSettingsSchema` in schema.py (line 110)
- [ ] 1.6 Remove `TemplateSettingsSchema` from `adapters/settings/__init__.py` exports (lines 10, 21)

## 2. Remove override rules from AssembledConfigResolver

- [ ] 2.1 Delete `OverrideRule("template.templates_dir", {OverrideSource.CLI, OverrideSource.ENV})` line from config_resolver.py (line 97)
- [ ] 2.2 Delete `OverrideRule("template.custom_templates_dir", ...)` line from config_resolver.py (line 98)
- [ ] 2.3 Remove `TemplateSettings` import from config_resolver.py (line 36)
- [ ] 2.4 Remove `template=TemplateSettings(...)` kwarg from `_convert_to_app_settings` in config_resolver.py (lines 52-55)

## 3. Update CLI flag routing (--templates-dir at root → ctx.obj → renderer directly)

- [ ] 3.1 In `cli/main.py` root callback: remove the `if templates_dir is not None: cli_overrides["template.templates_dir"] = str(templates_dir)` mapping (lines 142-143)
- [ ] 3.2 Store flag value in `ctx.obj["templates_dir"]` instead (alongside existing `templates_dir` capture in `ctx.obj` setup)
- [ ] 3.3 In `generate` body: replace `if settings.template.templates_dir is not None and deps.template_renderer is not None: deps.template_renderer.update_templates_dir(settings.template.templates_dir)` (lines 213-214) with `if ctx.obj.get("templates_dir") is not None and deps.template_renderer is not None: deps.template_renderer.update_templates_dir(ctx.obj["templates_dir"])`
- [ ] 3.4 In `show` body: apply the same change as 3.3 (replacing `settings.template.templates_dir` read with `ctx.obj.get("templates_dir")`)

## 4. Update info command

- [ ] 4.1 In `cli/info_cmd.py` (lines 52-57): replace `settings_dir = settings.template.templates_dir if settings else None` and `template_dir_resolver.resolve(settings_dir=settings_dir)` with `template_dir_resolver.resolve()` (no args)

## 5. Update default_app_settings helper

- [ ] 5.1 Remove `TemplateSettings` import from `cli/_helpers.py` (line 19)
- [ ] 5.2 Remove `template=TemplateSettings(templates_dir=None, custom_templates_dir=None)` kwarg from `default_app_settings()` in `_helpers.py` (lines 42-45)

## 6. Update settings serializer

- [ ] 6.1 Delete `sections.append(_dataclass_to_toml_section(settings.template, "template"))` line from `adapters/settings/settings_serializer.py` (line 59)

## 7. Update container processor

- [ ] 7.1 In `adapters/container_processor.py` delete the `[template]` block in `_serialize_settings` (lines 97-102 — `lines.append("[template]")` + `kv("templates_dir", ...)` + `kv("custom_templates_dir", ...)` + `lines.append("")`)
- [ ] 7.2 In `adapters/container_processor.py` `process_generate` (lines 162-164): drop `settings_dir = settings.template.templates_dir if settings else None` lookup; call `self._template_dir_resolver.resolve()` with no args
- [ ] 7.3 Confirm `_CONTAINER_ENV` injection of `COLORSCHEME_TEMPLATES_TEMPLATES_DIR` (line 34) is unchanged (no edit)

## 8. Update tests (14 files)

- [ ] 8.1 `tests/unit/domain/test_models.py`: delete `TestTemplateSettings` class (lines 292-304); remove `TemplateSettings` import (line 24); drop `template=...` kwarg from AppSettings fixtures (lines 339, 352, 358)
- [ ] 8.2 `tests/unit/adapters/settings/test_settings_serializer.py`: remove `TemplateSettings` import (line 18); drop `template=TemplateSettings(...)` from settings fixture (lines 34-36); remove `"[template]" in result` assertions (lines 64, 107); remove `"templates_dir"`/`"custom_templates_dir"` not-in-output assertions (lines 121-122)
- [ ] 8.3 `tests/unit/adapters/settings/test_config_resolver.py`: remove `TemplateSettings` import (line 28); drop `template={}` from CoreSettingsSchema fixture (line 38); drop `isinstance(result.template, TemplateSettings)` assertion (line 71)
- [ ] 8.4 `tests/unit/adapters/test_container_processor.py`: remove `TemplateSettings` import (line 27); drop `template=TemplateSettings(...)` from `_make_settings` (lines 43-45)
- [ ] 8.5 `tests/unit/adapters/test_dry_run_processor.py`: remove `TemplateSettings` import (line 31); drop `template=TemplateSettings(...)` from `_make_settings` (lines 48-51)
- [ ] 8.6 `tests/unit/cli/test_first_run.py`: remove `TemplateSettings` import (line 79); drop `template=...` kwarg (lines 92-95)
- [ ] 8.7 `tests/unit/cli/test_generate.py`: remove `TemplateSettings` import (line 19); drop `template=...` kwarg (line 35)
- [ ] 8.8 `tests/unit/cli/test_generate_full.py`: remove `TemplateSettings` import (line 24); drop `template=...` kwarg at all 4 sites (lines 40, 195, 290, 346)
- [ ] 8.9 `tests/unit/cli/test_show.py`: remove `TemplateSettings` import (line 21); drop `template=...` kwarg (line 49)
- [ ] 8.10 `tests/unit/cli/test_info_command.py`: remove `TemplateSettings` import (line 19); drop `template=...` kwarg (line 35)
- [ ] 8.11 `tests/unit/cli/test_install_command.py`: remove `TemplateSettings` import (line 16); drop `template=...` kwarg (line 32)
- [ ] 8.12 `tests/unit/cli/test_uninstall_command.py`: remove `TemplateSettings` import (line 16); drop `template=...` kwarg (line 32)
- [ ] 8.13 `tests/unit/cli/test_dump_config_command.py`: remove `TemplateSettings` import (line 18); drop `template=...` kwarg (line 34)
- [ ] 8.14 `tests/unit/ports/conftest.py`: remove `TemplateSettings` import (line 18); drop `template=...` kwarg from `_settings()` (line 44)

## 9. Verify behavior parity

- [ ] 9.1 Run full CSG unit test suite: all tests pass
- [ ] 9.2 Run full WEG unit test suite: all tests pass (no changes expected)
- [ ] 9.3 `csg generate img.png` works with bundled templates (no `--templates-dir`)
- [ ] 9.4 `csg generate img.png --templates-dir /custom/dir` works (direct renderer update via ctx.obj)
- [ ] 9.5 `COLORSCHEME_TEMPLATES_TEMPLATES_DIR=/custom/dir csg generate img.png` works (plural env var via TemplateDirResolver.EnvDirStrategy)
- [ ] 9.6 `csg info` shows templates path from resolver chain only (no `settings_dir`)
- [ ] 9.7 `csg dump-config --output /tmp/test.toml` no longer contains `[template]` section
- [ ] 9.8 `csg generate img.png --runtime container` mounts templates correctly (container processor calls `template_dir_resolver.resolve()` with no args; inner container uses `COLORSCHEME_TEMPLATES_TEMPLATES_DIR` from `_CONTAINER_ENV`)

## 10. Update help text

- [ ] 10.1 In `cli/main.py` root app help description: remove the "1. Explicit --templates-dir flag" bullet from the Templates directory discovery section (the flag stays at root in this change; help text cleanup is in `cli-flag-scope-completion`); keep the rest of the discovery chain help unchanged since `COLORSCHEME_TEMPLATES_TEMPLATES_DIR` env var and XDG path are still valid and documented
- [ ] 10.2 Remove the dead `_xdg_templates_path` constant use if no longer referenced after help edit