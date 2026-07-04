## RECONCILED Requirements

### Requirement: Domain concretions with adapter re-export

Domain-located concretions SHALL be the default arrangement: `PipeReader` (ABC), `SubprocessPipeReader`, and `EventPipeReader` live in `domain/pipe_reader.py`. The adapter module re-exports these names for modules that need an adapter-level binding seam. This arrangement satisfies strict hexagonal layering (domain owns the abstractions AND their default implementations; adapter layer re-exports for DI binding).

#### Scenario: No domain module imports from adapters
- **WHEN** `domain/pipe_reader.py` is scanned for `from oci_runtime.adapters`
- **THEN** no imports from adapters are found