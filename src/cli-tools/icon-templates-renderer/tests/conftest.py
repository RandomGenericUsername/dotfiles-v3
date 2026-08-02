from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from icon_templates_renderer.domain.models import (
    ListRequest,
    ListResult,
    RenderRequest,
    RenderResult,
    ValidateRequest,
    ValidateResult,
)
from icon_templates_renderer.factory import CliDependencies


@dataclass
class FakeIconRenderer:
    calls: list[dict[str, Any]] = field(default_factory=list)
    render_error: Exception | None = None
    list_error: Exception | None = None
    validate_error: Exception | None = None

    def render(self, request: RenderRequest) -> RenderResult:
        self.calls.append({"command": "render", "request": request})
        if self.render_error is not None:
            raise self.render_error
        return RenderResult(success=True)

    def list(self, request: ListRequest) -> ListResult:
        self.calls.append({"command": "list", "request": request})
        if self.list_error is not None:
            raise self.list_error
        return ListResult(groups=(("battery", ("battery-0",)),), single=False)

    def validate(self, request: ValidateRequest) -> ValidateResult:
        self.calls.append({"command": "validate", "request": request})
        if self.validate_error is not None:
            raise self.validate_error
        return ValidateResult(ok=True, checked_groups=1, checked_variants=1)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def fake_icon_renderer() -> FakeIconRenderer:
    return FakeIconRenderer()


@pytest.fixture
def cli_deps_with_renderer(
    monkeypatch: pytest.MonkeyPatch,
    fake_icon_renderer: FakeIconRenderer,
) -> CliDependencies:
    deps = CliDependencies(icon_renderer=fake_icon_renderer)
    monkeypatch.setattr("icon_templates_renderer.cli.main.build_deps", lambda: deps)
    return deps


@pytest.fixture
def colors_yaml(tmp_path: Path) -> Path:
    path = tmp_path / "colors.yaml"
    path.write_text(
        "special:\n"
        '  background: "#1a1a2e"\n'
        '  foreground: "#e0e0e0"\n'
        '  cursor: "#e0e0e0"\n'
        "colors:\n"
        '  - "#1a1a2e"\n'
        '  - "#e94560"\n'
    )
    return path


@pytest.fixture
def colors_json(tmp_path: Path) -> Path:
    path = tmp_path / "colors.json"
    path.write_text(
        "{\n"
        '  "special": {"background": "#aabbcc", "foreground": "#ddeeff"},\n'
        '  "colors": {"color0": "#aabbcc", "color5": "#112233"}\n'
        "}\n"
    )
    return path


@pytest.fixture
def svg_template(tmp_path: Path, name: str = "battery-0.svg") -> Path:
    path = tmp_path / "templates" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('<svg><path fill="{{background}}" stroke="{{foreground}}"/></svg>')
    return path


@pytest.fixture
def icons_yaml(tmp_path: Path, colors_yaml: Path, svg_template: Path) -> Path:
    path = tmp_path / "icons.yaml"
    path.write_text(
        "battery:\n"
        f"  color_scheme: {colors_yaml}\n"
        "  template_dir: templates/\n"
        "  output_dir: out/battery/\n"
        "  color_mappings:\n"
        "    background: background\n"
        "    foreground: foreground\n"
        "  variants:\n"
        f"    - name: battery-0\n"
        f"      template: {svg_template.name}\n"
        "      output: battery-0.svg\n"
    )
    return path
