from __future__ import annotations

import inspect
from datetime import datetime
from pathlib import Path

import pytest

from color_scheme_generator.domain.enums import Backend, RuntimeMode
from color_scheme_generator.domain.models import (
    AppSettings,
    Color,
    ColorScheme,
    ContainerSettings,
    GenerationSettings,
    OutputSettings,
    RuntimeSettings,
)

_now = datetime.now()


def _scheme(overrides: object = None) -> ColorScheme:
    return ColorScheme(
        background=Color("#000000", (0, 0, 0)),
        foreground=Color("#ffffff", (255, 255, 255)),
        cursor=Color("#00ff00", (0, 255, 0)),
        colors=tuple(Color("#000000", (0, 0, 0)) for _ in range(16)),
        source_image=Path("/tmp/test.png"),
        backend=Backend.CUSTOM,
        generated_at=_now,
    )


def _settings() -> AppSettings:
    return AppSettings(
        output=OutputSettings(
            directory=Path("/tmp/output"),
            default_formats=(),
            overwrite=False,
        ),
        generation=GenerationSettings(backend=Backend.CUSTOM, default_params={}),
        runtime=RuntimeSettings(
            mode=RuntimeMode.LOCAL,
        ),
        container=ContainerSettings(
            engine="docker",
            image_prefix="csg",
            image_tag="latest",
            timeout_seconds=300,
            memory_limit="512m",
            mount_timeout_seconds=30,
        ),
    )


@pytest.fixture
def scheme_fixture() -> ColorScheme:
    return _scheme()


@pytest.fixture
def settings_fixture() -> AppSettings:
    return _settings()


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
            f"{type(impl).__name__} is missing method '{method_name}' "
            f"(defined in {port.__name__})"
        )
        impl_fn = impl_methods[method_name]
        port_sig = inspect.signature(port_fn)
        impl_sig = inspect.signature(impl_fn)

        port_params = [p for p in port_sig.parameters.values() if p.name != "self"]
        impl_params = [p for p in impl_sig.parameters.values() if p.name != "self"]

        # Port must have <= implementation params (extra impl params with defaults are allowed)
        assert len(port_params) <= len(impl_params), (
            f"Parameter count too low for '{method_name}': "
            f"{port.__name__} needs {len(port_params)}, "
            f"{type(impl).__name__} has {len(impl_params)}"
        )

        for p_impl in impl_params[len(port_params):]:
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

        # Check return annotation compatibility
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
    assert not missing, (
        f"{type(impl).__name__} is missing methods: {missing}"
    )
