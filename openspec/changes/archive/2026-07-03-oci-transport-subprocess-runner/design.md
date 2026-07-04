## Context

_SubprocessRunner et al. are entangled in Lima adapter module. Need extraction + thread-safety fixes.

## Goals / Non-Goals

**Goals:** Extract to `adapters/transport/` modules. Fix CancelContext broadcast, AsyncStreamReader timeout.
**Non-Goals:** Domain relocation (these are OS-process primitives).

## Decisions

Four modules: `__init__.py` (re-exports), `runner.py` (_SubprocessRunner), `cancel.py` (_CancelContext with threading.Event), `stream.py` (_AsyncStreamReader with timeout). Lima adapter imports from `oci_runtime.adapters.transport`.

## Risks / Trade-offs

- Extraction changes import paths; verify lima adapter still works.