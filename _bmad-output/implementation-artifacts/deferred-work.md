# Deferred Work

## Deferred from: code review of 1-4-multi-format-output-adapters (2026-07-06)

## Deferred from: code review of 1-5-operational-commands (2026-07-08)

- Catalog reloaded on every show command — Each show subcommand re-parses the effects file. Cache catalog in `ctx.obj`. Performance concern.
- `quiet`/`verbose` flags stored but unused — Flags are stored in `ctx.obj` but no command reads them. May be used by process commands. Pre-existing, out of scope.
- No integration test for show without `--effects` — All integration tests provide `--effects`. Behavior when no effects path is given is untested. Test gap.

- Dead-code fallback branches in info/dump_config/dump_effects — Fallback Rich rendering paths are unreachable from CLI but harmless. Pre-existing design pattern.
- `plain_output` catalog_list dead `None` checks — `item_type in (ItemType.EFFECT, None)` — `None` is never passed. Harmless dead code.
- NaN/Inf in float fields could break JSON — `json.dumps(allow_nan=True)` encodes `NaN`/`Infinity` which are not valid JSON. Extremely unlikely in practice.
- Spec contradiction AC2 vs "Key code details" — AC2 lists `duration` and `output_path` unconditionally; dev notes say omit if None. Spec-level issue, not code.

## Deferred from: code review of 2-1-oci-runtime-integration-image-management (2026-07-08)

- `chmod 0o777` on output directory — security trade-off for container non-root user interop. Pre-existing design choice.
- `container.engine` locked to docker/podman — design constraint per spec, no extensibility path.
- `None` serialization with tomli-w — needs verification during implementation; TOML has no null concept.
- Batch no progress in JSON mode — intentional UX design decision, no streaming during processing.
- `magick`/`convert` binary auto-detection — existing design pattern, acceptable for now.
- `python:3.14-alpine` base image version — future concern, update when implementing.
- Cross-ref validation only at catalog load time — acceptable design, not re-run at process time.
- OCI exception mapping may not cover future `oci-runtime` exceptions — acceptable for initial implementation.

## Deferred from: code review of 2-3-runtime-mode-selection-error-mapping (2026-07-08)

- `ContainerProcessor` composite chains run N containers instead of 1 — tied to architecture decision that needs user resolution
- `sys.stderr.write` corrupts JSON output — pre-existing, `OutputPort` should route warnings
- Brittle tests mock implementation details instead of ports — pre-existing pattern
- `AppSettings` recomposition fragile — pre-existing design pattern
- `Path`→`str` type degradation in CLI — pre-existing pattern throughout `cli/main.py`
- `CliDependencies` constructed with uninitialized fields — pre-existing pattern
- Case-sensitive CLI enum validation — acceptable UX, not a bug
