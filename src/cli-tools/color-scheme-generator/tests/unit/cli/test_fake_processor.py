from __future__ import annotations

from color_scheme_generator.ports.processor import ColorSchemeProcessorPort
from tests.conftest import FakeProcessor


class TestFakeProcessor:
    def test_fake_processor_is_protocol_conformant(self) -> None:
        assert isinstance(FakeProcessor(), ColorSchemeProcessorPort)
