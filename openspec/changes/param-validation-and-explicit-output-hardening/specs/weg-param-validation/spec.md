## ADDED Requirements

### Requirement: Shared strict `--param` parsing
The CLI SHALL parse `--param` overrides with a single shared parser used by both the `process` and `batch` command groups. Each `--param` entry MUST be in `key=value` form. An entry without `=` SHALL be rejected with a `typer.BadParameter` error and a non-zero exit. An entry whose key is empty after stripping surrounding whitespace (e.g. `=5` or `  =5`) SHALL be rejected with a `typer.BadParameter` error and a non-zero exit.

#### Scenario: process rejects malformed param without equals
- **WHEN** `weg process effect blur <input> --param badparam` is invoked
- **THEN** the exit code is non-zero
- **AND** the output contains `Invalid param format`

#### Scenario: batch rejects malformed param without equals
- **WHEN** `weg batch effects <input> --param badparam` is invoked
- **THEN** the exit code is non-zero
- **AND** the output contains `Invalid param format`

#### Scenario: empty key is rejected for both command groups
- **WHEN** `weg process effect blur <input> --param =5` is invoked
- **AND** when `weg batch effects <input> --param "  =5"` is invoked
- **THEN** the exit code is non-zero in both cases
- **AND** the output contains `Invalid param format`

### Requirement: Unknown parameter keys are rejected before execution
For every `process` and `batch` command, user-supplied `--param` keys SHALL be validated against the union of declared parameter names across the command's in-scope target units before any processing begins. A key not declared by any in-scope unit SHALL raise a distinct `UnknownParamError` surfaced as `typer.BadParameter` with a message naming the unknown key(s), the scope, and the valid keys (or `(none declared)`). This SHALL happen before any item is processed.

#### Scenario: single effect rejects unknown key
- **WHEN** `weg process effect blur <input> --param bliur=0x15` is invoked
- **THEN** the exit code is non-zero
- **AND** the output names `bliur` as unknown
- **AND** the output names the scope `effect 'blur'`
- **AND** the output lists `blur` among the valid keys

#### Scenario: single zero-param effect rejects any key
- **WHEN** `weg process effect blackwhite <input> --param brightness=50` is invoked
- **THEN** the exit code is non-zero
- **AND** the output names `brightness` as unknown
- **AND** the output indicates no parameters are declared

#### Scenario: composite scope is its underlying step-effects
- **WHEN** `weg process composite blackwhite-blur <input> --param shadow=3` is invoked
- **THEN** the exit code is non-zero
- **AND** the output names the scope `composite 'blackwhite-blur'`
- **AND** `shadow` is not a declared key of that composite's step-effects

#### Scenario: composite accepts a key declared by any step-effect
- **WHEN** `weg process composite blur-brightness80 <input> --param blur=5x3 --param brightness=10` is invoked
- **THEN** the exit code is zero
- **AND** both keys are applied to the steps that declare them

### Requirement: Batch param validation is scoped per kind
Each batch kind SHALL validate `--param` keys against the union of declared parameter names of the units that kind actually runs, with error messages identifying the batch kind. `batch effects` SHALL use all catalog effects; `batch composites` SHALL use the step-effects of all composites; `batch presets` SHALL use the effects referenced by all presets; `batch all` SHALL use all catalog effects. A key valid for a unit outside the batch kind's scope SHALL be rejected even if it is declared by an effect elsewhere in the catalog.

#### Scenario: batch composites rejects a key unknown to composite step-effects
- **WHEN** `weg batch composites <input> --param contrast=40` is invoked against a catalog where no composite references an effect declaring `contrast`
- **THEN** the exit code is non-zero
- **AND** the output contains `for batch composites`
- **AND** the output names `contrast` as unknown
- **AND** the output's valid list does NOT include `contrast`

#### Scenario: batch effects accepts a key declared by any effect
- **WHEN** `weg batch effects <input> --param blur=5x3` is invoked
- **THEN** the exit code is zero

#### Scenario: batch presets scopes to preset-referenced effects
- **WHEN** `weg batch presets <input> --param <key-not-declared-by-any-preset>=1` is invoked
- **THEN** the exit code is non-zero
- **AND** the output contains `for batch presets`

### Requirement: Mixed-parameter batch all applies per-target
For `weg batch all`, a user-supplied `--param` key SHALL be accepted if it is declared by at least one effect in the catalog, and SHALL be applied only to the effects, composite steps, and presets that declare it. Effects, composite steps, and presets that do not declare a given accepted key SHALL run with their defaults and SHALL NOT error. A key declared nowhere in the catalog SHALL be rejected before any item is processed.

#### Scenario: batch all accepts keys declared somewhere
- **WHEN** `weg batch all <input> --param blur=5x3 --param brightness=10 --param color=#ffffff --param opacity=20 --param contrast=40 --param saturation=50 --param strength=10` is invoked against a catalog declaring all those keys
- **THEN** the exit code is zero

#### Scenario: batch all rejects a partially unknown key set
- **WHEN** `weg batch all <input> --param blur=5x3 --param typo=1` is invoked
- **THEN** the exit code is non-zero
- **AND** the output names `typo` as unknown
- **AND** the output contains `for batch all`

#### Scenario: batch all rejects a key declared nowhere
- **WHEN** `weg batch all <input> --param typo=1` is invoked against a catalog where no effect declares `typo`
- **THEN** the exit code is non-zero
- **AND** the output names `typo` as unknown

#### Scenario: unknown key in strict batch aborts before processing
- **WHEN** `weg batch effects --strict <input> --param typo=1` is invoked with a fake processor recording calls
- **THEN** the exit code is non-zero
- **AND** the fake processor records no calls (no item was processed)

### Requirement: Parameter resolution stays lenient per-target
`ParameterResolutionService.resolve_all` SHALL accept an `overrides` dict containing keys not declared by the given parameters, ignoring those keys without raising, and resolving declared parameters from their matching overrides or defaults. This is the per-target application contract that makes mixed-parameter batch execution viable after upfront scope validation passes.

#### Scenario: resolve_all ignores an unknown override key
- **WHEN** `resolve_all(parameters=(p_a,), overrides={"a": "1", "x": "2"})` is called where `p_a` declares key `a`
- **THEN** the result is `{"a": "1"}`
- **AND** no exception is raised

#### Scenario: resolve_all accepts empty overrides
- **WHEN** `resolve_all(parameters=(p_a,), overrides=None)` or `overrides={}` is called
- **THEN** declared parameters resolve to their defaults
- **AND** no exception is raised

### Requirement: Valid parameter overrides still apply
Known `--param` keys SHALL reach the processor unchanged as parameter overrides, so a legitimate override produces a successful run.

#### Scenario: known override reaches the processor
- **WHEN** `weg process effect blur <input> --param blur=5x3` is invoked with a fake processor recording its `params` argument
- **THEN** the exit code is zero
- **AND** the fake processor received `params["blur"] == "5x3"`

### Requirement: explicit-output requires an output directory
The `batch` command SHALL raise `typer.BadParameter("--explicit-output requires -o/--output")` when `--explicit-output` is supplied without `-o/--output`, exiting non-zero. Supplying `--explicit-output` together with `-o/--output` SHALL succeed and write output directly to the given directory.

#### Scenario: explicit-output without output directory is rejected
- **WHEN** `weg batch effects <input> --explicit-output` is invoked without `-o/--output`
- **THEN** the exit code is non-zero
- **AND** the output contains `--explicit-output requires`

#### Scenario: explicit-output with output directory succeeds
- **WHEN** `weg batch effects <input> --explicit-output -o <dir>` is invoked
- **THEN** the exit code is zero
- **AND** output files are written directly under `<dir>`
