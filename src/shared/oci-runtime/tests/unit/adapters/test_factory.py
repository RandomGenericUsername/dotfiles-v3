from unittest.mock import patch

import pytest

from oci_runtime.adapters.engine.cli import CliRuntime
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.domain.exceptions import ProviderNotRegisteredError
from oci_runtime.factory import RuntimeFactory
from oci_runtime.domain.types import RuntimePreference


def test_global_registry_no_longer_exists():
    import oci_runtime.factory as mod

    assert not hasattr(mod, "_PROVIDER_REGISTRY")
    assert not hasattr(mod, "register_provider")
    assert not hasattr(mod, "get_provider")


def test_factory_requires_providers():
    factory = RuntimeFactory(providers={})
    with pytest.raises(ProviderNotRegisteredError):
        factory.create(RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"))


class TestRuntimeFactoryCreate:
    @patch("shutil.which", return_value="/usr/bin/docker")
    def test_docker_returns_cli_runtime(self, mock_which):
        runtime = RuntimeFactory().create(
            RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker")
        )
        assert isinstance(runtime, CliRuntime)

    @patch("shutil.which", return_value="/usr/bin/podman")
    def test_podman_returns_cli_runtime(self, mock_which):
        runtime = RuntimeFactory().create(
            RuntimePreference(kind=RuntimeKind.PODMAN, binary="podman")
        )
        assert isinstance(runtime, CliRuntime)

    def test_create_does_not_probe(self):
        bogus = RuntimePreference(
            kind=RuntimeKind.DOCKER, binary="nonexistent-runtime-xyz"
        )
        engine = RuntimeFactory().create(bogus)
        assert engine.is_available() is False


def test_runtime_kind_extensible_to_unknown_value():
    k = RuntimeKind("nerdctl")
    assert k.value == "nerdctl"
    assert k != RuntimeKind.DOCKER
    assert k != RuntimeKind.PODMAN
    with pytest.raises(ProviderNotRegisteredError):
        RuntimeFactory().create(RuntimePreference(kind=k, binary="nerdctl"))


def test_provider_not_registered_error_carries_kind():
    k = RuntimeKind("nerdctl")
    err = ProviderNotRegisteredError(k)
    assert err.kind is k
