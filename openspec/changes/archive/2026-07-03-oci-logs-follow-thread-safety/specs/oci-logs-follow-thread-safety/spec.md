## ADDED Requirements

### Requirement: Logs follow uses transport primitives

`container_manager.logs(container_id, follow=True)` SHALL use `_AsyncStreamReader` for reading stdout/stderr and `_CancelContext` for coordinated teardown. The `timeout` parameter SHALL control how long the reader waits before yielding partial data. The background thread SHALL be joined on `__exit__` or context cancellation.

#### Scenario: Logs follow returns partial data on timeout
- **WHEN** `container_manager.logs("ctr", follow=True, timeout=0.5)` is called on a slow stream
- **THEN** partial log output is yielded after 500ms

#### Scenario: Logs follow cancels cleanly
- **WHEN** the context is cancelled during logs --follow
- **THEN** the background thread stops within 1 second and resources are released