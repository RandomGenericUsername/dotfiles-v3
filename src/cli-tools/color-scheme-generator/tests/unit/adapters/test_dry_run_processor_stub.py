from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from color_scheme_generator.adapters.dry_run_processor import DryRunProcessor
from color_scheme_generator.ports.processor import ColorSchemeProcessorPort


class TestDryRunProcessorStub:
    def test_isinstance_check_passes(self) -> None:
        processor = DryRunProcessor()

        assert isinstance(processor, ColorSchemeProcessorPort)

    def test_process_generate_raises_not_implemented(self) -> None:
        processor = DryRunProcessor()

        with pytest.raises(NotImplementedError, match="story 4.1"):
            processor.process_generate(MagicMock(), MagicMock())

    def test_process_show_raises_not_implemented(self) -> None:
        processor = DryRunProcessor()

        with pytest.raises(NotImplementedError, match="story 4.1"):
            processor.process_show(MagicMock(), MagicMock())
