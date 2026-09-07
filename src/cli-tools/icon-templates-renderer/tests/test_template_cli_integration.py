from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from icon_templates_renderer.cli.main import app
from icon_templates_renderer.domain.services import TemplateAnalysisService, attr_value
from icon_templates_renderer.factory import build_deps

POWER_MENU_BODY = (
    '<svg width="800" height="800" viewBox="0 0 800 800" fill="none" '
    'xmlns="http://www.w3.org/2000/svg">\n'
    '<path d="M400 66.668V200.001" stroke="{{COLOR_FOREGROUND}}" '
    'stroke-width="75" stroke-linecap="round"/>\n'
    '<path d="M283.333 123.535C175.602 169.052 100 275.7 100 400.003C100 476.84 '
    "128.885 546.93 176.39 600.007M516.667 123.535C624.397 169.052 700 275.7 700 "
    "400.003C700 565.69 565.687 700.003 400 700.003C364.937 700.003 331.278 693.99 "
    '300 682.934" stroke="{{COLOR_FOREGROUND}}" stroke-width="75" '
    'stroke-linecap="round"/>\n'
    "</svg>"
)

BARE_HEX = (
    '<svg width="24" height="24">\n'
    '<path fill="#c2c2c5" d="M0 0L1 1"/>\n'
    '<rect fill="#ffffff" x="0" y="0" width="4" height="4"/>\n'
    "</svg>"
)


@pytest.fixture
def cli_deps(monkeypatch: pytest.MonkeyPatch) -> object:
    deps = build_deps()
    monkeypatch.setattr("icon_templates_renderer.cli.main.build_deps", lambda: deps)
    return deps


def _analyze_json(path: Path) -> dict:
    result = CliRunner().invoke(app, ["template", "analyze", str(path), "--json"])
    assert result.exit_code == 0, result.stderr
    return json.loads(result.stdout)


def _worktree_root() -> Path:
    p = Path(__file__).resolve().parent
    while not (p / "dotfiles").exists() and p != p.parent:
        p = p.parent
    return p


def _expected_after_set(body: str, shape: dict) -> str:
    attr = shape["paint_attr"]
    service = TemplateAnalysisService()
    pairs = service.extract_with_elements(body)
    element = next((el for s, el in pairs if s.shape_id == shape["id"]), None)
    assert element is not None
    pattern = re.compile(rf'(\b{re.escape(attr)}\s*=\s*")([^"]*)(")')
    new_element = pattern.sub(lambda m: m.group(1) + "{{COLOR_TEST}}" + m.group(3), element, 1)
    return body.replace(element, new_element, 1)


class TestAnalyzeIntegration:
    def test_bare_classification(self, cli_deps, tmp_path: Path) -> None:
        path = tmp_path / "bare.svg"
        path.write_text(BARE_HEX, encoding="utf-8")
        payload = _analyze_json(path)
        assert payload["mode"] == "bare"
        assert [shape["literal"] for shape in payload["shapes"]] == ["#c2c2c5", "#ffffff"]
        assert all(shape["placeholder"] is None for shape in payload["shapes"])

    def test_templated_classification(self, cli_deps, tmp_path: Path) -> None:
        path = tmp_path / "templated.svg"
        path.write_text(BARE_HEX.replace("#c2c2c5", "{{COLOR_FOREGROUND}}"), encoding="utf-8")
        payload = _analyze_json(path)
        assert payload["mode"] == "templated"
        assert payload["shapes"][0]["placeholder"] == "COLOR_FOREGROUND"
        assert payload["shapes"][0]["literal"] is None

    def test_inherited_stroke_resolved(self, cli_deps, tmp_path: Path) -> None:
        path = tmp_path / "power-menu.svg"
        path.write_text(POWER_MENU_BODY, encoding="utf-8")
        payload = _analyze_json(path)
        assert payload["mode"] == "templated"
        assert all(shape["paint_attr"] == "stroke" for shape in payload["shapes"])
        assert all(shape["placeholder"] == "COLOR_FOREGROUND" for shape in payload["shapes"])


class TestSetPlaceholderIntegration:
    def test_happy_path(self, cli_deps, tmp_path: Path) -> None:
        path = tmp_path / "bare.svg"
        path.write_text(BARE_HEX, encoding="utf-8")
        before = path.read_bytes()
        result = CliRunner().invoke(
            app,
            [
                "template",
                "set-placeholder",
                str(path),
                "--shape",
                "1",
                "--name",
                "COLOR_FOREGROUND",
            ],
        )
        assert result.exit_code == 0, result.stderr
        assert "Set shape 1 paint = {{COLOR_FOREGROUND}}." in result.stdout
        assert path.read_bytes() != before
        text = path.read_text(encoding="utf-8")
        assert 'fill="{{COLOR_FOREGROUND}}"' in text
        assert 'fill="#ffffff"' in text
        payload = _analyze_json(path)
        assert payload["mode"] == "templated"
        assert payload["shapes"][0]["placeholder"] == "COLOR_FOREGROUND"

    def test_invalid_name_rejected_without_write(self, cli_deps, tmp_path: Path) -> None:
        path = tmp_path / "bare.svg"
        path.write_text(BARE_HEX, encoding="utf-8")
        before = path.read_bytes()
        result = CliRunner().invoke(
            app,
            ["template", "set-placeholder", str(path), "--shape", "1", "--name", "color contour"],
        )
        assert result.exit_code == 1
        assert path.read_bytes() == before

    def test_unknown_shape_rejected_without_write(self, cli_deps, tmp_path: Path) -> None:
        path = tmp_path / "bare.svg"
        path.write_text(BARE_HEX, encoding="utf-8")
        before = path.read_bytes()
        result = CliRunner().invoke(
            app,
            ["template", "set-placeholder", str(path), "--shape", "99", "--name", "COLOR_TEST"],
        )
        assert result.exit_code == 1
        assert path.read_bytes() == before


class TestRoundTripRealTemplates:
    def test_all_templates_round_trip(self, cli_deps, tmp_path: Path) -> None:
        template_root = _worktree_root() / "dotfiles" / "assets" / "icon-templates"
        assert template_root.exists(), f"template root missing: {template_root}"
        svgs = sorted(template_root.rglob("*.svg"))
        assert svgs, "no templates found"
        for svg in svgs:
            original = svg.read_bytes()
            target = tmp_path / svg.relative_to(template_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original)
            original_text = original.decode("utf-8")

            payload = _analyze_json(target)
            shapes_before = payload["shapes"]
            if not shapes_before:
                assert payload["mode"] == "bare"
                continue
            # A shape that paints via an inherited attribute (from the root
            # <svg> or a <g>) carries no own paint attribute to rewrite; the
            # write contract rejects it, so skip these templates like
            # zero-shape files.
            service = TemplateAnalysisService()
            shape1, element1 = next(
                (s, el) for s, el in service.extract_with_elements(original_text) if s.shape_id == 1
            )
            if attr_value(element1, shape1.paint_attr) is None:
                continue

            result = CliRunner().invoke(
                app,
                [
                    "template",
                    "set-placeholder",
                    str(target),
                    "--shape",
                    "1",
                    "--name",
                    "COLOR_TEST",
                ],
            )
            assert result.exit_code == 0, f"{svg}: {result.stderr}"

            new_text = target.read_bytes().decode("utf-8")
            payload_after = _analyze_json(target)
            shapes_after = payload_after["shapes"]
            assert shapes_after[0]["placeholder"] == "COLOR_TEST"
            assert shapes_after[0]["literal"] is None
            assert len(shapes_after) == len(shapes_before)
            for before, after in zip(shapes_before[1:], shapes_after[1:]):
                assert after["placeholder"] == before["placeholder"]
                assert after["literal"] == before["literal"]
                assert after["paint_attr"] == before["paint_attr"]
                assert after["tag"] == before["tag"]
            assert new_text == _expected_after_set(original_text, shapes_before[0]), (
                f"unexpected bytes for {svg}"
            )
