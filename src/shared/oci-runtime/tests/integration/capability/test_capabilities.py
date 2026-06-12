import pytest

from oci_runtime.adapters.engine.cli import CliRuntime
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimeCapabilities, RuntimePreference
from oci_runtime.ports.transport import ExecResult
from tests.helpers.mock_transport import RecordingTransport


from dataclasses import FrozenInstanceError


class TestCapabilityEdgeCases:
    def test_runtime_capabilities_is_frozen(self):
        caps = RuntimeCapabilities()
        with pytest.raises(FrozenInstanceError):
            caps.supports_log_drivers = False

    def test_runtime_capabilities_default_list_format_flags(self):
        caps = RuntimeCapabilities()
        assert caps.list_format_flags == []

    def test_runtime_preference_is_frozen(self):
        pref = RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker")
        with pytest.raises(Exception):
            pref.kind = RuntimeKind.PODMAN

    def test_runtime_preference_custom_binary(self):
        pref = RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker-custom")
        assert pref.binary == "docker-custom"

    def test_runtime_preference_required_binary(self):
        pref = RuntimePreference(kind=RuntimeKind.PODMAN, binary="podman")
        assert pref.binary == "podman"


