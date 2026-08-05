from __future__ import annotations

import json
import subprocess
from collections.abc import Callable

import pytest

from provisioning.adapters.ansible_fact_reader import (
    AnsibleFactReader,
    InvalidFactOutputError,
    UnknownOsFamilyError,
)
from provisioning.domain.enums import Distro


def _setup_output(family: str) -> str:
    return json.dumps({"ansible_facts": {"ansible_os_family": family}, "changed": False})


def _recording_runner(commands: list[list[str]], output: str) -> Callable[[list[str]], str]:
    def runner(command: list[str]) -> str:
        commands.append(command)
        return output

    return runner


class TestAnsibleFactReader:
    def test_archlinux_maps_to_arch(self) -> None:
        reader = AnsibleFactReader(runner=_recording_runner([], _setup_output("Archlinux")))
        assert reader.os_family() == Distro.ARCH.value

    @pytest.mark.parametrize("family", ["Debian", "Ubuntu"])
    def test_debian_family_values_map_to_debian_family(self, family: str) -> None:
        reader = AnsibleFactReader(runner=_recording_runner([], _setup_output(family)))
        assert reader.os_family() == Distro.DEBIAN_FAMILY.value

    def test_runner_receives_expected_command(self) -> None:
        commands: list[list[str]] = []
        reader = AnsibleFactReader(runner=_recording_runner(commands, _setup_output("Archlinux")))
        reader.os_family()
        assert commands == [["ansible", "-m", "setup", "localhost"]]

    def test_unrecognized_family_fails_loudly(self) -> None:
        reader = AnsibleFactReader(runner=_recording_runner([], _setup_output("FreeBSD")))
        with pytest.raises(UnknownOsFamilyError, match="FreeBSD"):
            reader.os_family()

    def test_host_success_prefix_is_tolerated(self) -> None:
        output = f"localhost | SUCCESS => {_setup_output('Archlinux')}"
        reader = AnsibleFactReader(runner=_recording_runner([], output))
        assert reader.os_family() == Distro.ARCH.value

    def test_leading_warning_with_braces_is_tolerated(self) -> None:
        output = (
            "[WARNING]: {not real json}\n"
            "[WARNING]: ignoring some deprecation\n"
            f"{_setup_output('Ubuntu')}"
        )
        reader = AnsibleFactReader(runner=_recording_runner([], output))
        assert reader.os_family() == Distro.DEBIAN_FAMILY.value

    def test_non_zero_exit_raises_invalid_fact_output(self) -> None:
        def failing_runner(command: list[str]) -> str:
            raise InvalidFactOutputError("ansible -m setup exited with 4: connection refused")

        reader = AnsibleFactReader(runner=failing_runner)
        with pytest.raises(InvalidFactOutputError, match="connection refused"):
            reader.os_family()

    def test_missing_binary_wrapped_as_invalid_fact_output(self) -> None:
        def missing_binary(command: list[str]) -> str:
            raise FileNotFoundError("ansible not found")

        reader = AnsibleFactReader(runner=missing_binary)
        with pytest.raises(InvalidFactOutputError, match="failed to run"):
            reader.os_family()

    def test_timeout_wrapped_as_invalid_fact_output(self) -> None:
        def timing_out(command: list[str]) -> str:
            raise subprocess.TimeoutExpired(command, timeout=5)

        reader = AnsibleFactReader(runner=timing_out, timeout=5)
        with pytest.raises(InvalidFactOutputError, match="exceeded 5s timeout"):
            reader.os_family()
