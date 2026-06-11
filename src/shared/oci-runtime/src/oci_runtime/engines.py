from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimePreference

docker_pref = RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker")
podman_pref = RuntimePreference(kind=RuntimeKind.PODMAN, binary="podman")
