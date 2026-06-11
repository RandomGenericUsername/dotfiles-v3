from config_assembler_engine.domain.models import OverrideRule, OverrideSource, OverrideValue
from config_assembler_engine.domain.services import OverrideMatchingService


class TestOverrideMatchingService:
    def test_empty_inputs(self):
        result = OverrideMatchingService.match({}, {}, [])
        assert result == []

    def test_env_var_matches_rule(self):
        rules = [OverrideRule(field_path="timeout", sources={OverrideSource.ENV})]
        result = OverrideMatchingService.match({"timeout": "30"}, {}, rules)
        assert len(result) == 1
        assert result[0].field_path == "timeout"
        assert result[0].raw_value == "30"
        assert result[0].source == OverrideSource.ENV

    def test_env_var_no_matching_rule(self):
        rules = [OverrideRule(field_path="engine", sources={OverrideSource.ENV})]
        result = OverrideMatchingService.match({"timeout": "30"}, {}, rules)
        assert result == []

    def test_env_var_rule_disallows_env(self):
        rules = [OverrideRule(field_path="timeout", sources={OverrideSource.CLI})]
        result = OverrideMatchingService.match({"timeout": "30"}, {}, rules)
        assert result == []

    def test_cli_override_matches_rule(self):
        rules = [OverrideRule(field_path="engine", sources={OverrideSource.CLI})]
        result = OverrideMatchingService.match({}, {"engine": "podman"}, rules)
        assert len(result) == 1
        assert result[0].field_path == "engine"
        assert result[0].raw_value == "podman"
        assert result[0].source == OverrideSource.CLI

    def test_cli_override_no_matching_rule(self):
        rules = [OverrideRule(field_path="engine", sources={OverrideSource.CLI})]
        result = OverrideMatchingService.match({}, {"timeout": "30"}, rules)
        assert result == []

    def test_cli_override_rule_disallows_cli(self):
        rules = [OverrideRule(field_path="timeout", sources={OverrideSource.ENV})]
        result = OverrideMatchingService.match({}, {"timeout": "30"}, rules)
        assert result == []

    def test_env_var_nested_path_with_separator(self):
        rules = [OverrideRule(field_path="map.host", sources={OverrideSource.ENV})]
        result = OverrideMatchingService.match({"map__host": "localhost"}, {}, rules)
        assert len(result) == 1
        assert result[0].field_path == "map.host"
        assert result[0].raw_value == "localhost"

    def test_both_sources(self):
        rules = [
            OverrideRule(field_path="timeout", sources={OverrideSource.ENV, OverrideSource.CLI}),
        ]
        result = OverrideMatchingService.match({"timeout": "30"}, {"timeout": "60"}, rules)
        assert len(result) == 2
        assert result[0].source == OverrideSource.ENV
        assert result[1].source == OverrideSource.CLI

    def test_multiple_rules(self):
        rules = [
            OverrideRule(field_path="timeout", sources={OverrideSource.ENV}),
            OverrideRule(field_path="engine", sources={OverrideSource.CLI}),
        ]
        result = OverrideMatchingService.match({"timeout": "30"}, {"engine": "podman"}, rules)
        assert len(result) == 2
        assert result[0].field_path == "timeout"
        assert result[1].field_path == "engine"

    def test_unknown_env_var_ignored(self):
        rules = [OverrideRule(field_path="timeout", sources={OverrideSource.ENV})]
        result = OverrideMatchingService.match(
            {"timeout": "30", "other": "val"}, {}, rules
        )
        assert len(result) == 1
        assert result[0].field_path == "timeout"

    def test_unknown_cli_override_ignored(self):
        rules = [OverrideRule(field_path="timeout", sources={OverrideSource.CLI})]
        result = OverrideMatchingService.match(
            {}, {"timeout": "30", "other": "val"}, rules
        )
        assert len(result) == 1
        assert result[0].field_path == "timeout"
