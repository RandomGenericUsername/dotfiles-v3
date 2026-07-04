from unittest.mock import MagicMock

import pytest

from oci_runtime.adapters.helpers.list_executor import CliListExecutor
from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.capabilities import RuntimeCapabilities


@pytest.fixture
def transport():
    t = MagicMock()
    t.execute.return_value = RawExecResult(returncode=0, stdout=b"[]", stderr=b"")
    t.get_runtime_binary.return_value = "/usr/bin/docker"
    return t


@pytest.fixture
def caps():
    return RuntimeCapabilities(
        list_format_flags=("--format", "{{json .}}"),
    )


@pytest.fixture
def result_checker():
    return MagicMock()


@pytest.fixture
def parse_list():
    return MagicMock(return_value=[])


@pytest.fixture
def executor(transport, caps, result_checker, parse_list):
    return CliListExecutor(transport, caps, result_checker, parse_list)


class TestListContainersFilters:
    def test_list_containers_all_filter(self, executor, transport):
        executor.execute_list(
            subcommand=["ps", "-a"],
            entity_type="container",
            show_all=False,
            filters={"name": "test-ctr"},
        )
        cmd = transport.execute.call_args[0][0]
        assert "--filter" in cmd
        assert "name=test-ctr" in cmd

    def test_list_containers_latest_filter(self, executor, transport):
        executor.execute_list(
            subcommand=["ps", "-n", "1"],
            entity_type="container",
            show_all=False,
            filters={"name": "latest-ctr"},
        )
        cmd = transport.execute.call_args[0][0]
        assert "--filter" in cmd
        assert "name=latest-ctr" in cmd

    def test_list_containers_since_filter(self, executor, transport):
        executor.execute_list(
            subcommand=["ps"],
            entity_type="container",
            show_all=False,
            filters={"since": "abc123"},
        )
        cmd = transport.execute.call_args[0][0]
        assert "--filter" in cmd
        assert "since=abc123" in cmd

    def test_list_containers_before_filter(self, executor, transport):
        executor.execute_list(
            subcommand=["ps"],
            entity_type="container",
            show_all=False,
            filters={"before": "xyz789"},
        )
        cmd = transport.execute.call_args[0][0]
        assert "--filter" in cmd
        assert "before=xyz789" in cmd

    def test_builder_map_unknown_fallthrough(self, executor, transport):
        executor.execute_list(
            subcommand=["ps"],
            entity_type="container",
            show_all=False,
            filters={"unknown_key": "some_value"},
        )
        cmd = transport.execute.call_args[0][0]
        assert "--filter" in cmd
        assert "unknown_key=some_value" in cmd

    def test_list_containers_empty_response(self, executor, parse_list):
        parse_list.return_value = []
        result = executor.execute_list(
            subcommand=["ps"],
            entity_type="container",
        )
        assert result == []

    def test_executor_teardown_error(self, executor, transport):
        transport.execute.side_effect = RuntimeError("Teardown failure")
        with pytest.raises(RuntimeError, match="Teardown failure"):
            executor.execute_list(
                subcommand=["ps"],
                entity_type="container",
            )
