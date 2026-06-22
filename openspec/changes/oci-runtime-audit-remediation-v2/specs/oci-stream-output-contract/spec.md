## ADDED Requirements

### Requirement: stream_output routes output through OutputStream

When `RunConfig.stream_output=True` and TTY is not effective, `ContainerManager.run()` SHALL call `StreamingTransport.stream()` with `on_stdout` and `on_stderr` callbacks that write to the container manager's `OutputStream`. This is consistent with PTY mode, which also routes output to the `OutputStream`. The method SHALL return `""` (the output went to the stream, not the return value).

#### Scenario: stream_output=True writes to OutputStream
- **WHEN** `run()` is called with `stream_output=True`, `detach=False`, and `tty=False`, and an `OutputStream` is wired
- **THEN** the streaming transport's `on_stdout`/`on_stderr` callbacks write each chunk to the `OutputStream`, and `run()` returns `""`

#### Scenario: stream_output=False returns stdout string
- **WHEN** `run()` is called with `stream_output=False`, `detach=False`, and `tty=False`
- **THEN** `run()` returns the decoded stdout as a string (unchanged behavior)

#### Scenario: stream_output=True with no OutputStream does not crash
- **WHEN** `run()` is called with `stream_output=True` and the container manager's `_output_stream` is `None`
- **THEN** `run()` does not crash (callbacks check for `None` before writing), and returns `""`

#### Scenario: detach=True ignores stream_output
- **WHEN** `run()` is called with `detach=True` and `stream_output=True`
- **THEN** `run()` uses batch `execute()`, returns the container ID, and does not stream

#### Scenario: TTY mode ignores stream_output flag
- **WHEN** `run()` is called with `tty=True` and `stream_output=True`
- **THEN** `run()` uses `pty_transport.execute_pty()` with the `OutputStream` (TTY takes precedence), and returns `""`
