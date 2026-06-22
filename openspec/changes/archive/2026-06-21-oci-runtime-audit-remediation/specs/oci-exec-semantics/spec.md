## ADDED Requirements

### Requirement: exec returns exit code on non-zero
`ContainerManager.exec_container()` SHALL return an `ExecResult` carrying the inner command's `returncode`, `stdout`, and `stderr` for any exit code, including non-zero. It MUST NOT raise `ContainerRuntimeError` merely because the inner command exited non-zero.

#### Scenario: Non-zero exec returns ExecResult
- **WHEN** `exec_container("c1", ["false"])` is called and the transport returns `RawExecResult(returncode=1, stdout=b"", stderr=b"")`
- **THEN** the method returns `ExecResult(returncode=1, stdout="", stderr="")` without raising

#### Scenario: Successful exec returns ExecResult
- **WHEN** `exec_container("c1", ["echo", "ok"])` is called and the transport returns `RawExecResult(returncode=0, stdout=b"ok\n", stderr=b"")`
- **THEN** the method returns `ExecResult(returncode=0, stdout="ok\n", stderr="")`

### Requirement: exec raises only on missing container
`ContainerManager.exec_container()` SHALL raise `ContainerNotFoundError` when the runtime reports the container does not exist (stderr matches the parser's `is_not_found_error`). It MUST NOT raise any other exception for a non-zero exit that is not a not-found condition.

#### Scenario: Missing container raises ContainerNotFoundError
- **WHEN** `exec_container("c1", ["ls"])` is called and the transport returns `RawExecResult(returncode=1, stdout=b"", stderr=b"No such container: c1")`
- **THEN** the method raises `ContainerNotFoundError` whose `container_id` attribute equals `"c1"`

#### Scenario: Generic exec error returns ExecResult
- **WHEN** `exec_container("c1", ["sh", "-c", "exit 42"])` is called and the transport returns `RawExecResult(returncode=42, stdout=b"", stderr=b"some error")` where stderr is not a not-found pattern
- **THEN** the method returns `ExecResult(returncode=42, stdout="", stderr="some error")` without raising
