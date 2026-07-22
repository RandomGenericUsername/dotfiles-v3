from __future__ import annotations

from unittest.mock import MagicMock

from color_scheme_generator.adapters.dry_run_processor import DryRunProcessor
from color_scheme_generator.ports.processor import ColorSchemeProcessorPort


class TestDryRunProcessorStub:
    def test_isinstance_check_passes(self) -> None:
        processor = DryRunProcessor(
            backend_catalog_loader=MagicMock(),
            output_adapter=MagicMock(),
        )

        assert isinstance(processor, ColorSchemeProcessorPort)
