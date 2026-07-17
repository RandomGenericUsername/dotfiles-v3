from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from color_scheme_generator.adapters.backends.pywal_generator import (
    _SUBPROCESS_TIMEOUT,
    PywalGenerator,
)
from color_scheme_generator.domain.enums import Backend, ColorFormat
from color_scheme_generator.domain.exceptions import (
    BackendNotAvailableError,
    ColorExtractionError,
)
from color_scheme_generator.domain.models import Color, GeneratorConfig
from color_scheme_generator.ports.palette_generator import PaletteGeneratorPort

_config = GeneratorConfig(
    backend=Backend.PYWAL,
    params={"saturation": 1.0, "algorithm": "wal"},
    formats=(ColorFormat.JSON,),
    output_dir=Path("/tmp/output"),
)


class TestPywalGenerator:
    def test_is_available_returns_true_when_wal_on_path(self):
        gen = PywalGenerator()
        with patch("shutil.which", return_value="/usr/bin/wal"):
            assert gen.is_available() is True

    def test_is_available_returns_false_when_wal_not_on_path(self):
        gen = PywalGenerator()
        with patch("shutil.which", return_value=None):
            assert gen.is_available() is False

    def test_is_available_side_effect_free(self):
        gen = PywalGenerator()
        with patch("shutil.which", return_value="/usr/bin/wal"):
            gen.is_available()
        with patch("shutil.which", return_value=None):
            gen.is_available()

    def test_generate_raises_backend_not_available_when_wal_missing(self):
        gen = PywalGenerator()
        with patch.object(gen, "is_available", return_value=False):
            with pytest.raises(
                BackendNotAvailableError, match="pip install color-scheme-generator"
            ):
                gen.generate(Path("/tmp/test.png"), _config)

    def test_generate_shells_out_with_correct_args(self):
        gen = PywalGenerator()
        _16_colors = [
            Color(f"#{i*17:02x}{i*17:02x}{i*17:02x}", (i*17, i*17, i*17))
            for i in range(16)
        ]

        with patch.object(gen, "is_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = b"#1a1b26\n#a9b1d6\n"
                mock_result.stderr = b""
                mock_run.return_value = mock_result
                with patch.object(gen, "_parse_stdout", return_value=_16_colors):
                    gen.generate(Path("/tmp/test.png"), _config)

        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert args[0] == [
            "wal", "-i", "/tmp/test.png",
            "-n", "-s", "-t", "-e",
            "--backend", "wal",
            "--stdout",
        ]
        assert kwargs["capture_output"] is True
        assert kwargs["timeout"] == _SUBPROCESS_TIMEOUT

    def test_generate_parses_cache_correctly(self):
        gen = PywalGenerator()
        cache_data = {
            "special": {
                "background": "#1a1b26",
                "foreground": "#a9b1d6",
                "cursor": "#c0caf5",
            },
            "colors": {
                "color0": "#1a1b26",
                "color1": "#f7768e",
                "color2": "#9ece6a",
                "color3": "#e0af68",
                "color4": "#7aa2f7",
                "color5": "#bb9af7",
                "color6": "#73daca",
                "color7": "#a9b1d6",
                "color8": "#414868",
                "color9": "#f7768e",
                "color10": "#9ece6a",
                "color11": "#e0af68",
                "color12": "#7aa2f7",
                "color13": "#bb9af7",
                "color14": "#73daca",
                "color15": "#c0caf5",
            },
        }

        with patch.object(gen, "is_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = b""
                mock_result.stderr = b""
                mock_run.return_value = mock_result
                with patch(
                    "builtins.open",
                    MagicMock(
                        return_value=MagicMock(
                            __enter__=MagicMock(
                                return_value=MagicMock(
                                    read=MagicMock(return_value=json.dumps(cache_data))
                                )
                            )
                        )
                    ),
                ):
                    scheme = gen.generate(Path("/tmp/test.png"), _config)

        assert len(scheme.colors) == 16
        assert scheme.colors[0].hex == "#1a1b26"
        assert scheme.colors[1].hex == "#414868"
        assert scheme.backend == Backend.PYWAL

    def test_generate_applies_saturation(self):
        gen = PywalGenerator()
        _16_colors = [
            Color(f"#{i*17:02x}{i*17:02x}{i*17:02x}", (i*17, i*17, i*17))
            for i in range(16)
        ]

        with patch.object(gen, "is_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = b"#1a1b26\n#a9b1d6\n"
                mock_result.stderr = b""
                mock_run.return_value = mock_result
                with patch.object(gen, "_parse_stdout", return_value=_16_colors):
                    cfg = GeneratorConfig(
                        backend=Backend.PYWAL,
                        params={"saturation": 0.5, "algorithm": "wal"},
                        formats=(ColorFormat.JSON,),
                        output_dir=Path("/tmp/output"),
                    )
                    scheme = gen.generate(Path("/tmp/test.png"), cfg)

        assert len(scheme.colors) == 16
        assert isinstance(scheme.background, Color)
        assert scheme.backend == Backend.PYWAL

    def test_generate_raises_color_extraction_error_on_nonzero_exit(self):
        gen = PywalGenerator()

        with patch.object(gen, "is_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_result = MagicMock()
                mock_result.returncode = 1
                mock_result.stdout = b""
                mock_result.stderr = b"error: image not found"
                mock_run.return_value = mock_result

                with pytest.raises(ColorExtractionError) as exc:
                    gen.generate(Path("/tmp/bad.png"), _config)

        assert exc.value.backend == Backend.PYWAL
        assert exc.value.stderr == "error: image not found"

    def test_generate_raises_color_extraction_error_on_timeout(self):
        gen = PywalGenerator()

        with patch.object(gen, "is_available", return_value=True):
            with patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd=["wal"], timeout=60),
            ):
                with pytest.raises(ColorExtractionError) as exc:
                    gen.generate(Path("/tmp/test.png"), _config)

        assert exc.value.backend == Backend.PYWAL
        assert "timed out" in exc.value.message

    def test_generate_retries_on_partially_written_cache(self):
        gen = PywalGenerator()
        cache_data = {
            "colors": {f"color{i}": "#1a1b26" for i in range(16)},
            "special": {},
        }

        open_mock = MagicMock()
        open_mock.side_effect = [
            json.JSONDecodeError("unexpected data", "", 0),
            MagicMock(
                __enter__=MagicMock(
                    return_value=MagicMock(
                        read=MagicMock(return_value=json.dumps(cache_data))
                    )
                )
            ),
        ]

        with patch.object(gen, "is_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = b""
                mock_result.stderr = b""
                mock_run.return_value = mock_result
                with patch("builtins.open", open_mock):
                    with patch("time.sleep") as mock_sleep:
                        scheme = gen.generate(Path("/tmp/test.png"), _config)

        assert len(scheme.colors) == 16
        mock_sleep.assert_called_once_with(0.5)

    def test_structural_subtyping(self):
        assert isinstance(PywalGenerator(), PaletteGeneratorPort)
