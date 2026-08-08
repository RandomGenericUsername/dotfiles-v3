---
baseline_commit: 4652161
---

# Story 1.8: Typer CLI

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Change Log

- 2026-08-05: Story created — ultimate context engine analysis completed; comprehensive developer guide created.

## Story

As an operator,
I want a `dotfiles-provision` CLI exposing `plan`, `apply`, `verify`, and `bootstrap`,
So that I can drive provisioning from a terminal with structured output.

## Acceptance Criteria

1. `main.py` (Typer app) and `options.py` exist under `src/provisioning/cli/` (AC 1, FR-11, FR-6)
2. `dotfiles-provision plan` runs `ProvisionMachineUseCase` with `check=True` (AC 2, FR-1)
3. `dotfiles-provision apply` runs `ProvisionMachineUseCase` with `check=False` (AC 3, FR-2)
4. `dotfiles-provision verify` runs `VerifyCapabilityUseCase` (AC 4, FR-3)
5. `dotfiles-provision bootstrap` runs `BootstrapUseCase` (AC 5, FR-4)
6. All commands render output through `cli-output` (JSON by default) (AC 6, FR-11)
7. CLI tests use Typer `CliRunner` with mock deps on `ctx.obj`, and each command exits 0 on success and non-zero with a structured error on failure (AC 7, FR-11, FR-1, FR-2, FR-3, FR-4, NFR-2)

## Tasks / Subtasks

- [ ] Create `cli/options.py` with shared option definitions (AC: 1, 6, 7)
  - [ ] `OUTPUT_FORMAT_OPT` — `typer.Option(OutputFormat.JSON, "--output-format", help=..., case_sensitive=False)` from `cli_output.domain.enums` (mirror CSG's `output_format` global)
  - [ ] `CHECK_OPT` — `typer.Option(False, "--check", help="Dry run: complete cleanly with no mutation")` for the `bootstrap` command (FR-4)
- [ ] Update `cli/main.py`: wire the composition root and the four commands (AC: 1–7)
  - [ ] Add `CliDependencies` dataclass + `build_deps()` (mirror CSG `build_deps()` pattern) — the **composition root** that Story 1.6/1.7 dev notes say must live in the CLI
  - [ ] `build_deps()` constructs `AnsibleExecutor` + `AnsibleFactReader`, wires them into `ProvisionMachineUseCase` (plan/apply, `bootstrap.yaml`), `VerifyCapabilityUseCase` (`verify.yaml`), and `BootstrapUseCase` (`bootstrap.yaml`)
  - [ ] Extend the existing `@app.callback()` to set `ctx.obj = {"renderer": create_renderer(output_format), "deps": build_deps()}` — **keep `version` working**
  - [ ] **Remove the now-dead `_renderer()` helper** (superseded by `create_renderer(output_format)` in the callback)
  - [ ] Add `plan(ctx)` → `deps.plan.provision(check=True)`
  - [ ] Add `apply(ctx)` → `deps.apply.provision(check=False)`
  - [ ] Add `verify(ctx)` → `deps.verify.verify()`
  - [ ] Add `bootstrap(ctx, check: bool = CHECK_OPT)` → `deps.bootstrap.bootstrap(check=check)`
  - [ ] Add a shared `_render_run(renderer, fn, command)` helper: run `fn()`, render success via `ResultView` (including `install_dir`), catch the four known adapter errors → `ErrorView` + `typer.Exit(code=1)`, and exit non-zero when `result.success is False`
  - [ ] Do NOT validate playbook existence, do NOT read manifests, do NOT branch on distro, do NOT persist state
- [ ] CLI tests with mock deps on `ctx.obj` (AC: 7, NFR-5)
  - [ ] `tests/unit/cli/conftest.py` — `FakeDeps` holding fake use cases backed by the existing `FakeExecutor`/`FakeFactReader` pattern
  - [ ] `tests/unit/cli/test_commands.py` — success + failure for each of plan/apply/verify/bootstrap
  - [ ] Extend `tests/test_cli.py` only if the `version` tests need the new callback shape (they should not — keep the `ctx.obj["renderer"]` contract)
- [ ] Verify against layering guard + full suite
  - [ ] `uv run pytest tests/architecture/test_layering.py` — cli/ scanned (now includes `options.py`), no violations
  - [ ] `uv run pytest` — full suite green (was 142 passed / 0 skipped)
  - [ ] `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean
  - [ ] Standalone nicety: `python tests/architecture/test_layering.py` still exits 0

## Dev Notes

### Composition root lives HERE — this is the story that wires the adapters

Stories 1.6/1.7 deliberately refused to instantiate adapters: *"Composition (wiring real adapters) happens in Story 1.8's CLI."* This story is that wiring. The CLI is the **outer shell of the hexagon** — the one layer allowed to import everything, including adapters. It is the only place `AnsibleExecutor`/`AnsibleFactReader` are constructed for production.

Mirror the established repo pattern (CSG `cli/main.py`): a `build_deps() -> CliDependencies` factory called by the callback, with `ctx.obj["deps"]` read by the commands. Tests monkeypatch `build_deps` (see CSG `tests/unit/cli/test_show.py` `_invoke` helper) — that is what "mock deps on `ctx.obj`" means in this codebase.

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class CliDependencies:
    plan: ProvisionMachineUseCase
    apply: ProvisionMachineUseCase
    verify: VerifyCapabilityUseCase
    bootstrap: BootstrapUseCase

_ANSIBLE_ROOT = Path(__file__).resolve().parents[3] / "ansible"
# main.py is at src/provisioning/src/provisioning/cli/main.py:
#   parents[0]=cli, parents[1]=provisioning, parents[2]=src, parents[3]=src/provisioning

def build_deps() -> CliDependencies:
    executor = AnsibleExecutor(
        inventory=_ANSIBLE_ROOT / "inventory" / "localhost.yaml",
        tags="all",
    )
    fact_reader = AnsibleFactReader()
    bootstrap_playbook = _ANSIBLE_ROOT / "playbooks" / "bootstrap.yaml"
    verify_playbook = _ANSIBLE_ROOT / "playbooks" / "verify.yaml"
    return CliDependencies(
        plan=ProvisionMachineUseCase(executor, fact_reader, bootstrap_playbook),
        apply=ProvisionMachineUseCase(executor, fact_reader, bootstrap_playbook),
        verify=VerifyCapabilityUseCase(executor, fact_reader, verify_playbook),
        bootstrap=BootstrapUseCase(executor, fact_reader, bootstrap_playbook),
    )
```

### Playbook paths are the Epic 2 contract — do NOT validate or create them

`ansible/playbooks/bootstrap.yaml` and `ansible/playbooks/verify.yaml` are **Epic 2 content** (Story 2.2 scaffold, Story 2.12 playbooks). The CLI wires the expected paths only. `AnsibleExecutor` shells to `ansible-playbook` lazily at `run()`, so construction is safe even before the files exist. Do NOT add `exists()` checks, do NOT create the ansible tree, do NOT hardcode the old `/tmp/color-scheme` patterns. The `parents[3]` resolution assumes the source checkout (the `uv run --directory ./src/provisioning` bootstrap contract) — that is the intended deployment mode for Phase 1.

### Command → use-case → playbook mapping (locked)

| Command | Use case | Method | `check` | Playbook |
|---|---|---|---|---|
| `plan` | `ProvisionMachineUseCase` | `provision(check=True)` | `True` | `bootstrap.yaml` (Ansible `--check` diff) |
| `apply` | `ProvisionMachineUseCase` | `provision(check=False)` | `False` | `bootstrap.yaml` (idempotent apply) |
| `verify` | `VerifyCapabilityUseCase` | `verify()` | `False` (hardcoded in use case) | `verify.yaml` |
| `bootstrap` | `BootstrapUseCase` | `bootstrap(check=...)` | `False` default, `--check` flag overrides | `bootstrap.yaml` |

Per plan §7: `plan` runs `bootstrap.yaml --check`; `apply` runs it with `check=False`. The `bootstrap --check` flag satisfies FR-4 ("completes cleanly with no mutation") and was prepared by Story 1.7's `BootstrapUseCase.bootstrap(check=...)`. **plan/apply/bootstrap share the bootstrap playbook; verify uses the verify playbook.** This is also how the CLI satisfies the 1.7 deferred item ("CLI infers meaning from which playbook ran") — each command knows its own playbook and renders a contextual error message.

### Keep `version` and the existing `ctx.obj["renderer"]` contract

`cli/main.py` already has: the Typer app (help text already advertises plan/apply/verify/bootstrap — the 1.1 deferred item resolves automatically once the commands exist), `_renderer()`, the callback setting `ctx.obj = {"renderer": _renderer()}`, and the `version` command reading `ctx.obj["renderer"]`. Preserve `version` exactly. The callback becomes:

**Remove the superseded `_renderer()` helper** — once the callback uses `create_renderer(output_format)`, the old `_renderer()` (hardcoded `OutputFormat.JSON`, `main.py:27-28`) is dead code. Delete it so no stale JSON-only path lingers and ruff/mypy stay clean.

```python
@app.callback()
def main_callback(
    ctx: typer.Context,
    output_format: OutputFormat = OUTPUT_FORMAT_OPT,
) -> None:
    ctx.obj = {
        "renderer": create_renderer(output_format),
        "deps": build_deps(),
    }
```

`version` still reads `ctx.obj["renderer"]` — unchanged. `ctx.obj["deps"]` is new and used only by the four commands. The existing `tests/test_cli.py` (`TestVersionCommand`, `TestAppEntrypoint`) must keep passing untouched.

### Rendering: success via `ResultView`, failure via `ErrorView` + non-zero exit

All four commands share one helper. Render the per-task changed/ok diff and the resolved install dir so plan/apply divergence is *visible* (addresses the 1.6 deferred item "plan mode can't surface `install_dir`"):

```python
def _render_run(
    renderer: Renderer,
    fn: Callable[[], ProvisionResult],
    command: str,
) -> None:
    try:
        result = fn()
    except (
        ProvisionExecutorError,
        ProvisionTimeoutError,
        UnknownOsFamilyError,
        InvalidFactOutputError,
    ) as exc:
        renderer.error(ErrorView(kind=type(exc).__name__, message=str(exc)))
        raise typer.Exit(code=1) from None
    if not result.success:
        renderer.error(
            ErrorView(
                kind="ProvisionFailed",
                message=f"{command} failed (returncode={result.returncode})",
                details={"stderr": result.stderr},
            )
        )
        raise typer.Exit(code=1) from None
    renderer.result(
        ResultView(
            success=True,
            title=command,
            fields={
                "command": command,
                "install_dir": str(resolve_install_dir()),
                "returncode": result.returncode,
                "tasks": dict(result.tasks),
            },
        )
    )
```

- **Success** → `ResultView` → JSON `{"success": true, "title": command, "command": ..., "install_dir": ..., "returncode": ..., "tasks": {...}}`, exit 0. (`JsonRenderer.result` also emits the `title` field — assert key *presence*, not exact equality.)
- **Known adapter/domain error** → `ErrorView` → JSON `{"kind": ..., "message": ...}` on **stderr**, `typer.Exit(code=1)`. (`ProvisionTimeoutError` subclasses `ProvisionExecutorError`, so listing both in the `except` tuple is redundant but harmless.)
- **`result.success is False`** (Ansible returned non-zero / a task failed) → `ErrorView` with the contextual `{command} failed` message, non-zero exit.
- **Unexpected exceptions propagate** (fail loudly) — the 1.6 review precedent "let unexpected errors propagate" applies; only the four known error types are translated into structured errors. A fake that raises anything else (e.g. `RuntimeError`) surfaces as a traceback, NOT a JSON `ErrorView`.

### `options.py` — importable constants, no eager `create_renderer`

```python
from __future__ import annotations

import typer
from cli_output.domain.enums import OutputFormat

OUTPUT_FORMAT_OPT: OutputFormat = typer.Option(
    OutputFormat.JSON,
    "--output-format",
    help="Output format for command results",
    case_sensitive=False,
)

CHECK_OPT: bool = typer.Option(
    False,
    "--check",
    help="Dry run: complete cleanly with no mutation",
)
```

`options.py` imports only `typer` and `cli_output` — both already declared deps; the layering guard's `_allowed_third_party_roots()` already includes them.

### Layering guard (Story 1.3) — `cli/` is the outer shell

1. `_ALLOWED_TARGETS["cli"] = {"domain", "ports", "adapters", "application", "cli"}` — `main.py` may import adapters + application. `options.py` imports only `cli_output` + `typer` (nothing in-package).
2. `_classify_layer` resolves by directory — `cli/options.py` and `cli/main.py` are both classified `cli`. No guard edits.
3. Rule 5 cross-package: `cli_output` and `typer` are allowed roots. No new dependencies added.

### Style / tooling (repo conventions, from Stories 1.1–1.7)

- `from __future__ import annotations`, `requires-python >= 3.12`, ruff `line-length = 100`, double quotes, ruff selects `E F I N W UP B`, ignore `B905`.
- `mypy src tests` strict (`import-untyped` disabled) — annotate every helper, fixture param, and test method; fully-typed fake bodies.
- `uv run pytest` from `src/provisioning/`.
- The 1.7 review established `tests/unit/application/conftest.py` with `FakeExecutor`/`RaisingExecutor`/`FakeFactReader`. The CLI test conftest can **reuse `FakeExecutor`/`FakeFactReader`** (they implement the locked port interfaces) and wrap them in fake use cases, or define CLI-local fakes — either is fine as long as the fakes record calls (e.g. `.calls`) so tests can assert `check=True`/`check=False`/`verify()`/`bootstrap(check=...)` reached the right use case.
- ⚠️ **Do NOT reuse `RaisingExecutor` as-is for the adapter-error test.** It raises `RuntimeError("boom")` (`conftest.py:25-32`), which `_render_run` does NOT catch — it propagates as a traceback, so "stderr contains a JSON `ErrorView`" would fail. The adapter-error test needs a fake that raises one of the four known error types (e.g. `ProvisionExecutorError("...")`) — define a CLI-local `RaisingKnownErrorExecutor` or extend the existing fake.
- Test fixtures use `monkeypatch: pytest.MonkeyPatch` annotations (1.6 mypy finding).

### What this story is NOT (scope guard)

- No Ansible content (`ansible/playbooks/*.yaml`, inventory, roles) — Epic 2.
- No manifests (`dotfiles/provisioning/*.yaml`) — Story 2.1. The CLI does NOT read manifests; Ansible does.
- No new ports or use cases; no changes to `application/` or `adapters/`.
- No distro branching, no `provisioning-state.json` persistence (NFR-2), no package inspection.
- No `--tags` / `--inventory` / `--timeout` CLI flags unless a future story needs them — keep the four commands minimal per the ACs.
- Do NOT change `version` behavior or break the `ctx.obj["renderer"]` contract.

## Previous Story Intelligence

### Story 1.7 — Verify and Bootstrap Use Cases (the use cases the CLI drives)

- `VerifyCapabilityUseCase(executor, fact_reader, playbook=Path("verify.yaml"))` — `verify() -> ProvisionResult` (always `check=False`; a real check, never `--check`).
- `BootstrapUseCase(executor, fact_reader, playbook=Path("bootstrap.yaml"))` — `bootstrap(check=False) -> ProvisionResult`; `check=True` supports `bootstrap --check`.
- Both pass exactly the seam extra-vars `install_dir` + `os_family` (via `_seam_extra_vars`). The CLI supplies playbook paths as **constructor config** — the exact thing Story 1.7's dev note reserves for this story.
- 1.7 deferred: "Undifferentiated `ProvisionResult` — CLI infers meaning from which playbook ran." → each command knows its own playbook and renders a contextual error.

### Story 1.6 — Provision Use Case (the template to drive)

- `ProvisionMachineUseCase(executor, fact_reader, playbook=Path("bootstrap.yaml"))` — `provision(check) -> ProvisionResult`.
- `resolve_install_dir()` is exported from `application` — the CLI calls it directly to surface the install dir in output (1.6 deferred item, now in scope).
- 1.6 deferred: "plan mode can't surface `install_dir` and apply re-resolves it from env — plan/apply can diverge. Story 1.8 CLI scope" → render `install_dir` in every command's output.
- Adapter errors propagate uncaught to the CLI — the CLI is the error-rendering boundary.

### Story 1.5 — Adapters (the objects the CLI composes)

- `AnsibleExecutor(inventory: Path, tags: str, timeout=None, runner=None)` — `tags` must be non-empty (`"all"` matches test usage); shells to `ansible-playbook -i <inventory> --tags <tags> [--check] --extra-vars <json> <playbook>`; returns `ProvisionResult(success, tasks, returncode, stderr)`. Raises `ProvisionExecutorError` / `ProvisionTimeoutError`.
- `AnsibleFactReader(host="localhost", timeout=None, runner=None)` — `os_family() -> "arch" | "debian-family"`. Raises `UnknownOsFamilyError` / `InvalidFactOutputError`.
- `ProvisionResult` shape: `success: bool, tasks: tuple[tuple[str, str], ...], returncode: int, stderr: str`.

### Story 1.4 — Ports (locked signatures the use cases consume)

- `IProvisionExecutor.run(playbook: Path, check: bool, extra_vars: Mapping[str, str]) -> ProvisionResult`
- `IFactReader.os_family() -> str` — `"arch"` | `"debian-family"`.
- `IManifestReader.read(manifest_path) -> ProvisionManifest` — NOT consumed by the CLI.

### Story 1.3 / 1.2 / 1.1

- Layering guard is fail-closed; `cli/` imports everything (outer shell). `options.py` must live under `cli/` (top-level hexagon dir) — never at package root.
- Package root `src/provisioning/src/provisioning/`; tests in `src/provisioning/tests/`; only cross-package deps are `cli-output` (always) and declared pyproject deps (`typer`, `pydantic`, `ansible`, `yaml`).
- `pyproject.toml` already sets `dotfiles-provision = "provisioning.cli.main:app"` (Story 1.1) — the Typer app instance is the entry point; nothing to change there.
- 1.1 deferred: "`--help` advertises not-yet-existing plan/apply/verify/bootstrap commands" — **resolved by this story**; the help text is now accurate.

## Architecture Compliance

- **In-package hexagon (plan §11 step 5):** the CLI is the outer shell/composition root — `main.py` (Typer app + `build_deps()`) and `options.py` under `cli/`. `_ALLOWED_TARGETS["cli"]` includes everything; `options.py` imports only `cli_output` + `typer`. No guard edits.
- **FR-11 / AC 6:** all four commands render through `cli-output` (JSON by default via `OUTPUT_FORMAT_OPT`); success via `ResultView`, structured failures via `ErrorView` + non-zero exit — [Source: prd.md#118-124].
- **FR-1 / AC 2:** `plan` → `ProvisionMachineUseCase.provision(check=True)` (Ansible `--check` diff, no mutation) — [Source: prd.md#82-92].
- **FR-2 / AC 3:** `apply` → `ProvisionMachineUseCase.provision(check=False)`, idempotent, no state file — [Source: prd.md#94-100].
- **FR-3 / AC 4:** `verify` → `VerifyCapabilityUseCase.verify()` against provisioned locations — [Source: prd.md#102-108].
- **FR-4 / AC 5:** `bootstrap` → `BootstrapUseCase.bootstrap(check=...)`; `--check` completes cleanly with no mutation — [Source: prd.md#110-116].
- **NFR-2 (No persisted provisioning state):** the CLI never writes `provisioning-state.json`; `verify` re-derives state on demand.
- **NFR-5 (Testability):** CLI tests use `CliRunner` + monkeypatched `build_deps` (CSG `_invoke` pattern) — no real `ansible-playbook` invocation.
- **Install-dir seam surfacing:** the CLI renders `resolve_install_dir()` in every command's output so plan/apply can't silently diverge (hardening + 1.6 deferred item).

## Testing Requirements

- **`tests/unit/cli/conftest.py`** — fakes implementing the locked port interfaces (reuse `FakeExecutor`/`FakeFactReader` from `tests/unit/application/conftest.py`; do **NOT** reuse `RaisingExecutor` for the error test — it raises `RuntimeError`, which `_render_run` doesn't catch; add a CLI-local fake raising a known error type such as `ProvisionExecutorError`), wrapped so `ctx.obj["deps"]` exposes `plan/apply/verify/bootstrap` fake use cases with recorded `.calls`. An `_invoke(runner, deps, args, monkeypatch)` helper mirroring CSG: `monkeypatch.setattr("provisioning.cli.main.build_deps", lambda: deps)` then `runner.invoke(app, args)`.
- **`tests/unit/cli/test_commands.py`** — for EACH command:
  - **plan:** exits 0; JSON `success` true; fake use case recorded `provision(check=True)`.
  - **apply:** exits 0; fake use case recorded `provision(check=False)`.
  - **verify:** exits 0; fake use case recorded `verify()`.
  - **bootstrap:** exits 0 with default `check=False`; `["bootstrap", "--check"]` records `check=True`.
  - **Rendering:** success payload includes `command`, `install_dir` (assert it equals `resolve_install_dir()`), `returncode`, `tasks` (as a dict) — assert key presence, not exact payload equality (the renderer also adds `title`).
  - **Failure (adapter error):** a fake raising one of the four known errors (`ProvisionExecutorError`, `UnknownOsFamilyError`, etc.) → exit code non-zero; **stderr** contains a JSON `ErrorView` with `kind`/`message`.
  - **Failure (result.success False):** fake returns `ProvisionResult(success=False, ...)` → exit non-zero; contextual `{command} failed` message; `stderr` is included in `details`.
- `uv run pytest tests/unit/cli/` — new tests green.
- `uv run pytest tests/architecture/test_layering.py` — no violations (now includes `cli/options.py`).
- `uv run pytest` — full suite green (was 142 passed / 0 skipped).
- `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean.
- Standalone nicety: `python tests/architecture/test_layering.py` still exits 0.

## Project Context Reference

- PRD: `_bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md` — FR-1..FR-4, FR-11 (§4.1), NFR-2/NFR-5 (§5)
- SPEC: `_bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md` — CAP-1..CAP-4, §11 boundary
- Plan: `docs/01-dotfiles-provisioning-phase1-plan.md` — §6 repo layout (`cli/main.py` + `cli/options.py`, `ansible/playbooks/{bootstrap,verify}.yaml`, `ansible/inventory/localhost.yaml`), §7 reconciliation shape, §11 step 5
- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md` — Story 1.8 ACs, FR-11
- Application (drive these): `src/provisioning/src/provisioning/application/use_cases.py` + `__init__.py` (`resolve_install_dir` exported)
- Adapters (compose these): `src/provisioning/src/provisioning/adapters/{ansible_executor,ansible_fact_reader}.py`
- CLI (extend this): `src/provisioning/src/provisioning/cli/main.py` + new `options.py`
- cli-output API: `src/shared/cli-output/src/cli_output/{ports/renderer.py, domain/views.py, domain/enums.py, adapters/factory.py}`
- CSG pattern to mirror: `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/main.py` (`build_deps` + callback `ctx.obj` + `--output-format`) and `tests/unit/cli/test_show.py` (`_invoke` monkeypatch helper)
- Domain: `src/provisioning/src/provisioning/domain/models.py` — `ProvisionResult`
- Layering guard: `src/provisioning/tests/architecture/test_layering.py` — `_ALLOWED_TARGETS["cli"]`, `_allowed_third_party_roots()`
- Sprint: `_bmad-output/implementation-artifacts/sprint-status.yaml`

## References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#263-278] — Story 1.8 ACs
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#82-92] — FR-1 plan (check=True, no mutation)
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#94-100] — FR-2 apply (check=False, idempotent, no state file)
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#102-108] — FR-3 verify (VerifyCapabilityUseCase)
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#110-116] — FR-4 bootstrap (+ `--check` no mutation)
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#118-124] — FR-11 cli-output rendering, exit codes, `ctx.obj` mocks
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#217-228] — §7 reconciliation shape (plan → bootstrap.yaml --check; verify → verify.yaml)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#183-184] — §6 `cli/main.py` + `cli/options.py` layout
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#281] — §11 step 5 (Typer CLI, uses cli-output)
- [Source: src/provisioning/src/provisioning/application/use_cases.py] — `ProvisionMachineUseCase`, `VerifyCapabilityUseCase`, `BootstrapUseCase`, `resolve_install_dir`
- [Source: src/provisioning/src/provisioning/adapters/ansible_executor.py] — constructor signature, error types
- [Source: src/provisioning/src/provisioning/adapters/ansible_fact_reader.py] — constructor signature, error types
- [Source: src/shared/cli-output/src/cli_output/domain/views.py] — `ResultView`, `ErrorView` shapes
- [Source: src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/main.py] — `build_deps()` / callback / `--output-format` pattern
- [Source: src/cli-tools/color-scheme-generator/tests/unit/cli/test_show.py] — `_invoke` monkeypatch helper (mock deps on ctx.obj)
- [Source: _bmad-output/implementation-artifacts/deferred-work.md] — 1.1/1.6/1.7 deferred items resolved by this story

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Debug Log References

- 2026-08-05: Story created via create-story workflow — context loaded from epics Story 1.8 ACs, PRD FR-1..FR-4/FR-11/NFR-2/NFR-5, SPEC CAP-1..CAP-4 + §11, plan §6/§7/§11, prior stories 1.6/1.7 (use-case signatures, deferred items now in scope), adapters 1.5 (constructor signatures + error types), cli-output API (views/renderer/enums), layering guard `_ALLOWED_TARGETS["cli"]`, CSG `build_deps` + `_invoke` test pattern.

### Completion Notes List

- Story 1.8 created with `Status: ready-for-dev`. Tasks, dev notes, testing requirements, and references cover: `options.py` (`OUTPUT_FORMAT_OPT`, `CHECK_OPT`), `main.py` composition root (`CliDependencies` + `build_deps()` wiring AnsibleExecutor/AnsibleFactReader into the three use cases), four commands with the locked plan/apply/verify/bootstrap → playbook → check mapping, shared `_render_run` (ResultView on success incl. `install_dir`; ErrorView + non-zero exit on adapter errors or `success=False`), preserved `version` + `ctx.obj["renderer"]` contract, CSG-style `_invoke` test helper for `CliRunner` mock deps.

### File List

- `src/provisioning/src/provisioning/cli/options.py` (new)
- `src/provisioning/src/provisioning/cli/main.py` (update — callback + `build_deps` + four commands + `_render_run`, remove dead `_renderer()`)
- `src/provisioning/tests/unit/cli/conftest.py` (new — reuse `FakeExecutor`/`FakeFactReader`; CLI-local raising fake for a known error type)
- `src/provisioning/tests/unit/cli/test_commands.py` (new)
- `src/provisioning/tests/unit/cli/__init__.py` (new, if the tests/unit/cli dir is created)
