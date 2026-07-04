import errno
import os
import threading
from unittest.mock import MagicMock, patch

from oci_runtime.adapters.transport.cancel import _CancelContext
from oci_runtime.adapters.transport.runner import _SubprocessRunner
from oci_runtime.adapters.transport.stream import _AsyncStreamReader


class _TrackingSelector:
    def __init__(self):
        self._fds: set[int] = set()

    def register(self, fd, events):
        self._fds.add(fd)

    def unregister(self, fd):
        self._fds.discard(fd)

    def get_map(self):
        return {fd: object() for fd in self._fds}

    def select(self, timeout=None):
        return [(MagicMock(fd=fd), 1) for fd in list(self._fds)]

    def close(self):
        pass


class TestSubprocessRunnerConcurrent:
    def test_subprocess_runner_concurrent_calls(self):
        with patch("subprocess.Popen") as MockPopen:
            mock_process = MagicMock()
            mock_process.stdout.fileno.return_value = 3
            mock_process.stderr.fileno.return_value = 4
            mock_process.pid = 9999
            mock_process.returncode = 0
            mock_process.poll.return_value = 0
            mock_process.communicate.return_value = (b"hello\n", b"")
            MockPopen.return_value = mock_process

            runner = _SubprocessRunner(["echo", "hello"])
            runner.start_stdin_writer()

            assert runner.process is mock_process
            assert runner.process.pid == 9999

            result = runner.wait()
            assert result.returncode == 0
            assert result.stdout == b"hello\n"


class TestCancelContext:
    def test_cancel_context_broadcast(self):
        event = threading.Event()

        ctx1 = _CancelContext()
        ctx2 = _CancelContext()

        def cancel_later():
            event.wait()
            ctx1.cancel()

        t = threading.Thread(target=cancel_later, daemon=True)
        t.start()

        assert not ctx1.is_cancelled
        assert not ctx2.is_cancelled

        event.set()
        t.join()

        assert ctx1.is_cancelled
        assert not ctx2.is_cancelled

        ctx2.cancel()
        assert ctx2.is_cancelled

    def test_cancel_context_wraps_token(self):
        mock_token = MagicMock()
        mock_token.is_cancelled = False

        ctx = _CancelContext(mock_token)
        assert not ctx.is_cancelled

        mock_token.is_cancelled = True
        assert ctx.is_cancelled

        ctx.cancel()
        assert ctx.is_cancelled

    def test_cancel_context_exit_cancels(self):
        ctx = _CancelContext()
        assert not ctx.is_cancelled
        with ctx as c:
            assert c is ctx
            assert not ctx.is_cancelled
        assert ctx.is_cancelled


class TestAsyncStreamReader:
    def test_async_stream_reader_timeout_yields_partial(self):
        mock_stdout_data = [b"chunk1\n", b"chunk2\n", b""]
        mock_stderr_data = [b""]

        def _os_read(fd, n):
            if fd == 3 and mock_stdout_data:
                return mock_stdout_data.pop(0)
            if fd == 4 and mock_stderr_data:
                return mock_stderr_data.pop(0)
            return b""

        selector = _TrackingSelector()
        selector.register(3, os.O_RDONLY)
        selector.register(4, os.O_RDONLY)

        with (
            patch("selectors.DefaultSelector", return_value=selector),
            patch("os.read", side_effect=_os_read),
        ):
            reader = _AsyncStreamReader(3, 4)
            cancel_ctx = _CancelContext()
            stdout_acc, stderr_acc = reader.read(cancel_ctx=cancel_ctx, timeout=0.01)

        assert b"".join(stdout_acc) == b"chunk1\nchunk2\n"

    def test_async_stream_reader_stream_closed(self):
        selector = _TrackingSelector()

        with (
            patch("selectors.DefaultSelector", return_value=selector),
            patch("os.read", return_value=b""),
        ):
            reader = _AsyncStreamReader(3, 4)
            cancel_ctx = _CancelContext()
            stdout_acc, stderr_acc = reader.read(cancel_ctx=cancel_ctx)

        assert stdout_acc == []
        assert stderr_acc == []

    def test_async_stream_reader_eio_handled(self):
        call_count = 0

        def _os_read(fd, n):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return b"data\n"
            raise OSError(errno.EIO, "EIO")

        selector = _TrackingSelector()
        selector.register(3, os.O_RDONLY)
        selector.register(4, os.O_RDONLY)

        with (
            patch("selectors.DefaultSelector", return_value=selector),
            patch("os.read", side_effect=_os_read),
        ):
            reader = _AsyncStreamReader(3, 4)
            stdout_acc, stderr_acc = reader.read(timeout=0.01)

        assert b"data\n" in b"".join(stdout_acc)

    def test_async_stream_reader_cancel_respects_stderr(self):
        called_stderr = []
        reads = 0

        def _os_read(fd, n):
            nonlocal reads
            reads += 1
            if fd == 4:
                return b"stderr data\n"
            return b"stdout data\n"

        selector = _TrackingSelector()
        selector.register(3, os.O_RDONLY)
        selector.register(4, os.O_RDONLY)

        with (
            patch("selectors.DefaultSelector", return_value=selector),
            patch("os.read", side_effect=_os_read),
        ):
            reader = _AsyncStreamReader(3, 4)
            cancel_ctx = _CancelContext()

            def _cancel_after_read():
                cancel_ctx.cancel()

            threading.Timer(0.05, _cancel_after_read).start()

            stdout_acc, stderr_acc = reader.read(
                on_stderr=lambda d: called_stderr.append(d),
                cancel_ctx=cancel_ctx,
                timeout=0.01,
            )

        assert b"stdout data\n" in b"".join(stdout_acc)
        assert b"stderr data\n" in b"".join(stderr_acc)
        assert b"stderr data\n" in b"".join(called_stderr)
