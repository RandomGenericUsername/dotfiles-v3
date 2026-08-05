from __future__ import annotations

import json
from collections.abc import Callable

import pytest

from provisioning.adapters.ansible_fact_reader import AnsibleFactReader, UnknownOsFamilyError
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
