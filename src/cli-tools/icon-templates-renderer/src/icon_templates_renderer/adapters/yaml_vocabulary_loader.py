from __future__ import annotations

from pathlib import Path

import yaml

from icon_templates_renderer.domain.exceptions import InvalidYamlError
from icon_templates_renderer.domain.models import Vocabulary


class YamlVocabularyLoader:
    def load(self, path: Path | None) -> Vocabulary:
        """Load vocabulary defaults from path. Returns empty Vocabulary if file absent."""
        if path is None:
            return Vocabulary.from_dict({})
        if not path.exists():
            return Vocabulary.from_dict({})
        with path.open() as f:
            try:
                data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise InvalidYamlError(f"Failed to parse vocabulary file: {e}") from e
        if not isinstance(data, dict) or "defaults" not in data:
            raise InvalidYamlError(f"Vocabulary file must contain a 'defaults' mapping: {path}")
        defaults = data["defaults"]
        if not defaults:
            return Vocabulary.from_dict({})
        if not isinstance(defaults, dict):
            raise InvalidYamlError("'defaults' must be a mapping of placeholder names to tokens")
        return Vocabulary.from_dict({str(k): str(v) for k, v in defaults.items()})
