# Container Adapter Decoupling

Replace CLI-flag-based in-container argument passing with env-var-based
discovery in both WEG and CSG container processors, and add interface
contract tests that validate the adapter's argv against the live CLI parser.

## Status

**The env-var migration was completed by the sibling change
`cli-flag-scope-refinement` (commit `9ee6595`).** Only the interface
contract tests (tasks 3.3 and 4.3) remain unimplemented.

## Why

The container_processor.py adapter in both tools constructs a CLI argv
that it passes into the container. This argv is coupled to the
flag-scope decisions of the CLI layer (root vs group vs leaf). Any
change to flag scope silently breaks the adapter — exactly what happened
with `cli-flag-scope-completion` (commit 29883d2), which moved
`--config`/`--effects` from root to sub-typer callbacks but never
updated `container_processor.py:_build_weg_command()`.

The result: `weg batch all ~/Downloads/test.jpg` fails 9/9 with
`"No such option: --config"`.
