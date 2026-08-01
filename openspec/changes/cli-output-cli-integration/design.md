## Context

The shared `cli-output` package (archived change `cli-output-shared`, commit `17c4ce0`) ships the domain-neutral `Renderer` port, eight frozen-dataclass views, three renderer adapters (`JsonRenderer`/`PlainRenderer`/`RichRenderer`), and `create_renderer(fmt, console=None)`. Both CLIs already depend on it via `[tool.uv.sources]`, but neither imports it in source — each still renders directly.

Current state per CLI:
- WEG `OutputPort` (`ports/output.py:14-34`): `process_result`, `batch_result`, `catalog_list`, `config_info`, `dump_config_template`, `dump_effects_template`, `error`, `message`. Three adapters write directly to stdout/stderr/Console; `factory.create_output_adapter` (`factory.py:133-143`) dispatches by format, ignores verbosity.
- CSG `OutputPort` (`ports/output.py:12-35`): `process_result`, `error`, `palette_display`, `message`, `config_info`, `install_result`, `uninstall_result`, `version_info`, `backends_catalog`. CSG's adapters carry duplicated `_format_error_details`/`_serialize_error` introspection tables (`json_output.py:126-152`, `plain_output.py:119-146`, `rich_output.py:212-239`); the CLI mutates `deps.output_adapter._verbosity` after config resolution (`cli/main.py:186-188`).
- **`dump-*` override is load-bearing:** WEG `dump_config_template`/`dump_effects_template` write raw content verbatim in all three adapters (`json_output.py:89-93`, etc.); CSG `dump-config` bypasses the adapter entirely (`print(content, end="")`). Routing these through `JsonRenderer.raw` (which wraps content in `{"content": ...}`) would break them — the override must be preserved.

Port convention (`@runtime_checkable Protocol`, structural, no explicit subclassing) and shared-package conventions are established in the `cli-output-shared` change and are not re-litigated here.

## Goals / Non-Goals

**Goals:**
- Both CLIs route all output through the shared `cli-output` renderer (`create_renderer` + `Renderer` methods).
- Each CLI's `OutputPort` adapters become thin projectors: domain types → views → delegate to the shared renderer.
- CSG's duplicated error-detail introspection collapses to one projector function.
- Errors render to stderr in all three backends (canonical cli-output behavior).
- `dump-*` commands keep printing raw content regardless of `--output-format`.
- CSG's curated `process_result` plain/rich output preserved via `CustomView`.
- No new commands, flags, or command-surface changes.

**Non-Goals:**
- Changing the `cli-output` port/views/factory contract (already archived and validated).
- Verbosity/logging integration (a later, separate concern per the original design).
- Progress/`status`/`stream_output` wiring (not currently used by any command; deferred).
- Introducing `OutputPort[T]` generics or a shared per-CLI port protocol (breaks repo convention; per-CLI `OutputPort` stays CLI-specific by design).
- Restructuring the CLI `_get_output_adapter` seams in `weg process`/`batch`/`show` — the existing per-sub-app rebuild behavior is preserved.

## Decisions

### D1: Per-CLI `OutputAdapterBase` + `projectors.py`; three adapters become format-tagged subclasses

**Choice:** Each CLI gets `adapters/output/base.py` defining `OutputAdapterBase`, holding a `Renderer` (injected or defaulted via `_default_format` + `cli_output.create_renderer`). Each of the three adapter files becomes a thin subclass setting `_default_format = OutputFormat.JSON/PLAIN/RICH`. `adapters/output/projectors.py` holds pure projection functions (`ProcessingResult`→`ResultView`, `GenerationResult`→`CustomView`, `ColorSchemeError`→`ErrorView`, etc.).

**Rationale:** The three adapters in each tool differ only by renderer, so one base + three tagged subclasses eliminates the triple duplication while keeping the existing class names (tests reference `JsonOutputAdapter`/`JsonOutput` and `isinstance` checks). Projectors are pure functions — unit-testable without renderer/IO. This mirrors how `config_assembler_engine` centralizes projection at the call site.

**Alternative considered:** *Keep per-adapter rendering and only swap the write sink.* Rejected: leaves the three-way rendering logic duplicated in each CLI, which is the exact duplication `cli-output` exists to remove.

### D2: `factory.create_output_adapter` builds the shared renderer and injects it

**Choice:** `create_output_adapter(output_format, console=None)` (WEG) and `create_output_adapter(fmt, verbosity=...)` (CSG) build `renderer = create_renderer(SharedOutputFormat(fmt.value), console=console)` and pass it to the adapter constructor. WEG's Rich adapter still accepts `console`; CSG's adapters keep `verbosity` and preserve the `_verbosity` attribute so `cli/main.py:186-188` keeps working.

**Rationale:** The factory stays the composition root (repo convention), and the shared renderer is constructed exactly once per command invocation. CSG's verbosity is a per-CLI concern that stays in the CLI adapter (the shared renderer is verbosity-agnostic by design) — QUIET gating lives in `OutputAdapterBase.process_result`.

### D3: Canonical output shapes — accept the change (per prior decision)

**Choice:** Rendering flows through the shared renderers' canonical forms. Concretely:
- WEG JSON `process_result` emits `{"success": true, ...}` (was `{"status": "success", ...}`); plain emits `success: true`.
- Errors emit `{kind, message, details}` (WEG: `kind = type(exc).__name__`, `message = str(exc)`, no details; CSG: `_error_details(exc)` fills `details`) — to **stderr** in all three backends. CSG's old `{"success": false, "error": {...}}` envelope and WEG's old `{"error": {...}}` envelope are dropped.
- Rich/plain errors move from stdout to stderr (matching the shared `Renderer.error` contract).

**Rationale:** This is the "canonicalize to cli-output" policy agreed during planning — the shared renderer is the point of standardization; the shape changes are cosmetic (same information, canonical keys) and update a bounded set of output tests.

### D4: CSG `process_result` uses `CustomView`, not `ResultView`

**Choice:** `project_result(GenerationResult)` returns a `CustomView` carrying `object` (the structured payload), `plain` (curated "Success/Backend/Duration/Output files" lines), and `rich` (a callable drawing the styled table + output files). `JsonRenderer.custom` emits `view.object` (same JSON as before); `PlainRenderer.custom` emits `view.plain`; `RichRenderer.custom` invokes the callable.

**Rationale:** The color-scheme payload is a nested domain structure; a generic `ResultView` would render `color_scheme: {dict-repr}` into plain text — a UX regression. `CustomView` is the designed escape hatch (per `cli-output-shared` D3) for exactly this: CLI-specific rich rendering without re-coupling the shared package. JSON output shape is unchanged from the pre-wiring behavior.

### D5: `dump-*` format override preserved by bypassing the renderer's format

**Choice:** WEG `OutputAdapterBase.dump_config_template`/`dump_effects_template` write `content` verbatim to `sys.stdout` directly (not via `renderer.raw`/`custom`). CSG `dump-config` already bypasses the adapter entirely (`print(content, end="")` in `cli/dump_config_cmd.py`) — unchanged.

**Rationale:** `JsonRenderer.raw` wraps content in `{"content": ...}`, which would corrupt `dump-config --output-format json`. The user explicitly flagged this requirement ("dump-config and dump-x commands need to override the output despite the --format flag"). Verified end-to-end: both tools print raw TOML under `--output-format json`.

### D6: `JsonRenderer._CustomEncoder` falls back to `str(o)` for unknown objects

**Choice:** In `cli-output/src/cli_output/adapters/output/json_renderer.py`, `_CustomEncoder.default` returns `str(o)` for objects that are neither `Path` nor `Enum` (previously it raised `TypeError` via `super().default`).

**Rationale:** CSG's old `JsonOutput` used `json.dump(..., default=str)`, stringifying any non-primitive (including test `MagicMock` results). The strict encoder broke CSG's existing test fixtures and the first-run/container-argv CLI tests. `str(o)` is a lenient, safe fallback that preserves the historical behavior while keeping Path→str and Enum→value special-casing. No cli-output test asserts the strict raise, so the shared suite stays green.

### D7: Per-sub-app `_get_output_adapter` seams left as-is

**Choice:** WEG's `cli/process.py:142-144`, `cli/batch.py:51-55`, and `cli/show.py:27-33` still build their own adapters via `create_output_adapter` (as they did before) — they now transparently get renderer-backed adapters.

**Rationale:** Preserving the existing command wiring avoids unrelated behavior changes; the factory change is sufficient to route everything through the shared renderer.

## Risks / Trade-offs

- **[Output shape changes are user-visible]** WEG JSON `status`→`success`; error envelope `{kind, message, details}`; rich/plain errors move to stderr. **Mitigation:** Accepted per the canonicalize policy; errors still carry the same information; updated tests lock the new shapes.
- **[`str(o)` fallback may hide serialization bugs]** Unknown objects silently stringify instead of raising. **Mitigation:** This matches the historical `default=str` behavior and is needed for test mocks; real domain results are projected into primitive-only views before rendering, so the fallback is rarely exercised in production paths.
- **[CSG `process_result` CustomView keeps CLI-side rendering]** The curated plain/rich output for generated schemes remains CSG-specific rather than fully generic. **Mitigation:** Deliberate — `CustomView` is the designed escape hatch; the JSON contract is unchanged and the shared renderer still owns the write path.
- **[Per-CLI `projectors.py` still holds domain knowledge]** Each CLI's projector knows its domain types. **Mitigation:** Correct by design (pattern B / projection at the call site) — domain-neutral views in the shared package, domain translation in the CLI.

## Migration Plan

Already shipped in the working tree; this change records it:

1. WEG: add `adapters/output/{base,projectors}.py`, rewrite three adapters, update `factory.create_output_adapter`.
2. CSG: add `adapters/output/{base,projectors}.py`, rewrite three adapters, update `factory.create_output_adapter`.
3. Shared: `json_renderer._CustomEncoder` `str(o)` fallback.
4. Update output-adapter + CLI tests to canonical shapes.
5. Verify: `cli-output` 62 passed, WEG 322 passed, CSG 550 passed; `ruff` clean on new/changed files; `dump-config --output-format json` prints raw TOML in both tools.

**Rollback:** reverting the per-CLI `adapters/output/*` and `factory.py` changes restores the direct-rendering adapters; `cli-output` dependency remains but unused. No migration of user data or config involved.
