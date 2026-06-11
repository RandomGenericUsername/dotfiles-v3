from dataclasses import is_dataclass

from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimePreference


class TestEngines:
    def test_docker_pref_is_dataclass(self):
        from oci_runtime.engines import docker_pref
        assert is_dataclass(docker_pref)
        assert isinstance(docker_pref, RuntimePreference)

    def test_docker_pref_has_correct_values(self):
        from oci_runtime.engines import docker_pref
        assert docker_pref.kind == RuntimeKind.DOCKER
        assert docker_pref.binary == "docker"

    def test_podman_pref_is_dataclass(self):
        from oci_runtime.engines import podman_pref
        assert is_dataclass(podman_pref)
        assert isinstance(podman_pref, RuntimePreference)

    def test_podman_pref_has_correct_values(self):
        from oci_runtime.engines import podman_pref
        assert podman_pref.kind == RuntimeKind.PODMAN
        assert podman_pref.binary == "podman"
