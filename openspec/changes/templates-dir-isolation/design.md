## Context

CSG mixes two config-assembler-engine subsystems for templates resolution:

- **Settings assembly subsystem** (`AssembleConfiguration`, `OverrideRule`, `OverrideMatchingService`): `--templates-dir` → `cli_overrides["template.templates_dir"]` → override rule match → `settings.template.templates_dir` populated → renderer called from CLI command.
- **Path resolution subsystem** (`CompositePathResolver`, `CliDirStrategy`, `EnvDirStrategy`, etc.): `TemplateDirResolver` resolves the templates directory via env var `COLORSCHEME_TEMPLATES_TEMPLATES_DIR`, CWD traversal, XDG, bundled default — invoked only when `settings.template.templates_dir is None`.

These overlap. WEG's parallel concern (`effects.yaml`) uses the path resolution subsystem exclusively (via `YamlEffectLoader` with `rules=[]`); the settings assembly subsystem never sees an effects path. This change brings CSG's template concerns to the same clean separation.

See `openspec/specs/cli-runtime-engine-scope/investigation-report.md` for the full architectural comparison and the verified asymmetric defect.

## Goals / Non-Goals

**Goals:**
- Single mechanism for templates directory resolution in CSG: `TemplateDirResolver`.
- Single env var: `COLORSCHEME_TEMPLATES_TEMPLATES_DIR` (plural).
- No `TemplateSettings` / `TemplateSettingsSchema` classes — no schema pollution.
- `dump-config` output no longer contains a phantom `[template]` section.
- No behavioral regression: `--templates-dir /x`, `COLORSCHEME_TEMPLATES_TEMPLATES_DIR=/x`, CWD `templates/`, XDG `~/.config/color-scheme/templates`, and bundled default all continue to work in the same priority order.

**Non-Goals:**
- Moving `--templates-dir` from root callback to leaves — that's `cli-flag-scope-completion` (sequenced after this change).
- Renaming or consolidating `TemplateDirResolver`'s strategies.
- Removing `JinjaTemplateRenderer.update_templates_dir()` API — kept as a valid runtime override hook.
- Removing `CliDependencies.template_dir_resolver` field — kept as a per-deps resolver instance.
- Any WEG code change — WEG is already on the target architecture.
- `dump-config` behavior change (resolve+serialize → print bundled) — that's `cli-flag-scope-completion`.

## Decisions

### D1: Remove `TemplateSettings` entirely; do not replace with a sentinel

**Choice:** Delete `TemplateSettings` class, `AppSettings.template` field, `TemplateSettingsSchema`, `CoreSettingsSchema.template` field, both override rules, and every consumer that reads `settings.template.*`.

**Alternatives considered:**
- *Keep `TemplateSettings` but stop populating it:* Dead schema, leaks the empty `[template]` section in serializer output, confuses readers. Worse than removing.
- *Replace with `Optional[Path]` on `AppSettings` directly (no nested dataclass):* Still carries the entanglement — just relocates it.
- *Keep `TemplateSettings` but cut override rules:* Inconsistent — the field exists in the schema but is silently ignored; users editing TOML get a phantom field with no effect.

**Why delete entirely:** The settings object has no domain use for a templates path. Templates resolution is a *path resolution* concern (where to find files), not a *settings* concern (behavioral configuration). WEG's clean separation proves this; matching it eliminates the asymmetry and the dual-env-var confusion.

### D2: Route `--templates-dir` through `ctx.obj`, not through `cli_overrides`

**Choice:** After deletion, `--templates-dir` (still at the root callback) stores its value in `ctx.obj["templates_dir"]`. The `generate`/`show` command bodies read this and call `renderer.update_templates_dir(value)` directly when non-None; otherwise the renderer relies on its construction-time `TemplateDirResolver` resolution (env→XDG→default).

**Alternatives considered:**
- *Call `TemplateDirResolver.resolve(explicit_path=...)` directly from the leaf:* Requires passing the resolver to the CLI layer or constructing a fresh instance. The renderer already owns a `TemplateDirResolver` instance and exposes `update_templates_dir()` as a runtime hook — reusing that API is smaller churn.
- *Pass `--templates-dir` as `cli_overrides["template.templates_dir"]` (existing path):* This is what we're removing — it's the entanglement.

**Why `ctx.obj`:** This stays within the CLI adapter layer's session-scoped context dict, doesn't leak into the domain schema, and preserves the existing `update_templates_dir()` API. In `cli-flag-scope-completion` we move the flag itself to leaf options and read it from the local parameter directly (replacing the `ctx.obj["templates_dir"]` read). The `ctx.obj` hop is a temporary bridge that supports incremental refactoring.

### D3: `TemplateDirResolver.resolve(settings_dir=None)` API left unchanged

**Choice:** Do not simplify the `resolve(settings_dir=None)` signature. Leave it as-is.

**Rationale:** The `settings_dir` parameter is still called by `info` (passes `settings.template.templates_dir` — now removed) and `ContainerProcessor.process_generate` (passes `settings.template.templates_dir` — now removed). After removal, both call `resolve()` with no args (falling through the full strategy chain). External callers/tests may still use the explicit-path form. Removing the parameter adds churn without behavioral gain in this change; leave the API simplification for a later cleanup.

### D4: Keep `_CONTAINER_ENV` injection unchanged

**Choice:** Do not modify `ContainerProcessor._CONTAINER_ENV["COLORSCHEME_TEMPLATES_TEMPLATES_DIR"] = "/templates"` — leave it as-is.

**Rationale:** This env var is read by the *inner* `csg` invocation inside the container, which uses its own `TemplateDirResolver.EnvDirStrategy`. It is unrelated to the CSG host-side settings-assembly override rule we are removing. The dual env var confusion is a host-side phenomenon; the container's inner csg already uses only the plural name.

### D5: Keep `JinjaTemplateRenderer.update_templates_dir()` API unchanged

**Choice:** Continue to support `renderer.update_templates_dir(path)` as the CLI override hook; do not remove or refactor it.

**Rationale:** The renderer still receives a `TemplateDirResolver` at construction time and calls `resolve()` (with `settings_dir=None`) to set up the Jinja environment. The CLI uses `update_templates_dir(explicit_path)` to override at runtime when `--templates-dir` is passed. Both behaviors are needed and correct. The "entanglement" was *not* that the renderer has an override method — it was that the override value was laundered through the settings schema. With `TemplateSettings` gone, `update_templates_dir()` cleanly serves the isolated path-resolution subsystem.

### D6: Sequencing with `cli-flag-scope-completion`

**Order:** This change (`templates-dir-isolation`) lands **first**. Then `cli-flag-scope-completion` moves `--templates-dir` from root callback to `generate`/`show`/`info` leaf options.

**Rationale:** `cli-flag-scope-completion`'s leaf-level wiring reads the leaf-local `--templates-dir` parameter and calls `renderer.update_templates_dir(local_value)` — that requires the renderer API to be the override hook (D5) and `cli_overrides["template.templates_dir"]` to be gone. If `cli-flag-scope-completion` landed first, the `cli_overrides` plumbing would still exist and need re-removal later. By landing isolation first, the flag-scope change becomes a clean relocation of an already-clean plumbing.

## Risks / Trade-offs

- **[Behavior parity with env var `COLORSCHEME_TEMPLATE_TEMPLATES_DIR` (singular)]** After removal, the singular env var stops having any effect. Users relying on it must switch to `COLORSCHEME_TEMPLATES_TEMPLATES_DIR` (plural). **Mitigation:** The plural form has always been the `TemplateDirResolver`'s native var; the singular form only worked via the override-rule-laundry path. Document this in README/release notes. Add a test that the singular form no longer overrides (and that it falls back to default).

- **[Behavior parity with TOML `[template]` section]** Users who had `[template]\ntemplates_dir = "/x"` in their `settings.toml` will have that section silently ignored after this change (the field no longer exists in the schema — pydantic will either drop or warn). **Mitigation:** The settings schema likely ignores unknown fields by default (verify). The bundled default `settings.toml` has never shipped a `[template]` section, so default users are unaffected. Document in release notes that `[template]` is no longer supported.

- **[Test churn]** 14 test files touch `template=` kwargs or `settings.template.*` assertions. **Mitigation:** All edits are mechanical deletions; no new test logic required besides removing `TestTemplateSettings`.

- **[Merge with `engine-qualified-image-tags` (in progress)]** Several files overlap (`adapters/container_processor.py`, `cli/_helpers.py`, `cli/install_cmd.py`). **Mitigation:** Engine-tags has only 5 verification tasks remaining (no implementation); its implementation work is already in the uncommitted working tree alongside `cli-flag-scope-refinement`. Commit the current uncommitted state as a clean baseline first (preflight commit), then land `templates-dir-isolation`.

## Migration Plan

1. **Preflight commit:** Commit all current uncommitted working tree changes (mixed engine-qualified-image-tags implementation + cli-flag-scope-refinement execution) as one cohesive snapshot to give a clean baseline.
2. **Land `templates-dir-isolation`:** Implement the changes per tasks.md. Tests must pass.
3. **Resume `engine-qualified-image-tags`:** Run the 5 remaining verification tasks; mark complete and archive.
4. **Land `cli-flag-scope-completion`:** Implement after `templates-dir-isolation` is in.

### Rollback strategy

If `templates-dir-isolation` causes unexpected behavior regression in container mode (where `TemplateDirResolver` resolution chain differs from settings-field-driven resolution): `git revert` the change. The schema/model changes are atomic — reverting restores `TemplateSettings`, the override rules, and the `settings.template.templates_dir` read path wholesale.