from __future__ import annotations

from pathlib import Path

import pytest
from rich.console import Console

from wallpaper_effects_generator.adapters.output.rich_output import RichOutputAdapter
from wallpaper_effects_generator.domain.models import (
    BatchResult,
    ProcessingResult,
)
from wallpaper_effects_generator.ports.output import OutputPort


class TestRichOutputAdapter:
    @pytest.fixture
    def adapter(self) -> RichOutputAdapter:
        return RichOutputAdapter(console=Console(width=200))

    def test_implements_output_port(self, adapter: RichOutputAdapter) -> None:
        assert isinstance(adapter, OutputPort)

    def test_process_result_success(self, adapter: RichOutputAdapter, capsys) -> None:
        result = ProcessingResult(
            success=True,
            command="magick in.png out.png",
            stdout="",
            stderr="",
            return_code=0,
            duration=1.5,
            output_path=Path("/out/img.png"),
        )
        adapter.process_result(result)
        captured = capsys.readouterr()
        assert "Success" in captured.out
        assert "magick in.png out.png" in captured.out
        assert "Output" in captured.out
        assert "/out/img.png" in captured.out
        assert "Duration" in captured.out

    def test_process_result_failure(self, adapter: RichOutputAdapter, capsys) -> None:
        result = ProcessingResult(
            success=False,
            command="magick in.png out.png",
            stdout="",
            stderr="error occurred",
            return_code=1,
        )
        adapter.process_result(result)
        captured = capsys.readouterr()
        assert "Failed" in captured.out
        assert "stderr" in captured.out
        assert "error occurred" in captured.out

    def test_batch_result_all_success(self, adapter: RichOutputAdapter, capsys) -> None:
        results = (
            ProcessingResult(success=True, command="cmd1", stdout="", stderr="", return_code=0),
            ProcessingResult(success=True, command="cmd2", stdout="", stderr="", return_code=0),
        )
        batch = BatchResult(total=2, succeeded=2, failed=0, results=results)
        adapter.batch_result(batch)
        captured = capsys.readouterr()
        assert "Batch" in captured.out
        assert "2/2" in captured.out

    def test_error(self, adapter: RichOutputAdapter, capsys) -> None:
        exc = ValueError("bad value")
        adapter.error(exc)
        captured = capsys.readouterr()
        assert "Error" in captured.out
        assert "ValueError" in captured.out
        assert "bad value" in captured.out

    def test_message(self, adapter: RichOutputAdapter, capsys) -> None:
        adapter.message("hello world")
        captured = capsys.readouterr()
        assert "hello world" in captured.out

    def test_dump_config_template(self, adapter: RichOutputAdapter, capsys) -> None:
        content = 'version = "1.0"\n[execution]\n'
        adapter.dump_config_template(content)
        captured = capsys.readouterr()
        assert captured.out == content

    def test_dump_effects_template(self, adapter: RichOutputAdapter, capsys) -> None:
        content = "version: '1.0'\neffects: []\n"
        adapter.dump_effects_template(content)
        captured = capsys.readouterr()
        assert captured.out == content
