from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from color_scheme_generator.domain.enums import Backend, ColorFormat
from color_scheme_generator.domain.exceptions import BackendNotAvailableError, InvalidImageError
from color_scheme_generator.domain.models import Color, GeneratorConfig

_config = GeneratorConfig(
    backend=Backend.CUSTOM,
    params={"saturation": 1.0, "n_clusters": 16},
    formats=(ColorFormat.JSON,),
    output_dir=Path("/tmp/output"),
)

_config_no_params = GeneratorConfig(
    backend=Backend.CUSTOM,
    params=None,
    formats=(ColorFormat.JSON,),
    output_dir=Path("/tmp/output"),
)


def _make_array_like(data):
    obj = MagicMock()
    obj.reshape.return_value = data
    obj.astype.return_value = data
    return obj


def _install_mock_modules():
    mock_pil = MagicMock()
    mock_pil.UnidentifiedImageError = type("UnidentifiedImageError", (Exception,), {})
    mock_pil.Image = MagicMock()
    mock_pil.Image.Resampling = MagicMock()
    mock_pil.Image.Resampling.LANCZOS = "lanczos"

    mock_numpy = MagicMock()

    mock_sklearn = MagicMock()
    mock_sklearn.cluster = MagicMock()
    mock_sklearn.cluster.KMeans = MagicMock()

    modules = {
        "PIL": mock_pil,
        "PIL.Image": mock_pil.Image,
        "PIL.Image.Resampling": mock_pil.Image.Resampling,
        "numpy": mock_numpy,
        "sklearn": mock_sklearn,
        "sklearn.cluster": mock_sklearn.cluster,
    }
    return modules, mock_pil, mock_numpy, mock_sklearn


class TestCustomGenerator:
    def test_is_available_returns_true_when_imports_succeed(self):
        from color_scheme_generator.adapters.backends.custom_generator import (
            CustomGenerator,
        )

        gen = CustomGenerator()
        with patch("builtins.__import__") as mock_import:
            mock_import.return_value = MagicMock()
            assert gen.is_available() is True

    def test_is_available_returns_false_on_import_error(self):
        from color_scheme_generator.adapters.backends.custom_generator import (
            CustomGenerator,
        )

        gen = CustomGenerator()
        with patch("builtins.__import__", side_effect=ImportError("no module")):
            assert gen.is_available() is False

    def test_generate_raises_backend_not_available_when_deps_missing(self):
        from color_scheme_generator.adapters.backends.custom_generator import (
            CustomGenerator,
        )

        gen = CustomGenerator()
        with patch.object(gen, "is_available", return_value=False):
            with pytest.raises(
                BackendNotAvailableError, match="pip install color-scheme-generator"
            ):
                gen.generate(Path("/tmp/test.png"), _config)

    def test_generate_raises_invalid_image_error_on_corrupt_image(self):
        modules, mock_pil, _mock_np, _mock_sk = _install_mock_modules()

        from color_scheme_generator.adapters.backends.custom_generator import (
            CustomGenerator,
        )

        gen = CustomGenerator()
        with patch.object(gen, "is_available", return_value=True):
            with patch.dict("sys.modules", modules):
                mock_pil.Image.open.side_effect = mock_pil.UnidentifiedImageError(
                    "corrupt"
                )
                with pytest.raises(InvalidImageError, match="PIL cannot decode"):
                    gen.generate(Path("/tmp/corrupt.png"), _config)

    def test_generate_returns_color_scheme_with_mocked_deps(self):
        modules, mock_pil, mock_numpy, mock_sklearn = _install_mock_modules()

        from color_scheme_generator.adapters.backends.custom_generator import (
            CustomGenerator,
        )

        gen = CustomGenerator()
        with patch.object(gen, "is_available", return_value=True):
            with patch.dict("sys.modules", modules):
                mock_img = MagicMock()
                mock_img.convert.return_value = mock_img
                mock_img.resize.return_value = mock_img
                mock_pil.Image.open.return_value = mock_img
                mock_numpy.array.return_value = _make_array_like(
                    [[i * 16, i * 16, i * 16] for i in range(16)]
                )
                mock_kmeans_instance = MagicMock()
                mock_kmeans_instance.cluster_centers_ = _make_array_like(
                    [[i * 16, i * 16, i * 16] for i in range(16)]
                )
                mock_kmeans_instance.fit.return_value = None
                mock_sklearn.cluster.KMeans.return_value = mock_kmeans_instance

                scheme = gen.generate(Path("/tmp/test.png"), _config)

        assert scheme.source_image == Path("/tmp/test.png")
        assert scheme.backend == Backend.CUSTOM
        assert len(scheme.colors) == 16
        assert isinstance(scheme.background, Color)
        assert isinstance(scheme.foreground, Color)
        assert isinstance(scheme.cursor, Color)

    def test_generate_with_solid_color_pads_to_16(self):
        modules, mock_pil, mock_numpy, mock_sklearn = _install_mock_modules()

        from color_scheme_generator.adapters.backends.custom_generator import (
            CustomGenerator,
        )

        gen = CustomGenerator()
        with patch.object(gen, "is_available", return_value=True):
            with patch.dict("sys.modules", modules):
                mock_img = MagicMock()
                mock_img.convert.return_value = mock_img
                mock_img.resize.return_value = mock_img
                mock_pil.Image.open.return_value = mock_img
                mock_numpy.array.return_value = _make_array_like([[128, 128, 128]])
                mock_kmeans_instance = MagicMock()
                mock_kmeans_instance.cluster_centers_ = _make_array_like([[128, 128, 128]])
                mock_kmeans_instance.fit.return_value = None
                mock_sklearn.cluster.KMeans.return_value = mock_kmeans_instance

                scheme = gen.generate(Path("/tmp/solid.png"), _config)

        assert len(scheme.colors) == 16
        original = scheme.colors[0]
        assert original.rgb == (128, 128, 128)
        for i in range(1, 16):
            assert scheme.colors[i] == original
            assert scheme.colors[i].rgb == original.rgb
        assert scheme.colors[0].rgb != (0, 0, 0)

    def test_generate_raises_invalid_image_error_on_file_not_found(self):
        modules, mock_pil, _mock_np, _mock_sk = _install_mock_modules()

        from color_scheme_generator.adapters.backends.custom_generator import (
            CustomGenerator,
        )

        gen = CustomGenerator()
        with patch.object(gen, "is_available", return_value=True):
            with patch.dict("sys.modules", modules):
                mock_pil.Image.open.side_effect = FileNotFoundError(
                    "No such file"
                )
                with pytest.raises(InvalidImageError, match="Cannot read image file"):
                    gen.generate(Path("/tmp/missing.png"), _config)

    def test_generate_raises_invalid_image_error_on_permission_error(self):
        modules, mock_pil, _mock_np, _mock_sk = _install_mock_modules()

        from color_scheme_generator.adapters.backends.custom_generator import (
            CustomGenerator,
        )

        gen = CustomGenerator()
        with patch.object(gen, "is_available", return_value=True):
            with patch.dict("sys.modules", modules):
                mock_pil.Image.open.side_effect = PermissionError(
                    "Permission denied"
                )
                with pytest.raises(InvalidImageError, match="Cannot read image file"):
                    gen.generate(Path("/tmp/no-perm.png"), _config)

    def test_generate_with_none_params_does_not_crash(self):
        modules, mock_pil, mock_numpy, mock_sklearn = _install_mock_modules()

        from color_scheme_generator.adapters.backends.custom_generator import (
            CustomGenerator,
        )

        gen = CustomGenerator()
        with patch.object(gen, "is_available", return_value=True):
            with patch.dict("sys.modules", modules):
                mock_img = MagicMock()
                mock_img.convert.return_value = mock_img
                mock_img.resize.return_value = mock_img
                mock_pil.Image.open.return_value = mock_img
                mock_numpy.array.return_value = _make_array_like(
                    [[i * 16, i * 16, i * 16] for i in range(16)]
                )
                mock_kmeans_instance = MagicMock()
                mock_kmeans_instance.cluster_centers_ = _make_array_like(
                    [[i * 16, i * 16, i * 16] for i in range(16)]
                )
                mock_kmeans_instance.fit.return_value = None
                mock_sklearn.cluster.KMeans.return_value = mock_kmeans_instance

                scheme = gen.generate(Path("/tmp/test.png"), _config_no_params)

        assert scheme.source_image == Path("/tmp/test.png")
        assert len(scheme.colors) == 16

    def test_generate_with_n_zero_clamps_to_1(self):
        modules, mock_pil, mock_numpy, mock_sklearn = _install_mock_modules()

        from color_scheme_generator.adapters.backends.custom_generator import (
            CustomGenerator,
        )

        gen = CustomGenerator()
        with patch.object(gen, "is_available", return_value=True):
            with patch.dict("sys.modules", modules):
                mock_img = MagicMock()
                mock_img.convert.return_value = mock_img
                mock_img.resize.return_value = mock_img
                mock_pil.Image.open.return_value = mock_img
                mock_numpy.array.return_value = _make_array_like(
                    [[i * 16, i * 16, i * 16] for i in range(16)]
                )
                mock_kmeans_instance = MagicMock()
                mock_kmeans_instance.cluster_centers_ = _make_array_like(
                    [[i * 16, i * 16, i * 16] for i in range(16)]
                )
                mock_kmeans_instance.fit.return_value = None
                mock_sklearn.cluster.KMeans.return_value = mock_kmeans_instance

                cfg = GeneratorConfig(
                    backend=Backend.CUSTOM,
                    params={"n_clusters": 0},
                    formats=(ColorFormat.JSON,),
                    output_dir=Path("/tmp/output"),
                )
                scheme = gen.generate(Path("/tmp/test.png"), cfg)

        assert len(scheme.colors) == 16

    def test_generate_with_nan_saturation_defaults_to_1(self):
        modules, mock_pil, mock_numpy, mock_sklearn = _install_mock_modules()

        from color_scheme_generator.adapters.backends.custom_generator import (
            CustomGenerator,
        )

        gen = CustomGenerator()
        with patch.object(gen, "is_available", return_value=True):
            with patch.dict("sys.modules", modules):
                mock_img = MagicMock()
                mock_img.convert.return_value = mock_img
                mock_img.resize.return_value = mock_img
                mock_pil.Image.open.return_value = mock_img
                mock_numpy.array.return_value = _make_array_like(
                    [[i * 16, i * 16, i * 16] for i in range(16)]
                )
                mock_kmeans_instance = MagicMock()
                mock_kmeans_instance.cluster_centers_ = _make_array_like(
                    [[i * 16, i * 16, i * 16] for i in range(16)]
                )
                mock_kmeans_instance.fit.return_value = None
                mock_sklearn.cluster.KMeans.return_value = mock_kmeans_instance

                cfg = GeneratorConfig(
                    backend=Backend.CUSTOM,
                    params={"saturation": float("nan")},
                    formats=(ColorFormat.JSON,),
                    output_dir=Path("/tmp/output"),
                )
                scheme = gen.generate(Path("/tmp/test.png"), cfg)

        assert len(scheme.colors) == 16

    def test_structural_subtyping(self):
        from color_scheme_generator.adapters.backends.custom_generator import (
            CustomGenerator,
        )
        from color_scheme_generator.ports.palette_generator import (
            PaletteGeneratorPort,
        )

        assert isinstance(CustomGenerator(), PaletteGeneratorPort)
