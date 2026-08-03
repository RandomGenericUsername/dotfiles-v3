from __future__ import annotations

from pathlib import Path

from icon_templates_renderer.domain.exceptions import (
    ColorSchemeKeyNotFoundError,
    ColorSchemeNotFoundError,
    ConfigResolutionError,
    IconNotFoundError,
    IconRendererError,
    InvalidYamlError,
    MissingMappingError,
    TemplateNotFoundError,
)


def test_hierarchy() -> None:
    for exc in (
        InvalidYamlError("x"),
        IconNotFoundError("nope", Path("/icons.yaml")),
        TemplateNotFoundError(Path("/t.svg")),
        ColorSchemeNotFoundError("x"),
        MissingMappingError("k"),
        ColorSchemeKeyNotFoundError("k", "v"),
        ConfigResolutionError("templates_dir", ("--template-dir",)),
    ):
        assert isinstance(exc, IconRendererError)


def test_icon_not_found_message() -> None:
    exc = IconNotFoundError("nope", Path("/icons.yaml"))
    assert str(exc) == "Icon 'nope' not found in /icons.yaml"


def test_template_not_found_message() -> None:
    exc = TemplateNotFoundError(Path("/t.svg"))
    assert str(exc) == "Template not found: /t.svg"


def test_missing_mapping_message() -> None:
    exc = MissingMappingError("unknown_color")
    assert str(exc) == "Placeholder '{{unknown_color}}' has no entry in color_mappings"


def test_color_scheme_key_not_found_message() -> None:
    exc = ColorSchemeKeyNotFoundError("k", "missing_key")
    expected = (
        "color_mappings entry for 'k' references color scheme key"
        " 'missing_key' which does not exist"
    )
    assert str(exc) == expected


def test_invalid_yaml_message() -> None:
    assert str(InvalidYamlError("YAML file not found: /x")) == "YAML file not found: /x"


def test_config_resolution_error_message() -> None:
    exc = ConfigResolutionError(
        "color_scheme",
        ("--color-scheme", "ICON_RENDERER__COLOR_SCHEME__PATH", "discovery"),
    )
    msg = str(exc)
    assert "color_scheme" in msg
    assert "--color-scheme" in msg
    assert "ICON_RENDERER__COLOR_SCHEME__PATH" in msg
    assert "discovery" in msg


def test_config_resolution_error_attributes() -> None:
    exc = ConfigResolutionError("templates_dir", ("--template-dir", "discovery"))
    assert exc.name == "templates_dir"
    assert exc.levers == ("--template-dir", "discovery")
