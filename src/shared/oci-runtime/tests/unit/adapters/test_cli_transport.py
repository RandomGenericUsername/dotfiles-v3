from unittest.mock import patch, MagicMock

import pytest

from oci_runtime.adapters.transport.cli import CliTransport
from oci_runtime.domain.exceptions import RuntimeNotAvailableError


class TestCliTransport:
    def test_stores_binary(self):
        t = CliTransport("docker", binary_resolver=MagicMock())
        assert t.binary == "docker"

    def test_execute_returns_bytes(self):
        t = CliTransport("docker", binary_resolver=MagicMock())
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch(
                "oci_runtime.adapters.transport.cli._SubprocessRunner"
            ) as MockRunner:
                mock_process = MagicMock()
                mock_process.stdout.fileno.return_value = 3
                mock_process.stderr.fileno.return_value = 4
                mock_process.wait.return_value = 0
                mock_process.poll.return_value = 0
                mock_runner = MockRunner.return_value
                mock_runner.process = mock_process
                with patch(
                    "oci_runtime.adapters.transport.cli._AsyncStreamReader"
                ) as MockReader:
                    mock_reader_instance = MockReader.return_value
                    mock_reader_instance.read.return_value = (
                        [b"binary\x00data"],
                        [b""],
                    )
                    result = t.execute(["docker", "build", "-"])
        assert isinstance(result.stdout, bytes)
        assert isinstance(result.stderr, bytes)
        assert result.stdout == b"binary\x00data"

    def test_execute_passes_input_data(self):
        t = CliTransport("docker", binary_resolver=MagicMock())
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch(
                "oci_runtime.adapters.transport.cli._SubprocessRunner"
            ) as MockRunner:
                mock_process = MagicMock()
                mock_process.stdout.fileno.return_value = 3
                mock_process.stderr.fileno.return_value = 4
                mock_process.wait.return_value = 0
                mock_process.poll.return_value = 0
                mock_runner = MockRunner.return_value
                mock_runner.process = mock_process
                with patch(
                    "oci_runtime.adapters.transport.cli._AsyncStreamReader"
                ) as MockReader:
                    mock_reader_instance = MockReader.return_value
                    mock_reader_instance.read.return_value = ([b""], [b""])
                    t.execute(["docker", "build", "-"], input_data=b"tar content")
        MockRunner.assert_called_once_with(["docker", "build", "-"], b"tar content")

    def test_execute_handles_binary_input_and_output(self):
        t = CliTransport("docker", binary_resolver=MagicMock())
        binary_input = b"\x00\x01\x02\x03binary data"
        binary_output = b"output\x00with\x00nulls"
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch(
                "oci_runtime.adapters.transport.cli._SubprocessRunner"
            ) as MockRunner:
                mock_process = MagicMock()
                mock_process.stdout.fileno.return_value = 3
                mock_process.stderr.fileno.return_value = 4
                mock_process.wait.return_value = 0
                mock_process.poll.return_value = 0
                mock_runner = MockRunner.return_value
                mock_runner.process = mock_process
                with patch(
                    "oci_runtime.adapters.transport.cli._AsyncStreamReader"
                ) as MockReader:
                    mock_reader_instance = MockReader.return_value
                    mock_reader_instance.read.return_value = (
                        [binary_output],
                        [b""],
                    )
                    result = t.execute(
                        ["docker", "build", "-"], input_data=binary_input
                    )
        assert result.stdout == binary_output
        assert result.returncode == 0

    def test_execute_raises_runtime_not_available_when_binary_missing(self):
        from oci_runtime.adapters.binary import CliBinaryResolver

        t = CliTransport("nonexistent-runtime", binary_resolver=CliBinaryResolver())
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeNotAvailableError, match="nonexistent-runtime"):
                t.execute(["nonexistent-runtime", "--version"])

    def test_probe_returns_true_when_binary_available(self):
        from oci_runtime.adapters.binary import CliBinaryResolver

        t = CliTransport("docker", binary_resolver=CliBinaryResolver())
        with patch("shutil.which", return_value="/usr/bin/docker"):
            assert t.probe() is True

    def test_probe_returns_false_when_binary_not_found(self):
        from oci_runtime.adapters.binary import CliBinaryResolver

        t = CliTransport("nonexistent", binary_resolver=CliBinaryResolver())
        with patch("shutil.which", return_value=None):
            assert t.probe() is False

    def test_transport_caches_which(self):
        from oci_runtime.adapters.binary import CliBinaryResolver

        with patch(
            "shutil.which",
            side_effect=["/usr/bin/docker", "/usr/bin/docker", "/usr/bin/docker"],
        ) as mock_which:
            with patch(
                "oci_runtime.adapters.transport.cli._SubprocessRunner"
            ) as MockRunner:
                mock_process = MagicMock()
                mock_process.stdout.fileno.return_value = 3
                mock_process.stderr.fileno.return_value = 4
                mock_process.wait.return_value = 0
                mock_process.poll.return_value = 0
                mock_runner = MockRunner.return_value
                mock_runner.process = mock_process
                with patch(
                    "oci_runtime.adapters.transport.cli._AsyncStreamReader"
                ) as MockReader:
                    mock_reader_instance = MockReader.return_value
                    mock_reader_instance.read.return_value = ([], [])
                    from oci_runtime.adapters.transport.cli import CliTransport

                    t = CliTransport("docker", binary_resolver=CliBinaryResolver())
                    t.get_runtime_binary()
                    t.execute(["docker", "ps"])
                    t.execute(["docker", "ps"])
                    assert mock_which.call_count == 1

    def test_execute_timeout_raises_operation_timeout(self):
        from oci_runtime.domain.exceptions import OperationTimeoutError

        t = CliTransport("docker", binary_resolver=MagicMock())
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch(
                "oci_runtime.adapters.transport.cli._SubprocessRunner"
            ) as MockRunner:
                mock_process = MagicMock()
                mock_process.stdout.fileno.return_value = 3
                mock_process.stderr.fileno.return_value = 4
                mock_process.poll.return_value = None
                mock_process.pid = 123
                mock_runner = MockRunner.return_value
                mock_runner.process = mock_process
                with patch(
                    "oci_runtime.adapters.transport.cli._AsyncStreamReader"
                ) as MockReader:
                    mock_reader_instance = MockReader.return_value
                    mock_reader_instance.read.return_value = ([b""], [b""])
                    with patch(
                        "oci_runtime.adapters.transport.cli.DeadlineCancellationToken"
                    ) as mock_dc:
                        mock_dc.return_value.is_cancelled = True
                        with pytest.raises(OperationTimeoutError):
                            t.execute(["docker", "sleep", "10"], timeout=0.1)

    def test_execute_pre_cancelled_token_returns_neg_one(self):
        t = CliTransport("docker", binary_resolver=MagicMock())
        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch(
                "oci_runtime.adapters.transport.cli._SubprocessRunner"
            ) as MockRunner:
                mock_process = MagicMock()
                mock_process.stdout.fileno.return_value = 3
                mock_process.stderr.fileno.return_value = 4
                mock_process.poll.return_value = None
                mock_runner = MockRunner.return_value
                mock_runner.process = mock_process
                with patch(
                    "oci_runtime.adapters.transport.cli._AsyncStreamReader"
                ) as MockReader:
                    mock_reader_instance = MockReader.return_value
                    mock_reader_instance.read.return_value = ([b""], [b""])
                    from oci_runtime.adapters.transport.cancellation import (
                        ThreadCancellationToken,
                    )

                    token = ThreadCancellationToken()
                    token.cancel()
                    result = t.execute(["docker", "version"], cancel_token=token)
        assert result.returncode == -1
