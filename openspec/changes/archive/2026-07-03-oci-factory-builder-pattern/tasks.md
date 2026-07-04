## 1. Add ResolvedRuntimeFactoryConfig

- [ ] 1.1 In `src/oci_runtime/domain/factory.py`, define `@dataclass(frozen=True) class ResolvedRuntimeFactoryConfig` with typed fields: `timeout: float`, `pty_mode: PtyMode`, `logs_follow: bool`, `runtime_kind: RuntimeKind`, etc.

## 2. Add OciRuntimeBuilder

- [ ] 2.1 In `src/oci_runtime/ports/runtime.py`, add `class OciRuntimeBuilder` with chainable `.with_*()` methods.
- [ ] 2.2 `build()` validates, resolves defaults, returns `(OciRuntime, ResolvedRuntimeFactoryConfig)`.

## 3. Update OciRuntime.__init__

- [ ] 3.1 Change `OciRuntime.__init__` to accept `ResolvedRuntimeFactoryConfig` (not `dict | None`).
- [ ] 3.2 Remove the `config: dict[str, Any] | None = None` overload.

## 4. Update tests

- [ ] 4.1 Update all `OciRuntime(config=...)` test calls to use builder.
- [ ] 4.2 Add `test_builder_resolved_config_types`, `test_builder_defaults`, `test_builder_chain`.
- [ ] 4.3 Run `uv run pytest -q` — green.
- [ ] 4.4 Run `uv run ruff check .` — green.