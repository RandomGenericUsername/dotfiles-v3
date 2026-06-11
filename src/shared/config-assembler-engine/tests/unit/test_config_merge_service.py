from config_assembler_engine.domain.models import OverrideSource, OverrideValue
from config_assembler_engine.domain.services import ConfigMergeService


class TestConfigMergeService:
    def test_flat_field_override(self):
        base = {"timeout": 30, "engine": "docker"}
        ov = OverrideValue(field_path="timeout", raw_value="60", source=OverrideSource.CLI)
        result = ConfigMergeService.apply(base, ov, 60)
        assert result == {"timeout": 60, "engine": "docker"}

    def test_nested_field_override(self):
        base = {"map": {"host": "localhost", "port": 8080}}
        ov = OverrideValue(field_path="map.host", raw_value="example.com", source=OverrideSource.ENV)
        result = ConfigMergeService.apply(base, ov, "example.com")
        assert result == {"map": {"host": "example.com", "port": 8080}}

    def test_deeply_nested_create_path(self):
        base = {}
        ov = OverrideValue(field_path="a.b.c", raw_value="val", source=OverrideSource.ENV)
        result = ConfigMergeService.apply(base, ov, "val")
        assert result == {"a": {"b": {"c": "val"}}}

    def test_partial_nested_override(self):
        base = {"a": {"b": 1}}
        ov = OverrideValue(field_path="a.b", raw_value="2", source=OverrideSource.CLI)
        result = ConfigMergeService.apply(base, ov, 2)
        assert result == {"a": {"b": 2}}

    def test_does_not_mutate_original(self):
        base = {"timeout": 30}
        ov = OverrideValue(field_path="timeout", raw_value="60", source=OverrideSource.CLI)
        result = ConfigMergeService.apply(base, ov, 60)
        assert base == {"timeout": 30}
        assert result == {"timeout": 60}
        assert result is not base

    def test_adds_new_field(self):
        base = {"timeout": 30}
        ov = OverrideValue(field_path="engine", raw_value="podman", source=OverrideSource.CLI)
        result = ConfigMergeService.apply(base, ov, "podman")
        assert result == {"timeout": 30, "engine": "podman"}

    def test_raises_type_error_on_non_dict_intermediate(self):
        base = {"a": "not_a_dict"}
        ov = OverrideValue(field_path="a.b", raw_value="val", source=OverrideSource.ENV)
        try:
            ConfigMergeService.apply(base, ov, "val")
            assert False, "Expected TypeError"
        except TypeError as e:
            assert "a" in str(e)

    def test_deep_nested_partial_path_exists(self):
        base = {"x": {"y": {"z": 1}}}
        ov = OverrideValue(field_path="x.y.z", raw_value="2", source=OverrideSource.CLI)
        result = ConfigMergeService.apply(base, ov, 2)
        assert result == {"x": {"y": {"z": 2}}}
