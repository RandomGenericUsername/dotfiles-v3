import os

from config_assembler_engine.adapters.env_reader import OsEnvironmentReader


class TestOsEnvironmentReader:
    def test_read_matching_prefix(self, monkeypatch):
        monkeypatch.setenv("TESTAPP__TIMEOUT", "30")
        monkeypatch.setenv("TESTAPP__ENGINE", "docker")
        reader = OsEnvironmentReader()
        result = reader.read("TESTAPP")
        assert result == {"timeout": "30", "engine": "docker"}

    def test_ignores_non_matching_vars(self, monkeypatch):
        monkeypatch.setenv("TESTAPP__TIMEOUT", "30")
        monkeypatch.setenv("OTHER__KEY", "val")
        reader = OsEnvironmentReader()
        result = reader.read("TESTAPP")
        assert "other__key" not in result
        assert result == {"timeout": "30"}

    def test_nested_key_with_double_underscore(self, monkeypatch):
        monkeypatch.setenv("TESTAPP__MAP__HOST", "localhost")
        reader = OsEnvironmentReader()
        result = reader.read("TESTAPP")
        assert result == {"map__host": "localhost"}

    def test_empty_result_when_no_match(self, monkeypatch):
        monkeypatch.setenv("OTHER__KEY", "val")
        reader = OsEnvironmentReader()
        result = reader.read("TESTAPP")
        assert result == {}

    def test_lowercases_keys(self, monkeypatch):
        monkeypatch.setenv("TESTAPP__MIXED_CASE_KEY", "val")
        reader = OsEnvironmentReader()
        result = reader.read("TESTAPP")
        assert "mixed_case_key" in result
        assert result["mixed_case_key"] == "val"

    def test_prefix_with_underscore(self, monkeypatch):
        monkeypatch.setenv("MY_APP__TIMEOUT", "30")
        reader = OsEnvironmentReader()
        result = reader.read("MY_APP")
        assert result == {"timeout": "30"}
