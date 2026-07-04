## ADDED Requirements

### Requirement: Extracted transport modules

`_SubprocessRunner` SHALL live in `adapters/transport/runner.py`. `_CancelContext` SHALL live in `adapters/transport/cancel.py`. `_AsyncStreamReader` SHALL live in `adapters/transport/stream.py`. `adapters/transport/__init__.py` SHALL re-export all three. The Lima adapter SHALL import from `oci_runtime.adapters.transport` instead of defining these classes inline.

#### Scenario: Transport classes importable from adapters.transport
- **WHEN** `from oci_runtime.adapters.transport import _SubprocessRunner, _CancelContext, _AsyncStreamReader`
- **THEN** all three are imported successfully