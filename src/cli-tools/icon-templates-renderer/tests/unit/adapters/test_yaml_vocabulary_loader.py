from __future__ import annotations

from pathlib import Path

import pytest

from icon_templates_renderer.adapters.yaml_vocabulary_loader import YamlVocabularyLoader
from icon_templates_renderer.domain.exceptions import InvalidYamlError


class TestYamlVocabularyLoader:
    def setup_method(self) -> None:
        self.loader = YamlVocabularyLoader()

    def test_absent_path_yields_empty(self) -> None:
        assert self.loader.load(None).as_dict() == {}

    def test_missing_file_yields_empty(self, tmp_path: Path) -> None:
        assert self.loader.load(tmp_path / "defaults.yaml").as_dict() == {}

    def test_defaults_mapping_is_loaded(self, tmp_path: Path) -> None:
        path = tmp_path / "defaults.yaml"
        path.write_text("defaults:\n  background: background\n  foreground: foreground\n")
        assert self.loader.load(path).as_dict() == {
            "background": "background",
            "foreground": "foreground",
        }

    def test_missing_defaults_key_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "defaults.yaml"
        path.write_text("other: {}\n")
        with pytest.raises(InvalidYamlError) as excinfo:
            self.loader.load(path)
        assert "Vocabulary file must contain a 'defaults' mapping:" in str(excinfo.value)

    def test_non_dict_defaults_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "defaults.yaml"
        path.write_text("defaults:\n  - a\n  - b\n")
        with pytest.raises(InvalidYamlError) as excinfo:
            self.loader.load(path)
        assert "'defaults' must be a mapping of placeholder names to tokens" in str(excinfo.value)

    def test_values_coerced_to_str(self, tmp_path: Path) -> None:
        path = tmp_path / "defaults.yaml"
        path.write_text("defaults:\n  num: 5\n")
        assert self.loader.load(path).as_dict() == {"num": "5"}
