from __future__ import annotations

from pathlib import Path

import pytest

from color_scheme_generator.adapters.settings.settings_serializer import (
    SettingsSerializer,
    _value_to_toml,
)
from color_scheme_generator.domain.enums import Backend, RuntimeMode
from color_scheme_generator.domain.models import (
    AppSettings,
    ContainerSettings,
    GenerationSettings,
    OutputSettings,
    RuntimeSettings,
    TemplateSettings,
)
from color_scheme_generator.ports.settings_serializer import SettingsSerializerPort


def _make_full_settings() -> AppSettings:
    return AppSettings(
        output=OutputSettings(
            directory=Path("/tmp/out"),
            default_formats=(),
            overwrite=True,
        ),
        generation=GenerationSettings(
            backend=Backend.CUSTOM,
            default_params={"saturation": 1.0},
        ),
        template=TemplateSettings(
            templates_dir=Path("/tmp/templates"),
            custom_templates_dir=None,
        ),
        runtime=RuntimeSettings(
            mode=RuntimeMode.LOCAL,
        ),
        container=ContainerSettings(
            engine="docker",
            image_prefix="csg",
            image_tag="latest",
            timeout_seconds=60,
            memory_limit="512m",
            mount_timeout_seconds=30,
        ),
    )


class TestSettingsSerializer:
    def test_implements_port(self) -> None:
        serializer = SettingsSerializer()
        assert isinstance(serializer, SettingsSerializerPort)

    def test_serialize_includes_all_sections(self) -> None:
        settings = _make_full_settings()
        serializer = SettingsSerializer()
        result = serializer.serialize(settings)

        assert "[output]" in result
        assert "[generation]" in result
        assert "[template]" in result
        assert "[runtime]" in result
        assert "[container]" in result

    def test_serialize_output_fields(self) -> None:
        settings = _make_full_settings()
        serializer = SettingsSerializer()
        result = serializer.serialize(settings)

        assert 'directory = "/tmp/out"' in result
        assert "default_formats = []" in result
        assert "overwrite = true" in result

    def test_serialize_generation_fields(self) -> None:
        settings = _make_full_settings()
        serializer = SettingsSerializer()
        result = serializer.serialize(settings)

        assert 'backend = "custom"' in result

    def test_serialize_runtime_fields(self) -> None:
        settings = _make_full_settings()
        serializer = SettingsSerializer()
        result = serializer.serialize(settings)

        assert 'mode = "local"' in result
        assert 'engine = "docker"' in result

    def test_serialize_container_fields(self) -> None:
        settings = _make_full_settings()
        serializer = SettingsSerializer()
        result = serializer.serialize(settings)

        assert 'image_prefix = "csg"' in result
        assert 'image_tag = "latest"' in result
        assert "timeout_seconds = 60" in result
        assert 'memory_limit = "512m"' in result
        assert "mount_timeout_seconds = 30" in result

    def test_serialize_omits_none_paths(self) -> None:
        settings = AppSettings(
            output=OutputSettings(directory=Path("/tmp"), default_formats=(), overwrite=False),
            generation=GenerationSettings(backend=Backend.CUSTOM, default_params={}),
            template=TemplateSettings(templates_dir=None, custom_templates_dir=None),
            runtime=RuntimeSettings(mode=RuntimeMode.LOCAL),
            container=ContainerSettings(
                engine="docker",
                image_prefix="csg",
                image_tag="latest",
                timeout_seconds=60,
                memory_limit="512m",
                mount_timeout_seconds=30,
            ),
        )
        serializer = SettingsSerializer()
        result = serializer.serialize(settings)

        assert "templates_dir" not in result
        assert "custom_templates_dir" not in result

    def test_serialize_handles_empty_tuple(self) -> None:
        settings = _make_full_settings()
        serializer = SettingsSerializer()
        result = serializer.serialize(settings)

        assert "default_formats = []" in result

    def test_deserialize_raises_not_implemented(self) -> None:
        serializer = SettingsSerializer()
        with pytest.raises(NotImplementedError):
            serializer.deserialize("")


class TestValueToToml:
    def test_bool_true(self) -> None:
        assert _value_to_toml(True) == "true"

    def test_bool_false(self) -> None:
        assert _value_to_toml(False) == "false"

    def test_enum(self) -> None:
        assert _value_to_toml(Backend.CUSTOM) == '"custom"'

    def test_path(self) -> None:
        assert _value_to_toml(Path("/tmp/foo")) == '"/tmp/foo"'

    def test_string(self) -> None:
        assert _value_to_toml("hello") == '"hello"'

    def test_int(self) -> None:
        assert _value_to_toml(42) == "42"

    def test_float(self) -> None:
        assert _value_to_toml(3.14) == "3.14"

    def test_empty_tuple(self) -> None:
        assert _value_to_toml(()) == "[]"

    def test_non_empty_tuple(self) -> None:
        assert _value_to_toml((1, 2, 3)) == "[1, 2, 3]"

    def test_none(self) -> None:
        assert _value_to_toml(None) == ""
