from unittest.mock import MagicMock, patch

import pytest

from oci_runtime.adapters.engine.cli import CliRuntime
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.factory import RuntimeFactory
from oci_runtime.domain.types import RuntimePreference
from oci_runtime.ports.capabilities import RuntimeCapabilities


def test_global_registry_no_longer_exists():
    import oci_runtime.factory as mod
    assert not hasattr(mod, "_PROVIDER_REGISTRY")
    assert not hasattr(mod, "register_provider")
    assert not hasattr(mod, "get_provider")


def test_factory_requires_providers():
    factory = RuntimeFactory(providers={})
    with pytest.raises(NotImplementedError):
        factory.create(RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"))


class TestRuntimeFactoryCreate:
    @patch("shutil.which", return_value="/usr/bin/docker")
    @patch("subprocess.run")
    def test_docker_returns_cli_runtime(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout="Docker version 24.0.0", stderr="")
        runtime = RuntimeFactory().create(RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"))
        assert isinstance(runtime, CliRuntime)

    @patch("shutil.which", return_value="/usr/bin/podman")
    @patch("subprocess.run")
    def test_podman_returns_cli_runtime(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout="podman version 4.0.0", stderr="")
        runtime = RuntimeFactory().create(RuntimePreference(kind=RuntimeKind.PODMAN, binary="podman"))
        assert isinstance(runtime, CliRuntime)

    def test_bogus_raises_runtime_not_available(self):
        bogus = RuntimePreference(kind=RuntimeKind.DOCKER, binary="nonexistent-runtime-xyz")
        with pytest.raises(RuntimeNotAvailableError):
            RuntimeFactory().create(bogus)
