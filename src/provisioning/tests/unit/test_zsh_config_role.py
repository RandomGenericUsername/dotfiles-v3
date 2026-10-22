from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.unit import assets_templates

_TASK_KEYWORDS = {
    "name",
    "when",
    "become",
    "become_user",
    "become_method",
    "become_flags",
    "args",
    "register",
    "changed_when",
    "failed_when",
    "creates",
    "vars",
    "loop",
    "until",
    "retries",
    "delay",
    "tags",
    "environment",
    "ignore_errors",
    "notify",
    "check_mode",
}


def _find_ansible_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError("src/provisioning/ansible/ not found walking up from the test file")


_ANSIBLE_DIR = _find_ansible_dir()
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "zsh_config"
_PLAYBOOKS_DIR = _ANSIBLE_DIR / "playbooks"
_REPO_ROOT = _ANSIBLE_DIR.parents[2]
_ZSH_TEMPLATE = "zsh/.zshrc.j2"


def _load_tasks() -> list[dict[str, object]]:
    data = yaml.safe_load((_ROLES_DIR / "tasks" / "main.yml").read_text())
    assert isinstance(data, list)
    return data


def _module_key(task: dict[str, object]) -> str | None:
    for key in task:
        if key not in _TASK_KEYWORDS and key != "with_items":
            return key
    return None


def _module(task: dict[str, object]) -> dict[str, object]:
    module = task.get(_module_key(task) or "", {})
    assert isinstance(module, dict)
    return module


def _render_task() -> dict[str, object]:
    matches = [t for t in _load_tasks() if _module_key(t) == "ansible.builtin.template"]
    assert len(matches) == 1, f"expected exactly one render task; found {len(matches)}"
    return matches[0]


def _vars() -> dict[str, Any]:
    data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
    assert isinstance(data, dict)
    return data


def _seed_role_host(root: Path) -> tuple[Path, Path, Path]:
    """Materialize the minimum host the zsh_config role needs to run in isolation."""
    home = root / "home"
    install = root / "install"
    state = root / "state"
    home.mkdir()
    (install / "config" / "starship").mkdir(parents=True)
    (install / "config" / "starship" / "starship.toml").write_text("")
    (state / "dotfiles" / "current").mkdir(parents=True)
    (state / "dotfiles" / "current" / "colors.sequences").write_text("")
    # S3: the template body ships in the pinned corpus; run the role the way the
    # assets playbook leaves the host (checkout at the tag).
    assets_templates.seed_install(install, "zsh_config")
    for directory in (home / ".oh-my-zsh", home / ".pyenv"):
        directory.mkdir(parents=True)
    return home, install, state


def _role_env(home: Path, state: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("ANSIBLE_")}
    env.update(
        {
            "HOME": str(home),
            "XDG_STATE_HOME": str(state),
            "ANSIBLE_CONFIG": str(_ANSIBLE_DIR / "ansible.cfg"),
        }
    )
    env.pop("XDG_CONFIG_HOME", None)
    return env


def _run_role_playbook(
    install: Path,
    env: dict[str, str],
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    args = [
        shutil.which("ansible-playbook") or "ansible-playbook",
        str(_PLAYBOOKS_DIR / "zsh-config.yaml"),
        "-e",
        f"install_dir={install}",
        "-e",
        f"shell_oh_my_zsh_dir={env['HOME']}/.oh-my-zsh",
        "-e",
        f"shell_pyenv_dir={env['HOME']}/.pyenv",
        "-e",
        f"shell_nvm_dir={env['HOME']}/.nvm",
        "-e",
        "shell_font_family=monospace",
        "-e",
        "shell_font_size_px=12",
    ]
    args.extend(extra_args or [])
    return subprocess.run(args, capture_output=True, text=True, env=env, timeout=120)


def _stub_getent(bin_dir: Path, shell: str) -> None:
    """A `getent passwd` stub so the probe reads a controlled login shell."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "getent"
    stub.write_text(f'#!/bin/sh\necho "user:x:1000:1000::/home/user:{shell}"\n')
    stub.chmod(0o755)


def _stub_become(path: Path, marker: Path) -> None:
    """A fake become exe: records the escalation attempt, then fails loudly."""
    path.write_text(
        "#!/bin/sh\n"
        f"touch '{marker}'\n"
        "echo FAKE_BECOME_INVOKED >&2\n"
        "exit 1\n"
    )
    path.chmod(0o755)


def _fake_shell_binary(root: Path) -> Path:
    """An executable stand-in so the role's binary assert never depends on the host."""
    fake = root / "fake-zsh"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(0o755)
    return fake


class TestZshConfigRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"

    def test_playbook_exists(self) -> None:
        assert (_PLAYBOOKS_DIR / "zsh-config.yaml").is_file(), "missing playbooks/zsh-config.yaml"


class TestZshConfigTasks:
    def test_first_task_is_fail_loud_install_dir_assert(self) -> None:
        tasks = _load_tasks()
        first = tasks[0]
        assert _module_key(first) == "ansible.builtin.assert", (
            "the first task must be the fail-loud install_dir assert"
        )
        that = str(_module(first).get("that", ""))
        assert "install_dir is defined" in that

    def test_render_task_targets_rendered_zshrc(self) -> None:
        """The render task must produce a FINAL .zshrc (no .j2 suffix) in the
        spine — this is the wiring the chain previously lacked."""
        task = _render_task()
        module = _module(task)
        assert str(module.get("dest")) == "{{ zsh_config_spine_dir }}/.zshrc", (
            "render dest must be {{ zsh_config_spine_dir }}/.zshrc (final, not .j2)"
        )
        assert str(module.get("src")) == "{{ zsh_config_assets_templates_dir }}/zsh/.zshrc.j2", (
            "render src must be the .zshrc.j2 template read from the pinned assets "
            "templates class (S3: the source is no longer authored in this repo)"
        )

    def test_render_task_defines_all_template_vars(self) -> None:
        """Every variable the .zshrc.j2 template consumes must be passed to the
        template module (a missing var would render as empty/broken output)."""
        template = assets_templates.template_file(_ZSH_TEMPLATE, "zsh_config").read_text()
        import re

        template_vars = set(re.findall(r"\{\{([A-Z_]+)\}\}", template))
        task = _render_task()
        vars_block = task.get("vars")
        assert isinstance(vars_block, dict), "render task must define a vars block"
        provided = set(vars_block.keys())
        missing = template_vars - provided
        assert not missing, f"render task does not define template vars: {sorted(missing)}"

    def test_render_has_full_check_mode_support(self) -> None:
        """The template module is check-safe natively — must NOT be --check-gated."""
        task = _render_task()
        assert task.get("when") is None, "render must not be --check-gated (template is check-safe)"

    def test_only_the_gated_login_shell_task_escalates(self) -> None:
        """Only the mutation task may escalate, and only conditionally: the
        role reads the current shell unprivileged first, so an already-zsh host
        never needs a sudo password. Every other task stays user-scoped."""
        for task in _load_tasks():
            name = str(task.get("name", ""))
            if name == "Ensure zsh is the login shell":
                assert task.get("become", False) is True, (
                    "the login-shell mutation must run become:true (usermod writes /etc/passwd)"
                )
                continue
            assert not task.get("become", False), (
                f"zsh_config must not use become outside the login-shell task (task {name!r})"
            )

    def test_login_shell_probe_is_unprivileged_and_read_only(self) -> None:
        """The current shell is read with a plain `getent passwd` command that
        needs no root — that is what lets the role skip become entirely on an
        already-zsh host (the S2/S3 host failure: sudo demanded a password)."""
        probes = [
            task
            for task in _load_tasks()
            if str(task.get("register", "")) == "zsh_config_passwd_check"
        ]
        assert len(probes) == 1, "exactly one task must register the getent probe"
        probe = probes[0]
        assert _module_key(probe) == "ansible.builtin.command", (
            "the probe must be `command` (no shell pipeline, no privilege)"
        )
        assert probe.get("become", False) is False, (
            "the probe must NOT become: that is the bug (sudo password demanded)"
        )
        argv = [str(part) for part in _module(probe).get("argv", [])]
        assert argv[:2] == ["getent", "passwd"], f"unexpected probe argv: {argv}"
        assert "ansible_facts['user_id']" in argv[2], (
            "the probe must target the login user from the user_id fact"
        )
        assert probe.get("changed_when") is False, "a read-only probe never reports changed"
        assert probe.get("check_mode") is False, (
            "the read-only probe must run under --check too, so the mutation's "
            "when condition is evaluated with real values"
        )
        assert "login_shell" in (probe.get("tags") or [])

    def test_current_shell_fact_parses_the_passwd_shell_field(self) -> None:
        fact_tasks = [
            task
            for task in _load_tasks()
            if _module_key(task) == "ansible.builtin.set_fact"
            and "zsh_config_current_shell" in _module(task)
        ]
        assert len(fact_tasks) == 1, "exactly one task must record the current shell"
        expression = str(_module(fact_tasks[0])["zsh_config_current_shell"])
        assert "zsh_config_passwd_check.stdout" in expression
        assert ".split(':')" in expression and "| last" in expression, (
            "the getent passwd shell is the LAST colon-separated field; parsing "
            "anything else risks comparing the wrong column"
        )

    def test_login_shell_mutation_is_gated_on_the_probe_and_check_mode(self) -> None:
        task = next(
            t
            for t in _load_tasks()
            if str(t.get("name", "")) == "Ensure zsh is the login shell"
        )
        assert _module_key(task) == "ansible.builtin.user", (
            "the mutation must use ansible.builtin.user (usermod writes the shell "
            "without the PAM /dev/tty chsh failure)"
        )
        module = _module(task)
        assert str(module.get("name")) == "{{ ansible_facts['user_id'] }}"
        assert str(module.get("shell")) == "{{ zsh_config_login_shell }}"
        when = task.get("when")
        assert isinstance(when, list), "the mutation must carry both gate conditions"
        assert "not ansible_check_mode" in when, "the mutation must stay --check-gated"
        assert "zsh_config_current_shell != zsh_config_login_shell" in when, (
            "become must only happen when the probe saw a non-zsh shell"
        )

    def test_login_shell_targets_login_user_not_environment(self) -> None:
        """Under become $USER is root — the mutation must target the user_id fact
        (`ansible_facts['user_id']`, never the deprecated top-level
        `ansible_user_id`) or it would change root's shell."""
        task = next(
            t
            for t in _load_tasks()
            if str(t.get("name", "")) == "Ensure zsh is the login shell"
        )
        module_text = str(_module(task))
        assert "ansible_facts['user_id']" in module_text
        assert "ansible_user_id" not in module_text.replace("ansible_facts['user_id']", "")
        assert "$USER" not in module_text, "the environment is root under become"
        assert "login_shell" in (task.get("tags") or []), (
            "the login-shell tasks must carry the login_shell tag so they run "
            "under the orchestrator's --tags all yet stay skippable in tests"
        )

    def test_login_shell_binary_is_pinned_in_vars(self) -> None:
        data = _vars()
        assert data["zsh_config_login_shell"] == "/usr/bin/zsh", (
            "the converge target is the absolute zsh path both supported distros install"
        )


class TestPreS3Prune:
    """S3: the retired in-spine template must disappear on the next provision.

    Before S3, `config_copies` copied the whole zsh directory into the spine, so a
    host provisioned earlier still carries `<spine>/config/zsh/.zshrc.j2`. zsh
    reads `.zshrc` through ZDOTDIR and never the template, so the copy is dead
    weight in the live config dir.
    """

    def _prune_task(self) -> dict[str, object]:
        matches = [
            t
            for t in _load_tasks()
            if _module_key(t) == "ansible.builtin.file"
            and _module(t).get("state") == "absent"
        ]
        assert len(matches) == 1, (
            "expected exactly one `state: absent` task pruning the pre-S3 template"
        )
        return matches[0]

    def test_prune_targets_the_legacy_template_path(self) -> None:
        module = _module(self._prune_task())
        assert str(module.get("path")) == "{{ zsh_config_legacy_template_path }}"

    def test_prune_is_idempotent_and_check_safe(self) -> None:
        task = self._prune_task()
        assert task.get("when") is None, (
            "a `state: absent` file task is natively idempotent and check-safe — "
            "gating it would leave the residue on a --check host and skip the prune"
        )

    def test_legacy_path_is_the_spine_dir_not_the_repo(self) -> None:
        value = str(_vars()["zsh_config_legacy_template_path"])
        assert value == "{{ zsh_config_spine_dir }}/.zshrc.j2", (
            "the prune must target the SPINE residue, never the corpus"
        )
        assert "dotfiles/config" not in value

    def test_prune_runs_before_the_render(self) -> None:
        names = [str(t.get("name", "")) for t in _load_tasks()]
        prune = names.index(str(self._prune_task()["name"]))
        render = names.index("Render .zshrc")
        assert prune < render, (
            "prune the stale template before rendering, so a failed render cannot "
            "leave both files in place"
        )


class TestLoginShellBecomeGate:
    """The login-shell probe must never escalate on an already-correct host, and
    a wrong shell must still reach the gated mutation.

    The real host check that motivated the fix: `getent passwd inumaki | cut -d:
    -f7` is `/usr/bin/zsh`, yet the unconditional become demanded a sudo
    password. These tests isolate the decision with a `getent` stub and a fake
    become exe, so they are deterministic and never touch the host's shell.
    """

    def test_already_zsh_never_invokes_become(self) -> None:
        if shutil.which("ansible-playbook") is None:
            pytest.skip("ansible-playbook not installed; skipping execution test")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, install, state = _seed_role_host(root)
            fake_shell = _fake_shell_binary(root)
            bin_dir = root / "stub-bin"
            _stub_getent(bin_dir, str(fake_shell))
            marker = root / "become-called"
            become = root / "fake-sudo"
            _stub_become(become, marker)
            env = _role_env(home, state)
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            env["ANSIBLE_BECOME_EXE"] = str(become)

            result = _run_role_playbook(
                install,
                env,
                extra_args=["-e", f"zsh_config_login_shell={fake_shell}"],
            )

            assert result.returncode == 0, result.stdout + result.stderr
            assert not marker.exists(), (
                "the role invoked become on a host whose login shell already "
                "matches — that is the unattended-run failure (sudo: a password "
                "is required)"
            )
            assert re.search(
                r"TASK \[zsh_config : Ensure zsh is the login shell\].*?skipping:",
                result.stdout,
                re.S,
            ), "the already-correct host must skip the mutation task outright"

    def test_wrong_shell_still_attempts_the_privileged_task(self) -> None:
        if shutil.which("ansible-playbook") is None:
            pytest.skip("ansible-playbook not installed; skipping execution test")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, install, state = _seed_role_host(root)
            fake_shell = _fake_shell_binary(root)
            bin_dir = root / "stub-bin"
            _stub_getent(bin_dir, "/bin/bash")
            marker = root / "become-called"
            become = root / "fake-sudo"
            _stub_become(become, marker)
            env = _role_env(home, state)
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            env["ANSIBLE_BECOME_EXE"] = str(become)

            result = _run_role_playbook(
                install,
                env,
                extra_args=["-e", f"zsh_config_login_shell={fake_shell}"],
            )

            assert marker.is_file(), (
                "a wrong login shell must still reach the gated mutation — the "
                "probe/gate fix must not turn the privileged step into a no-op"
            )
            assert result.returncode != 0, (
                "the fake become exe fails by design; a green run would mean the "
                "mutation never tried to escalate"
            )
            assert "FAKE_BECOME_INVOKED" in (result.stdout + result.stderr)


class TestZshConfigVars:
    _REQUIRED_KEYS = {
        "zsh_config_spine_dir",
        "zsh_config_login_shell",
        "zsh_config_legacy_template_path",
        "zsh_config_assets_pinned_tag",
        "zsh_config_assets_templates_dir",
        "zsh_config_xdg_state_home",
        "zsh_config_state_current_dir",
        "zsh_config_plugin_paths",
    }

    def test_vars_parse_with_required_keys(self) -> None:
        data = _vars()
        assert self._REQUIRED_KEYS.issubset(set(data))

    def test_spine_dir_is_trim_locked(self) -> None:
        data = _vars()
        assert str(data["zsh_config_spine_dir"]) == "{{ install_dir | trim }}/config/zsh"

    def test_plugin_paths_cover_both_distros(self) -> None:
        """The role must resolve plugin file paths for BOTH Arch and
        Debian-family (NFR-3 distro isolation: package names in group_vars,
        file paths in this role)."""
        data = _vars()
        arch = data.get("_zsh_config_arch")
        debian = data.get("_zsh_config_debian")
        assert isinstance(arch, dict) and isinstance(debian, dict), (
            "both _zsh_config_arch and _zsh_config_debian must be defined"
        )
        assert arch.keys() == debian.keys(), "both distros must resolve the same plugin set"
        for key in (
            "syntax_highlighting",
            "autosuggestions",
            "history_substring_search",
            "fzf_key_bindings",
            "fzf_completion",
        ):
            assert key in arch and key in debian, f"missing plugin path key {key}"
            assert str(arch[key]).startswith("/") and str(debian[key]).startswith("/")
        # Arch and Debian paths must actually differ (the whole point).
        assert arch != debian, "Arch and Debian plugin paths must differ"

    def test_xdg_state_home_mirrors_verify_derivation(self) -> None:
        """gt-3-2 (zshrc reads the runtime current pointer): the state root
        derives EXACTLY like the existing non-deprecated env-fact precedents
        (verify_xdg_state_home / filesystem_xdg_state_home /
        compositor_configs_xdg_state_home): honors $XDG_STATE_HOME with the
        spec default ~/.local/state via ansible_facts.env (F4 lock)."""
        data = _vars()
        value = str(data["zsh_config_xdg_state_home"])
        assert value == (
            "{{ ansible_facts.env.XDG_STATE_HOME | default(ansible_facts.env.HOME "
            "| default(ansible_facts.user_dir) + '/.local/state', true) }}"
        ), "zsh_config_xdg_state_home must carry the exact shared derivation string"
        assert "{{ ansible_env." not in value, "F4 lock: never the top-level ansible_env fact"

    def test_state_current_dir_derived_from_state_home(self) -> None:
        """gt-3-2: zsh_config_state_current_dir is <state>/dotfiles/current
        (AD-5: the state root is ALWAYS <XDG_STATE_HOME>/dotfiles/) DERIVED
        from zsh_config_xdg_state_home with the trim lock — no second XDG
        resolution is introduced."""
        data = _vars()
        value = str(data["zsh_config_state_current_dir"])
        assert value == "{{ zsh_config_xdg_state_home | trim }}/dotfiles/current", (
            "zsh_config_state_current_dir must derive from zsh_config_xdg_state_home "
            "(trim lock, mirror of verify_state_current_dir)"
        )
        assert "ansible_facts.env.XDG_STATE_HOME" not in value, (
            "never a second ansible_facts.env.XDG_STATE_HOME read — one XDG read per role"
        )

    def test_no_generated_palette_references_remain(self) -> None:
        """Epic 4 tripwire (gt-3-2): the zshrc reads the runtime-owned
        current/ pointer — no task, var, or template may reference the
        orphaned provisioning-era generated/palettes tree or the retired
        COLOR_SCHEME_OUTPUT_DIR var name."""
        for source_name, source_path in (
            ("tasks", _ROLES_DIR / "tasks" / "main.yml"),
            ("vars", _ROLES_DIR / "vars" / "main.yml"),
            ("template", assets_templates.template_file(_ZSH_TEMPLATE, "zsh_config")),
        ):
            text = source_path.read_text()
            assert "generated/palettes" not in text, (
                f"{source_name} must not reference the orphaned generated/palettes "
                "tree (Epic 4 removed it — the runtime owns current/)"
            )
            assert "COLOR_SCHEME_OUTPUT_DIR" not in text, (
                f"{source_name} must not reference the retired COLOR_SCHEME_OUTPUT_DIR "
                "var (gt-3-2: retired, not repurposed — the name asserted inverted "
                "provisioning-OUTPUT semantics)"
            )
        assert (
            "COLOR_SCHEME_CURRENT_DIR"
            in assets_templates.template_file(_ZSH_TEMPLATE, "zsh_config").read_text()
        ), "the template must consume COLOR_SCHEME_CURRENT_DIR (gt-3-2)"


class TestZshConfigPlaybook:
    def test_syntax_check_exits_zero(self) -> None:
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping syntax-check")
        env = {k: v for k, v in os.environ.items() if not k.startswith("ANSIBLE_")}
        env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")
        result = subprocess.run(
            [
                ansible_playbook,
                "--syntax-check",
                str(_PLAYBOOKS_DIR / "zsh-config.yaml"),
                "-e",
                "install_dir=/tmp/x",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_playbook_renders_zshrc_with_all_vars(self) -> None:
        """End-to-end render: run zsh-config.yaml against a temp spine, assert
        the rendered .zshrc resolves every template var (no raw {{...}} left).
        gt-3-2: the cat line reads the runtime state root — XDG_STATE_HOME is
        set EXPLICITLY in the env (the derivation reads ansible_facts.env; an
        ambient host value would silently win) and the rendered .zshrc cats
        exactly <state>/dotfiles/current/colors.sequences, never the orphaned
        generated/palettes tree."""
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping execution test")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            install = root / "install"
            state = root / "state"
            home.mkdir()
            zsh_dir = install / "config" / "zsh"
            (install / "config" / "starship").mkdir(parents=True)
            (install / "config" / "starship" / "starship.toml").write_text("")
            (state / "dotfiles" / "current").mkdir(parents=True)
            (state / "dotfiles" / "current" / "colors.sequences").write_text("")
            # S3: the template body ships in the pinned corpus; run the role the way
            # the assets playbook leaves the host (checkout at the tag).
            assets_templates.seed_install(install, "zsh_config")
            # The pre-S3 residue the role must prune on the same pass.
            zsh_dir.mkdir(parents=True, exist_ok=True)
            (zsh_dir / ".zshrc.j2").write_text("{{ legacy }}")
            for d in (home / ".oh-my-zsh", home / ".pyenv"):
                d.mkdir(parents=True)

            env = {k: v for k, v in os.environ.items() if not k.startswith("ANSIBLE_")}
            env.update(
                {
                    "HOME": str(home),
                    "XDG_STATE_HOME": str(state),
                    "ANSIBLE_CONFIG": str(_ANSIBLE_DIR / "ansible.cfg"),
                }
            )
            env.pop("XDG_CONFIG_HOME", None)
            result = subprocess.run(
                [
                    ansible_playbook,
                    str(_PLAYBOOKS_DIR / "zsh-config.yaml"),
                    # The login-shell task needs root (chsh has no non-interactive
                    # path) and this test carries no become credential — skip
                    # just that tagged step; the render is what is asserted.
                    "--skip-tags",
                    "login_shell",
                    "-e",
                    f"install_dir={install}",
                    "-e",
                    f"shell_oh_my_zsh_dir={home / '.oh-my-zsh'}",
                    "-e",
                    f"shell_pyenv_dir={home / '.pyenv'}",
                    "-e",
                    f"shell_nvm_dir={home / '.nvm'}",
                    "-e",
                    "shell_font_family=monospace",
                    "-e",
                    "shell_font_size_px=12",
                ],
                capture_output=True,
                text=True,
                env=env,
                timeout=120,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            rendered = zsh_dir / ".zshrc"
            assert rendered.is_file(), f".zshrc was never rendered ({rendered})"
            text = rendered.read_text()
            assert "{{" not in text and "{%" not in text, (
                "rendered .zshrc must have no unresolved Jinja: " + text
            )
            assert "starship init zsh" in text, "rendered .zshrc must init starship"
            expected_cat = f'(cat "{state / "dotfiles" / "current" / "colors.sequences"}" &)'
            assert expected_cat in text, (
                "rendered .zshrc must cat the runtime state-root current pointer "
                f"(gt-3-2); got: {text}"
            )
            assert "generated/palettes" not in text, (
                "rendered .zshrc must NOT reference the orphaned generated/palettes "
                "tree (Epic 4 removed it)"
            )
            assert not (zsh_dir / ".zshrc.j2").exists(), (
                "the pre-S3 .zshrc.j2 residue must be pruned on the same pass — a "
                "template nobody renders must not survive in the live config dir"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
