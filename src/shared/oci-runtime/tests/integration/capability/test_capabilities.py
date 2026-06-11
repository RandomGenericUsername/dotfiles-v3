import pytest

from oci_runtime import engines
from oci_runtime.adapters.engine.cli import CliRuntime
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimeCapabilities, RuntimePreference
from oci_runtime.ports.transport import ExecResult
from tests.helpers.mock_transport import RecordingTransport


class TestCapabilityEdgeCases:
    def test_runtime_capabilities_mutable(self):
        caps = RuntimeCapabilities()
        caps.supports_log_drivers = False
        assert caps.supports_log_drivers is False

    def test_runtime_capabilities_default_output_format(self):
        caps = RuntimeCapabilities()
        assert "json" in caps.supported_output_formats

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


