from __future__ import annotations

from pathlib import Path

import pytest

from icon_templates_renderer.adapters.output.json_output import JsonOutput
from icon_templates_renderer.adapters.output.plain_output import PlainOutput
from icon_templates_renderer.domain.enums import Verbosity
from icon_templates_renderer.domain.exceptions import InvalidYamlError
from icon_templates_renderer.domain.models import (
    ListResult,
    RenderedVariant,
    RenderResult,
    ValidateResult,
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
