## Why

WEG (`wallpaper-effects-generator`) and CSG (`color-scheme-generator`) independently reimplement the same output abstraction: byte-identical `Verbosity` and `OutputFormat` enums, an `OutputPort` protocol, and three output adapters (`Json`, `Plain`, `Rich`) that each hard-code the CLI's domain types and duplicate error-detail formatting (`_serialize_error`/`_format_error_details` are copy-pasted across CSG's three adapters). Neither tool has a real central renderer — every adapter writes directly to `sys.stdout`/`sys.stderr`/`rich.Console`. Future modules will need the same three-way output (plain text, structured JSON for LLM consumption, rich rendering) and would otherwise duplicate it a third time. Now is the right time because both CLIs are hexagonal and already share two sibling packages (`config-assembler-engine`, `oci-runtime`) that establish the extraction pattern.

## What Changes

1. **Introduce a new shared package `cli-output`** under `src/shared/`, structured hexagonally (`domain/`, `ports/`, `adapters/`), referencing the same `[tool.uv.sources]` workspace convention as `config-assembler-engine` and `oci-runtime`.
2. **Define a domain-neutral renderable family** (`domain/views.py`): frozen dataclasses `MessageView`, `ResultView`, `ListView`, `ErrorView`, `ConfigInfoView`, `RawView`, `ProgressEvent`, and `CustomView`. The shared package owns no CLI domain types.
3. **Define a `Renderer` port** (`ports/renderer.py`): a `@runtime_checkable Protocol` with named verb methods (`message`, `result`, `list`, `error`, `config`, `raw`, `custom`) plus `status(msg)` and `progress(total, msg)` context managers for loader/stream UX.
4. **Provide three renderer adapters** (`adapters/output/{json,plain,rich}_renderer.py`) implementing the port, plus `create_renderer(fmt, console=None) -> Renderer` in `adapters/factory.py`. Errors render to `stderr`; `status`/`progress` are live in rich mode and no-ops in json/plain (progress only appears in `--output rich`, per the existing WEG architecture plan).
5. **Decouple errors**: `ErrorView.kind` is a free string the CLI fills; the shared package never imports CLI exception classes. This is the key pressure point that lets the renderer be shared.
6. **Provide an escape hatch** `CustomView` (carrying pre-built `plain`/`object`/`rich` forms) for backend-specific rendering — e.g. CSG's palette swatches — without re-coupling the shared package to any domain.
7. **This change is additive only.** WEG and CSG are NOT migrated in this change; each migration ships as its own follow-up change. No CLI command behavior changes, no flags change.

## Capabilities

### New Capabilities
- `cli-output`: The shared output-rendering capability — the domain-neutral renderable views, the `Renderer` port, the three renderer adapters (`json`/`plain`/`rich`), the `create_renderer` factory, and the `status`/`progress` context managers.

### Modified Capabilities
<!-- None. This change is additive; it does not alter existing spec requirements in `openspec/specs/`. -->

## Impact

- **New shared package:** `src/shared/cli-output/` (hatchling package `cli-output`, name `cli-output`, requires-python `>=3.12`, sole runtime dep `rich>=13`), mirroring the `src/shared/config-assembler-engine/` and `src/shared/oci-runtime/` layout.
- **Dependency wiring:** both `wallpaper-effects-generator/pyproject.toml` and `color-scheme-generator/pyproject.toml` gain a `[tool.uv.sources]` entry for `cli-output`; the package is added as a dependency. The CLIs need not *use* it yet.
- **No public CLI surface change:** `weg`/`csg` command names, flags, and output byte-for-byte behavior are unchanged by this change.
- **Tests:** a `tests/` suite for the shared package covering the views × 3 backends matrix, error-kind decoupling, progress no-op behavior, and the factory dispatch.
- **Tooling:** `uv sync` across the two CLI projects to lock the new dependency; CI test discovery must include the new package.
