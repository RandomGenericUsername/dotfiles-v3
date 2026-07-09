from __future__ import annotations

from pathlib import Path

import pytest

from wallpaper_effects_generator.adapters.output.plain_output import PlainOutputAdapter
from wallpaper_effects_generator.domain.enums import CatalogQuery
from wallpaper_effects_generator.domain.models import (
    BatchResult,
    EffectsCatalog,
    ProcessingResult,
)
from wallpaper_effects_generator.ports.output import OutputPort


class TestPlainOutputAdapter:
    @pytest.fixture
    def adapter(self) -> PlainOutputAdapter:
        return PlainOutputAdapter()

    def test_implements_output_port(self, adapter: PlainOutputAdapter) -> None:
        assert isinstance(adapter, OutputPort)

    def test_process_result_success(self, adapter: PlainOutputAdapter, capsys) -> None:
        result = ProcessingResult(
            success=True,
            command="magick in.png out.png",
            stdout="ok",
            stderr="",
            return_code=0,
            duration=1.5,
            output_path=Path("/out/img.png"),
        )
        adapter.process_result(result)
        captured = capsys.readouterr()
        assert "status: success" in captured.out
        assert "command: magick in.png out.png" in captured.out
        assert "stdout: ok" in captured.out
        assert "output_path: /out/img.png" in captured.out
        assert "duration: 1.50s" in captured.out
        assert captured.err == ""

    def test_process_result_failure(self, adapter: PlainOutputAdapter, capsys) -> None:
        result = ProcessingResult(
            success=False,
            command="magick in.png out.png",
            stdout="",
            stderr="error occurred",
            return_code=1,
        )
        adapter.process_result(result)
        captured = capsys.readouterr()
        assert "status: failure" in captured.out
        assert "stderr: error occurred" in captured.out
        assert "return_code: 1" in captured.out

    def test_batch_result(self, adapter: PlainOutputAdapter, capsys) -> None:
        results = (
            ProcessingResult(success=True, command="cmd1", stdout="", stderr="", return_code=0),
            ProcessingResult(success=False, command="cmd2", stdout="", stderr="err", return_code=1),
        )
        batch = BatchResult(
            total=2, succeeded=1, failed=1, results=results, output_dir=Path("/out")
        )
        adapter.batch_result(batch)
        captured = capsys.readouterr()
        assert "total: 2" in captured.out
        assert "succeeded: 1" in captured.out
        assert "failed: 1" in captured.out
        assert "output_dir: /out" in captured.out
        assert "status: success" in captured.out
        assert "status: failure" in captured.out

    def test_catalog_list(self, adapter: PlainOutputAdapter, capsys) -> None:
        catalog = EffectsCatalog()
        adapter.catalog_list(catalog, CatalogQuery.EFFECT)
        captured = capsys.readouterr()
        assert captured.out == "\n"

    def test_error(self, adapter: PlainOutputAdapter, capsys) -> None:
        exc = ValueError("bad value")
        adapter.error(exc)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "error: ValueError: bad value" in captured.err

    def test_message(self, adapter: PlainOutputAdapter, capsys) -> None:
        adapter.message("hello")
        captured = capsys.readouterr()
        assert captured.out == "hello\n"

    def test_no_ansi_codes(self, adapter: PlainOutputAdapter, capsys) -> None:
        result = ProcessingResult(
            success=True,
            command="magick in.png out.png",
            stdout="",
            stderr="",
            return_code=0,
        )
        adapter.process_result(result)
        captured = capsys.readouterr()
        assert "\x1b[" not in captured.out
