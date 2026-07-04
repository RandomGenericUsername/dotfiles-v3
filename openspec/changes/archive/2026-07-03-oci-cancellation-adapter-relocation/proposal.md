## Why

v3 relocated cancellation/primitives to `adapters/` under `_pipe_reader_port`. The port (abstract class) stayed in `domain/_pipe_reader_port.py` but the concretions (`PipeReader`, `_EventPipeReader`) were moved to `adapters/managers/pipe_reader.py`. The v3 relocation was motivated by "testability" — empirically false since tests already monkeypatch the binding in the adapter module. v5 considers the relocation arbitrary and reverses it: re-extract the concretions alongside their port in `domain/`.

A3 creates a clean `domain/pipe_reader.py` with `PipeReader` (ABC) + concretions (`SubprocessPipeReader`, `EventPipeReader`). The adapter layer re-exports `SubprocessPipeReader` and `EventPipeReader` from `adapters/managers/pipe_reader.py` for modules that need an adapter-level binding point.

## What Changes

- Move `PipeReader`, `SubprocessPipeReader`, `EventPipeReader` into `domain/pipe_reader.py`.
- `adapters/managers/pipe_reader.py` re-exports them (short imports).
- Existing adapter-level tests continue to work (they import from the adapter module).

## Capabilities

### Modified Capabilities

- `oci-pipe-reader-port`: pipe reader concretions SHALL live in `domain/` alongside their ABC; adapter module SHALL re-export for binding.
- `oci-strict-hexagonal-layering`: domain-located concretions SHALL be the default; adapter re-exports provide the binding seam.

## Impact

- **Code**: move ~120 LOC from `adapters/managers/pipe_reader.py` to `domain/pipe_reader.py`.
- **Tests**: no test changes needed (import path unchanged).
- **Risk**: low — purely additive module creation; existing imports from adapter are unchanged.