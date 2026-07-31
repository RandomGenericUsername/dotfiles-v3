# Interface Contract Test

## Why

The container processor adapter constructs a CLI argv that it passes into
the container. This argv must be parseable by the in-container CLI. If the
CLI's flag scope changes (root → sub-typer callback → leaf), and the
adapter is not updated, the argv will be rejected at runtime. We need a
test that detects this at test time.

Existing tests of the container processor mock the container engine and
never validate the argv against the live CLI. Assertions like
`"process effect blur" in result.command` catch substring presence but
not flag positioning. Both `cli-flag-scope-completion` (commit `29883d2`)
and `cli-flag-scope-refinement` moved flags between scopes without tests
failing.

## Spec

### 1. Test structure

For each tool, a test that:

1. Constructs a `ProcessingRequest` / `GenerationRequest` with a
   synthetic input path.
2. Calls the production adapter method that produces the in-container argv
   (WEG: `_build_weg_command`; CSG: `process_generate`'s `inner_command`).
3. Strips the program name (`"weg"` or `"csg"`) from the argv.
4. Passes the remaining argv through `typer.testing.CliRunner` against
   the live CLI `app`.
5. Mocks processor resolution to short-circuit actual execution.
6. Asserts `exit_code == 0`.

### 2. WEG test

```python
def test_build_weg_command_argv_is_accepted_by_cli(self, processor, tmp_path):
    from typer.testing import CliRunner
    from wallpaper_effects_generator.cli.main import app

    request = ProcessingRequest(
        input_path=tmp_path / "img.png",
        output_path=tmp_path / "img.png",
    )
    cmd = processor._build_weg_command("effect", "blur", request, {"radius": "0x8"})
    # cmd looks like: ["weg", "process", "effect", "blur", "/input/img.png",
    #                   "-o", "/output", "--param", "radius=0x8"]
    cli_argv = cmd[1:]  # strip "weg" — CliRunner doesn't expect program name

    from unittest.mock import patch, MagicMock
    mock_processor = MagicMock()
    mock_processor.process_effect.return_value = ProcessingResult(
        success=True, command="", stdout="", stderr="", return_code=0,
    )

    runner = CliRunner()
    with (
        patch("wallpaper_effects_generator.cli.process._resolve_processor",
              return_value=mock_processor),
        patch("wallpaper_effects_generator.cli.process._resolve_context",
              return_value=(magic_mock_settings, magic_mock_catalog)),
        patch("wallpaper_effects_generator.cli.process.Path.exists",
              return_value=True),
    ):
        result = runner.invoke(app, cli_argv)

    assert result.exit_code == 0, (
        f"Adapter argv rejected by live CLI\n"
        f"  argv: {cli_argv}\n"
        f"  stderr: {result.stderr}"
    )
```

#### Parameterization

The test should test all three subcommand types:

| Subcommand | `_build_weg_command` call | Key assertion |
|------------|--------------------------|---------------|
| `effect` | `processor._build_weg_command("effect", "blur", request, {"radius": "0x8"})` | `result.exit_code == 0` |
| `composite` | `processor._build_weg_command("blur-resize", request, None)` | `result.exit_code == 0` |
| `preset` | `processor._build_weg_command("social", request, None)` | `result.exit_code == 0` |

### 3. CSG test

CSG's `generate` command inlines processor creation rather than calling
a `_resolve_processor` helper — it directly calls
`create_local_processor(...)` or `create_container_processor(...)` at
`cli/main.py:225-231`. The test must patch these factory functions.

CSG's argv is not built by a standalone `_build_weg_command` method but
internally in `process_generate`. The test captures it from the mock's
`call_args`, following the existing CSG test pattern
(`test_inner_command_contains_runtime_local`).

```python
def test_inner_command_argv_is_accepted_by_cli(self, tmp_path, monkeypatch):
    from typer.testing import CliRunner
    from color_scheme_generator.cli.main import app

    templates_dir, output_dir, processor = _setup_test_env(tmp_path)
    settings = _make_settings()
    request = GenerationRequest(
        image_path=tmp_path / "input" / "wallpaper.png",
        config=GeneratorConfig(
            backend=Backend.CUSTOM,
            params={},
            formats=(ColorFormat.JSON,),
            output_dir=output_dir,
        ),
    )

    mock_processor = MagicMock()
    mock_processor.process_generate.return_value = MagicMock(success=True)
    monkeypatch.setattr(
        "color_scheme_generator.cli.main.create_local_processor",
        lambda *a, **kw: mock_processor,
    )
    monkeypatch.setattr(
        "color_scheme_generator.cli.main.create_container_processor",
        lambda *a, **kw: mock_processor,
    )

    processor.process_generate(request, settings)

    call_args = processor._container_runtime.run.call_args
    command = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("command", [])
    cli_argv = command[1:]  # strip "csg" program name

    runner = CliRunner()
    result = runner.invoke(app, cli_argv)

    assert result.exit_code == 0, (
        f"Adapter argv rejected by live CLI\n"
        f"  argv: {cli_argv}\n"
        f"  stderr: {result.stderr}"
    )
```

Note: The CSG test does NOT need to patch `Path.is_file` or `Path.exists`
because the path validation in CSG's `generate` command is inside the
mocked processor path (after line 231) and not in the CLI parsing stage.
The CliRunner validates argv structure only — it doesn't touch the file.

### 4. What it guards against

If a future change moves a CLI flag from one scope to another (e.g.,
moving `--backend` from the `generate` leaf to a root callback, or vice
versa), this test will fail if the adapter's argv is not updated
accordingly.

Specific failure modes detected:

| Change | CLI behavior | Test signal |
|--------|--------------|-------------|
| Flag moved from sub-typer callback to root | CLI rejects the sub-typer position | `exit_code != 0`, stderr contains `"No such option"` |
| Flag moved from root to sub-typer callback | CLI rejects the root position | `exit_code != 0`, stderr contains `"No such option"` |
| Flag renamed | CLI rejects old name | `exit_code != 0`, stderr contains `"No such option"` |
| Flag removed entirely | CLI rejects flag | `exit_code != 0`, stderr contains `"No such option"` |
| Positional arguments reordered | CLI rejects wrong-arity or unknown positional | `exit_code != 0`, stderr contains `"Got unexpected extra argument"` |

### 5. What it does NOT guard against

The test patches processor resolution (WEG: `_resolve_processor` and
`_resolve_context`; CSG: `create_local_processor` and
`create_container_processor`), so it does not test:

- Whether the processor functions correctly with the given argv
- File existence or path resolution inside the container
- Version drift between the host `weg` and the container image's `weg`
