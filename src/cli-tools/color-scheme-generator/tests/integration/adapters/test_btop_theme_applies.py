"""Prove that btop both LOADS and APPLIES a generated theme -- without human eyes.

This is the promoted form of ``spikes/btop-theme-prototype/assert_theme_applies.py``.

The obvious verification, "launch btop and look at it", is not acceptable for
two reasons: it needs a person, and btop's most likely failure mode is
**silent**. ``Theme::setTheme`` leaves ``theme_path`` empty when
``color_theme`` does not resolve against the discovered list and then applies
``Default_theme`` with no error and no log entry (``btop_theme.cpp:465``). A
theme that never loads looks identical to one that does, except for colours.

So two machine-checkable channels are used, both verified against btop 1.4.7:

1. **Load.** ``Theme::loadFile`` logs ``Loading theme file: <abs path>`` at
   DEBUG (``btop_theme.cpp:397``). With ``log_level = "DEBUG"`` and an
   isolated ``XDG_STATE_HOME``, that line naming *our* file is asserted. An
   unresolvable theme produces no such line at all.
2. **Apply.** btop is run on a real pty (it requires a real terminal size;
   without one it only emits errors), the frame is captured, and every 24-bit
   SGR colour from both ``38;2`` (fg) and ``48;2`` (bg) is extracted. The frame
   must be **dominated** by the theme's colours -- measured as a share of the
   colours actually on screen, not of the file, since a frame shows only a
   few gradient stops at once -- and **zero** of btop's fallback colours may
   appear.

A verification that cannot fail proves nothing, so ``test_unresolvable_theme_
is_detected`` is the negative control and it asserts the *btop* channel
specifically: the theme files are present and discoverable, but ``color_theme``
names one that is not. btop then silently falls back -- which is exactly the
failure the positive case is claiming to rule out.

Every internal error is a failure, never a pass: ``check_one`` raising is
caught and turned into a failed assertion, never a silent green.
"""

from __future__ import annotations

import fcntl
import os
import pty
import re
import select
import shutil
import struct
import subprocess
import termios
import time
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import pytest

from color_scheme_generator.adapters.jinja_template_renderer import JinjaTemplateRenderer
from color_scheme_generator.domain.enums import Backend, ColorFormat
from color_scheme_generator.domain.models import Color, ColorScheme

# The spike hardcoded btop's Default_theme colours (src/btop_theme.cpp:52-101)
# as the negative signal. That list is wrong for a real installed btop: the
# compiled-in fallback differs from that source listing, and hardcoding a
# palette we cannot verify makes the assertion either vacuous or flaky.
#
# So the signal is derived instead: run btop ONCE with a color_theme that
# cannot resolve, and treat whatever it paints as "what Default looks like".
# That is measured, not assumed, and it is exactly the condition the positive
# case has to be distinguished from.
DEFAULT_THEME_COLORS: frozenset[str] = frozenset()  # superseded by default_frame_colors

WIDTH, HEIGHT, SETTLE_SECONDS = 200, 50, 4.0

VARIANTS: tuple[ColorFormat, ...] = (
    ColorFormat.BTOP_MINIMAL,
    ColorFormat.BTOP_BALANCED,
    ColorFormat.BTOP_FULL,
)

_LIVE_RAMP = (
    "#0b0b1a", "#575660", "#575660", "#5a5a6f",
    "#2d6596", "#2d6596", "#557690", "#557690",
    "#9a7268", "#9a7268", "#549ec8", "#549ec8",
    "#dbab67", "#dbab67", "#c2c2c5", "#c2c2c5",
)

_MISSING_THEME = "csg-theme-that-does-not-exist.theme"


class HarnessError(AssertionError):
    """An internal harness failure.

    Subclassing AssertionError means an unexpected error surfaces as a failed
    test rather than an error-pass or, worse, a skipped green.
    """


class _BundledDirResolver:
    def __init__(self, templates_dir: Path) -> None:
        self._templates_dir = templates_dir

    def resolve(self, settings_dir: Path | None = None) -> Path:
        return self._templates_dir


def _c(hexstr: str) -> Color:
    return Color(hexstr, tuple(int(hexstr[i : i + 2], 16) for i in (1, 3, 5)))


def _btop_bin() -> str:
    """Resolve btop, or skip VISIBLY -- never pass silently."""
    path = shutil.which("btop")
    if path is None:
        pytest.skip(
            "btop binary not installed: theme LOAD/APPLY cannot be proved here. "
            "This is a skip, not a pass -- install btop to exercise this channel."
        )
    return path


@pytest.fixture(scope="module")
def btop_bin() -> str:
    return _btop_bin()


@pytest.fixture(scope="module")
def rendered_themes(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """The three real artifacts, rendered once through the production renderer."""
    # tests/integration/adapters/ -> package root
    pkg_dir = Path(__file__).resolve().parents[3]
    templates_dir = pkg_dir / "src" / "color_scheme_generator" / "defaults" / "templates"
    assert templates_dir.is_dir(), templates_dir
    scheme = ColorScheme(
        background=_c("#0b0b1a"),
        foreground=_c("#c2c2c5"),
        cursor=_c("#c2c2c5"),
        colors=tuple(_c(h) for h in _LIVE_RAMP),
        source_image=Path("/input/default.png"),
        backend=Backend.PYWAL,
        generated_at=datetime(2026, 9, 30, 13, 38, 39),
    )
    renderer = JinjaTemplateRenderer(_BundledDirResolver(templates_dir))
    out_dir = tmp_path_factory.mktemp("btop-themes")
    rendered: dict[str, Path] = {}
    for fmt in VARIANTS:
        path = out_dir / f"colors.{fmt.value}"
        renderer.render(f"colors.{fmt.value}.j2", scheme, path)
        rendered[fmt.value] = path
    return rendered


def _stage(
    root: Path,
    btop_bin: str,
    color_theme: str,
    themes: Sequence[Path],
) -> tuple[bytes, str]:
    """Run btop on a private pty with a staged themes dir; return (frame, log).

    ``color_theme`` is written to btop.conf verbatim and the theme files are
    copied into the discovered themes dir, so the caller controls exactly one
    thing: whether ``color_theme`` resolves.
    """
    (root / "state").mkdir(parents=True, exist_ok=True)
    themes_dir = root / "config/btop/themes"
    themes_dir.mkdir(parents=True, exist_ok=True)
    for src in themes:
        shutil.copy(src, themes_dir / src.name)

    (root / "config/btop/btop.conf").write_text(
        f'color_theme = "{color_theme}"\n'
        'log_level = "DEBUG"\n'
        "update_ms = 3000\n"
    )
    env = dict(
        os.environ,
        XDG_STATE_HOME=str(root / "state"),
        XDG_CONFIG_HOME=str(root / "config"),
        TERM="xterm-256color",
        COLORTERM="truecolor",
    )

    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", HEIGHT, WIDTH, 0, 0))
    proc = subprocess.Popen(
        [btop_bin, "--no-tty"],
        stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True,
    )
    os.close(slave)
    try:
        time.sleep(SETTLE_SECONDS)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        os.set_blocking(master, False)
        buf = b""
        while True:
            ready, _, _ = select.select([master], [], [], 0.5)
            if not ready:
                break
            try:
                chunk = os.read(master, 65536)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
    finally:
        os.close(master)

    log = root / "state/btop.log"
    return buf, log.read_text(errors="replace") if log.is_file() else ""


def frame_colors(frame: bytes) -> set[str]:
    """Every 24-bit SGR colour in the frame, both fg (38;2) and bg (48;2)."""
    out: set[str] = set()
    for r, g, b in re.findall(rb"(?:38|48);2;(\d+);(\d+);(\d+)", frame):
        out.add(f"#{int(r):02x}{int(g):02x}{int(b):02x}")
    return out


def file_colors(path: Path) -> set[str]:
    text = path.read_text()
    return {"#" + h.lower() for h in re.findall(r'="#([0-9a-fA-F]{6})"', text)}


def loaded_theme_paths(log: str) -> list[str]:
    return [
        line.split("Loading theme file: ", 1)[1].strip()
        for line in log.splitlines()
        if "Loading theme file:" in line
    ]


def assert_theme_applied(
    root: Path,
    btop_bin: str,
    theme: Path,
    staged: Sequence[Path],
    default_colors: frozenset[str],
) -> None:
    """Assert BOTH channels for one theme. Raises on any failure, never returns quietly."""
    try:
        frame, log = _stage(root, btop_bin, theme.name, staged)
    except Exception as exc:  # a crash must be a FAIL, never a pass
        raise HarnessError(
            f"{theme.name}: harness error: {type(exc).__name__}: {exc}"
        ) from exc

    loaded = loaded_theme_paths(log)
    assert loaded, (
        f"{theme.name}: btop logged no 'Loading theme file:' at all -- it never "
        f"loaded any theme and silently fell back to Default_theme "
        f"(btop_theme.cpp:465)"
    )
    assert loaded[0].endswith(theme.name), (
        f"{theme.name}: btop loaded {loaded[0]!r}, not our theme"
    )

    got = frame_colors(frame)
    assert got, f"{theme.name}: no 24-bit colours in the captured frame"
    want = file_colors(theme)
    hit = want & got
    leaked = got & default_colors

    assert not leaked, (
        f"{theme.name}: Default_theme colours leaked into the frame: {sorted(leaked)}"
    )
    # "Dominated by the theme's colours" -- measured over the FRAME, not over
    # the file. A 200x50 frame shows at most a handful of gradient stops at
    # once, so requiring half the file's 48-key palette to appear is
    # unsatisfiable; what actually distinguishes a themed run is that nearly
    # every colour ON SCREEN came from our file.
    dominance = len(hit) / len(got)
    assert hit, (
        f"{theme.name}: none of the theme's colours were painted; "
        f"frame had {sorted(got)}, theme has {sorted(want)}"
    )
    assert dominance >= 0.6, (
        f"{theme.name}: only {len(hit)}/{len(got)} painted colours came from the "
        f"theme ({dominance:.0%}); the frame is not dominated by it. "
        f"frame={sorted(got)}"
    )


@pytest.fixture(scope="module")
def default_frame_colors(
    btop_bin: str, tmp_path_factory: pytest.TempPathFactory
) -> frozenset[str]:
    """MEASURE what btop paints when ``color_theme`` cannot resolve.

    This is the negative signal for the positive cases, derived rather than
    hardcoded: it is literally btop's silent ``Default_theme`` fallback
    (``btop_theme.cpp:465``), captured from the same binary under test.
    """
    root = tmp_path_factory.mktemp("btop-default")
    staged = []
    frame, log = _stage(root, btop_bin, _MISSING_THEME, staged)
    colors = frame_colors(frame)
    assert colors, "btop painted no colours at all even on the fallback path"
    assert not loaded_theme_paths(log) or not any(
        p.endswith(_MISSING_THEME) for p in loaded_theme_paths(log)
    ), "btop loaded the missing theme; the fallback is not being exercised"
    return frozenset(colors)


@pytest.mark.parametrize("fmt", VARIANTS, ids=[f.value for f in VARIANTS])
def test_generated_theme_is_proved_applied(
    fmt: ColorFormat,
    rendered_themes: dict[str, Path],
    btop_bin: str,
    default_frame_colors: frozenset[str],
    tmp_path: Path,
) -> None:
    theme = rendered_themes[fmt.value]
    staged = [rendered_themes[f.value] for f in VARIANTS]
    assert_theme_applied(
        tmp_path / fmt.value.replace(".", "_"),
        btop_bin,
        theme,
        staged,
        default_frame_colors,
    )


def test_unresolvable_theme_is_detected(
    rendered_themes: dict[str, Path],
    btop_bin: str,
    default_frame_colors: frozenset[str],
    tmp_path: Path,
) -> None:
    """NEGATIVE CONTROL -- the positive cases above are meaningless without it.

    Every theme file is staged and therefore DISCOVERABLE, but ``color_theme``
    names one that is not present. btop must then silently fall back to
    ``Default_theme``: no load log line naming our theme, and its own colours on
    the frame. This is the exact condition the positive cases claim to rule
    out, and it is what gives them their meaning.
    """
    staged = [rendered_themes[f.value] for f in VARIANTS]
    try:
        frame, log = _stage(tmp_path / "control", btop_bin, _MISSING_THEME, staged)
    except Exception as exc:
        raise HarnessError(
            f"negative control harness error: {type(exc).__name__}: {exc}"
        ) from exc

    # Channel 1 fails: the load assertion is exactly "btop logged a
    # 'Loading theme file:' line naming our file". Here it cannot hold.
    loaded = loaded_theme_paths(log)
    assert not any(p.endswith(_MISSING_THEME) for p in loaded), (
        "btop claimed to load a theme file that does not exist"
    )
    for theme in staged:
        assert not any(p.endswith(theme.name) for p in loaded), (
            f"NEGATIVE CONTROL BROKEN: btop logged a load of {theme.name} even "
            f"though color_theme was {_MISSING_THEME!r}"
        )

    # Channel 2: the frame must be Default's colours, not ours.
    got = frame_colors(frame)
    assert got, "negative control produced no colours at all -- the run never happened"
    # A captured frame is not perfectly reproducible -- a meter can land on a
    # different gradient stop between runs -- so compare by OVERLAP, not
    # equality. What must hold is that the frame is overwhelmingly Default's
    # and contains none of ours.
    default = set(default_frame_colors)
    union = got | default
    jaccard = len(got & default) / len(union)
    assert jaccard >= 0.6, (
        "NEGATIVE CONTROL BROKEN: the fallback frame does not look like the "
        f"measured Default frame (jaccard={jaccard:.2f}). "
        f"got={sorted(got)} default={sorted(default)}"
    )
    for theme in staged:
        assert not (got & file_colors(theme)), (
            "NEGATIVE CONTROL BROKEN: our theme's colours painted even though "
            f"color_theme did not resolve to it ({theme.name})"
        )


def test_harness_error_is_reported_as_failure_not_pass(
    rendered_themes: dict[str, Path], tmp_path: Path
) -> None:
    """An internal error must surface as a FAILURE, never as a pass or a skip.

    Pointed at a nonexistent btop binary, ``_stage`` raises ``FileNotFoundError``
    inside ``assert_theme_applied``; that must be converted to ``HarnessError``
    (an AssertionError subclass) so pytest records a failure.
    """
    theme = rendered_themes[ColorFormat.BTOP_MINIMAL.value]
    staged = list(rendered_themes.values())
    with pytest.raises(HarnessError) as excinfo:
        assert_theme_applied(
            tmp_path / "boom",
            "/nonexistent/btop-binary",
            theme,
            staged,
            frozenset(),
        )
    assert "harness error" in str(excinfo.value)
    assert issubclass(HarnessError, AssertionError)


def test_frame_colour_extraction_reads_both_foreground_and_background() -> None:
    frame = b"\x1b[38;2;11;22;33m x \x1b[48;2;44;55;66m y \x1b[38;5;9m z"
    assert frame_colors(frame) == {"#0b1621", "#2c3742"}


def test_missing_btop_binary_is_a_visible_skip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No btop -> skip WITH A STATED REASON, never a silent green."""
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    with pytest.raises(pytest.skip.Exception) as excinfo:
        _btop_bin()
    assert "btop binary not installed" in str(excinfo.value)
    assert "not a pass" in str(excinfo.value)


def test_btop_binary_resolves_on_this_machine(btop_bin: str) -> None:
    assert shutil.which(btop_bin) is not None


def test_file_colors_ignores_the_empty_two_stop_marker(tmp_path: Path) -> None:
    probe = tmp_path / "probe.theme"
    probe.write_text(
        'theme[main_bg]="#0b0b1a"\ntheme[temp_end]="#dbab67"\ntheme[download_mid]=""\n'
    )
    assert file_colors(probe) == {"#0b0b1a", "#dbab67"}
