from unittest.mock import MagicMock

import pytest

from oci_runtime.adapters.managers._timeouts import cli_seconds
from oci_runtime.adapters.helpers.result_checker import CliResultChecker
from oci_runtime.adapters.helpers.list_executor import CliListExecutor
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.capabilities import RuntimeCapabilities


class TestCliSeconds:
    def test_ceil_1_9_returns_2(self):
        assert cli_seconds(1.9, default=10) == "2"

    def test_ceil_1_0_returns_1(self):
        assert cli_seconds(1.0, default=10) == "1"

    def test_ceil_1_01_returns_2(self):
        assert cli_seconds(1.01, default=10) == "2"

    def test_none_returns_default(self):
        assert cli_seconds(None, default=10) == "10"

    def test_0_5_returns_1(self):
        assert cli_seconds(0.5, default=10) == "1"


class TestResultCheckerConstruction:
    def test_result_checker_requires_error_types(self):
        with pytest.raises(TypeError):
            CliResultChecker()
        with pytest.raises(TypeError):
            CliResultChecker(generic_error=ValueError)


class TestListExecutorCallable:
    def test_list_executor_parse_list_callable(self):
        transport = MagicMock()
        transport.execute.return_value = RawExecResult(
            returncode=0, stdout=b'[{"id": "abc"}]', stderr=b""
        )
        transport.get_runtime_binary.return_value = "docker"
        caps = RuntimeCapabilities()
        checker = MagicMock()
        parse_list = MagicMock(return_value=["parsed"])

        executor = CliListExecutor(transport, caps, checker, parse_list=parse_list)
        result = executor.execute_list(["image", "list"], "images")

        assert result == ["parsed"]
        parse_list.assert_called_once_with('[{"id": "abc"}]')
