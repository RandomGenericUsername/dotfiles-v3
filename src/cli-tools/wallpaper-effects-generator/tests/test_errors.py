from pathlib import Path

from wallpaper_effects_generator.errors import (
    BinaryNotFoundError,
    CatalogError,
    CommandExecutionError,
    CompositeNotFoundError,
    ConfigResolutionError,
    ContainerImageNotFoundError,
    ContainerRuntimeUnavailableError,
    ContainerTimeoutError,
    EffectNotFoundError,
    EffectsLoadError,
    EffectsValidationError,
    ImagePullAccessError,
    PresetNotFoundError,
    WallpaperEffectsError,
)


class TestWallpaperEffectsError:
    def test_is_base(self) -> None:
        assert issubclass(EffectsLoadError, WallpaperEffectsError)
        assert issubclass(CatalogError, WallpaperEffectsError)
        assert issubclass(ConfigResolutionError, WallpaperEffectsError)


class TestEffectsLoadError:
    def test_attributes(self) -> None:
        err = EffectsLoadError(file_path=Path("/test.yaml"), reason="corrupt")
        assert err.file_path == Path("/test.yaml")
        assert err.reason == "corrupt"
        assert "corrupt" in str(err)


class TestEffectsValidationError:
    def test_message(self) -> None:
        err = EffectsValidationError(message="invalid field")
        assert err.message == "invalid field"


class TestCommandExecutionError:
    def test_attributes(self) -> None:
        err = CommandExecutionError(command="convert", return_code=1, stderr="error msg")
        assert err.command == "convert"
        assert err.return_code == 1
        assert err.stderr == "error msg"


class TestCatalogErrors:
    def test_effect_not_found(self) -> None:
        err = EffectNotFoundError(name="blur")
        assert err.name == "blur"
        assert issubclass(EffectNotFoundError, CatalogError)

    def test_composite_not_found(self) -> None:
        err = CompositeNotFoundError(name="combo")
        assert err.name == "combo"
        assert issubclass(CompositeNotFoundError, CatalogError)

    def test_preset_not_found(self) -> None:
        err = PresetNotFoundError(name="preset1")
        assert err.name == "preset1"
        assert issubclass(PresetNotFoundError, CatalogError)


class TestBinaryNotFoundError:
    def test_binary(self) -> None:
        err = BinaryNotFoundError(binary="magick")
        assert err.binary == "magick"


class TestContainerErrors:
    def test_image_not_found(self) -> None:
        err = ContainerImageNotFoundError(image="img:latest")
        assert err.image == "img:latest"

    def test_runtime_unavailable(self) -> None:
        err = ContainerRuntimeUnavailableError(runtime="docker")
        assert err.runtime == "docker"

    def test_image_pull_access(self) -> None:
        err = ImagePullAccessError(image="img", registry="ghcr.io")
        assert err.image == "img"
        assert err.registry == "ghcr.io"

    def test_container_timeout(self) -> None:
        err = ContainerTimeoutError(command="docker run ...", timeout=60)
        assert err.command == "docker run ..."
        assert err.timeout == 60
        assert "timed out after" in str(err)
        assert str(60) in str(err)


class TestConfigResolutionError:
    def test_creation(self) -> None:
        err = ConfigResolutionError("config not found")
        assert "config not found" in str(err)
