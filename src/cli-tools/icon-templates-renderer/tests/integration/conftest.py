from __future__ import annotations

from pathlib import Path

import pytest

from icon_templates_renderer.factory import build_deps
from tests.conftest import FakeIconRenderer


@pytest.fixture
def integration_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, str]:
    """Point the three path roots at tmp_path via env (single-env axis)."""
    env = {
        "ICON_RENDERER__TEMPLATES__DIR": str(tmp_path),
        "ICON_RENDERER__COLOR_SCHEME__PATH": str(tmp_path / "colors.yaml"),
        "ICON_RENDERER__OUTPUT__OUTPUT_DIR": str(tmp_path),
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return env


@pytest.fixture
def integration_icons_yaml(tmp_path: Path) -> Path:
    """battery + network groups with real templates/colors in tmp_path.

    Uses the simplified YAML shape: relative dirs default under the global roots;
    no per-group color_scheme and no top-level roots.
    """
    colors = tmp_path / "colors.yaml"
    colors.write_text(
        "metadata:\n"
        '  source_image: "/tmp/test.png"\n'
        '  backend: "test"\n'
        '  generated_at: "2026-02-17T00:00:00"\n'
        "special:\n"
        '  background: "#1a1a2e"\n'
        '  foreground: "#e0e0e0"\n'
        '  cursor: "#e0e0e0"\n'
        "colors:\n"
        '  - "#1a1a2e"\n'
        '  - "#e94560"\n'
        '  - "#0f3460"\n'
        '  - "#533483"\n'
        '  - "#e94560"\n'
        '  - "#0f3460"\n'
        '  - "#533483"\n'
        '  - "#e0e0e0"\n'
        '  - "#16213e"\n'
        '  - "#e94560"\n'
        '  - "#0f3460"\n'
        '  - "#533483"\n'
        '  - "#e94560"\n'
        '  - "#0f3460"\n'
        '  - "#533483"\n'
        '  - "#e0e0e0"\n'
    )

    battery_dir = tmp_path / "battery"
    battery_dir.mkdir(parents=True)
    (battery_dir / "battery-0.svg").write_text(
        '<svg width="24" height="24"><path fill="{{background}}" stroke="{{foreground}}"/></svg>'
    )
    (battery_dir / "battery-100.svg").write_text(
        '<svg width="24" height="24"><path fill="{{foreground}}" stroke="{{background}}"/></svg>'
    )

    network_dir = tmp_path / "network"
    network_dir.mkdir(parents=True)
    (network_dir / "wifi.svg").write_text(
        '<svg width="24" height="24"><path fill="{{color0}}" stroke="{{foreground}}"/></svg>'
    )

    icons = tmp_path / "icons.yaml"
    icons.write_text(
        "battery:\n"
        "  template_dir: battery/\n"
        "  output_dir: out/battery/\n"
        "  color_mappings:\n"
        "    background: background\n"
        "    foreground: foreground\n"
        "  variants:\n"
        "    - name: battery-0\n"
        "      template: battery-0.svg\n"
        "      output: battery-0.svg\n"
        "    - name: battery-100\n"
        "      template: battery-100.svg\n"
        "      output: battery-100.svg\n"
        "network:\n"
        "  template_dir: network/\n"
        "  output_dir: out/network/\n"
        "  color_mappings:\n"
        "    color0: color0\n"
        "    foreground: foreground\n"
        "  variants:\n"
        "    - name: wifi\n"
        "      template: wifi.svg\n"
        "      output: wifi.svg\n"
    )
    return icons


@pytest.fixture
def fake_icon_renderer_integration() -> FakeIconRenderer:
    return FakeIconRenderer()


@pytest.fixture
def cli_deps_integration(monkeypatch: pytest.MonkeyPatch) -> object:
    deps = build_deps()
    monkeypatch.setattr("icon_templates_renderer.cli.main.build_deps", lambda: deps)
    return deps


def invoke(app: object, args: list[str]) -> object:
    from typer.testing import CliRunner

    return CliRunner().invoke(app, args)
