import subprocess
import shutil

import pytest


def _is_runtime_available(name: str) -> bool:
    binary = shutil.which(name)
    if binary is None:
        return False
    try:
        result = subprocess.run([binary, "--version"], capture_output=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


@pytest.fixture(scope="session")
def docker_available():
    return _is_runtime_available("docker")


@pytest.fixture(scope="session")
def podman_available():
    return _is_runtime_available("podman")


@pytest.fixture(scope="session")
def live_docker_engine(docker_available):
    if not docker_available:
        pytest.skip("Docker not available")
    from oci_runtime import engines
    from oci_runtime.factory import RuntimeFactory
    return RuntimeFactory().create(engines.docker_pref)


@pytest.fixture(scope="session")
def live_podman_engine(podman_available):
    if not podman_available:
        pytest.skip("Podman not available")
    from oci_runtime import engines
    from oci_runtime.factory import RuntimeFactory
    return RuntimeFactory().create(engines.podman_pref)
