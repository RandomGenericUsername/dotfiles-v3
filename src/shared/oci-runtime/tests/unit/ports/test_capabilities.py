from dataclasses import is_dataclass, fields, field

import pytest
from dataclasses import FrozenInstanceError

from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.ports.capabilities import RuntimeCapabilities, RuntimePreference


class TestEngineProfileRemoved:
    def test_engine_profile_no_longer_exists(self):
        import oci_runtime.ports.capabilities as mod
        assert not hasattr(mod, "EngineProfile")


class TestRuntimeCapabilities:
    def test_is_dataclass(self):
        assert is_dataclass(RuntimeCapabilities)

    def test_defaults(self):
        caps = RuntimeCapabilities()
        assert caps.needs_userns_keep_id is False
        assert caps.supports_log_drivers is True
        assert caps.tar_entry_name == "Dockerfile"
        assert caps.default_run_flags == []
        assert caps.default_build_flags == []

    def test_custom_values(self):
        caps = RuntimeCapabilities(
            needs_userns_keep_id=True,
            supports_log_drivers=False,
            tar_entry_name="Containerfile",
            default_run_flags=["--userns=keep-id"],
            default_build_flags=["--no-cache"],
        )
        assert caps.needs_userns_keep_id is True
        assert caps.supports_log_drivers is False
        assert caps.tar_entry_name == "Containerfile"
        assert caps.default_run_flags == ["--userns=keep-id"]
        assert caps.default_build_flags == ["--no-cache"]

    def test_default_run_flags_is_new_list_each_time(self):
        c1 = RuntimeCapabilities()
        c2 = RuntimeCapabilities()
        assert c1.default_run_flags is not c2.default_run_flags


class TestRuntimePreference:
    def test_is_frozen_dataclass(self):
        pref = RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker")
        assert is_dataclass(pref)
        with pytest.raises(FrozenInstanceError):
            pref.kind = RuntimeKind.PODMAN

    def test_binary_is_required(self):
        with pytest.raises(TypeError):
            RuntimePreference(kind=RuntimeKind.DOCKER)

    def test_stores_binary(self):
        pref = RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker")
        assert pref.binary == "docker"

    def test_stores_kind(self):
        pref = RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker")
        assert pref.kind == RuntimeKind.DOCKER

    def test_podman_preference(self):
        pref = RuntimePreference(kind=RuntimeKind.PODMAN, binary="podman")
        assert pref.binary == "podman"
        assert pref.kind == RuntimeKind.PODMAN

    def test_has_no_get_binary_method(self):
        pref = RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker")
        assert not hasattr(pref, "get_binary")
