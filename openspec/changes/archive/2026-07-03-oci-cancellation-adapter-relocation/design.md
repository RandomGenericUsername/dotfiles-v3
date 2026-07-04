## Context

v3 moved concretions to adapters/; v5 reverses it. ABC and concretions together in domain/; adapter re-exports for binding.

## Goals / Non-Goals

**Goals:** PipeReader, SubprocessPipeReader, EventPipeReader in domain/pipe_reader.py. Adapter module re-exports unchanged names.
**Non-Goals:** Changing class behavior.

## Decisions

Create `domain/pipe_reader.py` with all three classes. `adapters/managers/pipe_reader.py` becomes `from oci_runtime.domain.pipe_reader import PipeReader, SubprocessPipeReader, EventPipeReader`. No import changes needed in consuming code.

## Risks / Trade-offs

- None. Pure relocation.