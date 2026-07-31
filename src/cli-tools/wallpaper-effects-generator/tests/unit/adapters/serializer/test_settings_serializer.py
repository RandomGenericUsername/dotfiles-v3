from __future__ import annotations

from pathlib import Path

import pytest

from wallpaper_effects_generator.adapters.serializer.settings_serializer import (
    SettingsSerializer,
)
from wallpaper_effects_generator.domain.enums import RuntimeMode, Verbosity
from wallpaper_effects_generator.domain.models import (
    AppSettings,
    BackendSettings,
    ContainerSettings,
    ExecutionSettings,
    OutputSettings,
    RuntimeSettings,
)


class TestSettingsSerializer:
    def test_round_trip_defaults(self, tmp_path: Path) -> None:
        original = AppSettings()
        path = tmp_path / "settings.toml"
        serializer = SettingsSerializer()
        serializer.serialize(original, path)
        restored = serializer.deserialize(path)
        assert restored.version == original.version
        assert restored.execution == original.execution
        assert restored.output == original.output
        assert restored.backend == original.backend
        assert restored.runtime == original.runtime
        assert restored.container == original.container

    def test_round_trip_custom(self, tmp_path: Path) -> None:
        original = AppSettings(
            version="1.0.0",
            execution=ExecutionSettings(parallel=False, strict=True, max_workers=2),
            output=OutputSettings(verbosity=Verbosity.VERBOSE, directory=Path("/out")),
            backend=BackendSettings(binary="convert"),
            runtime=RuntimeSettings(mode=RuntimeMode.CONTAINER),
            container=ContainerSettings(
                engine="podman", image_tag="v2", image_registry="docker.io"
            ),
        )
        path = tmp_path / "settings.toml"
        serializer = SettingsSerializer()
        serializer.serialize(original, path)
        restored = serializer.deserialize(path)
        assert restored.version == "1.0.0"
        assert restored.execution.parallel is False
        assert restored.execution.strict is True
        assert restored.execution.max_workers == 2
        assert restored.output.verbosity == Verbosity.VERBOSE
        assert restored.backend.binary == "convert"
        assert restored.runtime.mode == RuntimeMode.CONTAINER
        assert restored.container.engine == "podman"
        assert restored.container.image_tag == "v2"
        assert restored.container.image_registry == "docker.io"

    def test_serialize_creates_file(self, tmp_path: Path) -> None:
        serializer = SettingsSerializer()
        path = tmp_path / "out.toml"
        serializer.serialize(AppSettings(), path)
        assert path.exists()
        content = path.read_text()
        assert 'version = "0.1.0"' in content
        assert "[execution]" in content

    def test_deserialize_missing_file(self, tmp_path: Path) -> None:
        serializer = SettingsSerializer()
        with pytest.raises(FileNotFoundError):
            serializer.deserialize(tmp_path / "nonexistent.toml")
