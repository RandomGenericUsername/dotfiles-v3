from wallpaper_effects_generator.domain.enums import (
    ContainerEngine,
    ItemType,
    OutputFormat,
    RuntimeMode,
    Verbosity,
)


class TestItemType:
    def test_values(self) -> None:
        assert ItemType.EFFECT.value == "effect"
        assert ItemType.COMPOSITE.value == "composite"
        assert ItemType.PRESET.value == "preset"

    def test_subdir_name(self) -> None:
        assert ItemType.EFFECT.subdir_name == "effect"
        assert ItemType.COMPOSITE.subdir_name == "composite"
        assert ItemType.PRESET.subdir_name == "preset"


class TestVerbosity:
    def test_values(self) -> None:
        assert Verbosity.QUIET.value == 0
        assert Verbosity.NORMAL.value == 1
        assert Verbosity.VERBOSE.value == 2
        assert Verbosity.DEBUG.value == 3


class TestRuntimeMode:
    def test_values(self) -> None:
        assert RuntimeMode.LOCAL.value == "local"
        assert RuntimeMode.CONTAINER.value == "container"


class TestContainerEngine:
    def test_values(self) -> None:
        assert ContainerEngine.DOCKER.value == "docker"
        assert ContainerEngine.PODMAN.value == "podman"

    def test_members(self) -> None:
        assert len(ContainerEngine) == 2


class TestOutputFormat:
    def test_values(self) -> None:
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.RICH.value == "rich"
        assert OutputFormat.PLAIN.value == "plain"
