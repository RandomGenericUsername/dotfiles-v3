## Context

WEG and CSG are hexagonal Python CLIs sharing two sibling packages (`config-assembler-engine`, `oci-runtime`) under `src/shared/`. Both reimplement the same output layer independently:

- **Duplicated enums:** `Verbosity` (byte-identical: WEG `domain/enums.py:22-26`, CSG `domain/enums.py:61-64`) and `OutputFormat` (`json`/`rich`/`plain`; WEG `:45-51`, CSG `:52-58`).
- **Diverged `OutputPort` protocols:** WEG `ports/output.py:14-34` and CSG `ports/output.py:12-35` share only four method *names* (`process_result`, `error`, `message`, `config_info`) and diverge in every signature. Both take **CLI-specific domain types** (`ProcessingResult` vs `GenerationResult`, `EffectsCatalog` vs `TemplateCatalog`).
- **Adapters hard-coded to domain:** the three adapters per tool (`Json`/`Plain`/`Rich`) write directly to `sys.stdout`/`sys.stderr`/`rich.Console`. CSG's adapters carry copy-pasted `_serialize_error`/`_format_error_details` that `isinstance`-switch on 8+ exception subclasses (`json_output.py:126-152`, `plain_output.py:119-146`, `rich_output.py:212-239`).
- **Asymmetric factories:** WEG `create_output_adapter(fmt, console=None)` (`factory.py:133-143`) ignores verbosity; CSG `create_output_adapter(fmt, verbosity=...)` (`factory.py:71-83`) forwards it.
- **Progress rule already settled:** the WEG architecture plan (`docs/ARCHITECTURE_PLAN.md:542`) states progress bars appear only in `--output rich`.

The CLI-tool port convention is `@runtime_checkable Protocol` + `XxxPort` suffix + structural (duck-typed, no explicit subclassing). Shared-package conventions (per `config-assembler-engine`, `oci_runtime`): `domain/`+`ports/`+`adapters/`, re-export from `__init__.py`, frozen-dataclass domain types, a `create_*` composition factory. `oci_runtime` uses `abc.ABC` ports; `config-assembler-engine` uses plain `Protocol`; the CLI tools use `@runtime_checkable Protocol`. A shared package consumed by both CLIs should use `@runtime_checkable Protocol` to satisfy consumers' structural-typing fields.

## Goals / Non-Goals

**Goals:**
- A reusable `cli-output` shared package that renders domain-neutral values in three formats: plain text, structured JSON, rich.
- The shared package owns **no** CLI domain types — WEG/CSG project their domain results into shared views at the call site.
- Errors render through a decoupled `ErrorView` whose `kind` is a free string; the shared package never imports CLI exception classes.
- Loader/stream UX via `status(msg)` and `progress(total, msg)` context managers that are live in rich mode and no-ops in json/plain.
- Hexagonal structure (`domain/`, `ports/`, `adapters/`) matching the shared-package precedent.
- **Additive only:** this change lands the package + tests + dependency wiring. Neither CLI is migrated here.

**Non-Goals:**
- Migrating WEG or CSG to the shared package (each is a separate follow-up change).
- Verbosity/logging integration — the shared renderer does not gate on verbosity; `--quiet`/`-v` wiring stays a per-CLI concern that consumes the renderer later.
- Introducing Pydantic (config schema validation only, per repo convention).
- Introducing generics on ports (`OutputPort[T]`) — breaks the repo convention.
- An `application/` layer — `cli-output` has no use-case orchestration; the factory is the composition root (same as `oci_runtime`).

## Decisions

### D1: Projection at the call site (pattern B) — CLI domain types never cross into the shared package

**Choice:** The shared package exposes a small closed family of domain-neutral frozen-dataclass views (`MessageView`, `ResultView`, `ListView`, `ErrorView`, `ConfigInfoView`, `RawView`, `ProgressEvent`, `CustomView`). Each CLI keeps its own per-domain `OutputPort` protocol (signatures unchanged, taking `ProcessingResult`/`GenerationResult`/etc.), but its adapter bodies become thin projectors that translate the CLI domain object into a view and delegate to a shared `Renderer`.

**Rationale:** Matches the established `config-assembler-engine` pattern, where the shared use case takes domain-neutral types (`ResolutionPolicy`, `OverrideRule`) and each CLI adapter projects its config into them. Domain types stay pure (no `to_plain`/`to_json`/`to_rich` methods on frozen dataclasses), and per-CLI outputs that will never unify (`batch_result`, `backends_catalog`) stay CLI-specific by design.

**Alternative considered:** *Pattern C — render-trait on domain types*: a `Renderable` protocol with `to_plain()/to_object()/to_rich()` that each domain type implements. Rejected: it pushes rendering concerns into the domain layer and re-couples every domain type to three backends — exactly the duplication we're extracting. *Pattern A — generic port* `OutputPort[T]`: rejected, breaks the repo's no-generics-on-ports convention and still forces every adapter to hard-code CLI types.

### D2: `ErrorView.kind` is a free string — decoupled error rendering

**Choice:** `ErrorView(kind: str, message: str, details: dict[str, str])`. The renderer treats `kind` as opaque — it renders it verbatim into the JSON envelope / plain line / rich Panel. The CLI-side mapping of its own exception hierarchy to `kind`+`details` lives in one CLI-specific projector (e.g. CSG `error_projector.py`).

**Rationale:** CSG's adapters currently duplicate an `isinstance`-introspection table across three files. Moving that into one CLI-side projector (which happens in the CSG migration change, not this one) deduplicates it and keeps the shared package free of any CLI exception import. The renderer can style by presence of fields without needing to know error kinds.

**Alternative considered:** *Shared error-kind enum* the formatter knows. Rejected: re-couples the shared package to every consumer's error taxonomy, which is exactly the coupling D1 removes.

### D3: `CustomView` as the named escape hatch

**Choice:** `CustomView(plain: str, object: Any, rich: str | Callable[[Console], None])`. The CLI pre-builds each backend form (e.g. CSG computes palette swatch markup in CSG) and hands it over; the renderer just emits each field. `rich` may be a markup string or a callable that draws onto the passed `Console`.

**Rationale:** Keeps the renderable surface closed while letting CLIs express backend-specific rendering (palette swatches, arbitrary rich layouts) without teaching the shared package about any domain. This is the bounded "escape hatch" — it carries *already-rendered* forms, not a render-trait the domain must implement.

### D4: `Renderer` port with named verb methods, not a single `render(view)` dispatch

**Choice:** `@runtime_checkable Protocol` with `message(view: MessageView)`, `result(view: ResultView)`, `list(view: ListView)`, `error(view: ErrorView)`, `config(view: ConfigInfoView)`, `raw(view: RawView)`, `custom(view: CustomView)`, plus `status(msg)` and `progress(total, msg)` context managers.

**Rationale:** Matches the `XxxPort` named-verb convention used by every port in both CLIs. A single `render(view)` dispatcher would hide the per-view-type contract and be less discoverable. `error` renders to `stderr` in all three backends (matching current JSON adapter behavior).

### D5: `status`/`progress` are context managers; no-op in json/plain, live in rich

**Choice:** `status(message: str)` returns `AbstractContextManager[None]`; `progress(total: int, message: str)` returns a context manager exposing `advance()`. `RichRenderer` returns `rich.console.status` / `rich.progress.Progress`; `JsonRenderer` and `PlainRenderer` return a no-op context manager.

**Rationale:** Encodes the already-settled rule (progress only in `--output rich`, `ARCHITECTURE_PLAN.md:542`) at the contract level, so consumers cannot accidentally stream to a structured output. Final results still flow through the normal verb methods honoring the user's chosen format — loaders never fight the structured contract.

### D6: Hexagonal layout with no `application/` layer

**Choice:** `src/shared/cli-output/src/cli_output/` with `domain/{enums,views}.py`, `ports/renderer.py`, `adapters/output/{json,plain,rich}_renderer.py`, `adapters/factory.py`, re-export from `__init__.py`. No `application/` directory; `adapters/factory.py` exposes `create_renderer(fmt, console=None) -> Renderer`.

**Rationale:** Matches the shared-package precedent. `config-assembler-engine` has an `application/` layer because it orchestrates a multi-port pipeline; `cli-output` has a single port and three backends — a use-case layer would be empty ceremony. `oci_runtime` likewise has no `application/` dir (its factory is the composition root).

**Alternative considered:** *Full `application/` layer with a `RenderUseCase`*. Rejected: no orchestration to encapsulate; YAGNI.

### D7: Adapter naming follows CSG (`JsonRenderer`/`PlainRenderer`/`RichRenderer`), port follows CLI-tools (`Renderer` + `@runtime_checkable`)

**Choice:** Renderer adapters named `JsonRenderer`, `PlainRenderer`, `RichRenderer` (CSG's no-`Adapter`-suffix spelling, the majority convention in `adapters/output/`). The port is `Renderer` (the CLI-tools' `XxxPort` naming, though the suffix is dropped for a noun that reads naturally as the port name — matching how both tools already name their `OutputPort`).

**Rationale:** Consistent with the exploration's synthesis (section 8a of the WEG/CSG hex report): `@runtime_checkable Protocol` for the port so consumers' `CliDependencies.output_adapter: OutputPort | None` structural-typing fields keep working; CSG-style adapter names.

## Risks / Trade-offs

- **[Closed renderable family may not cover a future shape]** A future module's output might not map to any of the 8 views. **Mitigation:** `CustomView` is the designed escape hatch — any shape can be pre-rendered by the consumer. The family can grow additive-only (new frozen dataclass + new renderer method) without breaking existing views.
- **[Projection is per-CLI work]** Each CLI migration writes its own projectors; the shared package alone doesn't remove WEG/CSG duplication until both migrations land. **Mitigation:** This is why migrations ship as separate follow-up changes — the shared contract is proven independently (Phase 1) before either CLI is touched.
- **[`status`/`progress` no-op semantics may surprise consumers]** A consumer wrapping work in `progress()` in json mode gets silence. **Mitigation:** The spec makes this explicit (progress SHALL be a no-op outside rich), and it matches the settled WEG plan rule.
- **[Double-maintenance window]** Until WEG and CSG migrate, both tools keep their old adapters alongside the new shared package — three renderer implementations plus the shared ones coexist. **Mitigation:** The shared package is additive; no behavior changes. Old adapters are deleted only in their respective migration changes.
- **[`@runtime_checkable` structural typing edge cases]** `CustomView.rich` accepts a `Callable[[Console], None]`, which a runtime-checkable protocol cannot fully verify. **Mitigation:** The `Renderer` protocol is duck-typed (structural) as in both CLIs; the renderer adapters are tested directly (unit tests), not just via `isinstance`.

## Migration Plan

This change is **additive only** and ships no behavior change:

1. Scaffold `src/shared/cli-output/` (hatchling package, `rich>=13` dep).
2. Implement `domain/enums.py` + `domain/views.py`.
3. Implement `ports/renderer.py`.
4. Implement `adapters/output/{json,plain,rich}_renderer.py` + `adapters/factory.py`.
5. Add `tests/` (views × 3 backends matrix, error-kind decoupling, progress no-op, factory dispatch).
6. Wire `cli-output` into both CLI `pyproject.toml` `[tool.uv.sources]` + dependencies; `uv sync`.
7. Run full test suites for the shared package and both CLIs (regression check — nothing consumed the new package yet).

**Rollback:** deleting `src/shared/cli-output/` and the `[tool.uv.sources]` entries fully reverts; no CLI behavior depends on it.

## Open Questions

- None blocking. Naming of the capability (`cli-output`) and package (`cli-output`) are settled; the views' field sets may be refined during implementation, but the contract shape (8 views, `Renderer` port, 3 adapters, factory) is fixed by this design.
