from __future__ import annotations

from pathlib import Path

import pytest
from rich.console import Console

from wallpaper_effects_generator.adapters.output.rich_output import RichOutputAdapter
from wallpaper_effects_generator.domain.enums import CatalogQuery
from wallpaper_effects_generator.domain.models import (
    AppSettings,
    BackendSettings,
    BatchResult,
    ContainerSettings,
    EffectsCatalog,
    ExecutionSettings,
    OutputSettings,
    ProcessingResult,
    RuntimeSettings,
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
        assert "/out/img.png" in captured.out
        assert "duration" in captured.out

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
        assert "Failure" in captured.out
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
        assert "Error" in captured.err
        assert "ValueError" in captured.err
        assert "bad value" in captured.err

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

    def test_catalog_list_effects(self, adapter: RichOutputAdapter, capsys) -> None:
        from wallpaper_effects_generator.domain.models import (
            EffectDefinition,
            ParameterDefinition,
        )

        catalog = EffectsCatalog(
            effects=(
                EffectDefinition(
                    name="blur",
                    description="Blur effect",
                    command="magick {{input}} -blur {{radius}} {{output}}",
                    parameters=(
                        ParameterDefinition(key="radius", description="Radius", default="0x8"),
                    ),
                ),
            ),
        )
        adapter.catalog_list(catalog, CatalogQuery.EFFECT)
        captured = capsys.readouterr()
        assert "blur" in captured.out

    def test_catalog_list_composites(self, adapter: RichOutputAdapter, capsys) -> None:
        from wallpaper_effects_generator.domain.models import (
            ChainStep,
            CompositeDefinition,
        )

        catalog = EffectsCatalog(
            composites=(
                CompositeDefinition(
                    name="blur-resize",
                    description="Blur then resize",
                    steps=(ChainStep(effect_name="blur", parameters={"radius": "0x4"}),),
                ),
            ),
        )
        adapter.catalog_list(catalog, CatalogQuery.COMPOSITE)
        captured = capsys.readouterr()
        assert "blur-resize" in captured.out

    def test_catalog_list_all(self, adapter: RichOutputAdapter, capsys) -> None:
        catalog = EffectsCatalog()
        adapter.catalog_list(catalog, CatalogQuery.ALL)
        captured = capsys.readouterr()
        assert "Catalog" in captured.out

    def test_config_info(self, adapter: RichOutputAdapter, capsys) -> None:
        settings = AppSettings(
            version="1.0",
            execution=ExecutionSettings(parallel=True),
            output=OutputSettings(),
            backend=BackendSettings(binary="magick"),
            runtime=RuntimeSettings(),
            container=ContainerSettings(engine="docker"),
        )
        catalog = EffectsCatalog()
        sources = ["/custom/path/settings.toml", "/custom/path/effects.yaml"]
        adapter.config_info(settings, catalog, sources)
        captured = capsys.readouterr()
        assert "Configuration Info" in captured.out
        assert "Runtime Mode" in captured.out
