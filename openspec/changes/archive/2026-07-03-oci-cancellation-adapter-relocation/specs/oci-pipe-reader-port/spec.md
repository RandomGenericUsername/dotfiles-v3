## RECONCILED Requirements

### Requirement: Pipe reader classes in domain with adapter re-export

`PipeReader`, `SubprocessPipeReader`, and `EventPipeReader` SHALL live in `domain/pipe_reader.py`. The adapter module `adapters/managers/pipe_reader.py` SHALL re-export all three: `from oci_runtime.domain.pipe_reader import PipeReader, SubprocessPipeReader, EventPipeReader`. Existing importers of `oci_runtime.adapters.managers.pipe_reader.PipeReader` etc. SHALL continue to work without changes.

#### Scenario: PipeReader available from domain
- **WHEN** `from oci_runtime.domain.pipe_reader import PipeReader` is executed
- **THEN** it succeeds and `PipeReader` is the ABC

#### Scenario: PipeReader still available from adapter
- **WHEN** `from oci_runtime.adapters.managers.pipe_reader import PipeReader` is executed
- **THEN** it succeeds (re-export from adapter module)