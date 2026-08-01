from __future__ import annotations

from pathlib import Path
from unittest.mock import create_autospec

import pytest
from config_assembler_engine.application.use_cases import AssembleConfiguration
from config_assembler_engine.domain.models import (
    AppliedOverride,
    AssemblyResult,
    OverrideSource,
    PathSource,
    ResolvedPath,
)

from color_scheme_generator.adapters.schemas.backends_catalog_schema import BackendsCatalogSchema
from color_scheme_generator.adapters.yaml_backend_catalog_loader import YamlBackendCatalogLoader
from color_scheme_generator.domain.enums import Backend
from color_scheme_generator.domain.exceptions import ConfigResolutionError
from color_scheme_generator.domain.models import BackendDefinition
from color_scheme_generator.ports.backend_catalog_loader import BackendCatalogLoaderPort


def _make_assembly_result() -> AssemblyResult:
    data = {
        "custom": {
            "display_name": "Custom",
            "description": "Custom backend",
            "parameters": [
                {
                    "key": "saturation",
                    "param_type": "float",
                    "default": 1.0,
                    "min": 0.0,
                    "max": 2.0,
                    "description": "Saturation factor",
                    "required": False,
                },
            ],
        },
    }
    return AssemblyResult(
        config=BackendsCatalogSchema.model_validate(data),
        resolved_path=ResolvedPath(path=Path("/tmp/backends.yaml"), source=PathSource.CLI_PATH),
        applied_overrides=[
            AppliedOverride(
                field_path="custom.display_name",
                raw_value="MyCustom",
                coerced_value="MyCustom",
                source=OverrideSource.CLI,
            ),
        ],
    )


class TestYamlBackendCatalogLoader:
    def test_implements_backend_catalog_loader_port(self) -> None:
        loader = YamlBackendCatalogLoader()
        assert isinstance(loader, BackendCatalogLoaderPort)

    def test_load_returns_dict_with_backend_keys(self) -> None:
        mock_assembler = create_autospec(AssembleConfiguration, instance=True)
        mock_assembler.execute.return_value = _make_assembly_result()

        loader = YamlBackendCatalogLoader(assembler=mock_assembler)
        result = loader.load()

        assert isinstance(result, dict)
        assert Backend.CUSTOM in result
        assert isinstance(result[Backend.CUSTOM], BackendDefinition)

    def test_load_returns_correct_domain_values(self) -> None:
        mock_assembler = create_autospec(AssembleConfiguration, instance=True)
        mock_assembler.execute.return_value = _make_assembly_result()

        loader = YamlBackendCatalogLoader(assembler=mock_assembler)
        result = loader.load()

        custom = result[Backend.CUSTOM]
        assert custom.backend == Backend.CUSTOM
        assert custom.display_name == "Custom"
        assert custom.description == "Custom backend"
        assert len(custom.parameters) == 1
        param = custom.parameters[0]
        assert param.name == "saturation"
        assert param.type_ == "float"
        assert param.default == 1.0

    def test_load_passes_correct_schema_and_policy(self) -> None:
        mock_assembler = create_autospec(AssembleConfiguration, instance=True)
        mock_assembler.execute.return_value = _make_assembly_result()

        loader = YamlBackendCatalogLoader(assembler=mock_assembler)
        loader.load()

        _, kwargs = mock_assembler.execute.call_args
        assert kwargs["schema"] == BackendsCatalogSchema
        assert kwargs["policy"].env_prefix == "COLORSCHEME_BACKENDS"
        assert kwargs["rules"] == []

    def test_load_raises_config_resolution_error_on_config_parse_error(self) -> None:
        from config_assembler_engine.errors import ConfigParseError

        mock_assembler = create_autospec(AssembleConfiguration, instance=True)
        mock_assembler.execute.side_effect = ConfigParseError("bad yaml")

        loader = YamlBackendCatalogLoader(assembler=mock_assembler)
        with pytest.raises(ConfigResolutionError) as excinfo:
            loader.load()
        assert "backends.yaml" in str(excinfo.value.key)

    def test_load_raises_config_resolution_error_on_path_resolution_error(self) -> None:
        from config_assembler_engine.errors import PathResolutionError

        mock_assembler = create_autospec(AssembleConfiguration, instance=True)
        mock_assembler.execute.side_effect = PathResolutionError("not found")

        loader = YamlBackendCatalogLoader(assembler=mock_assembler)
        with pytest.raises(ConfigResolutionError) as excinfo:
            loader.load()
        assert "backends.yaml" in str(excinfo.value.key)


class TestYamlBackendCatalogLoaderIntegration:
    def test_load_default_bundled_backends_yaml(self, tmp_path: Path) -> None:
        backends_yaml = tmp_path / "backends.yaml"
        backends_yaml.write_text("""\
custom:
  description: Custom backend
  display_name: Custom
  parameters:
    - key: saturation
      param_type: float
      default: 1.0
      min: 0.0
      max: 2.0
      description: Saturation factor
      required: false
    - key: algorithm
      param_type: str
      default: kmeans
      choices: [kmeans]
      description: Algorithm
      required: false

pywal:
  description: Pywal backend
  display_name: Pywal
  parameters:
    - key: saturation
      param_type: float
      default: 1.0
      min: 0.0
      max: 2.0
      description: Saturation factor
      required: false

wallust:
  description: Wallust backend
  display_name: Wallust
  parameters:
    - key: algorithm
      param_type: str
      default: kmeans
      choices: [kmeans, kmeans-new]
      description: Algorithm
      required: false
""")

        loader = YamlBackendCatalogLoader()
        result = loader.load(explicit_path=str(backends_yaml))

        assert len(result) == 3
        assert Backend.CUSTOM in result
        assert Backend.PYWAL in result
        assert Backend.WALLUST in result

        custom = result[Backend.CUSTOM]
        assert custom.backend == Backend.CUSTOM
        assert len(custom.parameters) == 2
        assert custom.parameters[0].name == "saturation"


class TestMinVersionRoundTrip:
    def test_min_version_round_trips_when_declared(self, tmp_path: Path) -> None:
        backends_yaml = tmp_path / "backends.yaml"
        backends_yaml.write_text("""\
custom:
  description: Custom backend
  display_name: Custom
  min_version: "1.2.3"
  parameters: []
""")

        loader = YamlBackendCatalogLoader()
        result = loader.load(explicit_path=str(backends_yaml))

        assert result[Backend.CUSTOM].min_version == "1.2.3"
