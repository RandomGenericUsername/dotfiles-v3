from __future__ import annotations

import pytest
from pydantic import ValidationError

from color_scheme_generator.adapters.schemas.backends_catalog_schema import (
    BackendDefinitionSchema,
    BackendParameterSchema,
    BackendsCatalogSchema,
)


class TestBackendsCatalogSchema:
    def test_valid_yaml_with_three_backends(self) -> None:
        data = {
            "custom": {
                "description": "Custom backend",
                "display_name": "Custom",
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
            "pywal": {
                "description": "Pywal backend",
                "display_name": "Pywal",
                "parameters": [
                    {
                        "key": "algorithm",
                        "param_type": "str",
                        "default": "wal",
                        "choices": ["auto", "wal"],
                        "description": "Algorithm",
                        "required": True,
                    },
                ],
            },
            "wallust": {
                "description": "Wallust backend",
                "display_name": "Wallust",
                "parameters": [
                    {
                        "key": "algorithm",
                        "param_type": "str",
                        "default": "kmeans",
                        "choices": [
                            "kmeans",
                            "kmeans-new",
                        ],
                        "description": "Algorithm",
                        "required": True,
                    },
                ],
            },
        }
        schema = BackendsCatalogSchema.model_validate(data)
        assert isinstance(schema, BackendsCatalogSchema)
        assert len(schema.root) == 3
        for name in ("custom", "pywal", "wallust"):
            assert name in schema.root
            backend = schema.root[name]
            assert isinstance(backend, BackendDefinitionSchema)

    def test_backend_parameter_schema_fields(self) -> None:
        data = {
            "test_backend": {
                "parameters": [
                    {
                        "key": "test_param",
                        "param_type": "int",
                        "default": 42,
                        "min": 0,
                        "max": 100,
                        "choices": None,
                        "description": "A test parameter",
                        "required": True,
                    },
                ],
            },
        }
        schema = BackendsCatalogSchema.model_validate(data)
        param = schema.root["test_backend"].parameters[0]
        assert isinstance(param, BackendParameterSchema)
        assert param.key == "test_param"
        assert param.param_type == "int"
        assert param.default == 42
        assert param.min == 0
        assert param.max == 100
        assert param.choices is None
        assert param.description == "A test parameter"
        assert param.required is True


class TestBackendParameterSchema:
    def test_valid_param_types(self) -> None:
        for pt in ("float", "int", "str"):
            schema = BackendParameterSchema(key="p", param_type=pt)
            assert schema.param_type == pt

    def test_invalid_param_type_raises(self) -> None:
        with pytest.raises(ValidationError, match="param_type"):
            BackendParameterSchema(key="p", param_type="bool")

    def test_invalid_param_type_message_includes_valid_types(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            BackendParameterSchema(key="p", param_type="list")
        error_msg = str(excinfo.value)
        assert "float" in error_msg
        assert "int" in error_msg
        assert "str" in error_msg

    def test_default_values(self) -> None:
        schema = BackendParameterSchema(key="p", param_type="str")
        assert schema.default is None
        assert schema.min is None
        assert schema.max is None
        assert schema.choices is None
        assert schema.description == ""
        assert schema.required is False

    def test_choices_as_list(self) -> None:
        schema = BackendParameterSchema(
            key="algo", param_type="str", choices=["a", "b", "c"]
        )
        assert schema.choices == ["a", "b", "c"]


class TestBackendsCatalogSchemaValidation:
    def test_missing_required_key_raises(self) -> None:
        with pytest.raises(ValidationError):
            BackendParameterSchema(param_type="str")
