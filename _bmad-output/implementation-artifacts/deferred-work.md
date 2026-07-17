# Deferred Work

## Deferred from: code review of 1-3-custom-backend-adapter (2026-07-15)

- pyproject.toml test deps — pre-existing, not in scope for this story's ACs
- CustomGenerator not re-exported from adapters/__init__.py — not required by spec
- Timezone-naive datetime.now() — can be addressed when multi-zone support needed

## Deferred from: code review of 1-3-custom-backend-adapter (2026-07-16)

- Timezone-naive datetime.now() [custom_generator.py:82] — pre-existing, re-deferred
- Empty colors list fallback to black [domain/services.py:33] — pre-existing domain code, out of scope for this story
- n_clusters upper bound [custom_generator.py:47] — performance concern (cap at 40000 for 200x200 images), not a correctness issue

## Deferred from: code review of 1-5-local-processor-generation-service (2026-07-16)

- success=True hardcoded without post-generation validation [local_processor.py:47,70] — matches current spec
- generator.generate() exceptions propagate raw across port boundary [local_processor.py:43,66] — design choice
- request.image_path not validated before use [local_processor.py:43,66] — out of scope for this story
- settings parameter silently ignored [local_processor.py:34,57] — AppSettings is a known placeholder

## Deferred from: code review of 1-6-cli-generate-command (2026-07-16)

- Backend generators eagerly instantiated [factory.py:28-30] — low overhead (stubs + no custom __init__)
- Hardcoded /tmp/color-scheme output dir [main.py:36] — out of scope (Epic 2 adds -o/--output-dir)
- `.` in pythonpath is a fixture hazard [pyproject.toml:25] — pre-existing, not specific to this change
- Only ColorSchemeError caught [main.py:47] — by design per spec ("let unexpected errors propagate")
- Callback has no error handling for factory failures [main.py:22-26] — low risk, systemic config issues handled at app level
- CliDependencies.processor field declared but never set [factory.py:23] — forward-looking, will be used in Epic 2/3

## Deferred from: code review of 1-7-cli-show-version-commands (2026-07-16)

- Hardcoded `/tmp/color-scheme` output directory — pre-existing pattern from story 1.6, output customization is Epic 2 scope
- Empty `formats=()` produces no output files — pre-existing from story 1.6; `show` by design doesn't write files
- Hardcoded `Backend.CUSTOM` with empty `params` — backend selection is Epic 2 scope
- Duplicate `GeneratorConfig` construction across `generate` and `show` — pre-existing pattern from story 1.6
- Silent success in `generate` command (no console feedback) — by-design for JSON output mode, pre-existing
- `build_deps()` exception propagates uncaught through callback — pre-existing pattern from story 1.6
- `image_path` not validated for type (accepts directories, special files) — file validation is processor responsibility

## Deferred from: code review of story 2-1-full-domain-and-remaining-ports (2026-07-16)

- `resolve_all` silently ignores unknown override keys — caller typos produce no warning
- `resolve_all` never enforces `choices` constraint — override values not validated against BackendParameterDefinition.choices
- ContainerSettings fields lack validation — `timeout_seconds` can be negative, `memory_limit` is unvalidated
- BackendParameterDefinition.choices and default are type-incompatible — no static check
- `resolve_all` ignores GenerationSettings.default_params — pipeline not yet built (story 2.2 scope)
- ConfigResolverPort has no failure contract — undocumented exceptions
- TemplateRendererPort has no error contract — undocumented exceptions
- TemplateDirResolverPort returns Path even when both dirs can be None — no fallback contract
- SettingsSerializerPort has no error contract — undocumented exceptions
- BackendCatalogLoaderPort contract allows empty dict — no minimum-registration guarantee

## Deferred from: code review of 2-2-settings-config-resolution-pipeline (2026-07-16)

- `explicit_path` to missing file not wrapped — depends on config-assembler-engine contract
- `resolved_path` and `applied_overrides` could be `None` — depends on config-assembler-engine contract

## Deferred from: code review of 2-3-backend-yaml-catalog-resolution (2026-07-16)

- Cross-field validation on BackendParameterSchema — no validators for `min <= max`, `default` type matching `param_type`, or `default` in `choices`. Pre-existing pattern from settings resolver.
- Empty `choices` list accepted — `choices: []` passes all validators but is semantically void.
- Duplicate param keys silently accepted — two parameters with same key in one backend both added.
- AssemblyResult metadata discarded — `resolved_path` and `applied_overrides` not exposed by `load()`. Port signature limits this.
- `min_version="0.0.0"` hardcoded — no source of truth in YAML for this domain field.
- Integration test doesn't test actual bundled file — test writes own YAML to `tmp_path`, never loads real `defaults/backends.yaml`.
