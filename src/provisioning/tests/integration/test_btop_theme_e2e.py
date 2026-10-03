"""btop integration — end-to-end, fully machine-checkable (spec tasks 5.3-5.10).

Every assertion in this module is an EXIT CODE. Nothing here requires a person
to watch a running btop: theme discovery, theme application, palette
propagation, the save_config_on_exit guarantee, the backup guard, and
idempotence are all read from btop's own DEBUG log, a frame captured from a
real pty, or the filesystem.

What runs for real
------------------
- REAL ``ansible-playbook`` renders ``btop.conf`` and creates the spine's
  ``btop/themes/`` dir (tasks 5.3, 5.8-5.10).
- REAL ``ansible-playbook config-links.yaml`` creates the ``~/.config/btop``
  symlink and exercises the migrate-then-backup guard (tasks 5.9, 5.10).
- REAL ``btop`` on a REAL pty, DEBUG-logged (tasks 5.5, 5.6, 5.8).
- A real 3-hop symlink chain — spine pointer -> ``current/`` -> palette cache
  entry — i.e. the exact topology the runtime's ``repoint_consumer_symlinks``
  builds, so btop's ``extension() == ".theme"`` and ``access(R_OK)``
  predicates are exercised against it rather than against a plain file.

DEVIATION (stated, not silent) — task 5.7 "after ``wallpaper set``"
------------------------------------------------------------------
This test drives the swap at the layer the swap is defined at: it repoints
``current/`` at a NEW palette cache entry and re-places the three consumer
pointers, which is verbatim what ``CacheSeeder.repoint_consumer_symlinks``
does. It does NOT shell out to ``dotfiles-runtime wallpaper set``, because
the CSG ``btop-*.theme`` backends that command needs are a SIBLING change
that does not exist in this worktree — invoking it here would fail on a
missing template, not on a broken pointer. The palette CONTENT is synthetic
(crafted in ``_THEME_BODY``) for the same reason: btop's theme FILE format is
btop's, and the palette DERIVATION from a wallpaper is CSG's, not this
change's. Both are covered by the sibling changes' own gates.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

from tests.integration.btop_theme_harness import (
    ThemeApplicationError,
    assert_theme_applied,
    btop_binary,
)

pytestmark = pytest.mark.integration

_BTOP = btop_binary()
if _BTOP is None:
    pytest.skip(
        "btop not installed — the theme-APPLICATION gate needs real btop output "
        "(its DEBUG log + a pty frame). Discovery/backup/idempotence gates in "
        "test_btop_config_role.py still run.",
        allow_module_level=True,
    )

_ANSIBLE_PLAYBOOK = shutil.which("ansible-playbook")
if _ANSIBLE_PLAYBOOK is None:
    pytest.skip(
        "ansible-playbook not on PATH; skipping the provisioned-machine gates",
        allow_module_level=True,
    )

_DIFFICULTIES = ("minimal", "balanced", "full")
_SELECTED = "colors.btop-minimal.theme"

# btop's Theme parser: `key="#rrggbb"`, `#` comments only at column 0. Colors
# here are deliberately outside btop's Default_theme palette so "our colors
# painted, zero Default leak" is a real signal, and they differ per difficulty
# so a stale palette entry is detectable by content (task 5.7).
# fmt: off
_THEME_BODY: dict[str, dict[str, str]] = {
    "minimal": {
        "main_bg": "#101418", "main_fg": "#c8d0d8", "title": "#e05561",
        "hi_fg": "#4aa5d8", "selected_bg": "#1c242c", "inactive_fg": "#586470",
        "cpu_mid": "#4aa5d8", "cpu_end": "#9ad0e8",
    },
    "balanced": {
        "main_bg": "#14100c", "main_fg": "#d8cec0", "title": "#d8734a",
        "hi_fg": "#d8a04a", "selected_bg": "#241c14", "inactive_fg": "#706450",
        "cpu_mid": "#d8a04a", "cpu_end": "#f0d0a0",
    },
    "full": {
        "main_bg": "#0c1010", "main_fg": "#c0d8d0", "title": "#3ad8a0",
        "hi_fg": "#3ad8c0", "selected_bg": "#142420", "inactive_fg": "#507060",
        "cpu_mid": "#3ad8a0", "cpu_end": "#a0f0d8",
    },
}
# fmt: on


def _find_ansible_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError("src/provisioning/ansible/ not found walking up from the test file")


_ANSIBLE_DIR = _find_ansible_dir()
_PLAYBOOKS_DIR = _ANSIBLE_DIR / "playbooks"


def _theme_text(difficulty: str, salt: str = "") -> str:
    """A renderable .theme file for one difficulty.

    ``salt`` shifts the accent pair so a swapped palette entry is
    content-distinguishable (task 5.7 asserts contents CHANGED, not just that
    the files still exist).
    """
    palette = dict(_THEME_BODY[difficulty])
    if salt:
        base = int(salt, 16)
        palette["hi_fg"] = f"#{(base & 0xFFFFFF):06x}"
        palette["cpu_end"] = f"#{(0xFFFFFF - base) & 0xFFFFFF:06x}"
    return "".join(f'theme[{key}]="{value}"\n' for key, value in palette.items())


def _run_playbook(playbook: Path, install: Path, home: Path, xdg: Path) -> str:
    """Run one playbook against the throwaway machine. Never mocked."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ANSIBLE_", "XDG_"))}
    env.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(xdg),
            "ANSIBLE_CONFIG": str(_ANSIBLE_DIR / "ansible.cfg"),
        }
    )
    result = subprocess.run(
        [_ANSIBLE_PLAYBOOK, str(playbook), "-e", f"install_dir={install}"],
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )
    assert result.returncode == 0, (
        f"{playbook.name} failed:\n{result.stdout}\n{result.stderr}"
    )
    return result.stdout


class _Machine:
    """A throwaway "provisioned" machine: home, XDG config home, install spine.

    Built by REAL playbooks, not by hand — the spine contents under
    ``config/btop/`` must be the role's output or the whole gate is vacuous.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.home = root / "home"
        self.xdg = root / "xdg"
        self.install = root / "install"
        self.state = root / "state"
        for path in (self.home, self.xdg, self.install):
            path.mkdir(parents=True, exist_ok=True)
        self.btop_spine = self.install / "config" / "btop"
        self.btop_xdg = self.xdg / "btop"

    def provision(self) -> None:
        _run_playbook(_PLAYBOOKS_DIR / "btop-config.yaml", self.install, self.home, self.xdg)
        _run_playbook(_PLAYBOOKS_DIR / "config-links.yaml", self.install, self.home, self.xdg)

    # ── the runtime side, reproduced at the seeder's own layer ──────────────

    def seed_palette(self, entry_hash: str, salt: str = "") -> Path:
        """Write a palette cache entry and point ``current/`` at it, then place
        the three consumer pointers — the exact topology
        ``CacheSeeder.repoint_consumer_symlinks`` produces (spine pointer ->
        ``current/`` -> cache entry)."""
        cache_entry = self.state / "dotfiles" / "cache" / "palettes" / entry_hash
        cache_entry.mkdir(parents=True, exist_ok=True)
        current = self.state / "dotfiles" / "current"
        current.mkdir(parents=True, exist_ok=True)
        themes_dir = self.btop_spine / "themes"
        themes_dir.mkdir(parents=True, exist_ok=True)
        for difficulty in _DIFFICULTIES:
            name = f"colors.btop-{difficulty}.theme"
            (cache_entry / name).write_text(_theme_text(difficulty, salt))
            link = current / name
            if link.is_symlink() or link.exists():
                link.unlink()
            link.symlink_to(cache_entry / name)
            pointer = themes_dir / name
            if pointer.is_symlink() or pointer.exists():
                pointer.unlink()
            pointer.symlink_to(current / name)
        return cache_entry


@pytest.fixture
def machine(tmp_path: Path) -> _Machine:
    m = _Machine(tmp_path)
    m.provision()
    m.seed_palette("a" * 64)
    return m


# ── 5.3 config assertions, no launching ────────────────────────────────────


class TestRenderedConfig:
    def test_selects_the_minimal_theme_and_disables_save_on_exit(self, machine: _Machine) -> None:
        conf = machine.btop_spine / "btop.conf"
        assert conf.is_file()
        text = conf.read_text()
        assert f'color_theme = "{_SELECTED}"' in text
        assert "save_config_on_exit = false" in text

    def test_every_other_key_is_btops_stock_default(self, machine: _Machine) -> None:
        """D6: every other setting stays at btop's default, which operationally
        means the key is ABSENT — btop applies its own default for a key it
        does not find. A key that IS present must equal btop's default.

        The stock set is read from ``btop --default-config`` (btop's own
        authority), not from a hand-typed table.
        """
        defaults = _btop_stock_defaults()
        present = _parse_config(machine.btop_spine / "btop.conf")
        for key, value in present.items():
            if key == "color_theme":
                continue
            if key == "save_config_on_exit":
                assert value == "false", (
                    "save_config_on_exit is the ONE deliberate non-default value"
                )
                continue
            assert key in defaults, f"btop.conf sets unknown key {key!r}"
            assert value == defaults[key], (
                f"btop.conf sets {key}={value!r} but btop's stock default is "
                f"{defaults[key]!r} — every setting other than color_theme and "
                "save_config_on_exit must stay at btop's default"
            )

    def test_themes_dir_exists_before_any_swap(self, tmp_path: Path) -> None:
        """D4: the role creates config/btop/themes/ itself. The runtime's
        seeder skips a pointer whose parent is missing and NEVER mkdirs into
        the spine, so without this dir the first swap drops all three."""
        m = _Machine(tmp_path)
        _run_playbook(_PLAYBOOKS_DIR / "btop-config.yaml", m.install, m.home, m.xdg)
        assert (m.install / "config" / "btop" / "themes").is_dir()

    def test_native_location_resolves_into_the_spine(self, machine: _Machine) -> None:
        """~/.config/btop IS the spine (config_links), so btop reads its config
        and scans its themes at their native XDG location."""
        assert machine.btop_xdg.is_symlink()
        assert machine.btop_xdg.resolve() == machine.btop_spine.resolve()
        assert (machine.btop_xdg / "btop.conf").resolve() == (
            machine.btop_spine / "btop.conf"
        ).resolve()


def _parse_config(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"')
    return out


def _btop_stock_defaults() -> dict[str, str]:
    """btop's own defaults, parsed from ``btop --default-config``.

    Read from the binary rather than transcribed, so this gate cannot drift
    from the installed btop.
    """
    text = subprocess.run(
        [_BTOP, "--default-config"], capture_output=True, text=True, timeout=60
    ).stdout
    defaults = _parse_config(_write_tmp(text))
    return defaults


def _write_tmp(text: str) -> Path:
    import tempfile

    handle = tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False)
    handle.write(text)
    handle.close()
    return Path(handle.name)


# ── 5.4 discoverability, using btop's own predicates ───────────────────────


class TestThemeDiscovery:
    """``Theme::updateThemes`` (btop_theme.cpp:430-442) admits an entry iff
    ``file.path().extension() == ".theme"`` (LEXICAL — reads the LINK's own
    name) and ``access(path, R_OK) != -1`` (FOLLOWS the chain). Asserting
    exactly those two predicates on the real 3-hop chain proves discoverability
    without launching btop."""

    @pytest.mark.parametrize("difficulty", _DIFFICULTIES)
    def test_meets_btops_discovery_predicates(self, machine: _Machine, difficulty: str) -> None:
        import os as _os

        name = f"colors.btop-{difficulty}.theme"
        pointer = machine.btop_spine / "themes" / name
        assert pointer.is_symlink(), "the theme must be a POINTER, not a copy"
        assert pointer.suffix == ".theme", (
            "extension() is lexical on the link's own name — a renamed pointer "
            "is invisible to btop's scan"
        )
        assert _os.access(pointer, _os.R_OK), "access(R_OK) must follow the chain"
        resolved = pointer.resolve()
        assert resolved.is_file()
        assert resolved.suffix == ".theme"
        assert "palettes" in resolved.parts, (
            f"the chain must land in a palette cache entry; got {resolved}"
        )

    def test_all_three_are_listed_in_the_themes_dir(self, machine: _Machine) -> None:
        names = {p.name for p in (machine.btop_spine / "themes").iterdir()}
        for difficulty in _DIFFICULTIES:
            assert f"colors.btop-{difficulty}.theme" in names


# ── 5.5 / 5.6 application, proven from btop's own output ───────────────────


class TestThemeApplication:
    def test_btop_loads_and_paints_the_generated_theme(self, machine: _Machine) -> None:
        frame, log = assert_theme_applied(
            config_home=machine.xdg,
            state_home=machine.state,
            theme_name=_SELECTED,
            theme_file=machine.btop_spine / "themes" / _SELECTED,
            binary=_BTOP,
        )
        assert b"38;2;" in frame or b"48;2;" in frame
        assert "Loading theme file:" in log

    def test_negative_control_a_renamed_theme_fails(self, machine: _Machine) -> None:
        """5.6: proving 5.5 is not vacuously green. Pointing the PROVISIONED
        config at a theme that does not exist must make the SAME harness fail —
        this is the check that would catch a broken config_links link or a
        dangling consumer pointer, because btop's own failure mode for both is
        a silent Default_theme fallback."""
        conf = machine.btop_spine / "btop.conf"
        conf.write_text(conf.read_text().replace(_SELECTED, "csg-minimal.theme"))
        with pytest.raises(ThemeApplicationError):
            assert_theme_applied(
                config_home=machine.xdg,
                state_home=machine.state,
                theme_name=_SELECTED,
                theme_file=machine.btop_spine / "themes" / _SELECTED,
                binary=_BTOP,
            )

    def test_negative_control_a_dangling_pointer_fails(self, machine: _Machine) -> None:
        """Same proof from the other end: break the runtime's pointer (the
        seeder's `missing target` skip) and the harness must fail too."""
        machine.seed_palette("b" * 64)
        for difficulty in _DIFFICULTIES:
            pointer = machine.btop_spine / "themes" / f"colors.btop-{difficulty}.theme"
            target = machine.state / "dotfiles" / "current" / pointer.name
            target.unlink()
        with pytest.raises(ThemeApplicationError):
            assert_theme_applied(
                config_home=machine.xdg,
                state_home=machine.state,
                theme_name=_SELECTED,
                theme_file=machine.btop_spine / "themes" / _SELECTED,
                binary=_BTOP,
            )


# ── 5.7 palette propagation ────────────────────────────────────────────────


class TestPalettePropagation:
    def test_a_swap_updates_all_three_theme_files_in_place(self, machine: _Machine) -> None:
        """After a palette swap every theme file reflects the NEW entry and
        still resolves. The reload deferral (D7) is asserted as a NON-action:
        this test writes files and never signals, kills, or relaunches btop,
        and no btop is running here at all."""
        themes = machine.btop_spine / "themes"
        before = {p.name: p.read_text() for p in themes.iterdir()}
        old_entry = (machine.btop_spine / "themes" / _SELECTED).resolve().parent

        new_entry = machine.seed_palette("c" * 64, salt="abcdef")
        after = {p.name: p.read_text() for p in themes.iterdir()}

        assert set(before) == set(after)
        for name in before:
            assert after[name] != before[name], (
                f"{name} did not change across the swap — the consumer pointer "
                "is stale or the seeder never repointed it"
            )
            resolved = (themes / name).resolve()
            assert resolved.parent == new_entry, f"{name} still lands in the old entry"
            assert resolved.parent != old_entry

    def test_the_swap_is_visible_on_the_next_launch(self, machine: _Machine) -> None:
        """D7: btop resolves its theme once at startup, so the swap reaches
        btop on the NEXT launch — the frame proves the new palette is what a
        fresh btop paints."""
        machine.seed_palette("c" * 64, salt="abcdef")
        assert_theme_applied(
            config_home=machine.xdg,
            state_home=machine.state,
            theme_name=_SELECTED,
            theme_file=machine.btop_spine / "themes" / _SELECTED,
            binary=_BTOP,
        )


# ── 5.8 the save_config_on_exit guarantee ──────────────────────────────────


class TestSaveConfigOnExit:
    def test_btop_does_not_rewrite_the_spine_owned_conf(self, machine: _Machine) -> None:
        """The risk that made save_config_on_exit = false mandatory: btop
        defaults it TRUE and Config::write() truncates the whole config on
        exit, and ~/.config/btop is a symlink into the spine — so the default
        would land the user's UI changes in version control. Asserted by
        HASH, run to termination, not assumed."""
        conf = machine.btop_spine / "btop.conf"
        before = hashlib.sha256(conf.read_bytes()).hexdigest()
        mtime_before = conf.stat().st_mtime_ns

        from tests.integration.btop_theme_harness import run_btop

        # A real btop on a real pty, sent SIGINT after it has drawn frames —
        # SIGINT is the signal that actually runs btop's shutdown path (see the
        # harness docstring); SIGTERM would leave this gate vacuous.
        run_btop(
            config_home=machine.xdg,
            state_home=machine.state,
            binary=_BTOP,
            exit_signal=signal.SIGINT,
        )
        # Margin, not a wait-for-event: the write is synchronous with exit.
        time.sleep(1.0)

        after = hashlib.sha256(conf.read_bytes()).hexdigest()
        assert after == before, (
            "btop rewrote the provisioning-owned btop.conf through the spine "
            "symlink — save_config_on_exit is not doing its job"
        )
        assert conf.stat().st_mtime_ns == mtime_before

    def test_negative_control_btop_does_rewrite_when_the_setting_is_true(
        self, machine: _Machine
    ) -> None:
        """Without this control, 5.8 would be vacuously green: btop might
        simply never write. Flip the setting back to its default and the SAME
        run must change the file — proving the hash check has teeth."""
        conf = machine.btop_spine / "btop.conf"
        conf.write_text(conf.read_text().replace(
            "save_config_on_exit = false", "save_config_on_exit = true"
        ))
        before = hashlib.sha256(conf.read_bytes()).hexdigest()

        from tests.integration.btop_theme_harness import run_btop

        run_btop(
            config_home=machine.xdg,
            state_home=machine.state,
            binary=_BTOP,
            exit_signal=signal.SIGINT,
        )
        time.sleep(1.0)

        assert hashlib.sha256(conf.read_bytes()).hexdigest() != before, (
            "btop did not rewrite its config even with save_config_on_exit = "
            "true — the hash assertion cannot distinguish the two cases, so it "
            "proves nothing"
        )


# ── 5.9 / 5.10 the backup guard and idempotence ────────────────────────────


class TestBackupGuardAndIdempotence:
    def test_a_preexisting_config_dir_is_preserved_not_deleted(self, tmp_path: Path) -> None:
        """config_links must move a real ~/.config/btop aside to a timestamped
        backup — never delete it — then replace it with the managed link."""
        m = _Machine(tmp_path)
        _run_playbook(_PLAYBOOKS_DIR / "btop-config.yaml", m.install, m.home, m.xdg)

        marker = m.btop_xdg / "user-theme-backup-marker.conf"
        m.btop_xdg.mkdir(parents=True, exist_ok=True)
        marker.write_text("# hand-written by the user\n")

        _run_playbook(_PLAYBOOKS_DIR / "config-links.yaml", m.install, m.home, m.xdg)

        assert m.btop_xdg.is_symlink(), "~/.config/btop must become the spine link"
        assert m.btop_xdg.resolve() == m.btop_spine.resolve()
        backups = sorted(_backup_root(m).glob("btop-*"))
        assert backups, (
            "a real ~/.config/btop must be moved aside to a timestamped backup "
            f"under the backup root ({_backup_root(m)}), never deleted"
        )
        preserved = [b for b in backups if (b / marker.name).is_file()]
        assert preserved, (
            f"the user's file is not readable at any backup path: {backups}"
        )
        assert (preserved[0] / marker.name).read_text() == "# hand-written by the user\n"

    def test_rerunning_creates_no_second_backup(self, machine: _Machine) -> None:
        """Idempotence: a ~/.config/btop that already points at the spine is a
        no-op — nothing moved, no second backup dir."""
        backup_root = _backup_root(machine)
        before = sorted(backup_root.glob("btop-*")) if backup_root.is_dir() else []
        _run_playbook(
            _PLAYBOOKS_DIR / "config-links.yaml", machine.install, machine.home, machine.xdg
        )
        after = sorted(backup_root.glob("btop-*")) if backup_root.is_dir() else []
        assert after == before, "a re-run must not create a second backup"
        assert machine.btop_xdg.is_symlink()


def _backup_root(machine: _Machine) -> Path:
    """The config_links backup root, read from the role's vars (never guessed)."""
    import yaml

    vars_path = _ANSIBLE_DIR / "roles" / "config_links" / "vars" / "main.yml"
    data = yaml.safe_load(vars_path.read_text())
    template = str(data["config_links_backup_root"])
    assert template == "{{ config_links_xdg_config_home }}/.dotfiles-backups", (
        f"config_links_backup_root moved; update _backup_root(): {template!r}"
    )
    return machine.xdg / ".dotfiles-backups"
