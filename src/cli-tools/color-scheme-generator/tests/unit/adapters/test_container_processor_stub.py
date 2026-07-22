from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from color_scheme_generator.adapters.container_processor import ContainerProcessor
from color_scheme_generator.ports.processor import ColorSchemeProcessorPort


class TestContainerProcessorStub:
    def test_isinstance_check_passes(self) -> None:
        mock_runtime = MagicMock()
        processor = ContainerProcessor(mock_runtime)

        assert isinstance(processor, ColorSchemeProcessorPort)

    def test_process_generate_raises_not_implemented(self) -> None:
        mock_runtime = MagicMock()
        processor = ContainerProcessor(mock_runtime)

        with pytest.raises(NotImplementedError, match="story 3.2"):
            processor.process_generate(MagicMock(), MagicMock())

    def test_process_show_raises_not_implemented(self) -> None:
        mock_runtime = MagicMock()
        processor = ContainerProcessor(mock_runtime)

        with pytest.raises(NotImplementedError, match="story 3.2"):
            processor.process_show(MagicMock(), MagicMock())
