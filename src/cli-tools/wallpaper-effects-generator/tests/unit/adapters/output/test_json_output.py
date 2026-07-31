from __future__ import annotations

import json
from pathlib import Path

import pytest

from wallpaper_effects_generator.adapters.output.json_output import JsonOutputAdapter
from wallpaper_effects_generator.domain.enums import CatalogQuery
from wallpaper_effects_generator.domain.models import (
    AppSettings,
    BatchResult,
    EffectsCatalog,
    ProcessingResult,
)
from wallpaper_effects_generator.ports.output import OutputPort


class TestJsonOutputAdapter:
    @pytest.fixture
    def adapter(self) -> JsonOutputAdapter:
        return JsonOutputAdapter()

    def test_implements_output_port(self, adapter: JsonOutputAdapter) -> None:
        assert isinstance(adapter, OutputPort)

    def test_process_result_success(self, adapter: JsonOutputAdapter, capsys) -> None:
        result = ProcessingResult(
            success=True,
            command="magick input.png output.png",
            stdout="",
            stderr="",
            return_code=0,
            duration=1.5,
            output_path=Path("/out/img.png"),
        )
        adapter.process_result(result)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "success"
        assert data["command"] == "magick input.png output.png"
        assert data["return_code"] == 0
        assert data["duration"] == 1.5
        assert data["output_path"] == "/out/img.png"
        assert captured.err == ""

    def test_process_result_failure(self, adapter: JsonOutputAdapter, capsys) -> None:
        result = ProcessingResult(
            success=False,
            command="magick input.png output.png",
            stdout="",
            stderr="error occurred",
            return_code=1,
        )
        adapter.process_result(result)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "failure"
        assert data["stderr"] == "error occurred"

    def test_batch_result(self, adapter: JsonOutputAdapter, capsys) -> None:
        results = (
            ProcessingResult(success=True, command="cmd1", stdout="", stderr="", return_code=0),
            ProcessingResult(success=False, command="cmd2", stdout="", stderr="err", return_code=1),
        )
        batch = BatchResult(total=2, succeeded=1, failed=1, results=results)
        adapter.batch_result(batch)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["total"] == 2
        assert data["succeeded"] == 1
        assert data["failed"] == 1
        assert len(data["results"]) == 2

    def test_catalog_list_effects(self, adapter: JsonOutputAdapter, capsys) -> None:
        catalog = EffectsCatalog()
        adapter.catalog_list(catalog, CatalogQuery.EFFECT)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "items" in data
        assert data["count"] == 0

    def test_config_info(self, adapter: JsonOutputAdapter, capsys) -> None:
        settings = AppSettings()
        catalog = EffectsCatalog()
        adapter.config_info(settings, catalog, ["settings: /path"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["version"] == "0.1.0"
        assert data["sources"] == ["settings: /path"]

    def test_error(self, adapter: JsonOutputAdapter, capsys) -> None:
        exc = ValueError("bad value")
        adapter.error(exc)
        captured = capsys.readouterr()
        data = json.loads(captured.err)
        assert data["error"]["type"] == "ValueError"
        assert data["error"]["message"] == "bad value"

    def test_message(self, adapter: JsonOutputAdapter, capsys) -> None:
        adapter.message("hello")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["message"] == "hello"

    def test_dump_config_template(self, adapter: JsonOutputAdapter, capsys) -> None:
        content = 'version = "1.0"\n[execution]\n'
        adapter.dump_config_template(content)
        captured = capsys.readouterr()
        assert captured.out == content

    def test_dump_effects_template(self, adapter: JsonOutputAdapter, capsys) -> None:
        content = "version: '1.0'\neffects: []\n"
        adapter.dump_effects_template(content)
        captured = capsys.readouterr()
        assert captured.out == content
