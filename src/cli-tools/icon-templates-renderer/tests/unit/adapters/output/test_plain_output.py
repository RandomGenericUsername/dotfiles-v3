from __future__ import annotations

from pathlib import Path

import pytest

from icon_templates_renderer.adapters.output.json_output import JsonOutput
from icon_templates_renderer.adapters.output.plain_output import PlainOutput
from icon_templates_renderer.domain.enums import MappingOrigin, Verbosity
from icon_templates_renderer.domain.exceptions import InvalidYamlError
from icon_templates_renderer.domain.models import (
    ColorScheme,
    GroupMappingView,
    ListResult,
    MappingEntry,
    MappingSetDefaultResult,
    MappingSetResult,
    MappingShowResult,
    RenderedVariant,
    RenderResult,
    ValidateResult,
    VariantMappingView,
)

PLAIN = "plain_output_fixture"


class TestPlainOutput:
    def setup_method(self) -> None:
        self.output = PlainOutput(verbosity=Verbosity.NORMAL)

    def test_render_result_plain_verbatim(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = RenderResult(
            success=True,
            rendered=(
                RenderedVariant("battery-0", "battery", Path("out/a.svg")),
                RenderedVariant("battery-100", "battery", Path("out/b.svg")),
            ),
        )
        self.output.render_result(result)
        captured = capsys.readouterr()
        assert captured.out == ("Rendered: out/a.svg\nRendered: out/b.svg\n\n2 icon(s) rendered.\n")

    def test_list_result_all_plain(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = ListResult(
            groups=(
                ("battery", ("battery-0", "battery-100")),
                ("network", ("wifi",)),
            ),
            single=False,
        )
        self.output.list_result(result)
        captured = capsys.readouterr()
        assert captured.out == ("battery:\n  - battery-0\n  - battery-100\nnetwork:\n  - wifi\n")

    def test_list_result_single_plain(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = ListResult(groups=(("battery", ("battery-0",)),), single=True)
        self.output.list_result(result)
        captured = capsys.readouterr()
        assert captured.out == "Variants:\n  - battery-0\n"

    def test_validate_result_plain(self, capsys: pytest.CaptureFixture[str]) -> None:
        self.output.validate_result(ValidateResult(ok=True, checked_groups=1, checked_variants=1))
        captured = capsys.readouterr()
        assert captured.out == "Validation passed.\n"

    def test_error_plain_verbatim(self, capsys: pytest.CaptureFixture[str]) -> None:
        self.output.error(InvalidYamlError("YAML file not found: /x"))
        captured = capsys.readouterr()
        assert captured.err == "Error: YAML file not found: /x\n"

    def test_quiet_suppresses_non_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        quiet = PlainOutput(verbosity=Verbosity.QUIET)
        quiet.render_result(RenderResult(success=True))
        captured = capsys.readouterr()
        assert captured.out == ""


def _mapping_show_result() -> MappingShowResult:
    return MappingShowResult(
        groups=(
            GroupMappingView(
                group="battery",
                variants=(
                    VariantMappingView(
                        variant="battery-0",
                        template_path=Path("battery/battery-0.svg"),
                        svg_body="<svg/>",
                        entries=(
                            MappingEntry(
                                placeholder="COLOR_ACCENT",
                                token="color12",
                                origin=MappingOrigin.GROUP,
                            ),
                        ),
                    ),
                ),
            ),
        ),
        palette=ColorScheme.from_dict({"color12": "#6ea8fe"}),
        missing_tokens=("surface",),
        shadows=(("COLOR_ACCENT", ("battery",)),),
    )


class TestMappingShowOutput:
    def test_mapping_show_plain(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = PlainOutput(verbosity=Verbosity.NORMAL)
        output.mapping_show_result(_mapping_show_result())
        captured = capsys.readouterr()
        assert "battery:" in captured.out
        assert "COLOR_ACCENT: color12 [group]" in captured.out
        assert "Missing tokens: surface" in captured.out
        assert "COLOR_ACCENT: battery" in captured.out

    def test_mapping_show_plain_no_missing_or_shadows(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        output = PlainOutput(verbosity=Verbosity.NORMAL)
        output.mapping_show_result(MappingShowResult())
        captured = capsys.readouterr()
        assert "Missing tokens: none" in captured.out
        assert "Shadowing groups: none" in captured.out

    def test_mapping_show_json_is_gui_contract(self, capsys: pytest.CaptureFixture[str]) -> None:
        import json

        output = JsonOutput(verbosity=Verbosity.NORMAL)
        output.mapping_show_result(_mapping_show_result())
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        variant = payload["groups"][0]["variants"][0]
        assert variant["variant"] == "battery-0"
        assert variant["template_path"] == "battery/battery-0.svg"
        assert variant["svg_body"] == "<svg/>"
        assert variant["mappings"][0] == {
            "placeholder": "COLOR_ACCENT",
            "token": "color12",
            "origin": "group",
        }
        assert payload["palette"] == {"color12": "#6ea8fe"}
        assert payload["missing_tokens"] == ["surface"]
        assert payload["shadows"] == {"COLOR_ACCENT": ["battery"]}


class TestMappingSetOutput:
    def test_set_confirmation_plain(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = PlainOutput(verbosity=Verbosity.NORMAL)
        output.mapping_set_result(
            MappingSetResult(group="battery", placeholder="COLOR_ACCENT", token="color10")
        )
        captured = capsys.readouterr()
        assert captured.out == "Set battery.color_mappings.COLOR_ACCENT = color10.\n"

    def test_set_variant_confirmation_plain(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = PlainOutput(verbosity=Verbosity.NORMAL)
        output.mapping_set_result(
            MappingSetResult(
                group="battery",
                placeholder="COLOR_ACCENT",
                token="color10",
                variant="battery-0",
            )
        )
        assert "battery-0" in capsys.readouterr().out

    def test_set_dry_run_note_plain(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = PlainOutput(verbosity=Verbosity.NORMAL)
        output.mapping_set_result(
            MappingSetResult(
                group="battery",
                placeholder="COLOR_ACCENT",
                token="color10",
                dry_run=True,
            )
        )
        assert "dry run" in capsys.readouterr().out

    def test_set_diff_plain(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = PlainOutput(verbosity=Verbosity.NORMAL)
        output.mapping_set_result(
            MappingSetResult(
                group="battery",
                placeholder="COLOR_ACCENT",
                token="color10",
                diff_text="-old\n+new\n",
            )
        )
        assert capsys.readouterr().out == "-old\n+new\n"

    def test_set_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        import json

        output = JsonOutput(verbosity=Verbosity.NORMAL)
        output.mapping_set_result(
            MappingSetResult(
                group="battery",
                placeholder="COLOR_ACCENT",
                token="color10",
                variant="battery-0",
                dry_run=True,
                diff_text="-old\n+new\n",
            )
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload == {
            "group": "battery",
            "variant": "battery-0",
            "placeholder": "COLOR_ACCENT",
            "token": "color10",
            "dry_run": True,
            "diff": "-old\n+new\n",
        }


class TestMappingSetDefaultOutput:
    def test_set_default_confirmation_and_shadows(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = PlainOutput(verbosity=Verbosity.NORMAL)
        output.mapping_set_default_result(
            MappingSetDefaultResult(
                placeholder="COLOR_ACCENT",
                token="color10",
                shadows=("battery", "network"),
            )
        )
        captured = capsys.readouterr()
        assert "Set defaults.COLOR_ACCENT = color10." in captured.out
        assert "Shadowing groups: battery, network" in captured.out

    def test_set_default_no_shadows(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = PlainOutput(verbosity=Verbosity.NORMAL)
        output.mapping_set_default_result(MappingSetDefaultResult(placeholder="K", token="color1"))
        assert "Shadowing groups: none" in capsys.readouterr().out

    def test_set_default_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        import json

        output = JsonOutput(verbosity=Verbosity.NORMAL)
        output.mapping_set_default_result(
            MappingSetDefaultResult(
                placeholder="COLOR_ACCENT",
                token="color10",
                shadows=("battery",),
            )
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload["shadows"] == ["battery"]
        assert payload["placeholder"] == "COLOR_ACCENT"


class TestJsonOutput:
    def test_render_result_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        import json

        output = JsonOutput(verbosity=Verbosity.NORMAL)
        result = RenderResult(
            success=True,
            rendered=(RenderedVariant("battery-0", "battery", Path("out/a.svg")),),
        )
        output.render_result(result)
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert payload["success"] is True
        assert payload["output_files"] == ["out/a.svg"]

    def test_list_result_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        import json

        output = JsonOutput(verbosity=Verbosity.NORMAL)
        output.list_result(ListResult(groups=(("battery", ("battery-0",)),), single=False))
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert payload["groups"]["battery"] == ["battery-0"]
