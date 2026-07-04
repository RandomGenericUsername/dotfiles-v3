from unittest.mock import patch

from oci_runtime.builder import EngineBuildResult, OciRuntimeBuilder
from oci_runtime.adapters.engine.cli import CliRuntime
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.factory import ResolvedRuntimeFactoryConfig


def test_builder_defaults():
    with patch("shutil.which", return_value="/usr/bin/docker"):
        result = OciRuntimeBuilder().build()
    assert isinstance(result, EngineBuildResult)
    assert isinstance(result.engine, CliRuntime)
    assert isinstance(result.resolved_config, ResolvedRuntimeFactoryConfig)


def test_builder_with_runtime_kind():
    with patch("shutil.which", return_value="/usr/bin/podman"):
        result = (
            OciRuntimeBuilder()
            .with_runtime_kind(RuntimeKind.PODMAN)
            .with_binary("podman")
            .build()
        )
    assert isinstance(result.engine, CliRuntime)


def test_builder_chain():
    b = OciRuntimeBuilder().with_runtime_kind(RuntimeKind.PODMAN).with_binary("podman")
    assert b._kind == RuntimeKind.PODMAN
    assert b._binary == "podman"


def test_builder_resolved_config_type():
    with patch("shutil.which", return_value="/usr/bin/docker"):
        result = OciRuntimeBuilder().build()
    assert isinstance(result.resolved_config, ResolvedRuntimeFactoryConfig)
    assert result.resolved_config.transport_factory is not None
    assert result.resolved_config.streaming_transport_factory is not None


def _null_factory(*a, **kw):
    return None


def test_builder_with_config_override():
    with patch("shutil.which", return_value="/usr/bin/docker"):
        result = OciRuntimeBuilder().with_transport_factory(_null_factory).build()
    assert result.resolved_config.transport_factory is _null_factory
