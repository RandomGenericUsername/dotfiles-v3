"""AD-8.4 — the required-var parity test between the assets contracts and the roles.

S3 split the templates from the values: `dotfiles-assets` ships `<name>.j2` plus
`<name>.vars.schema.json` (the names the consumer MUST supply), and the rendering
roles here supply them. Nothing connected the two sides — the schema's own
well-formedness is validated in the assets repo CI, but "does the installer supply
what the contract requires?" was a review habit.

This module makes it executable, statically and offline (no Ansible run, no render):

  * forward — every `required[]` name of the schema is supplied by that role's
    render task: its `vars:` block, the role's `vars/main.yml`, or a `set_fact`
    earlier in the role. A missing name would otherwise be an undefined-variable
    failure at render time on a user's machine.
  * reverse — every name the render task passes explicitly is a declared property
    of the schema. The assets schemas are `additionalProperties: false`, so a name
    the template does not read is a consumer defect (a typo that silently does
    nothing), not harmless extra data.
  * coverage — the rendered set is exactly the six (role, template) pairs declared
    below. A role that stops rendering, or renders a different file, fails here
    instead of passing vacuously.
  * pin parity — every role's `<role>_assets_pinned_tag` mirror equals the
    manifest's `assets.tag` (spine AD-6). Five new mirrors in S3 means five new
    drift opportunities; one test closes them.

WHY IT RESOLVES THE CORPUS INSTEAD OF READING IT FROM THIS CHECKOUT. The schemas
are assets, not sources of this repo (that is the whole point of the slice). The
resolver in `assets_templates.py` reads an explicit directory, a local
`dotfiles-assets` checkout, or a provisioned spine; when none exists the tests SKIP
loudly. There is no vendored copy to keep in step, deliberately.
"""

from __future__ import annotations

import json
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

#: The rendered (role, template) pairs at this tag — six of the nine templates in
#: the corpus. The other three are display-manager files retained for the
#: greetd+regreet fallback path (spine AD-9) and are not rendered by any role.
EXPECTED_RENDERED: dict[str, tuple[str, ...]] = {
    "zsh_config": ("zsh/.zshrc.j2",),
    "kitty_config": ("kitty/kitty.conf.j2",),
    "btop_config": ("btop/btop.conf.j2",),
    "wlogout_config": ("wlogout/style.css.tpl",),
    "display_manager": ("display-manager/config.toml.j2", "display-manager/sddm.conf.j2"),
}


def _module_key(task: dict[str, Any]) -> str | None:
    for key in task:
        if key not in _TASK_KEYWORDS and key != "with_items":
            return key
    return None


def _module(task: dict[str, Any], key: str) -> dict[str, Any]:
    body = task.get(key, {})
    assert isinstance(body, dict), f"task {task.get('name')!r}: {key} must be a mapping"
    return body


def _render_tasks(role: str) -> list[dict[str, Any]]:
    return [t for t in assets_templates.role_tasks(role) if _module_key(t) == "ansible.builtin.template"]


def _template_relative(task: dict[str, Any], role: str) -> str:
    """The template path inside the corpus, from `<role>_assets_templates_dir>/…`."""
    src = str(_module(task, "ansible.builtin.template").get("src", ""))
    expected_prefix = f"{{{{ {role}_assets_templates_dir }}}}/"
    assert src.startswith(expected_prefix), (
        f"role {role}: render task {task.get('name')!r} must read "
        f"`{expected_prefix}<group>/<file>` (the pinned assets templates class); "
        f"got {src!r}. A bare file name would resolve inside the role's own "
        f"templates/ dir — the source S3 deleted."
    )
    return src[len(expected_prefix) :]


def _set_fact_names(role: str) -> set[str]:
    names: set[str] = set()
    for task in assets_templates.role_tasks(role):
        if _module_key(task) == "ansible.builtin.set_fact":
            names.update(_module(task, "ansible.builtin.set_fact").keys())
    return names


def _supplied(role: str, task: dict[str, Any]) -> set[str]:
    supplied = set(assets_templates.role_vars(role))
    supplied |= _set_fact_names(role)
    task_vars = task.get("vars")
    if isinstance(task_vars, dict):
        supplied |= set(task_vars)
    return supplied


def _render_pairs() -> list[tuple[str, str, dict[str, Any]]]:
    pairs: list[tuple[str, str, dict[str, Any]]] = []
    for role in EXPECTED_RENDERED:
        for task in _render_tasks(role):
            pairs.append((role, _template_relative(task, role), task))
    return pairs


class TestRenderedSetIsTheDeclaredSet:
    def test_exactly_the_declared_pairs_are_rendered(self) -> None:
        rendered = sorted(relative for role, relative, _ in _render_pairs())
        declared = sorted(t for pairs in EXPECTED_RENDERED.values() for t in pairs)
        assert rendered == declared, (
            "the rendered (role, template) set drifted from the declared set; a new "
            f"render pair must join EXPECTED_RENDERED and the parity assertions. "
            f"rendered={rendered} declared={declared}"
        )

    def test_every_render_role_reads_its_own_pin_mirror(self) -> None:
        for role in EXPECTED_RENDERED:
            data = assets_templates.role_vars(role)
            assert f"{role}_assets_templates_dir" in data, (
                f"{role} must define {role}_assets_templates_dir (the templates class "
                f"inside the pinned checkout)"
            )
            assert (
                f"{{{{ install_dir | trim }}}}/assets/{{{{ {role}_assets_pinned_tag }}}}/templates"
                == str(data[f"{role}_assets_templates_dir"])
            ), (
                f"{role}_assets_templates_dir must resolve through the role's own pin "
                f"mirror and the trim-locked install_dir seam"
            )


class TestRequiredVarsAreSupplied:
    def test_each_schema_required_name_is_supplied_by_the_render_task(self) -> None:
        """AD-8.4 forward: required[] ⊆ (task vars ∪ role vars ∪ set_fact names)."""
        checked = 0
        for role, relative, task in _render_pairs():
            schema = assets_templates.schema_for(relative, role)
            required = set(schema.get("required", []))
            supplied = _supplied(role, task)
            missing = sorted(required - supplied)
            assert not missing, (
                f"{role} renders {relative} but does not supply its required "
                f"variable(s) {missing}. The assets schema declares them required; "
                f"an undefined var fails the render on a user's machine. Supply them "
                f"in the task's vars block (or the role's vars/main.yml)."
            )
            checked += 1
        assert checked == sum(len(p) for p in EXPECTED_RENDERED.values()), (
            f"expected to check every declared render pair; checked {checked}"
        )
        print(f"parity: {checked} rendered templates, every required name supplied")

    def test_explicit_task_vars_are_declared_properties(self) -> None:
        """AD-8.4 reverse: a name the role passes must be one the template reads."""
        for role, relative, task in _render_pairs():
            schema = assets_templates.schema_for(relative, role)
            properties = set(schema.get("properties", {}))
            task_vars = task.get("vars")
            passed = set(task_vars) if isinstance(task_vars, dict) else set()
            undeclared = sorted(passed - properties)
            assert not undeclared, (
                f"{role} passes {undeclared} to {relative}, but the schema declares no "
                f"such property (additionalProperties: false). Either the template "
                f"does not read it (a typo that silently does nothing) or the assets "
                f"contract is missing a name."
            )

    def test_no_required_name_is_a_consumer_only_path(self) -> None:
        """A required name must not smuggle a destination into the corpus contract.

        The schemas describe VALUES; the consumer decides where they point. A
        required name ending in `_path`/`_dir` is legitimate only when the consumer
        supplies the absolute path (it does for all four such names today) — so the
        real assertion is that no schema hard-codes an absolute path as a `const`
        or an `enum` value.
        """
        root = assets_templates.require_templates_root()
        offenders: list[str] = []

        for schema_path in sorted(root.rglob("*.vars.schema.json")):
            schema = json.loads(schema_path.read_text())
            for name, spec in schema.get("properties", {}).items():
                for key in ("const",):
                    if key in spec and str(spec[key]).startswith("/"):
                        offenders.append(f"{schema_path.name}:{name}.{key}")
                for value in spec.get("enum", []):
                    if isinstance(value, str) and value.startswith("/"):
                        offenders.append(f"{schema_path.name}:{name}.enum")
        assert not offenders, (
            f"an assets schema pins an absolute host path: {offenders}. Values are "
            f"the consumer's; the corpus supplies the template and the contract."
        )


class TestPinMirrorsMatchTheManifest:
    def test_every_render_role_pin_equals_assets_tag(self) -> None:
        manifest = yaml.safe_load(
            (assets_templates.REPO_ROOT / "dotfiles" / "provisioning" / "assets.yaml").read_text()
        )
        tag = str(manifest["assets"]["tag"])
        mirrors = {
            role: assets_templates.assets_tag(role) for role in EXPECTED_RENDERED
        }
        drift = {role: value for role, value in mirrors.items() if value != tag}
        assert not drift, (
            f"role pin mirrors must equal the manifest's assets.tag ({tag}); got "
            f"{drift}. S3 added these mirrors, so one bump edits the manifest + five "
            f"roles (spine AD-6)."
        )
        print(f"parity: assets.tag {tag} mirrored by {', '.join(sorted(mirrors))}")


class TestTheCorpusActuallyHasTheseTemplates:
    def test_the_declared_templates_and_schemas_exist_in_the_corpus(self) -> None:
        root = assets_templates.require_templates_root()
        missing: list[str] = []
        for pairs in EXPECTED_RENDERED.values():
            for relative in pairs:
                if not (root / relative).is_file():
                    missing.append(relative)
        assert not missing, (
            f"the pinned assets templates class at {root} lacks {missing}; the role "
            f"would fail the render on a real provision"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
