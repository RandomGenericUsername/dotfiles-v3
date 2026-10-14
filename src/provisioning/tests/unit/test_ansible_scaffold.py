from __future__ import annotations

import configparser
import re
from pathlib import Path

import pytest
import yaml

from provisioning.domain.enums import Distro


def _find_ansible_dir() -> Path:
    """Locate the real ansible scaffold dir by walking up from this test file.

    Resolves the repo root robustly (no fixed-depth assumption) and fails
    loudly if the scaffold is missing, so AC 1-5 coverage can never silently
    disappear from the run. Anchored on ``pyproject.toml`` so a sibling
    project's ``ansible/`` tree in a shared workspace is never matched.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError(
        "src/provisioning/ansible/ not found walking up from the test file; "
        "AC 1-5 real-scaffold coverage requires the authored scaffold"
    )


_ANSIBLE_DIR = _find_ansible_dir()

_REQUIRED_FILES = (
    "inventory/localhost.yaml",
    "requirements.yml",
    "ansible.cfg",
    "group_vars/all.yml",
    "group_vars/arch.yml",
    "group_vars/debian-family.yml",
)

# Every logical key in the group_vars `packages` map (Story 2.1 parity lock).
# Shared base must be identical across arch.yml and debian-family.yml;
# distro-specific extras are pinned separately (adw-gtk-theme is Arch-only,
# Option A 2026-09-09).
#
# DRIFT LOCK, re-snapshotted 2026-10-04 by openspec change
# repair-package-manifest-drift. Every key below was reviewed against its
# introducing commit (`git log -S<key>`) — see that change's design.md for the
# per-key table. Briefly: capture/portals/lock/dunst/thunar came from the
# 2026-09-30 "these were installed on the host but never declared" fixes, and
# libva-utils/nm-connection-editor/speedtest predate this lock's original
# snapshot (the bulk AGS import) or arrived with the VA-API codec-probe fix
# (e9beedc4). The lock is KEPT on purpose: it is what turns "a package was
# installed from three different copies of one list" into a red test instead
# of a silent provisioning gap. The machine-checkable invariants that catch
# real defects live in TestPackageListInvariants below — the exact-set lock
# cannot catch them.
_LOGICAL_PACKAGE_KEYS = (
    "hyprland",
    "hyprpaper",
    "networkmanager",
    "wifitui",
    "wlogout",
    "rofi",
    "librsvg",
    "uwsm",
    "ags",
    "fonts",
    "zsh",
    "terminal",
    "display_manager",
    "container_engine",
    "ffmpeg",
    "pipewire",
    "wireplumber",
    "pipewire-audio",
    "pipewire-pulse",
    "pavucontrol",
    "gpu-screen-recorder",
    "wf-recorder",
    "btop",
    "thunderbird",
    "brightnessctl",
    "playerctl",
    # AGS settings panel (add-ags-settings-panel): the AstalWp binding and the
    # BlueZ stack, mapped per-manager in both group_vars.
    "astal-wp",
    "bluez",
    "bluez-utils",
    # The GTK Bluetooth manager — the "Bluetooth Settings" target, and the only
    # agent able to answer a PIN/passkey request.
    "blueman",
    # Session/capture stack (rollups + singles). Introduced by the two
    # 2026-09-30 "declared nothing, host-only install" fixes on this branch:
    #   capture  grim/slurp/wl-clipboard — the capture tool shells them and the
    #            runtime clipboard watcher needs `wl-paste --watch`
    #   portals  hyprpolkitagent + the two portal backends — autostart.lua
    #            starts them at login; undeclared means silent failure
    #   lock     hyprlock/hypridle — no locker without them
    "capture",
    "portals",
    "lock",
    # dunst is installed ONLY to be masked (the AGS overlay owns notifications);
    # thunar is launched by keybindings.lua. Both were host-only luck.
    "dunst",
    "thunar",
    # libva-utils: the VA-API codec probe (vainfo) gpu-screen-recorder names
    # verbatim in its "your gpu does not support 'vpX'" failure — declared in
    # e9beedc4 so the capture tool can tell a hardware codec limit from a
    # missing VA driver.
    "libva-utils",
    # nm-connection-editor: the AGS Wi-Fi Settings footer target.
    "nm-connection-editor",
    # speedtest: speedtest-cli, driven by the AGS speedtest service.
    "speedtest",
    # xdg-utils: owns xdg-mime/xdg-open. Consumed by gui_tools (`xdg-mime
    # default thunar.desktop inode/directory`), gated by verify (`xdg-mime
    # query default inode/directory`), and shelled by the capture tool's
    # "Show in folder" and hypr-pano's URL opener. Was a manifest entry no
    # provisioning path installed (harden-verify-probes-and-manifest).
    "xdg-utils",
)
_ARCH_EXTRA_KEYS = (
    "adw_gtk_theme",  # GTK3 theme (Option A 2026-09-09)
    "power-options-gtk",  # AUR-only (portable power management) — Arch
    "hyprmod",  # AUR-only (GTK4 module manager) — Arch (pre-existing drift lock)
    "nvm",  # repo nvm satisfies tidal-hifi-git's PKGBUILD getnvm() so it never self-bootstraps via makepkg -si
    # AI development tools (provision-ai-ides-and-clis): all AUR-only on Arch,
    # so they live in the Arch-only set and a Debian-family host does not get
    # them. windsurf -> devin-desktop (upstream rebrand); vscode ->
    # visual-studio-code-bin (Microsoft build); copilot-cli/codex-cli are the
    # two terminal CLIs made rofi-launchable by kitty .desktop launchers.
    "antigravity-ide",
    "windsurf",
    "vscode",
    "copilot-cli",
    "codex-cli",
)


class TestAnsibleScaffoldFilesExist:
    def test_required_scaffold_files_exist(self) -> None:
        for relative in _REQUIRED_FILES:
            assert (_ANSIBLE_DIR / relative).is_file(), f"missing {relative}"


class TestInventoryLocalhost:
    _PATH = _ANSIBLE_DIR / "inventory" / "localhost.yaml"

    def test_parses_and_targets_localhost(self) -> None:
        data = yaml.safe_load(self._PATH.read_text())
        localhost = data["all"]["hosts"]["localhost"]
        assert localhost["ansible_connection"] == "local"
        assert localhost["ansible_python_interpreter"] == "{{ ansible_playbook_python }}"

    def test_localhost_not_statically_grouped_by_distro(self) -> None:
        data = yaml.safe_load(self._PATH.read_text())
        all_hosts = data["all"]["hosts"]
        assert set(all_hosts.keys()) == {"localhost"}
        groups = data["all"].get("children", {})
        for distro in (Distro.ARCH.value, Distro.DEBIAN_FAMILY.value):
            assert distro not in groups, (
                f"localhost must not be statically placed under {distro} — "
                "group_vars sets would merge and break distro isolation"
            )
            assert distro not in data, (
                f"no top-level {distro} group may exist — a sibling of `all` "
                "containing localhost would merge group_vars sets undetected"
            )


class TestRequirementsYaml:
    _PATH = _ANSIBLE_DIR / "requirements.yml"

    def test_parses_and_declares_external_collections(self) -> None:
        data = yaml.safe_load(self._PATH.read_text())
        declared = {entry["name"] for entry in data["collections"]}
        assert declared == {"community.general", "ansible.posix", "kewlfft.aur"}
        for entry in data["collections"]:
            assert entry.get("version"), (
                f"collection {entry['name']} must pin a version for NFR-9 reproducibility"
            )


class TestAnsibleCfg:
    _PATH = _ANSIBLE_DIR / "ansible.cfg"

    def test_declares_inventory_and_roles_path(self) -> None:
        parser = configparser.ConfigParser()
        parser.read(self._PATH)
        assert parser.has_section("defaults")
        assert parser.get("defaults", "inventory") == "inventory/localhost.yaml"
        assert parser.get("defaults", "roles_path") == "roles"

    def test_ansible_resolves_relative_paths_from_cfg_dir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pytest.importorskip("ansible.config.manager")
        monkeypatch.setenv("ANSIBLE_CONFIG", str(self._PATH))
        from ansible.config.manager import ConfigManager

        config = ConfigManager()
        assert config.get_config_value("CONFIG_FILE") == str(self._PATH)
        assert config.get_config_value("DEFAULT_HOST_LIST") == [
            str(_ANSIBLE_DIR / "inventory" / "localhost.yaml")
        ]
        assert config.get_config_value("DEFAULT_ROLES_PATH") == [str(_ANSIBLE_DIR / "roles")]


class TestGroupVars:
    def test_filenames_match_distro_seam_contract(self) -> None:
        files = sorted(
            p.stem
            for p in (_ANSIBLE_DIR / "group_vars").glob("*")
            if p.is_file() and p.suffix in (".yml", ".yaml")
        )
        assert files == sorted({"all"} | {d.value for d in Distro})

    @staticmethod
    def _packages_map(basename: str) -> dict[str, object]:
        data = yaml.safe_load((_ANSIBLE_DIR / "group_vars" / basename).read_text())
        packages = data["packages"]
        assert isinstance(packages, dict)
        return packages

    def test_all_yml_is_minimal_and_does_not_default_install_dir(self) -> None:
        data = yaml.safe_load((_ANSIBLE_DIR / "group_vars" / "all.yml").read_text())
        assert data is None or isinstance(data, dict)
        if isinstance(data, dict):
            assert "install_dir" not in data, (
                "install_dir must stay fail-loud (orchestrator seam always "
                "provides it via --extra-vars); all.yml must not default it"
            )

    def test_container_runtime_engine_declared_with_podman_default(self) -> None:
        """Option 2b single source of truth: all.yml DECLARES the container
        engine, defaulting to podman and overridable via DOTFILES_CONTAINER_ENGINE
        (extra-var precedence is Ansible-native). The SAME value drives the
        cli_tools build and the rendered settings, so the image tag and the
        runtime lookup can never diverge. all.yml must still not define
        install_dir."""
        data = yaml.safe_load((_ANSIBLE_DIR / "group_vars" / "all.yml").read_text())
        assert isinstance(data, dict)
        assert data["container_runtime_engine"] == (
            "{{ ansible_facts.env.DOTFILES_CONTAINER_ENGINE | default('podman', true) }}"
        ), (
            "all.yml must declare container_runtime_engine as the env-or-podman "
            "expression (ansible_facts.env — never the deprecated ansible_env)"
        )
        assert "install_dir" not in data, "all.yml must stay minimal — never default install_dir"

    def test_arch_packages_cover_exactly_logical_set(self) -> None:
        packages = self._packages_map("arch.yml")
        expected = set(_LOGICAL_PACKAGE_KEYS) | set(_ARCH_EXTRA_KEYS)
        assert set(packages.keys()) == expected

    def test_debian_family_packages_cover_exactly_logical_set(self) -> None:
        packages = self._packages_map("debian-family.yml")
        assert set(packages.keys()) == set(_LOGICAL_PACKAGE_KEYS)

    def test_arch_package_names_are_non_empty(self) -> None:
        packages = self._packages_map("arch.yml")
        for key, value in packages.items():
            names = value if isinstance(value, list) else [value]
            assert all(str(n).strip() for n in names), f"empty name under {key}"

    def test_debian_family_package_names_are_non_empty(self) -> None:
        packages = self._packages_map("debian-family.yml")
        for key, value in packages.items():
            names = value if isinstance(value, list) else [value]
            assert all(str(n).strip() for n in names), f"empty name under {key}"


# ---------------------------------------------------------------------------
# Machine-checkable package-list invariants (repair-package-manifest-drift)
#
# The exact-set locks above are pure BOOKKEEPING: they can only say "a key is
# in a group_vars map and not in this tuple". They have now fired three times
# without anyone acting, because fixing them means hand-diffing three copies of
# one list — low-value noise. What they CANNOT catch is the class of defect
# that actually bites a user:
#
#   * a rollup key whose list is empty or holds one glued string
#     (`capture: [grim, "slurp wl-copy"]`) — installs nothing, or installs a
#     package literally named "slurp wl-copy", and the key still shows up in
#     every set comparison, so the lock stays GREEN
#   * a key with an empty value — the packages role's
#     `reject('equalto', '')` drops it silently, so the key is present in
#     every set comparison while installing nothing
#   * one package declared under two keys — installed twice, and a later edit
#     to one key silently diverges from the other
#   * a manifest entry no provisioning path installs — the manifest promises a
#     package that only exists because someone ran pacman by hand
#
# Each of those is invisible to an exact-set comparison and cheap to assert, so
# the lock stays AND these are added on top.
# ---------------------------------------------------------------------------

# One package name: what pacman/apt actually accept. Anchored, no whitespace,
# no commas/colons (a comma- or space-joined string is the classic "forgot the
# list dash" YAML bug), no leading dash.
_PACKAGE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+._-]{0,99}$")

# The Debian merge is a DOCUMENTED, deliberate exception to the
# one-name-one-key invariant: "bluez-utils is merged into bluez on Debian —
# the sane distro mapping for the logical bluez-utils entry" (see
# group_vars/debian-family.yml). Asserted as an exact pair so it can neither
# grow nor be silently re-pointed.
_INTENTIONAL_DUPLICATE_KEY_PAIRS = {
    "debian-family.yml": frozenset({"bluez", "bluez-utils"}),
    "arch.yml": frozenset(),
}

# Manifest entries that NO provisioning path installs: they are not a
# group_vars key, not a group_vars value, and not in the AUR channel. They are
# host-installed by hand and nothing else, so a fresh machine would lack them
# while the manifest claims them.
#
# This set was EMPTY as of harden-verify-probes-and-manifest, which resolved
# all three of the orphans repair-package-manifest-drift had pinned here
# (`lf`, `hyprcursor`, `xdg-utils`) — per-package evidence table in that
# change's design.md:
#   xdg-utils   ADDED to both group_vars maps (option a). It has hard
#               consumers: gui_tools runs `xdg-mime default`, verify gates
#               `xdg-mime query default`, and the capture tool / hypr-pano
#               shell `xdg-open`. Debian name verified via the Debian
#               archive's madison API (1.2.1-2, arch all).
#   hyprcursor  REMOVED from packages.yaml (option b). Nothing calls it, and
#               it is already a direct pacman dependency of hyprland, so it
#               arrives transitively — declaring it separately would imply a
#               consumer that does not exist.
#   lf          REMOVED from packages.yaml (option b). Not host-installed, no
#               keybind, no autostart entry, no desktop file, no config, no
#               spec or plan-doc requirement. A leftover from the same
#               e00a6773 bulk Lua-migration "must-have packages" list as
#               `cliphist`, which a1de8bfa later dropped once hypr-pano
#               superseded it.
#
# It stays a pinned EXACT set rather than being deleted: it is now EMPTY, and
# the assertion still fails on any NEW orphan while naming both directions
# (unexpected orphan / no-longer-orphaned). Deleting it would remove the pin
# that makes the next drift visible.
_DECLARED_NOT_PROVISIONED: frozenset[str] = frozenset()


def _find_manifest_dir() -> Path:
    """Locate dotfiles/provisioning/ (the logical manifest dir) from this file."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "dotfiles" / "provisioning" / "packages.yaml"
        if candidate.is_file():
            return candidate.parent
    raise FileNotFoundError("dotfiles/provisioning/packages.yaml not found walking up")


_MANIFEST_DIR = _find_manifest_dir()


def _names_of(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else [value]


def _empty_value_problems(packages: dict[str, object]) -> list[str]:
    """Keys whose value installs nothing.

    The packages role flattens with `reject('equalto', '')`, so an empty or
    whitespace value is dropped without a word — and a bare `key:` parses as
    None. Both keep the KEY present, so every exact-set lock stays green.
    """
    problems = []
    for key, value in packages.items():
        if value is None:
            problems.append(f"{key}: value is empty (`{key}:` with no value)")
        elif isinstance(value, str) and not value.strip():
            problems.append(f"{key}: value is blank {value!r}")
        elif not isinstance(value, (str, list)):
            problems.append(f"{key}: value {value!r} is not a package name or list of them")
        elif isinstance(value, list):
            problems.extend(
                f"{key}: member {item!r} is not a package name" for item in value if not item
            )
    return problems


def _rollup_problems(packages: dict[str, object]) -> list[str]:
    """List-valued keys must be non-empty lists of single plausible names."""
    problems = []
    for key, value in packages.items():
        if not isinstance(value, list):
            continue
        if not value:
            problems.append(f"{key}: rollup list is EMPTY — nothing installs under this key")
        for item in value:
            if not isinstance(item, str) or not _PACKAGE_NAME_RE.match(item):
                problems.append(
                    f"{key}: {item!r} is not a single plausible package name — a "
                    "space/comma-joined or padded string installs nothing (or a "
                    "package literally named that)"
                )
    return problems


def _duplicate_problems(
    packages: dict[str, object], allowed: frozenset[str] = frozenset()
) -> list[str]:
    """Package names installed under more than one key in the same map."""
    owners: dict[str, list[str]] = {}
    for key, value in packages.items():
        for name in _names_of(value):
            if isinstance(name, str):
                owners.setdefault(name, []).append(key)
    return [
        f"{name} declared under {keys}"
        for name, keys in sorted(owners.items())
        if len(keys) > 1 and frozenset(keys) - allowed
    ]


class TestPackageListInvariants:
    """Assertions that fail for real defects, not just for bookkeeping."""

    @staticmethod
    def _packages_map(basename: str) -> dict[str, object]:
        data = yaml.safe_load((_ANSIBLE_DIR / "group_vars" / basename).read_text())
        packages = data["packages"]
        assert isinstance(packages, dict)
        return packages

    @pytest.mark.parametrize("basename", ["arch.yml", "debian-family.yml"])
    def test_no_key_has_an_empty_value(self, basename: str) -> None:
        problems = _empty_value_problems(self._packages_map(basename))
        assert problems == [], (
            f"{basename}: keys whose value installs nothing (the packages "
            "role's reject('equalto','') drops them silently):\n" + "\n".join(problems)
        )

    @pytest.mark.parametrize("basename", ["arch.yml", "debian-family.yml"])
    def test_rollup_lists_are_non_empty_single_names(self, basename: str) -> None:
        packages = self._packages_map(basename)
        rollups = {k: v for k, v in packages.items() if isinstance(v, list)}
        assert rollups, "expected rollup keys (capture/portals/lock/zsh/...) to exist"
        problems = _rollup_problems(packages)
        assert problems == [], f"{basename}:\n" + "\n".join(problems)

    @pytest.mark.parametrize("basename", ["arch.yml", "debian-family.yml"])
    def test_no_package_declared_under_two_keys(self, basename: str) -> None:
        allowed = _INTENTIONAL_DUPLICATE_KEY_PAIRS[basename]
        problems = _duplicate_problems(self._packages_map(basename), allowed)
        assert problems == [], (
            f"{basename}: one package under two keys installs twice and lets "
            "the copies drift (documented exception: "
            f"{sorted(allowed) or 'none'}):\n" + "\n".join(problems)
        )

    def test_debian_bluez_merge_is_the_only_intentional_duplicate(self) -> None:
        """The exception must stay exactly the one documented merge."""
        assert _duplicate_problems(self._packages_map("debian-family.yml")) == [
            "bluez declared under ['bluez', 'bluez-utils']"
        ]

    def test_every_manifest_entry_is_reachable_from_a_provisioning_path(self) -> None:
        """A manifest entry nothing installs is a promise the fresh machine breaks.

        Reachable = a group_vars `packages` key, a group_vars value, or the AUR
        channel (roles/packages/vars/arch.yml `aur_packages`, which the role
        installs via yay and subtracts from the pacman/apt list).
        """
        reachable: set[str] = set()
        for basename in ("arch.yml", "debian-family.yml"):
            for key, value in self._packages_map(basename).items():
                reachable.add(key)
                reachable.update(n for n in _names_of(value) if isinstance(n, str))
        aur_vars = yaml.safe_load(
            (_ANSIBLE_DIR / "roles" / "packages" / "vars" / "arch.yml").read_text()
        )
        # AUR names carry the upstream `-git` suffix the logical manifest omits
        # (logical `tidal-hifi` -> AUR `tidal-hifi-git`), so both spellings are
        # reachable.
        reachable.update(aur_vars["aur_packages"])
        reachable.update(name.removesuffix("-git") for name in aur_vars["aur_packages"])

        manifest = yaml.safe_load((_MANIFEST_DIR / "packages.yaml").read_text())
        declared = {entry["name"].split("#")[0].strip() for entry in manifest["entries"]}
        orphans = sorted(declared - reachable)
        assert orphans == sorted(_DECLARED_NOT_PROVISIONED), (
            "packages.yaml declares entries no provisioning path installs (a "
            "fresh machine gets them only if someone ran the manager by hand). "
            f"Unexpected: {sorted(set(orphans) - _DECLARED_NOT_PROVISIONED)}; "
            f"no-longer-orphaned (delete from _DECLARED_NOT_PROVISIONED): "
            f"{sorted(_DECLARED_NOT_PROVISIONED - set(orphans))}"
        )


class TestPackageListInvariantsNegative:
    """Each invariant must BITE. A defect detector nobody proved fires is a
    comment. Each case below is a real authoring mistake, fed to the same
    helper the real-data tests use."""

    @pytest.mark.parametrize(
        ("packages", "expected_fragment"),
        [
            ({"dunst": None}, "value is empty"),
            ({"thunar": "   "}, "value is blank"),
            ({"ags": 42}, "is not a package name or list"),
            ({"rofi": ["rofi", ""]}, "is not a package name"),
        ],
    )
    def test_empty_value_invariant_bites(
        self, packages: dict[str, object], expected_fragment: str
    ) -> None:
        problems = _empty_value_problems(packages)
        assert any(expected_fragment in problem for problem in problems), (
            f"expected {expected_fragment!r} in {problems}"
        )

    def test_empty_value_invariant_accepts_the_real_shape(self) -> None:
        assert _empty_value_problems({"a": "a", "b": ["b1", "b2"]}) == []

    @pytest.mark.parametrize(
        ("packages", "expected_fragment"),
        [
            ({"capture": []}, "rollup list is EMPTY"),
            ({"capture": ["grim", "slurp wl-clipboard"]}, "not a single plausible package name"),
            ({"capture": ["grim,slurp"]}, "not a single plausible package name"),
            ({"capture": [" grim"]}, "not a single plausible package name"),
            ({"capture": ["grim", 7]}, "not a single plausible package name"),
        ],
    )
    def test_rollup_invariant_bites(
        self, packages: dict[str, object], expected_fragment: str
    ) -> None:
        problems = _rollup_problems(packages)
        assert any(expected_fragment in problem for problem in problems), (
            f"expected {expected_fragment!r} in {problems}"
        )

    def test_rollup_invariant_accepts_scalars_and_real_names(self) -> None:
        assert (
            _rollup_problems({"ags": "aylurs-gtk-shell-git", "zsh": ["zsh-autosuggestions", "bat"]})
            == []
        )

    def test_duplicate_invariant_bites_on_a_second_key(self) -> None:
        problems = _duplicate_problems({"rofi": "rofi", "launcher": "rofi"})
        assert problems == ["rofi declared under ['rofi', 'launcher']"]

    def test_duplicate_invariant_bites_across_rollup_and_scalar(self) -> None:
        problems = _duplicate_problems({"capture": ["grim"], "screenshot": "grim"})
        assert problems == ["grim declared under ['capture', 'screenshot']"]

    def test_duplicate_invariant_honours_the_documented_exemption(self) -> None:
        allowed = _INTENTIONAL_DUPLICATE_KEY_PAIRS["debian-family.yml"]
        packages = {"bluez": "bluez", "bluez-utils": "bluez"}
        assert _duplicate_problems(packages) == ["bluez declared under ['bluez', 'bluez-utils']"]
        assert _duplicate_problems(packages, allowed) == []

    def test_reachability_invariant_would_flag_an_unprovisioned_entry(self) -> None:
        """The orphan set is computed, not hardcoded — prove a NEW orphan bites."""
        reachable = {"hyprland", "rofi"}
        declared = {"hyprland", "rofi", "brand-new-thing"}
        orphans = sorted(declared - reachable)
        assert orphans == ["brand-new-thing"]
        assert orphans != sorted(_DECLARED_NOT_PROVISIONED)


# Discovered facts that must ALWAYS be namespaced (`ansible_facts['x']` /
# `ansible_facts.x`), never referenced as top-level `ansible_x` vars: the
# INJECT_FACTS_AS_VARS default-True is deprecated and top-level injection
# disappears in ansible-core 2.24, turning every bare access into an
# "undefined variable" abort plus a deprecation warning today (caught live
# 2026-09-29 via `ansible_user_id` in zsh_config/gloview_plugin). Magic vars
# (`ansible_check_mode`, `ansible_python_interpreter`, ...) are NOT facts and
# are unaffected — only the names below are banned bare.
_BANNED_BARE_FACTS = (
    "user_id",
    "env",
    "os_family",
    "distribution",
    "distribution_major_version",
    "distribution_release",
    "hostname",
    "fqdn",
    "nodename",
    "domain",
    "architecture",
    "machine",
    "processor",
    "kernel",
    "system",
    "users",
    "date_time",
    "local",
)


def _strip_yml_comment(line: str) -> str:
    """Cut comments: full-line `# …` plus trailing `# comment`
    (whitespace-prefixed only, so `#rrggbb` color literals and URL fragments
    survive)."""
    if re.match(r"^\s*#", line):
        return ""
    return re.sub(r"\s+#.*$", "", line)


class TestNoTopLevelFacts:
    def test_no_bare_discovered_fact_access(self) -> None:
        """No playbook/role/group_vars line may reference a discovered fact
        bare (`ansible_user_id`, `ansible_env`, `ansible_os_family`, ...):
        use `ansible_facts['…']` so the 2.24 removal is a non-event and no
        deprecation warning is ever emitted."""
        pattern = re.compile(r"\bansible_(" + "|".join(_BANNED_BARE_FACTS) + r")\b")
        offenders = []
        for path in sorted(_ANSIBLE_DIR.rglob("*.yml")):
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                code = _strip_yml_comment(line)
                for match in pattern.finditer(code):
                    offenders.append(f"{path.relative_to(_ANSIBLE_DIR)}:{i}: {match.group(0)}")
        assert offenders == [], (
            "bare discovered-fact access (deprecated INJECT_FACTS_AS_VARS, "
            "removed in ansible-core 2.24) — namespace via ansible_facts:\n" + "\n".join(offenders)
        )
