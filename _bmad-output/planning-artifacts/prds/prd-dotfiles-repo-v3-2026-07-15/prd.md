---
title: color-scheme-generator v3
status: final
created: 2026-07-15
updated: 2026-07-15
---

# PRD: color-scheme-generator v3

## 0. Document Purpose

This PRD defines the v3 rewrite of the color-scheme-generator CLI tool. It is written for the developer maintaining the tool, downstream workflow owners, and anyone integrating color scheme extraction into their dotfiles pipeline. Features are grouped by capability with globally-numbered functional requirements (FR-N). This PRD builds on the ARCHITECTURE_PLAN.md and the v2 reference implementation at `dotfiles-repo-v2/src/cli-tools/color-scheme-generator/`.

## 1. Vision

color-scheme-generator extracts color palettes from wallpaper images and renders them into config formats (JSON, shell scripts, CSS, GTK CSS, YAML, Rofi RASI, SCSS, terminal sequences) for use in Linux desktop environments, terminal emulators, and application themes.

v2 was organized as a multi-package monorepo (`core` + `orchestrator` + `templates`) with a `layered-settings` config system, `transparent-orchestrator` proxy command pattern, and `container-manager` for Docker/Podman execution. While functional, this architecture made maintenance, debugging, extension, and testing unnecessarily difficult.

v3 replaces that stack with a single-package hexagonal architecture: pure domain models with zero I/O, explicit ports and adapter implementations, deterministic single-file config resolution via `config-assembler-engine`, and runtime-agnostic processing through `oci-runtime`. The result is a tool that is testable in isolation, debuggable through clear error types and source attribution, and extensible by adding adapter implementations rather than modifying existing code.

## 2. Target User

**Primary — Juan David (maintainer & integrator).** Needs the tool to be testable in isolation, debuggable through clear error types and source attribution, extensible by adding adapter implementations. Integrates `csg` as a CLI dependency in a larger dotfiles pipeline where deterministic, scriptable output is required.

**Secondary — Linux desktop theming user.** Runs `csg generate wallpaper.jpg` to get color schemes for terminal, rofi, GTK. Does not care about architecture; expects the tool to work out of the box and produce usable config files.

### 2.1 Key User Journeys

- **UJ-1. Juan David debugs a failing extraction in CI.**
  A CI pipeline runs `csg generate` with a new wallpaper. The command produces unexpected colors. Juan David runs `csg generate --dry-run` to pre-flight the backend params, `csg info` to verify which settings.toml was resolved and which overrides applied, and `csg list-backends` to confirm the target backend is available. Error output is structured JSON with a type code and message — no Rich formatting needed in CI.

- **UJ-2. A user extracts a palette for the first time.**
  User installs `csg` via pip, runs `csg generate ~/wallpaper.jpg`. The tool resolves its default settings, uses the configured default backend, extracts the palette, and writes `colors.json` and `colors.sh` to `/tmp/color-scheme/`. The user sources the shell file and their terminal colors update.

- **UJ-3. A user runs in container mode because they don't have `pywal` installed.**
  User runs `csg generate --runtime container ~/wallpaper.jpg --backend pywal`. The host resolves config, checks that the `color-scheme-pywal:latest` image exists, mounts the input/output/templates into a container, and runs extraction inside it. The resulting files appear on the host as if extraction ran locally.

## 3. Glossary

- **Backend** — An extraction algorithm that derives a color palette from an image. One of `custom` (PIL + KMeans), `pywal` (`wal` binary), `wallust` (`wallust` binary). Explicit only — no auto-detection.
- **Runtime Mode** — Where backend execution happens: `local` (host binaries) or `container` (OCI container with per-backend image).
- **GeneratorConfig** — The resolved set of parameters passed to a backend for a single extraction: backend selection, per-backend parameter overrides, output formats, output directory.
- **ColorScheme** — The output of extraction: background/foreground/cursor colors (as hex + RGB), a 16-color palette, source image path, backend identity, generation timestamp.
- **OutputPort** — The rendering boundary between domain and user display. Takes domain objects (ColorScheme, GenerationResult, errors) and renders them as JSON (default), Rich (terminal), or Plain (pipes).
- **Container Engine** — The OCI runtime used for container-mode execution. One of `docker` or `podman`.
- **Backend Parameter** — A named runtime parameter specific to a backend (e.g. `saturation`, `n_clusters`, `algorithm`). Defined in `BACKEND_DEFINITIONS`, overridden at CLI via `--param key=value`.
- **Settings.toml** — Single TOML configuration file resolved by config-assembler-engine. Contains output, generation, templates, runtime, and container settings. No multi-file merge.
- **AppSettings** — The resolved domain dataclass containing all configuration after validation and override application.

## 4. Features

### 4.1 Color Extraction

The core capability: extract a color palette from an image using a selected backend. Realizes UJ-2, UJ-3.

#### FR-1: Palette Extraction

User can run `csg generate <image_path>` to extract a color palette from a valid image file. The system resolves config, selects the backend, runs extraction, renders templates, and writes output files.

**Consequences (testable):**
- System accepts PNG, JPEG, and other common image formats readable by PIL
- System produces a ColorScheme with exactly 16 palette colors + background + foreground + cursor
- System writes output files for each requested format to the output directory
- System returns structured JSON output (default) with success status and output file paths
- System raises `InvalidImageError` for unreadable or nonexistent image paths
- System raises `ColorExtractionError` when backend extraction fails

#### FR-2: Backend Selection

User can select the extraction backend via CLI flag `--backend custom|pywal|wallust`, or rely on the configured default in settings.toml. Backend is always explicit — no auto-detection.

**Consequences (testable):**
- `--backend custom` selects CustomGenerator (PIL + scikit-learn KMeans)
- `--backend pywal` selects PywalGenerator (subprocess `wal`)
- `--backend wallust` selects WallustGenerator (subprocess `wallust`)
- Omitting `--backend` uses the value from `settings.generation.backend`
- Passing an invalid backend value raises a validation error with accepted values
- If the selected backend is not available on the host (local mode), raises `BackendNotAvailableError` with an install hint

#### FR-3: Per-Backend Parameter Overrides (--param)

User can pass backend-specific runtime parameters via repeatable `--param key=value` flags. Parameters are defined in `BACKEND_DEFINITIONS` per backend and include type, min/max/choices validation.

**Consequences (testable):**
- `--param saturation=1.5` overrides the saturation parameter for the active backend
- `--param n_clusters=8` overrides the cluster count (custom backend only)
- Multiple `--param` flags are accepted: `--param saturation=1.5 --param algorithm=thief`
- Last value wins for duplicate keys
- Malformed entries (no `=`) are silently dropped
- Non-existent parameter for the active backend raises `ConfigResolutionError`
- Coercion failure (e.g. `--param saturation=abc` where saturation expects float) raises `ConfigResolutionError`
- Validation failure (out of min/max/choices range) raises `ConfigResolutionError`

#### FR-4: Show Command

User can run `csg show <image_path>` to extract and display a color palette without writing any output files. Uses the same extraction pipeline as generate but skips template rendering and file writing.

**Consequences (testable):**
- Runs the full extraction pipeline (config resolution, backend selection, palette generation)
- Does not write any output files
- Displays the palette via the active OutputPort adapter
- Supports `--backend`, `--param`, `--dry-run` flags with the same semantics as `generate`

#### FR-5: Dry-Run Mode

User can append `--dry-run` / `-n` to `generate` or `show` to pre-flight the command without executing extraction.

**Consequences (testable):**
- Validates input image exists and is readable
- Validates backend is available (local mode) or engine+image available (container mode)
- Validates output directory is writable
- Validates templates directory is resolvable
- Validates all `--param` overrides coerce cleanly against `BACKEND_DEFINITIONS[backend].parameters`
- Renders the resolved command that would execute, without running it
- Returns success if all validations pass; raises first validation failure otherwise

### 4.2 Container Image Lifecycle

Manage per-backend OCI container images for container-mode execution.

#### FR-6: Install Backends

User can run `csg install` to build OCI container images for one or more backends. Each backend gets its own image using backend-specific Dockerfiles built on a shared base.

**Consequences (testable):**
- `csg install` without `--backend` builds all three backend images
- `csg install --backend custom --backend pywal` builds only those two
- Each image is named `[registry/]color-scheme-<backend>:<tag>`
- Build uses `oci-runtime`'s `engine.images.build()` with the appropriate Dockerfile
- Supports `--engine docker|podman` to select the container engine
- Supports `--dry-run` to render the build plan without executing
- `--dump-config` and `--dump-templates` can bootstrap default config/template files post-build
- Image build errors map to explicit domain error categories

#### FR-7: Uninstall Backends

User can run `csg uninstall` to remove OCI container images for one or more backends.

**Consequences (testable):**
- `csg uninstall` without `--backend` removes all three backend images (with confirmation)
- `csg uninstall --backend wallust --yes` removes only the wallust image without prompting
- Uses `oci-runtime`'s `engine.images.remove()`
- Supports `--engine docker|podman`
- Supports `--dry-run`
- Image removal errors map to explicit domain error categories

### 4.3 Configuration & Diagnostics

Deterministic config resolution and operational introspection. Realizes UJ-1.

#### FR-8: Config Resolution (Settings.toml)

The system resolves a single `settings.toml` file using config-assembler-engine's `AssembleConfiguration` pipeline with strategy chain: CLI explicit path > ENV path > directory traversal > XDG > package default.

**Consequences (testable):**
- `csg generate --config /path/to/settings.toml` uses the explicit path
- `COLORSCHEME_CONFIG_FILE_PATH=/env/path.toml csg generate` uses the env path
- Without explicit path or env, traverses up to 3 directory levels for `settings.toml`
- Falls back to `$XDG_CONFIG_HOME/color-scheme/settings.toml`
- Falls back to package-bundled `defaults/settings.toml`
- Fails with `PathResolutionError` if no config file is found and no default exists
- Returns the resolved path and all applied overrides via `info`

#### FR-9: Override Rules

Declared settings fields can be overridden via ENV vars (double-underscore separated) or CLI flags. Override rules are defined per-field with allowed sources (ENV, CLI, or both).

**Consequences (testable):**
- `COLORSCHEME__RUNTIME__MODE=container csg generate` overrides runtime mode
- `COLORSCHEME__GENERATION__BACKEND=wallust csg generate` overrides default backend
- CLI flag `--backend custom` overrides both the config file and ENV value
- Override rules exist for: `output.verbosity`, `output.directory`, `generation.backend`, `generation.default_formats`, `templates.directory`, `runtime.mode`, `container.engine`, `container.image_tag`, `container.image_registry`
- Fields not in override rules (e.g. `version`) are not overridable via ENV/CLI
- Applied overrides are reported via `info`

#### FR-10: Info Command

User can run `csg info` to display resolved config source path, effective runtime mode, container engine, resolved templates directory, applied overrides, and backend availability status.

**Consequences (testable):**
- Displays the resolved settings.toml path and its source (CLI/ENV/XDG/DEFAULT)
- Displays all applied overrides with source and coerced value
- Displays the effective runtime mode and container engine
- Displays the resolved templates directory
- Displays backend availability for all three backends
- Supports `--output-format json|rich|plain`

#### FR-11: Dump-Config Command

User can run `csg dump-config` to output the full resolved AppSettings as TOML to stdout or a file.

**Consequences (testable):**
- `csg dump-config` prints resolved config TOML to stdout
- `csg dump-config --output /path/to/output.toml --overwrite` writes to file
- The output includes all applied overrides inline

#### FR-12: Dump-Templates Command

User can run `csg dump-templates` to copy the bundled default `.j2` template files to the user templates directory.

**Consequences (testable):**
- `csg dump-templates` copies all 8 bundled templates to `$XDG_CONFIG_HOME/color-scheme/templates/`
- Creates parent directories if they don't exist
- `--overwrite` replaces existing files; without it, skips existing files
- `csg dump-templates --output /custom/path` copies to a custom path

#### FR-13: List-Backends Command

User can run `csg list-backends` to see all available backends with their host availability, image presence (container mode), and supported parameters.

**Consequences (testable):**
- For each backend: shows name, description, whether available on the host, whether the container image exists
- Shows supported parameters with type, default, and allowed values/range
- Supports `--output-format json|rich|plain`

#### FR-14: Version Command

User can run `csg version` to display the current version string.

**Consequences (testable):**
- Outputs the version from `importlib.metadata.version("color-scheme-generator")`
- Supports `--output-format json|rich|plain`

### 4.4 Template Rendering

Render extracted ColorSchemes into multiple output formats using Jinja2 templates.

#### FR-15: Template Rendering

The system renders a ColorScheme into each requested output format using Jinja2 `.j2` templates resolved from the templates directory.

**Consequences (testable):**
- Supported formats: JSON, SH, CSS, GTK_CSS, YAML, SEQUENCES, RASI, SCSS
- Templates use Jinja2 with `StrictUndefined` (undefined variables raise an error)
- Templates are loaded from the resolved templates directory via `CompositePathResolver`
- Default templates are bundled in the package at `defaults/templates/`
- The `sequences` format gets binary post-processing (`]` → `\x1b]`, `\` → `\x1b\\`)
- Missing template raises `TemplateNotFoundError` with searched paths
- Template render failure raises `TemplateRenderError`

### 4.5 Multi-Format Output

Structured command output in three formats selected via `--output-format`.

#### FR-16: JSON Output (Default)

All commands return structured JSON by default. JSON output is parseable by CI pipelines and automation.

**Consequences (testable):**
- `generate` success: `{"success": true, "color_scheme": {...}, "output_files": [...], "backend": "...", "duration": ...}`
- `generate` failure: `{"success": false, "error": {"type": "ColorExtractionError", "message": "..."}}`
- All operational commands (`info`, `list-backends`, `version`, etc.) return JSON
- Error output is always JSON with type code and message — never terminal-only formatting

#### FR-17: Rich Output

With `--output-format rich`, commands render with colors, tables, and structure for terminal readability.

#### FR-18: Plain Output

With `--output-format plain`, commands render as minimal plain text with no formatting for pipe-friendly consumption.

### 4.6 Container Execution

Run extraction inside OCI containers for environments where backends are not installed on the host. Realizes UJ-3.

#### FR-19: Container-Mode Processing

User can run `generate` or `show` with `--runtime container` to execute extraction inside a pre-built OCI container image matching the selected backend.

**Consequences (testable):**
- Pre-flight: resolves config, resolves templates, resolves backend params
- Selects image `[registry/]color-scheme-<backend>:<tag>` matching the active backend
- Verifies container engine is available (raises `ContainerRuntimeUnavailableError` if not)
- Verifies image exists (raises `ContainerImageNotFoundError` if not)
- Serializes resolved AppSettings (as-resolved, no rewrite) to a temp TOML file
- Mounts: input parent dir → `/input` (RO), output dir → `/output` (RW), temp TOML → `/csg-config/settings.toml` (RO), templates dir → `/templates` (RO)
- Inner command receives `--runtime local` (overrides config via CLI override priority, preventing recursion)
- Forwards `--param` pairs verbatim to inner command
- Cleans up temp TOML in `finally`
- Container output matches the same contract shape as local mode (NFR-1)

**Feature-specific NFRs:**
- Container execution must not depend on host ENV forwarding for configuration parity (NFR-4)
- Container mount model must avoid implicit host-environment leakage (NFR-6)

#### FR-20: Runtime Mode and Container Engine Selection

Runtime mode (`local`/`container`) and container engine (`docker`/`podman`) are orthogonal, independently selectable controls.

**Consequences (testable):**
- `--runtime local` uses host binaries regardless of `--container-engine` value
- `--runtime container --container-engine docker` uses Docker
- `--runtime container --container-engine podman` uses Podman
- Invalid engine value raises a validation error with accepted values
- Changing one flag does not affect the other's available values

## 5. Cross-Cutting Non-Functional Requirements

#### NFR-1: Determinism (Runtime Parity)

Equivalent commands under equivalent resolved settings must produce equivalent ColorSchemes and result contracts across Runtime Modes.

**Consequences (testable):**
- Running `csg generate` with identical config in local and container mode produces the same result contract shape (same fields, same structure)
- Any differences are surfaced only through explicit runtime errors (not silent contract divergence)

#### NFR-2: Reliability (Graceful Degradation)

Errors never produce unstructured output. Every failure returns a structured JSON error with type code, message, and actionable context.

**Consequences (testable):**
- All domain exceptions (ColorSchemeError hierarchy) serialize to JSON error payloads
- Container runtime errors (timeout, image not found, engine unavailable) map to explicit domain error categories
- Batch/sequence operations that fail still return structured results for completed items

#### NFR-3: Observability (Source Attribution)

Resolution source paths and effective runtime mode must be inspectable from operational commands (info) without running extraction.

#### NFR-4: Runtime/Engine Orthogonality

Runtime mode and container engine selection remain independent controls. Changing one does not affect the other's available values or semantics.

#### NFR-5: Container Security Baseline

Container mount model avoids implicit host-environment leakage. All mounts are explicit host-to-container binds. Writable output directories use permission strategy for non-root container user execution.

#### NFR-6: Testability

Domain logic (models, services, enums, exceptions) is testable with zero I/O — pure function calls with no mocking. Adapters are testable with mocked ports.

**Consequences (testable):**
- Domain unit tests: no fixtures, no temp files, no subprocess mocking
- Adapter tests: mock PaletteGeneratorPort / OutputPort / ConfigResolverPort via Protocol
- CLI tests: Typer CliRunner with Mock deps on ctx.obj

## 6. Non-Goals (Explicit)

- **Not a GUI/TUI.** color-scheme-generator is a CLI tool. No graphical interface, no interactive wizard.
- **Not a template editor.** Templates are Jinja2 files; the tool renders them, it does not validate or edit template content.
- **Not an image manipulation tool.** Color extraction only. No resizing, cropping, filtering beyond what extraction requires internally.
- **Not a template editor.** Templates are Jinja2 files; the tool renders them, it does not validate or edit template content.
- **Not a generic container runner.** Container execution is limited to the three managed backends. No arbitrary command execution inside containers.
- **Not a wallpaper manager.** No wallpaper setting, no desktop environment integration, no image catalog.
- **Not a multi-file merge config system.** Config is a single settings.toml with opt-in overrides — no layered merge (ADR-001).

## 7. MVP Scope

### 7.1 In Scope

- All 9 CLI commands: `generate`, `show`, `install`, `uninstall`, `info`, `dump-config`, `dump-templates`, `list-backends`, `version`
- Three backends: custom, pywal, wallust
- Two runtime modes: local, container
- Two container engines: docker, podman
- 8 output formats: JSON, SH, CSS, GTK_CSS, YAML, SEQUENCES, RASI, SCSS
- 3 output formats for command status: JSON (default), Rich, Plain
- Per-backend parameter overrides via `--param`
- Dry-run mode for `generate`, `show`, `install`, `uninstall`
- Config resolution via config-assembler-engine with 5-strategy chain
- Override rules for all declared settings fields
- **Backend parameter definitions as a YAML catalog file** — `BackendCatalogLoaderPort` + `YamlBackendCatalogLoader` adapter, resolved via config-assembler-engine full pipeline (parallel to WEG `effects.yaml`)
- Investigation of `--stdout` / `--print` flags for pywal and wallust subprocess adapters to avoid cache file path coupling
- Error mapping for all known failure modes
- Unit and integration test suites

### 7.2 Out of Scope for MVP

- Additional backends beyond the three (requires new adapter + Dockerfile + BackendDefinition entry)
- Host-side wallpaper caching (container mode uses ephemeral in-container cache per ADR-008)
- Auto-detection of backends (ADR-010 — explicit only)
- Container image registry push (`install --push` deferred to a separate story)
- Hidden display flags from v2 (`--display-image-path`, `--display-output-dir` — v2 artefacts, ADR-015)

## 8. Success Metrics

**Primary**
- **SM-1: Test coverage.** Domain layer has >=95% line coverage; adapters >=80%. Validates NFR-6.
- **SM-2: CI determinism.** The same `csg generate` command with the same input and config produces byte-identical output in local and container mode. Validates NFR-1.

**Secondary**
- **SM-3: Command parity.** All 9 commands listed in §7.1 are implemented with documented CLI surfaces.
- **SM-4: Error coverage.** Every exception in the ColorSchemeError hierarchy has an end-to-end test that produces the expected JSON error payload.

## 9. Open Questions

1. **Image registry push.** `install --push` deferred to a separate story post-MVP.

