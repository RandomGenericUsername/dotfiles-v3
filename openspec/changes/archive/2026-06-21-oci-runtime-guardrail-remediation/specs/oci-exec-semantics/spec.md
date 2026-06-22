## MODIFIED Requirements

### Requirement: ExecResult.stderr preserves real stderr on success

`exec_container` must decode and return `result.stderr` as `ExecResult.stderr` for all exit codes, including `returncode == 0`. The current implementation forces `stderr_str = ""` when the exit code is zero, discarding real stderr content that a successful inner command may have written to its stderr.

#### Scenario: Exec success with stderr output
- **WHEN** `docker exec ctr1 sh -c 'echo err >&2'` returns exit code 0, stdout `"out\n"`, stderr `"err\n"`
- **THEN** `ExecResult.stderr` is `"err\n"`, not `""`

#### Scenario: Exec success with empty stderr
- **WHEN** `docker exec ctr1 ls` returns exit code 0, stdout `"file1\n"`, stderr `""`
- **THEN** `ExecResult.stderr` is `""` (unchanged)

#### Scenario: Exec non-zero returns ExecResult (unchanged from prior spec)
- **WHEN** `docker exec ctr1 false` returns exit code 1
- **THEN** `exec_container` returns `ExecResult(returncode=1)` without raising (unless not-found)
