"""Validation of the three btop theme formats against btop 1.4.7's real parser.

Everything asserted here mirrors ``src/btop_theme.cpp`` rather than being
re-derived from memory:

* ``Default_theme`` key set (:52-101) -- 48 keys, exact and case-sensitive.
  An unknown key is silently ignored by btop, so it is a silent failure.
* ``#`` is a comment ONLY at offset 0 (:399-406). A leading space before
  ``[`` makes the parser skip forward and mangle the line, so every emitted
  line must start at column 0.
* Values are ``#RRGGBB``, ``#GG`` greyscale, or ``"12 34 56"`` decimals.
  There is no 8-digit/alpha form.
* An empty ``<x>_mid`` / ``<x>_end`` is btop's documented two-stop gradient
  idiom (:260-264).

The difficulty-dial assertions are the drift guard. The three templates are
deliberately near-copies of one another and cannot share a partial (any extra
``.j2`` in the templates directory is catalog-scanned and would be rejected
as an unknown format), so "minimal vs balanced differ only in temp_*/cached_*"
is what keeps the copies honest.
"""

from __future__ import annotations

import re
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from color_scheme_generator.adapters.jinja_template_renderer import JinjaTemplateRenderer
from color_scheme_generator.adapters.local_processor import LocalProcessor
from color_scheme_generator.domain.enums import Backend, ColorFormat
from color_scheme_generator.domain.models import (
    Color,
    ColorScheme,
    GenerationRequest,
    GeneratorConfig,
)

# btop 1.4.7 Default_theme, src/btop_theme.cpp:52-101. Exactly 48 keys.
BTOP_KEYS: frozenset[str] = frozenset(
    """
    main_bg main_fg title hi_fg selected_bg selected_fg inactive_fg
    graph_text meter_bg proc_misc cpu_box mem_box net_box proc_box div_line
    temp_start temp_mid temp_end cpu_start cpu_mid cpu_end
    free_start free_mid free_end cached_start cached_mid cached_end
    available_start available_mid available_end used_start used_mid used_end
    download_start download_mid download_end upload_start upload_mid upload_end
    process_start process_mid process_end
    proc_pause_bg proc_follow_bg proc_banner_bg proc_banner_fg
    followed_bg followed_fg
    """.split()
)
assert len(BTOP_KEYS) == 48

GRADIENTS: tuple[str, ...] = (
    "temp",
    "cpu",
    "free",
    "cached",
    "available",
    "used",
    "download",
    "upload",
    "process",
)

OUTLINE_KEYS: tuple[str, ...] = ("cpu_box", "mem_box", "net_box", "proc_box")
OUTLINE_AND_DIV: tuple[str, ...] = (*OUTLINE_KEYS, "div_line")

# variant name -> which gradients that variant forces semantic. This is the
# difficulty dial, and it is asserted against the templates' own marker
# comments as well as against their colours.
SEMANTIC_BY_VARIANT: dict[str, tuple[str, ...]] = {
    "minimal": (),
    "balanced": ("temp", "cached"),
    "full": ("temp", "cached", "cpu"),
}

_VARIANTS: tuple[tuple[ColorFormat, str], ...] = (
    (ColorFormat.BTOP_MINIMAL, "minimal"),
    (ColorFormat.BTOP_BALANCED, "balanced"),
    (ColorFormat.BTOP_FULL, "full"),
)
_VARIANT_NAMES: tuple[str, ...] = tuple(n for _, n in _VARIANTS)
_FMT_BY_NAME: dict[str, ColorFormat] = {n: f for f, n in _VARIANTS}

# btop accepts "#RRGGBB", "#GG" greyscale, or "12 34 56" decimals -- never 8 digits.
_VALUE_RE = re.compile(
    r'"(?:#[0-9a-fA-F]{2}|#[0-9a-fA-F]{6}|\d{1,3} \d{1,3} \d{1,3})"'
)
_LINE_RE = re.compile(r'^theme\[(?P<key>[A-Za-z0-9_]+)\]=(?P<rhs>.*)$')


class _BundledDirResolver:
    def __init__(self, templates_dir: Path) -> None:
        self._templates_dir = templates_dir

    def resolve(self, settings_dir: Path | None = None) -> Path:
        return self._templates_dir


@pytest.fixture
def bundled_templates_dir() -> Path:
    pkg_dir = Path(__file__).resolve().parent.parent.parent.parent
    return pkg_dir / "src" / "color_scheme_generator" / "defaults" / "templates"


def _c(hexstr: str) -> Color:
    return Color(hexstr, tuple(int(hexstr[i : i + 2], 16) for i in (1, 3, 5)))


# The live pywal palette: luminance-sorted, with the duplicate adjacent stops
# real backends emit (16 slots, 9 distinct). This is the shape the templates
# actually have to survive, so the ramp-dedupe logic is exercised for real.
_LIVE_RAMP = (
    "#0b0b1a",
    "#575660",
    "#575660",
    "#5a5a6f",
    "#2d6596",
    "#2d6596",
    "#557690",
    "#557690",
    "#9a7268",
    "#9a7268",
    "#549ec8",
    "#549ec8",
    "#dbab67",
    "#dbab67",
    "#c2c2c5",
    "#c2c2c5",
)


@pytest.fixture
def scheme() -> ColorScheme:
    return ColorScheme(
        background=_c("#0b0b1a"),
        foreground=_c("#c2c2c5"),
        cursor=_c("#c2c2c5"),
        colors=tuple(_c(h) for h in _LIVE_RAMP),
        source_image=Path("/input/default.png"),
        backend=Backend.PYWAL,
        generated_at=datetime(2026, 9, 30, 13, 38, 39),
    )


@pytest.fixture
def render_all(
    bundled_templates_dir: Path, scheme: ColorScheme, tmp_path: Path
) -> dict[str, Path]:
    """Render all three variants through the real renderer."""
    renderer = JinjaTemplateRenderer(_BundledDirResolver(bundled_templates_dir))
    out: dict[str, Path] = {}
    for fmt, name in _VARIANTS:
        path = tmp_path / f"colors.{fmt.value}"
        renderer.render(f"colors.{fmt.value}.j2", scheme, path)
        out[name] = path
    return out


def parse_theme(path: Path) -> dict[str, str]:
    """Return the theme[key]=value map, asserting the line grammar on the way."""
    result: dict[str, str] = {}
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        if line.startswith("#"):
            continue
        assert not line[:1].isspace(), (
            f"{path.name}:{lineno} begins with whitespace -- btop treats '#' as a "
            f"comment only at offset 0 and mangles an indented '[' line: {line!r}"
        )
        match = _LINE_RE.match(line)
        assert match is not None, f"{path.name}:{lineno} unparseable: {line!r}"
        key = match.group("key")
        assert key in BTOP_KEYS, (
            f"{path.name}:{lineno} unknown key {key!r} -- btop silently ignores it"
        )
        assert key not in result, f"{path.name}:{lineno} duplicate key {key!r}"
        rhs = match.group("rhs")
        assert rhs.startswith('"') and rhs.endswith('"'), f"{path.name}:{lineno} unquoted"
        result[key] = rhs[1:-1]
    return result


def _stops(parsed: dict[str, str], gradient: str) -> tuple[str, str, str]:
    return tuple(parsed[f"{gradient}_{s}"] for s in ("start", "mid", "end"))  # type: ignore[return-value]


# --- CIELAB -------------------------------------------------------------


def _rgb(value: str) -> tuple[int, int, int]:
    return tuple(int(value[i : i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def _lab_bstar(rgb: tuple[int, int, int]) -> float:
    """CIELAB b* -- the blue(-) <-> yellow(+) axis, i.e. 'perceived heat'."""
    channels = []
    for raw in rgb:
        c = raw / 255.0
        channels.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 0.008856 else 7.787 * t + 16.0 / 116.0

    return 200.0 * (f(y) - f(z))


def _warmth(value: str) -> float:
    return _lab_bstar(_rgb(value))


# --- parser rules -------------------------------------------------------


class TestParserRules:
    @pytest.mark.parametrize("variant", _VARIANT_NAMES)
    def test_every_line_starts_at_column_zero(
        self, render_all: dict[str, Path], variant: str
    ) -> None:
        path = render_all[variant]
        offenders = [
            lineno
            for lineno, line in enumerate(path.read_text().splitlines(), 1)
            if line.strip() and line[:1].isspace()
        ]
        assert offenders == [], f"{path.name} indents lines {offenders}"

    @pytest.mark.parametrize("variant", _VARIANT_NAMES)
    def test_key_set_equals_btop_default_theme(
        self, render_all: dict[str, Path], variant: str
    ) -> None:
        path = render_all[variant]
        keys = parse_theme(path)
        assert set(keys) == BTOP_KEYS
        assert len(keys) == 48

    @pytest.mark.parametrize("variant", _VARIANT_NAMES)
    def test_every_value_is_a_valid_color_form(
        self, render_all: dict[str, Path], variant: str
    ) -> None:
        path = render_all[variant]
        for key, value in parse_theme(path).items():
            # btop's two-stop idiom: an empty mid/end is legal and intended.
            if value == "":
                assert key.endswith(("_mid", "_end")), key
                continue
            assert _VALUE_RE.fullmatch(f'"{value}"'), (
                f"{path.name}: bad value for {key}: {value!r}"
            )
            assert not re.fullmatch(r"#[0-9a-fA-F]{8}", value), (
                f"{path.name}: {key} is 8 hex digits -- btop has no alpha form"
            )

    @pytest.mark.parametrize("variant", _VARIANT_NAMES)
    def test_all_colors_come_from_the_shared_scheme(
        self, render_all: dict[str, Path], scheme: ColorScheme, variant: str
    ) -> None:
        allowed = {scheme.background.hex, scheme.foreground.hex, scheme.cursor.hex}
        allowed |= {c.hex for c in scheme.colors}
        path = render_all[variant]
        for key, value in parse_theme(path).items():
            # An empty value is btop's two-stop marker, not a colour.
            if value == "":
                continue
            assert value in allowed, f"{path.name}: {key}={value} is not a palette colour"

    def test_no_template_is_a_shared_partial(self, bundled_templates_dir: Path) -> None:
        """Every *.j2 must be a real format -- a partial would break csg entirely."""
        names = sorted(p.name for p in bundled_templates_dir.glob("*.j2"))
        assert len(names) == 14
        for fmt, _ in _VARIANTS:
            assert f"colors.{fmt.value}.j2" in names
        for name in names:
            body = (bundled_templates_dir / name).read_text()
            assert "{% include" not in body, f"{name} uses a shared partial"
            assert "{% import" not in body, f"{name} imports a shared partial"

    def test_templates_directory_is_exactly_the_registered_formats(
        self, bundled_templates_dir: Path
    ) -> None:
        """The catalog scans this directory, so nothing unregistered may sit here."""
        from color_scheme_generator.domain.services import TemplateCatalogService

        names = {p.name for p in bundled_templates_dir.glob("*.j2")}
        catalog = TemplateCatalogService().derive(bundled_templates_dir)
        assert {t.name for t in catalog.templates} == names


# --- the difficulty dial ------------------------------------------------


class TestDifficultyDial:
    def test_minimal_and_balanced_differ_only_in_temp_and_cached(
        self, render_all: dict[str, Path]
    ) -> None:
        minimal = parse_theme(render_all["minimal"])
        balanced = parse_theme(render_all["balanced"])
        differing = {k for k in minimal if minimal[k] != balanced[k]}
        allowed = {f"{g}_{s}" for g in ("temp", "cached") for s in ("start", "mid", "end")}
        assert differing <= allowed, f"balanced drifted outside temp_*/cached_*: {differing}"
        assert differing, "balanced must actually force something semantic"

    def test_balanced_and_full_differ_only_in_cpu(
        self, render_all: dict[str, Path]
    ) -> None:
        balanced = parse_theme(render_all["balanced"])
        full = parse_theme(render_all["full"])
        differing = {k for k in balanced if balanced[k] != full[k]}
        assert differing <= {"cpu_start", "cpu_mid", "cpu_end"}, (
            f"full drifted outside cpu_*: {differing}"
        )
        assert differing, "full must actually force cpu semantic"

    @pytest.mark.parametrize("variant", ["balanced", "full"])
    def test_non_semantic_gradients_are_identical_to_minimal(
        self, render_all: dict[str, Path], variant: str
    ) -> None:
        minimal = parse_theme(render_all["minimal"])
        other = parse_theme(render_all[variant])
        forced = set(SEMANTIC_BY_VARIANT[variant])
        for gradient in GRADIENTS:
            if gradient in forced:
                continue
            assert _stops(other, gradient) == _stops(minimal, gradient), (
                f"{variant}: {gradient} is not forced semantic but changed anyway"
            )

    def test_forced_gradients_actually_change(self, render_all: dict[str, Path]) -> None:
        """Forcing a gradient semantic must visibly move its stops."""
        minimal = parse_theme(render_all["minimal"])
        balanced = parse_theme(render_all["balanced"])
        full = parse_theme(render_all["full"])
        for gradient in ("temp", "cached"):
            assert _stops(balanced, gradient) != _stops(minimal, gradient), gradient
        assert _stops(full, "cpu") != _stops(balanced, "cpu")

    def test_semantic_set_is_a_superset_chain(self, render_all: dict[str, Path]) -> None:
        declared: dict[str, set[str]] = {}
        for variant in _VARIANT_NAMES:
            found = set()
            for line in render_all[variant].read_text().splitlines():
                if line.startswith("# ") and ": SEMANTIC" in line:
                    found.add(line[1:].split(":", 1)[0].strip())
            declared[variant] = found

        assert declared["minimal"] == set()
        assert declared["balanced"] == {"temp", "cached"}
        assert declared["full"] == {"temp", "cached", "cpu"}
        assert declared["minimal"] <= declared["balanced"] <= declared["full"]

    @pytest.mark.parametrize("variant", _VARIANT_NAMES)
    def test_markers_name_every_gradient(
        self, render_all: dict[str, Path], variant: str
    ) -> None:
        text = render_all[variant].read_text()
        semantic = set(SEMANTIC_BY_VARIANT[variant])
        for gradient in GRADIENTS:
            marker = f"# {gradient}: "
            assert marker in text, f"{variant}: no marker for {gradient}"
            line = next(ln for ln in text.splitlines() if ln.startswith(marker))
            declared = line.split(":", 1)[1].strip().split(",", 1)[0].split(" ", 1)[0]
            if gradient in semantic:
                assert declared == "SEMANTIC", line
            else:
                assert declared == "ramp", line


# --- the two known traps -----------------------------------------------


class TestKnownTraps:
    @pytest.mark.parametrize("variant", _VARIANT_NAMES)
    def test_process_gradient_cannot_fade_to_black(
        self, render_all: dict[str, Path], variant: str
    ) -> None:
        """btop guards the fallback on process_start but reads process_end directly."""
        path = render_all[variant]
        parsed = parse_theme(path)
        for stop in ("process_start", "process_mid", "process_end"):
            assert parsed.get(stop), f"{path.name}: {stop} missing or empty"

    @pytest.mark.parametrize("variant", _VARIANT_NAMES)
    def test_throughput_gradients_are_two_stop(
        self, render_all: dict[str, Path], variant: str
    ) -> None:
        path = render_all[variant]
        parsed = parse_theme(path)
        assert parsed["download_mid"] == ""
        assert parsed["upload_mid"] == ""
        for key in ("download_start", "download_end", "upload_start", "upload_end"):
            assert parsed[key], f"{path.name}: {key} must be present and non-empty"

    @pytest.mark.parametrize("variant", _VARIANT_NAMES)
    def test_process_state_keys_from_btop_1_4_6_are_present(
        self, render_all: dict[str, Path], variant: str
    ) -> None:
        parsed = parse_theme(render_all[variant])
        for key in (
            "proc_pause_bg",
            "proc_follow_bg",
            "proc_banner_bg",
            "proc_banner_fg",
            "followed_bg",
            "followed_fg",
        ):
            assert key in parsed and parsed[key], key


# --- neutral chrome -----------------------------------------------------


class TestOutlineNeutrality:
    @pytest.mark.parametrize("variant", _VARIANT_NAMES)
    def test_box_outlines_share_one_colour(
        self, render_all: dict[str, Path], variant: str
    ) -> None:
        parsed = parse_theme(render_all[variant])
        values = {parsed[k] for k in OUTLINE_KEYS}
        assert len(values) == 1, f"outlines disagree: {values}"

    @pytest.mark.parametrize("variant", _VARIANT_NAMES)
    def test_outlines_and_divider_are_palette_derived(
        self, render_all: dict[str, Path], scheme: ColorScheme, variant: str
    ) -> None:
        parsed = parse_theme(render_all[variant])
        allowed = {scheme.background.hex, scheme.foreground.hex, scheme.cursor.hex}
        allowed |= {c.hex for c in scheme.colors}
        for key in OUTLINE_AND_DIV:
            assert parsed[key] in allowed, key


# --- the render path ----------------------------------------------------


class TestRenderPath:
    def test_generation_request_writes_three_theme_files(
        self, bundled_templates_dir: Path, scheme: ColorScheme, tmp_path: Path
    ) -> None:
        mock_gen = MagicMock()
        mock_gen.is_available.return_value = True
        mock_gen.generate.return_value = scheme

        renderer = JinjaTemplateRenderer(_BundledDirResolver(bundled_templates_dir))
        processor = LocalProcessor({Backend.CUSTOM: mock_gen}, template_renderer=renderer)

        out_dir = tmp_path / "out"
        request = GenerationRequest(
            image_path=Path("/tmp/wallpaper.png"),
            config=GeneratorConfig(
                backend=Backend.CUSTOM,
                params={},
                formats=tuple(fmt for fmt, _ in _VARIANTS),
                output_dir=out_dir,
            ),
        )
        result = processor.process_generate(request, object())

        assert result.success is True, result.stderr
        produced = sorted(p.name for p in out_dir.iterdir())
        assert produced == [
            "colors.btop-balanced.theme",
            "colors.btop-full.theme",
            "colors.btop-minimal.theme",
        ]
        assert {out_dir / name for name in produced} == set(result.output_files)
        for name in produced:
            assert name.endswith(".theme")
            assert set(parse_theme(out_dir / name)) == BTOP_KEYS

    def test_render_path_needs_no_special_casing(
        self, bundled_templates_dir: Path, scheme: ColorScheme, tmp_path: Path
    ) -> None:
        """colors.<value>.j2 -> colors.<value>, exactly like every other format."""
        renderer = JinjaTemplateRenderer(_BundledDirResolver(bundled_templates_dir))
        for fmt, _ in _VARIANTS:
            out = tmp_path / f"colors.{fmt.value}"
            renderer.render(f"colors.{fmt.value}.j2", scheme, out)
            assert out.name == f"colors.{fmt.value}"

    def test_render_is_deterministic(
        self, bundled_templates_dir: Path, scheme: ColorScheme, tmp_path: Path
    ) -> None:
        renderer = JinjaTemplateRenderer(_BundledDirResolver(bundled_templates_dir))
        first = tmp_path / "a.theme"
        renderer.render("colors.btop-full.theme.j2", scheme, first)
        with tempfile.TemporaryDirectory() as td:
            other = Path(td) / "colors.btop-full.theme"
            renderer.render("colors.btop-full.theme.j2", scheme, other)
            second_bytes = other.read_bytes()
        assert first.read_bytes() == second_bytes


# --- semantic monotonicity ---------------------------------------------


class TestSemanticMonotonicity:
    @pytest.mark.parametrize("variant", _VARIANT_NAMES)
    def test_each_semantic_stop_is_not_cooler_than_the_previous(
        self, render_all: dict[str, Path], variant: str
    ) -> None:
        parsed = parse_theme(render_all[variant])
        for gradient in SEMANTIC_BY_VARIANT[variant]:
            values = [parsed[f"{gradient}_{s}"] for s in ("start", "mid", "end")]
            assert all(values), f"{gradient}: an empty stop"
            warmths = [_warmth(v) for v in values]
            assert warmths[0] <= warmths[1] <= warmths[2], (
                f"{variant} {gradient} cools as the reading rises: "
                f"{values} -> b* {warmths}"
            )

    @pytest.mark.parametrize("variant", ["balanced", "full"])
    def test_semantic_stops_are_legibly_separated(
        self, render_all: dict[str, Path], variant: str
    ) -> None:
        """A semantic ramp that collapses to one colour is not a semantic ramp."""
        parsed = parse_theme(render_all[variant])
        for gradient in SEMANTIC_BY_VARIANT[variant]:
            values = _stops(parsed, gradient)
            assert len(set(values)) >= 2, f"{gradient} collapsed to {values[0]}"
            gaps = [abs(_warmth(values[i + 1]) - _warmth(values[i])) for i in range(2)]
            assert min(gaps) > 5.0, (
                f"{variant} {gradient}: adjacent semantic stops are within 5 CIELAB b* "
                f"units, which is not legible: {values}"
            )

    def test_degenerate_palette_still_renders_a_valid_theme(
        self, bundled_templates_dir: Path, tmp_path: Path
    ) -> None:
        """A monochrome wallpaper must not crash or corrupt the output.

        design.md's Risks section accepts this explicitly: with one distinct
        stop every semantic pick collapses onto that stop, so all three
        variants render identical low-contrast-but-valid bytes.
        """
        renderer = JinjaTemplateRenderer(_BundledDirResolver(bundled_templates_dir))
        mono = ColorScheme(
            background=_c("#6496c8"),
            foreground=_c("#6496c8"),
            cursor=_c("#6496c8"),
            colors=tuple(_c("#6496c8") for _ in range(16)),
            source_image=Path("/input/flat.png"),
            backend=Backend.CUSTOM,
            generated_at=datetime(2026, 9, 30),
        )
        rendered = []
        for fmt, _ in _VARIANTS:
            path = tmp_path / f"colors.{fmt.value}"
            renderer.render(f"colors.{fmt.value}.j2", mono, path)
            parsed = parse_theme(path)
            assert set(parsed) == BTOP_KEYS, fmt
            assert parsed["download_mid"] == ""
            assert parsed["process_end"]
            rendered.append(parsed)
        # The dial collapses -- every semantic pick lands on the same stop --
        # but it collapses VALIDLY, and all three variants agree on every value.
        # (The header comments still differ by design: they name the variant.)
        assert rendered[0] == rendered[1] == rendered[2]

    def test_relative_semantics_survive_a_palette_change(
        self, bundled_templates_dir: Path, tmp_path: Path
    ) -> None:
        """Two different wallpapers: temp_* stays monotone in both.

        btop scales temp against the detected maximum, so a semantic temp ramp
        must stay ordered no matter which wallpaper produced the palette.
        """
        renderer = JinjaTemplateRenderer(_BundledDirResolver(bundled_templates_dir))
        palettes = (
            _LIVE_RAMP,
            ("#101418", "#1b2630", "#2c3e50", "#3a5f7d", "#4a90a4", "#5fb3b3",
             "#8fd694", "#c3d96b", "#f2e394", "#f7c873", "#f39c5a", "#e2684a",
             "#c9455f", "#a03a6a", "#7a3f7a", "#3f5b8a"),
            ("#000000", "#000000", "#000000", "#111111", "#222222", "#333333",
             "#444444", "#555555", "#666666", "#777777", "#888888", "#999999",
             "#aaaaaa", "#bbbbbb", "#cccccc", "#dddddd"),
        )
        for ramp in palettes:
            sc = ColorScheme(
                background=_c(ramp[0]),
                foreground=_c(ramp[-1]),
                cursor=_c(ramp[-1]),
                colors=tuple(_c(h) for h in ramp),
                source_image=Path("/input/other.png"),
                backend=Backend.CUSTOM,
                generated_at=datetime(2026, 9, 30),
            )
            for fmt, variant in _VARIANTS:
                path = tmp_path / f"{variant}-{sc.background.hex}.theme"
                renderer.render(f"colors.{fmt.value}.j2", sc, path)
                parsed = parse_theme(path)
                for gradient in SEMANTIC_BY_VARIANT[variant]:
                    values = [parsed[f"{gradient}_{s}"] for s in ("start", "mid", "end")]
                    warmths = [_warmth(v) for v in values]
                    assert warmths[0] <= warmths[1] <= warmths[2], (
                        f"palette {ramp[0]}: {variant} {gradient} inverts -- "
                        f"{values} -> b* {warmths}"
                    )
