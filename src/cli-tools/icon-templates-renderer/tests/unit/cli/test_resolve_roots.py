from __future__ import annotations

from pathlib import Path

import pytest

from icon_templates_renderer.cli._helpers import resolve_roots
from icon_templates_renderer.domain.exceptions import ConfigResolutionError
from icon_templates_renderer.domain.models import (
    AppSettings,
    ColorSchemeSettings,
    OutputSettings,
    TemplatesSettings,
)
from icon_templates_renderer.factory import CliDependencies


class _FakeConfigResolver:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings(
            output=OutputSettings(output_dir=Path("/default/out"))
        )
        self.calls: list[dict] = []

    def resolve(self, *, cli_overrides=None, explicit_path=None) -> AppSettings:
        self.calls.append({"cli_overrides": cli_overrides, "explicit_path": explicit_path})
        if not cli_overrides:
            return self.settings
        merged = self.settings
        tpl = cli_overrides.get("templates.dir") or (
            merged.templates.dir if merged.templates else None
        )
        cs = cli_overrides.get("color_scheme.path") or (
            merged.color_scheme.path if merged.color_scheme else None
        )
        out = cli_overrides.get("output.output_dir") or (
            merged.output.output_dir if merged.output else None
        )
        return AppSettings(
            output=OutputSettings(
                output_dir=Path(out) if out else None,
                verbosity=merged.output.verbosity,
            ),
            templates=TemplatesSettings(dir=Path(tpl) if tpl else None),
            color_scheme=ColorSchemeSettings(path=Path(cs) if cs else None),
        )

    def get_resolved_path(self) -> Path | None:
        return None


class _FakeTemplateResolver:
    def __init__(self, result: Path | None) -> None:
        self.result = result

    def resolve(self) -> Path | None:
        return self.result


class _FakeColorResolver:
    def __init__(self, result: Path | None) -> None:
        self.result = result

    def resolve(self) -> Path | None:
        return self.result


def _deps(
    config: _FakeConfigResolver | None = None,
    template: Path | None = None,
    color_scheme: Path | None = None,
) -> CliDependencies:
    return CliDependencies(
        config_resolver=config or _FakeConfigResolver(),
        template_dir_resolver=_FakeTemplateResolver(template),
        color_scheme_resolver=_FakeColorResolver(color_scheme),
    )


class TestResolveRoots:
    def test_flag_overrides_settings_and_discovery(self) -> None:
        config = _FakeConfigResolver(
            AppSettings(
                output=OutputSettings(output_dir=Path("/settings/out")),
                templates=TemplatesSettings(dir=Path("/settings/tpls")),
                color_scheme=ColorSchemeSettings(path=Path("/settings/c.yaml")),
            )
        )
        deps = _deps(config=config, template=Path("/discovery/tpls"))
        roots = resolve_roots(
            deps,
            config_flag=None,
            template_dir_flag=Path("/flag/tpls"),
            color_scheme_flag=Path("/flag/c.yaml"),
            output_dir_flag=Path("/flag/out"),
            required=True,
        )
        assert roots.template_root == Path("/flag/tpls")
        assert roots.color_scheme == Path("/flag/c.yaml")
        assert roots.output_root == Path("/flag/out")
        assert config.calls[0]["cli_overrides"] == {
            "templates.dir": str(Path("/flag/tpls")),
            "color_scheme.path": str(Path("/flag/c.yaml")),
            "output.output_dir": str(Path("/flag/out")),
        }

    def test_settings_used_when_no_flags(self) -> None:
        config = _FakeConfigResolver(
            AppSettings(
                output=OutputSettings(output_dir=Path("/settings/out")),
                templates=TemplatesSettings(dir=Path("/settings/tpls")),
                color_scheme=ColorSchemeSettings(path=Path("/settings/c.yaml")),
            )
        )
        deps = _deps(config=config, template=Path("/discovery/tpls"))
        roots = resolve_roots(deps, None, None, None, None, required=True)
        assert roots.template_root == Path("/settings/tpls")
        assert roots.color_scheme == Path("/settings/c.yaml")
        assert roots.output_root == Path("/settings/out")

    def test_discovery_used_when_settings_absent(self) -> None:
        deps = _deps(template=Path("/discovery/tpls"), color_scheme=Path("/discovery/c.yaml"))
        roots = resolve_roots(deps, None, None, None, None, required=True)
        assert roots.template_root == Path("/discovery/tpls")
        assert roots.color_scheme == Path("/discovery/c.yaml")

    def test_missing_required_templates_raises(self) -> None:
        deps = _deps(color_scheme=Path("/discovery/c.yaml"))
        with pytest.raises(ConfigResolutionError) as excinfo:
            resolve_roots(deps, None, None, None, None, required=True)
        assert excinfo.value.name == "templates_dir"

    def test_missing_required_color_scheme_raises(self) -> None:
        deps = _deps(template=Path("/discovery/tpls"))
        with pytest.raises(ConfigResolutionError) as excinfo:
            resolve_roots(deps, None, None, None, None, required=True)
        assert excinfo.value.name == "color_scheme"

    def test_list_not_required_allows_none(self) -> None:
        deps = _deps()
        roots = resolve_roots(deps, None, None, None, None, required=False)
        assert roots.template_root is None
        assert roots.color_scheme is None

    def test_config_flag_passed_to_resolver(self) -> None:
        config = _FakeConfigResolver()
        deps = _deps(config=config)
        resolve_roots(deps, Path("/custom/settings.toml"), None, None, None, required=False)
        assert config.calls[0]["explicit_path"] == "/custom/settings.toml"
