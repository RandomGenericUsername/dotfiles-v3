from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from icon_templates_renderer.domain.enums import Verbosity
from icon_templates_renderer.domain.models import (
    AppSettings,
    ColorScheme,
    ListResult,
    OutputSettings,
    RenderResult,
    ValidateResult,
)

COLORS_YAML = """special:
  background: "#1a1a2e"
colors:
  - "#1a1a2e"
"""


@pytest.fixture
def scheme_fixture() -> ColorScheme:
    return ColorScheme.from_dict({"background": "#1a1a2e"})


@pytest.fixture
def settings_fixture() -> AppSettings:
    return AppSettings(output=OutputSettings(verbosity=Verbosity.NORMAL))


@pytest.fixture
def render_result_fixture() -> RenderResult:
    return RenderResult(success=True)


@pytest.fixture
def list_result_fixture() -> ListResult:
    return ListResult(groups=(("battery", ("battery-0",)),), single=False)


@pytest.fixture
def validate_result_fixture() -> ValidateResult:
    return ValidateResult(ok=True, checked_groups=1, checked_variants=1)


@pytest.fixture
def icons_yaml_text() -> str:
    return (
        "battery:\n"
        f"  color_scheme: {COLORS_YAML!r}\n"
        "  template_dir: templates/\n"
        "  output_dir: out/\n"
        "  variants:\n"
        "    - name: battery-0\n"
        "      template: battery-0.svg\n"
        "      output: battery-0.svg\n"
    )


@pytest.fixture
def tmp_icons_yaml(tmp_path: Path) -> Path:
    path = tmp_path / "icons.yaml"
    path.write_text(
        "battery:\n"
        "  color_scheme: colors.yaml\n"
        "  template_dir: templates/\n"
        "  output_dir: out/\n"
        "  variants:\n"
        "    - name: battery-0\n"
        "      template: battery-0.svg\n"
        "      output: battery-0.svg\n"
    )
    return path


def assert_isinstance(impl: object, port: type) -> None:
    assert isinstance(impl, port), (
        f"{type(impl).__name__} is not an instance of {port.__name__}. "
        f"Missing or incorrectly named methods detected by structural subtyping."
    )


def assert_signature_compatible(impl: object, port: type) -> None:
    port_methods = {
        name: fn
        for name, fn in inspect.getmembers(port, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    impl_methods = {
        name: fn
        for name, fn in inspect.getmembers(type(impl), predicate=inspect.isfunction)
        if not name.startswith("_")
    }

    for method_name, port_fn in port_methods.items():
        assert method_name in impl_methods, (
            f"{type(impl).__name__} is missing method '{method_name}' (defined in {port.__name__})"
        )
        impl_fn = impl_methods[method_name]
        port_sig = inspect.signature(port_fn)
        impl_sig = inspect.signature(impl_fn)

        port_params = [p for p in port_sig.parameters.values() if p.name != "self"]
        impl_params = [p for p in impl_sig.parameters.values() if p.name != "self"]

        assert len(port_params) <= len(impl_params), (
            f"Parameter count too low for '{method_name}': "
            f"{port.__name__} needs {len(port_params)}, "
            f"{type(impl).__name__} has {len(impl_params)}"
        )

        for p_impl in impl_params[len(port_params) :]:
            assert p_impl.default is not inspect.Parameter.empty, (
                f"Extra parameter '{p_impl.name}' in '{method_name}' "
                f"of {type(impl).__name__} must have a default value"
            )

        for p_port, p_impl in zip(port_params, impl_params):
            assert p_port.name == p_impl.name, (
                f"Parameter name mismatch in '{method_name}': "
                f"expected '{p_port.name}', got '{p_impl.name}'"
            )
            assert p_port.kind == p_impl.kind, (
                f"Parameter kind mismatch for '{p_port.name}' in '{method_name}'"
            )

        port_return = port_sig.return_annotation
        impl_return = impl_sig.return_annotation
        if port_return is not inspect.Parameter.empty:
            assert impl_return is not inspect.Parameter.empty, (
                f"Return annotation missing in '{method_name}' of {type(impl).__name__}"
            )


def assert_interface_method_count(impl: object, port: type) -> None:
    port_public_methods = {
        name
        for name, fn in inspect.getmembers(port, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    impl_public_methods = {
        name
        for name, fn in inspect.getmembers(type(impl), predicate=inspect.isfunction)
        if not name.startswith("_")
    }

    missing = port_public_methods - impl_public_methods
    assert not missing, f"{type(impl).__name__} is missing methods: {missing}"
