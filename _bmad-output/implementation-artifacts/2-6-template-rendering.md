---
baseline_commit: 653b9af82568818913828f940befe81ef7165fc1
---

# Story 2.6: Template Rendering

Status: done

## Story

As a theming user,
I want color schemes rendered into all my config file formats,
So that my terminal, rofi, GTK, and other tools get themed automatically.

## Acceptance Criteria

### AC 1: JinjaTemplateRenderer implements TemplateRendererPort

**Given** JinjaTemplateRenderer implementing TemplateRendererPort
**When** render() is called with template_name, ColorScheme, and output_path
**Then** it resolves the template from the TemplateDirResolver-resolved directory
**And** uses Jinja2 `Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)`
**And** writes rendered output to the specified output_path
**And** the template context contains: source_image, backend, generated_at, background, foreground, cursor, colors (16-tuple)
**And** each Color in context exposes `.hex` (str) and `.rgb` (tuple[int,int,int])

### AC 2: 8 bundled templates produce valid output

**Given** 8 bundled templates in defaults/templates/
**When** each format is rendered
**Then** colors.json.j2 produces valid JSON
**And** colors.sh.j2 produces a valid shell script (key=value pairs)
**And** colors.css.j2 produces valid CSS
**And** colors.gtk.css.j2 produces valid GTK CSS
**And** colors.yaml.j2 produces valid YAML
**And** colors.rasi.j2 produces valid RASI
**And** colors.scss.j2 produces valid SCSS
**And** colors.sequences.j2 renders with binary post-processing: `]` → `\x1b]`, `\` → `\x1b\\`

### AC 3: TemplateDirResolver implements TemplateDirResolverPort

**Given** TemplateDirResolver implementing TemplateDirResolverPort
**When** resolve() is called
**Then** it uses CompositePathResolver with: env var `COLORSCHEME_TEMPLATES_TEMPLATES_DIR` > XDG `$XDG_CONFIG_HOME/color-scheme/templates` > package defaults `defaults/templates/`
**And** returns a directory Path

### AC 4: Error handling for missing templates

**Given** a missing template name
**When** render() is called
**Then** TemplateNotFoundError is raised with searched paths
**When** template rendering fails (e.g., Jinja2 syntax error)
**Then** TemplateRenderError is raised with the template name and reason

### AC 5: Structural subtyping

**Given** JinjaTemplateRenderer
**When** verified via `isinstance(obj, TemplateRendererPort)`
**Then** it passes structural subtype checking

**Given** TemplateDirResolver
**When** verified via `isinstance(obj, TemplateDirResolverPort)`
**Then** it passes structural subtype checking

## Tasks / Subtasks

### Domain exceptions (new)
- [x] Add `TemplateNotFoundError` to `domain/exceptions.py` (AC: 4)
  - Fields: `template_name: str`, `searched_paths: tuple[Path, ...]`
  - Message: `"Template '{name}' not found. Searched: {paths}"`
- [x] Add `TemplateRenderError` to `domain/exceptions.py` (AC: 4)
  - Fields: `template_name: str`, `reason: str`
  - Message: `"Failed to render template '{name}': {reason}"`
- [x] Export both from `domain/__init__.py` and `errors.py`

### TemplateDirResolver adapter (new)
- [x] Create `adapters/template_dir_resolver.py` (AC: 3)
  - Implements `TemplateDirResolverPort`
  - Uses `config-assembler-engine`'s `CompositePathResolver`
  - Custom strategies:
    - `EnvPathStrategy(var="TEMPLATES_DIR")` with prefix `COLORSCHEME_TEMPLATES`
    - `DirectoryXdgStrategy(xdg_subdir="color-scheme", dirname="templates")` — thin custom strategy
    - `DefaultDirectoryStrategy(path=<package defaults/templates>)` — thin custom strategy
  - Resolve order: env -> XDG -> package defaults
  - Returns resolved directory Path

### JinjaTemplateRenderer adapter (new)
- [x] Create `adapters/jinja_template_renderer.py` (AC: 1)
  - Implements `TemplateRendererPort`
  - Accepts `TemplateDirResolverPort` in constructor
  - Jinja2 `Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)`
  - Renders template from TemplateDirResolver-resolved dir to output_path
  - Template context:
    - `source_image`: str (image path)
    - `backend`: str (backend name)
    - `generated_at`: str (ISO datetime)
    - `background`: Color
    - `foreground`: Color
    - `cursor`: Color
    - `colors`: list of Color (16 items)
  - Color exposes `.hex` and `.rgb` as template variables
  - Binary post-processing for sequences format:
    - `]` → `\x1b]`
    - `\` → `\x1b\\`
    - Output is bytes, written as binary
  - Missing template raises `TemplateNotFoundError` (AC: 4)
  - Render failure raises `TemplateRenderError` (AC: 4)
  - All directories created if they don't exist (mkdir parents)

### 8 bundled templates (new)
- [x] Create `defaults/templates/colors.json.j2` (AC: 2)
  - JSON output: `{"background": "...", "foreground": "...", "cursor": "...", "colors": [...], "source_image": "...", "backend": "...", "generated_at": "..."}`
- [x] Create `defaults/templates/colors.sh.j2` (AC: 2)
  - Shell script: `COLOR_BACKGROUND='...'`, etc.
- [x] Create `defaults/templates/colors.css.j2` (AC: 2)
  - CSS custom properties: `--color-background: ...;`
- [x] Create `defaults/templates/colors.gtk.css.j2` (AC: 2)
  - GTK CSS: `@define-color color_background ...;`
- [x] Create `defaults/templates/colors.yaml.j2` (AC: 2)
  - YAML output
- [x] Create `defaults/templates/colors.rasi.j2` (AC: 2)
  - Rofi RASI
- [x] Create `defaults/templates/colors.scss.j2` (AC: 2)
  - SCSS variables
- [x] Create `defaults/templates/colors.sequences.j2` (AC: 2)
  - Terminal escape sequences with `]` and `\` markers for post-processing

### Factory wiring (existing file: factory.py)
- [x] Add `TemplateDirResolver` to `factory.py`
  - Import and instantiate
  - Add to `CliDependencies`
- [x] Add `JinjaTemplateRenderer` to `factory.py`
  - Import and instantiate with TemplateDirResolver
  - Add to `CliDependencies`
- [x] Add `create_template_dir_resolver()` helper function
- [x] Add `create_template_renderer()` helper function
- [x] Wire renderer into `CliDependencies` dataclass

### Update LocalProcessor (existing file: local_processor.py)
- [x] Accept `TemplateRendererPort` in constructor
- [x] In `process_generate()`: after extraction, iterate `GeneratorConfig.formats` and call `renderer.render()` for each
- [x] Collect output file paths and populate `GenerationResult.output_files`
- [x] `process_show()` should NOT render templates (display-only)

### Dependencies
- [x] Add `jinja2>=3.1` to `pyproject.toml` dependencies

### Write tests
- [x] Create `tests/unit/adapters/test_jinja_template_renderer.py` (AC: 1, 2, 4, 5)
  - test_render_calls_resolve_and_writes_output
  - test_render_context_contains_required_fields
  - test_render_uses_strict_undefined
  - test_render_creates_parent_directories
  - test_render_raises_template_not_found
  - test_render_raises_template_render_error_on_failure
  - test_sequences_post_processing
  - test_structural_subtyping
- [x] Create `tests/unit/adapters/test_template_dir_resolver.py` (AC: 3, 5)
  - test_resolve_uses_env_var_first
  - test_resolve_falls_back_to_xdg
  - test_resolve_falls_back_to_package_defaults
  - test_structural_subtyping
- [x] Update `tests/unit/adapters/test_local_processor.py` to cover template rendering
  - test_generate_renders_templates
  - test_show_does_not_render_templates
  - test_output_files_populated_in_result

### Templates for review
- [x] Review all templated Jinja2 content for correctness since templates must produce valid files

## Dev Notes

### Current State

The template ports already exist:
- `ports/template_renderer.py:10-12` — `TemplateRendererPort` Protocol with `render(template_name, scheme, output_path)` → `None`
- `ports/template_dir_resolver.py:8-9` — `TemplateDirResolverPort` Protocol with `resolve()` → `Path`

No adapter implementations exist yet. The `defaults/templates/` directory does not exist — must be created with all 8 `.j2` template files. The `defaults/` directory currently only contains `backends.yaml`.

The `factory.py` has no template wiring. `LocalProcessor` (local_processor.py) currently only does palette extraction and returns empty `output_files=()`. It must be extended to accept and use a `TemplateRendererPort`.

Domain exceptions `TemplateNotFoundError` and `TemplateRenderError` don't exist yet — must be added to `domain/exceptions.py` and exported from both `domain/__init__.py` and top-level `errors.py`.

Jinja2 is not listed in `pyproject.toml` dependencies — must be added.

### Established Pattern (from PywalGenerator and other adapters)

- Class-based adapter implementing a Protocol port
- Constructor injection for dependencies
- All exceptions use domain exception hierarchy (never bare Python exceptions)
- `isinstance(obj, Port)` structural subtyping test
- Tests use `unittest.mock` (patch, MagicMock) — follow `test_pywal_generator.py` pattern

### Architecture Plan Reference

From `ARCHITECTURE_PLAN.md:113-114`:
```
| `JinjaTemplateRenderer` | `TemplateRendererPort` | Jinja2 `Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)`. Loads `.j2` files from the `TemplateDirResolverPort`-resolved directory. Renders each requested format, writes to `output_dir/<filename>`. Special binary post-processing for the `sequences` format (`]` → `\x1b]`, `\` → `\x1b\\`) |
```

From `ARCHITECTURE_PLAN.md:670-672`:
```
8 Jinja2 templates ported verbatim from v2 `packages/core/src/color_scheme/templates/`: colors.{css,gtk.css,json,rasi,scss,sequences,sh,yaml}.j2. Render context: `source_image`, `backend`, `generated_at`, `background`/`foreground`/`cursor` (`Color` with `.hex`/`.rgb`), `colors` (16-tuple of `Color`). The `sequences` format gets binary post-processing in `JinjaTemplateRenderer`.
```

From `ARCHITECTURE_PLAN.md:192-203`:
```
Templates Directory — path-resolver only (ADR-004):
Prefix: COLORSCHEME_TEMPLATES
Default dir: package-bundled defaults/templates/
Strategies:
  EnvPathStrategy(var="TEMPLATES_DIR")    # COLORSCHEME_TEMPLATES_TEMPLATES_DIR
  DirectoryXdgStrategy(xdg_subdir="color-scheme", dirname="templates")
  DefaultDirectoryStrategy(path=<package defaults/templates>)
Resolver: CompositePathResolver
```

### Template context shape

```python
{
    "source_image": str(path),        # Path as string
    "backend": str(backend.value),     # Backend enum value
    "generated_at": str(datetime),     # ISO format string
    "background": Color,               # .hex, .rgb attributes
    "foreground": Color,
    "cursor": Color,
    "colors": list[Color],             # 16 items, each with .hex, .rgb
}
```

Color objects expose `.hex` (str like `"#1a1b26"`) and `.rgb` (tuple like `(26, 27, 38)`) that Jinja2 can access directly.

### Binary post-processing for sequences format

The sequences template contains literal `]` and `\` as placeholders that must be post-processed:
- `]` → `\x1b]` (OSC escape)
- `\` → `\x1b\\` (ST string terminator)

This is because embedding raw escape sequences in Jinja2 templates is fragile and hard to edit. The renderer must:
1. Render the template as string
2. Replace `]` with `\x1b]` and `\` with `\x1b\\`
3. Encode to bytes
4. Write as binary

### File naming convention for output

Output files follow the pattern: `<output_dir>/colors.<format>` where format is the ColorFormat value:
- JSON → `colors.json`
- SH → `colors.sh`
- CSS → `colors.css`
- GTK_CSS → `colors.gtk.css`
- YAML → `colors.yaml`
- SEQUENCES → `colors.sequences` (binary)
- RASI → `colors.rasi`
- SCSS → `colors.scss`

### Previous Story Intelligence (from 2.5)

- **Review findings to pre-apply** (from 2.5 review patches):
  - No `Path.home()` at import time — defer to lazy evaluation
  - Use `isinstance` guards on file content reads
  - No bare exceptions — wrap all I/O in domain exceptions
  - All new exceptions exported from `domain/__init__.py` and `errors.py`
  - Coverage target: all acceptance criteria covered by tests
- **Test count target**: ~12+ tests (new adapter, more complex than backend adapters due to 8 formats + sequences post-processing)
- **All existing ~203 tests must pass** — zero regressions
- **Ruff clean required** for all new/modified files

### Project Structure Notes

- New adapter (JinjaTemplateRenderer): `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/jinja_template_renderer.py`
- New adapter (TemplateDirResolver): `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/template_dir_resolver.py`
- New templates: `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/` (8 files)
- Domain exceptions to modify: `domain/exceptions.py` (add 2 exception classes)
- Domain init to modify: `domain/__init__.py` (export new exceptions)
- Top-level errors: `errors.py` (re-export new exceptions)
- Factory: `factory.py` (add template wiring, update CliDependencies)
- LocalProcessor: `adapters/local_processor.py` (add template rendering)
- Tests: `tests/unit/adapters/test_jinja_template_renderer.py` and `test_template_dir_resolver.py`
- Port interface: `ports/template_renderer.py` — TemplateRendererPort Protocol
- Port interface: `ports/template_dir_resolver.py` — TemplateDirResolverPort Protocol

### Test patterns to follow

Follow the existing test patterns from `tests/unit/adapters/test_pywal_generator.py`:
- Class-based test suite
- `unittest.mock.patch` and `MagicMock`
- `pytest.raises` for exception testing
- `pytest` fixtures for shared config

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Dev Notes from Previous Story (2.5)

- Follow the established adapter pattern
- Pre-apply review findings from 2.5
- All ~203 existing tests must pass — zero regressions
- Ruff clean required for all new/modified files
- Test count target: ~12 tests minimum

### Post-implementation verification

```bash
cd src/cli-tools/color-scheme-generator
pytest
ruff check --fix
```

### Implementation Plan

1. Add `TemplateNotFoundError` and `TemplateRenderError` to `domain/exceptions.py`
2. Export new exceptions from `domain/__init__.py` and `errors.py`
3. Create `defaults/templates/` directory with 8 `.j2` template files
4. Implement `adapters/template_dir_resolver.py` — TemplateDirResolver with CompositePathResolver
5. Implement `adapters/jinja_template_renderer.py` — JinjaTemplateRenderer
6. Update `adapters/local_processor.py` — inject renderer, iterate formats, populate output_files
7. Update `factory.py` — wire template resolver and renderer into CliDependencies
8. Add `jinja2>=3.1` to `pyproject.toml` dependencies
9. Write tests for both new adapters
10. Update existing LocalProcessor tests
11. Run full test suite and ruff

### Completion Notes

- Implemented `TemplateNotFoundError` and `TemplateRenderError` domain exceptions with proper fields and messages
- Created `TemplateDirResolver` adapter using `CompositePathResolver` with three custom strategies:
  - `_EnvDirStrategy`: resolves `COLORSCHEME_TEMPLATES_TEMPLATES_DIR` env var
  - `_XdgDirStrategy`: resolves `$XDG_CONFIG_HOME/color-scheme/templates`
  - `_DefaultDirStrategy`: resolves package-bundled `defaults/templates/`
- Created `JinjaTemplateRenderer` adapter with Jinja2 `Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)`
- Template context includes all required fields: source_image, backend, generated_at, background, foreground, cursor, colors (16-tuple)
- Sequences format gets binary post-processing: `]` → `\x1b]`, `\` → `\x1b\\`
- Missing templates raise `TemplateNotFoundError`, render failures raise `TemplateRenderError`
- Created 8 bundled templates (json, sh, css, gtk.css, yaml, rasi, scss, sequences)
- Updated `LocalProcessor` to accept optional `TemplateRendererPort` and render templates in `process_generate()`
- `process_show()` does NOT render templates (display-only)
- Wired template resolver and renderer into `factory.py` CliDependencies
- Added `jinja2>=3.1` to pyproject.toml
- 8 new tests for JinjaTemplateRenderer + 4 for TemplateDirResolver + 3 updated LocalProcessor tests
- All 218 tests pass, ruff clean (no new issues)

### Dependencies

- New PyPI dependency: `jinja2>=3.1` (add to pyproject.toml)
- Uses built-in `pathlib`, `json` for file I/O
- Uses `config-assembler-engine`'s `CompositePathResolver` for template directory resolution
- Uses `typing.Protocol` for port conformance (no change needed)

### References

- [Source: epics.md:413-441] Story 2.6 acceptance criteria
- [Source: ARCHITECTURE_PLAN.md:113-114] JinjaTemplateRenderer adapter spec
- [Source: ARCHITECTURE_PLAN.md:192-203] TemplateDirResolver (CompositePathResolver)
- [Source: ARCHITECTURE_PLAN.md:670-672] 8 bundled templates specification
- [Source: PRD.md:225-240] FR-15 Template Rendering requirements
- [Source: ports/template_renderer.py] TemplateRendererPort Protocol
- [Source: ports/template_dir_resolver.py] TemplateDirResolverPort Protocol
- [Source: domain/models.py] Color, ColorScheme, ColorFormat models
- [Source: domain/exceptions.py] Existing exception hierarchy
- [Source: adapters/local_processor.py] LocalProcessor to modify
- [Source: factory.py] Factory to wire

### Review findings pre-applied (from 2.5 review)

Prevent re-review of issues already caught in 2.5:
1. No `Path.home()` at import time — use lazy properties or function calls
2. `isinstance` guards on file content types (JSON root is dict, etc.)
3. No bare Python exceptions — wrap all I/O errors in domain exceptions
4. All new exceptions registered in `__init__.py` and `errors.py`
5. Template names sanitized — no path traversal in template_name
6. Output file path validated — no writes outside output_dir
7. Sequences binary post-processing must handle both `]` and `\` replacements in correct order
8. TemplateDirResolver must handle missing env var gracefully (not crash)

## File List

### New files
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/jinja_template_renderer.py` (new — JinjaTemplateRenderer implementing TemplateRendererPort)
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/template_dir_resolver.py` (new — TemplateDirResolver implementing TemplateDirResolverPort)
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/colors.json.j2` (new template)
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/colors.sh.j2` (new template)
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/colors.css.j2` (new template)
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/colors.gtk.css.j2` (new template)
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/colors.yaml.j2` (new template)
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/colors.rasi.j2` (new template)
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/colors.scss.j2` (new template)
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/colors.sequences.j2` (new template)
- `src/cli-tools/color-scheme-generator/tests/unit/adapters/test_jinja_template_renderer.py` (new tests)
- `src/cli-tools/color-scheme-generator/tests/unit/adapters/test_template_dir_resolver.py` (new tests)

### Modified files
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/exceptions.py` (add TemplateNotFoundError, TemplateRenderError)
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/__init__.py` (export new exceptions)
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/errors.py` (re-export new exceptions)
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/local_processor.py` (add template rendering to process_generate)
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/factory.py` (wire template resolver and renderer)
- `src/cli-tools/color-scheme-generator/pyproject.toml` (add jinja2 dependency)
- `src/cli-tools/color-scheme-generator/tests/unit/adapters/test_local_processor.py` (add template rendering tests)

## Change Log

- 2026-07-16: Created comprehensive story spec for Template Rendering
- 2026-07-17: Implemented TemplateDirResolver and JinjaTemplateRenderer adapters, 8 bundled templates, factory wiring, LocalProcessor updates, and 15 tests

## Review Findings

- [x] [Review][Defer] TemplateDirResolver custom strategies (DirectoryXdgStrategy, DefaultDirectoryStrategy) extend config-assembler-engine — if config-assembler-engine's CompositePathResolver API changes, these may need updating. This is a pre-existing dependency concern, not specific to this change.
- [x] [Review][Defer] Sequences binary post-processing uses simple str.replace() — if the template ever contains literal `]` or `\` that should NOT be escaped, this will produce incorrect output. However, the current template design intentionally uses these as markers, so this is by design. Document as a known limitation.

### Code Review (2026-07-17)

- [x] [Review][Patch] OSC 10/11 sequences background/foreground swapped [`defaults/templates/colors.sequences.j2:17-18`] — Fixed.
- [x] [Review][Patch] Broad `except Exception` masks real errors [`adapters/template_dir_resolver.py:78`] — Changed to catch `PathResolutionError` specifically.
- [x] [Review][Patch] Factory typed to concrete class instead of port [`factory.py:29`] — Changed to `TemplateRendererPort`.
- [x] [Review][Patch] Missing output path validation [`adapters/jinja_template_renderer.py:53`] — Added PermissionError/OSError handling and type coercion guards.
- [x] [Review][Patch] Template name path traversal guard missing [`adapters/jinja_template_renderer.py:27`] — Added `os.path.basename` validation.
- [x] [Review][Patch] Partial output_files on render failure [`adapters/local_processor.py:62`] — Extracted `_render_formats()`; collects partial results with error continuation.
- [x] [Review][Patch] Environment/FileSystemLoader created per render call [`adapters/jinja_template_renderer.py:19-24`] — Moved `Environment` creation to `__init__`.
- [x] [Review][Patch] Broad `except Exception` in renderer [`adapters/jinja_template_renderer.py:33-34,50-51`] — Changed to catch `TemplateError` specifically.
- [x] [Review][Patch] Lazy import in factory [`factory.py:49`] — Moved `JinjaTemplateRenderer` import to top level.
- [x] [Review][Patch] `ResolutionPolicy` reconstructed on every `resolve()` call [`adapters/template_dir_resolver.py:75`] — Made `_RESOLUTION_POLICY` a module constant.
- [x] [Review][Patch] Missing empty string guard on `template_name` [`adapters/jinja_template_renderer.py:27`] — Added `if not template_name: raise ValueError`.
- [x] [Review][Patch] `_EnvDirStrategy` treats empty env var as unset [`adapters/template_dir_resolver.py:26`] — Changed to use `in os.environ` check.
- [x] [Review][Patch] `_XdgDirStrategy` `Path.home()` may raise RuntimeError [`adapters/template_dir_resolver.py:44`] — Added try/except with fallback to `/root/.config`.
- [x] [Review][Patch] Missing `output_path` type coercion [`adapters/jinja_template_renderer.py:55-59`] — Added `Path` coercion at function entry.
- [x] [Review][Patch] `mkdir` uses default umask [`adapters/jinja_template_renderer.py:53`] — Added explicit `mode=0o755`.
- [x] [Review][Patch] Missing `ColorScheme` type check [`adapters/jinja_template_renderer.py:36-45`] — Added `isinstance` guard.
- [x] [Review][Patch] `searched_paths` not asserted in test [`tests/unit/adapters/test_jinja_template_renderer.py:114-117`] — Added assertion.
- [x] [Review][Dismiss] Resolver strategies ignore `explicit_path` parameter — By design; parameter is part of the protocol interface, not used by current callers.
- [x] [Review][Dismiss] `process_show` duplicates result construction — Intentional; `process_show` genuinely differs from `process_generate` (no rendering).
- [x] [Review][Dismiss] `sequences.j2` post-processing replacement order is fragile — Not an issue: `\x1b]` does not contain `\`, so replacements are independent.
- [x] [Review][Dismiss] Test passes `object()` as `settings` — Pre-existing pattern across entire test file; keeping for consistency.
