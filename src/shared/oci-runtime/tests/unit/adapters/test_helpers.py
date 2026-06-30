from unittest.mock import MagicMock

import pytest

from oci_runtime.adapters.helpers.result_checker import CliResultChecker
from oci_runtime.adapters.helpers.list_executor import CliListExecutor
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.capabilities import RuntimeCapabilities


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
