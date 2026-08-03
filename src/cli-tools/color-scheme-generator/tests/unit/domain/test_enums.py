from __future__ import annotations

from color_scheme_generator.domain.enums import Backend, ColorFormat, OutputFormat


class TestBackend:
    def test_members(self) -> None:
        assert Backend.CUSTOM.value == "custom"
        assert Backend.PYWAL.value == "pywal"
        assert Backend.WALLUST.value == "wallust"

    def test_no_auto(self) -> None:
        names = [m.name for m in Backend]
        assert "AUTO" not in names

    def test_image_suffix(self) -> None:
        assert Backend.CUSTOM.image_suffix == "custom"
        assert Backend.PYWAL.image_suffix == "pywal"
        assert Backend.WALLUST.image_suffix == "wallust"


class TestColorFormat:
    def test_members(self) -> None:
        assert ColorFormat.JSON.value == "json"
        assert ColorFormat.SH.value == "sh"
        assert ColorFormat.CSS.value == "css"
        assert ColorFormat.GTK_CSS.value == "gtk.css"
        assert ColorFormat.YAML.value == "yaml"
        assert ColorFormat.SEQUENCES.value == "sequences"
        assert ColorFormat.RASI.value == "rasi"
        assert ColorFormat.SCSS.value == "scss"
        assert ColorFormat.HYPRLAND.value == "conf"


class TestOutputFormat:
    def test_members(self) -> None:
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.RICH.value == "rich"
        assert OutputFormat.PLAIN.value == "plain"

    def test_str(self) -> None:
        assert str(OutputFormat.JSON) == "json"
        assert str(OutputFormat.RICH) == "rich"
        assert str(OutputFormat.PLAIN) == "plain"
