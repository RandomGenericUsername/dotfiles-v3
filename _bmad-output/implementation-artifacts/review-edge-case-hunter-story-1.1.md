[{
  "location": "src/provisioning/src/provisioning/cli/main.py:42-43",
  "trigger_condition": "PackageNotFoundError caught and error JSON emitted via raw print()",
  "guard_snippet": "ctx.obj['renderer'].error(ErrorView(kind='not-installed', message='dotfiles-provision package not installed'))",
  "potential_consequence": "Error output diverges from renderer schema and formatting; bypasses cli-output abstraction"
},
{
  "location": "src/provisioning/src/provisioning/cli/main.py:46",
  "trigger_condition": "ctx.obj dereferenced with [\"renderer\"] when callback may not have run",
  "guard_snippet": "renderer = (ctx.obj or {}).get('renderer'); if renderer is None: raise typer.Exit(code=1)",
  "potential_consequence": "Unhandled TypeError on None ctx.obj when version invoked outside normal typer callback flow"
},
{
  "location": "src/provisioning/src/provisioning/cli/main.py:39-44",
  "trigger_condition": "Metadata lookup raises PackageNotFoundError while __version__ is importable",
  "guard_snippet": "except PackageNotFoundError: ver = __version__",
  "potential_consequence": "version command exits 1 in non-installed run even though code-level version exists"
},
{
  "location": "src/provisioning/src/provisioning/__init__.py:6 (vs src/provisioning/pyproject.toml:20)",
  "trigger_condition": "Version stored twice as independent literals (__version__ vs pyproject version)",
  "guard_snippet": "assert __version__ == importlib.metadata.version('dotfiles-provision') in a sanity test",
  "potential_consequence": "Hardcoded __version__ silently drifts from packaged metadata the CLI reports"
},
{
  "location": "src/provisioning/src/provisioning/cli/main.py:28,46",
  "trigger_condition": "create_renderer return typed as object and ctx.obj dict untyped; custom() invisible to type checker",
  "guard_snippet": "def _renderer() -> Renderer: return create_renderer(OutputFormat.JSON)",
  "potential_consequence": "Refactor to a renderer lacking custom() compiles and crashes at runtime only"
},
{
  "location": "src/provisioning/tests/test_cli.py:14-18",
  "trigger_condition": "Happy-path version test relies on installed distribution metadata, no mock of _pkg_version",
  "guard_snippet": "monkeypatch.setattr(cli_main, '_pkg_version', lambda n: '0.1.0')",
  "potential_consequence": "Test fails in source checkout/CI without editable install despite correct code"
},
{
  "location": "src/provisioning/src/provisioning/cli/main.py:40",
  "trigger_condition": "Distribution name string hardcoded where app.info.name also exists",
  "guard_snippet": "_pkg_version(__name__.split('.')[0] if False else 'dotfiles-provision') or shared constant",
  "potential_consequence": "Renaming the project makes version lookup silently hit not-installed error path"
},
{
  "location": "src/provisioning/src/provisioning/cli/main.py:40-46",
  "trigger_condition": "Metadata returns empty/whitespace version string, unvalidated before render",
  "guard_snippet": "if not ver or not ver.strip(): raise typer.Exit(code=1)",
  "potential_consequence": "Corrupt metadata renders {\"version\": \"\"} as a successful result"
}]
