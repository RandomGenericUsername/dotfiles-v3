---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-07-15/prd.md
  - src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md
---

# color-scheme-generator v3 - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for the color-scheme-generator v3 rewrite, decomposing the requirements from the PRD and Architecture plan into implementable stories for a single-package hexagonal architecture CLI tool.

## Requirements Inventory

### Functional Requirements

FR-1: Palette Extraction — User can run `csg generate <image_path>` to extract a 16-color palette from an image using a selected backend.
FR-2: Backend Selection — User can select the extraction backend via `--backend custom|pywal|wallust` or rely on the configured default. Backend is always explicit — no auto-detection.
FR-3: Per-Backend Parameter Overrides — User can pass backend-specific runtime parameters via repeatable `--param key=value` with type coercion and validation against the backend's parameter definitions.
FR-4: Show Command — User can run `csg show <image_path>` to extract and display a palette without writing output files.
FR-5: Dry-Run Mode — User can append `--dry-run` to pre-flight a command, validating inputs, backend availability, and param coercion without executing extraction.
FR-6: Install Backends — User can run `csg install` to build per-backend OCI container images using oci-runtime.
FR-7: Uninstall Backends — User can run `csg uninstall` to remove per-backend OCI container images.
FR-8: Config Resolution — System resolves a single `settings.toml` via config-assembler-engine with priority chain: CLI path > ENV path > directory traversal > XDG > package default.
FR-9: Override Rules — Declared settings fields are overridable via ENV vars or CLI flags with per-field allowed sources.
FR-10: Info Command — User can run `csg info` to display resolved config source path, runtime mode, and backend status.
FR-11: Dump-Config Command — User can run `csg dump-config` to output resolved AppSettings as TOML.
FR-12: Dump-Templates Command — User can run `csg dump-templates` to copy bundled `.j2` templates to the user templates directory.
FR-13: List-Backends Command — User can run `csg list-backends` to see all backends with availability and parameter info.
FR-14: Version Command — User can run `csg version` to display the current version.
FR-15: Template Rendering — System renders ColorSchemes into 8 output formats (JSON, SH, CSS, GTK_CSS, YAML, SEQUENCES, RASI, SCSS) using Jinja2 templates.
FR-16: JSON Output — All commands return structured JSON by default, parseable by CI pipelines.
FR-17: Rich Output — With `--output-format rich`, commands render with terminal formatting.
FR-18: Plain Output — With `--output-format plain`, commands render as minimal plain text.
FR-19: Container-Mode Processing — User can run `generate`/`show` with `--runtime container` to execute inside a pre-built OCI container.
FR-20: Runtime Mode and Container Engine Selection — Runtime mode (`local`/`container`) and container engine (`docker`/`podman`) are orthogonal, independently selectable controls.

### NonFunctional Requirements

NFR-1: Determinism — Equivalent commands under equivalent resolved settings produce equivalent results across Runtime Modes.
NFR-2: Reliability — Errors never produce unstructured output. Every failure returns structured JSON error with type code and message.
NFR-3: Observability — Resolution source paths and effective runtime mode are inspectable via `info` without running extraction.
NFR-4: Runtime/Engine Orthogonality — Runtime mode and container engine selection remain independent controls.
NFR-5: Container Security — Container mount model uses explicit host-to-container binds only, no implicit host-environment leakage.
NFR-6: Testability — Domain logic is testable with zero I/O (pure functions). Adapters are testable with mocked ports via Protocols.

### Additional Requirements

- Hexagonal architecture with pure domain (frozen dataclasses, zero I/O) and side-effecting adapters
- Pydantic lives only at adapter boundary (settings schema + backends catalog schema); domain never imports it
- Single-file config resolution via config-assembler-engine — no multi-file merge (ADR-001)
- Backend parameter definitions as YAML catalog file resolved via config-assembler-engine full pipeline (ADR-011)
- ContainerRuntimePort abstraction — container adapter depends on port, not directly on oci-runtime
- Docker/Podman via oci-runtime v0.4.0 — typed RunConfig, BuildContext, VolumeMount APIs
- Container-mode uses pre-resolved host config handoff with CLI override (not config rewrite) for recursion guard (improved ADR-003)
- Template directory resolved via CompositePathResolver only — no AssembleConfiguration for templates (ADR-004)
- One OCI image per backend, built on shared Dockerfile.base (ADR-005, ADR-014)
- JSON-first output with multi-format OutputPort adapters (ADR-007)
- Ephemeral in-container cache — no host cache mount (ADR-008)
- `--stdout` mode for pywal/wallust subprocess adapters (decided, not deferred)
- Shell completion via Typer's built-in `--install-completion`
- First-run experience: bundled `defaults/settings.toml` + `defaults/backends.yaml` provide out-of-box defaults; `csg generate` works without any setup
- Graceful degradation: if no backend is available, error message suggests `csg install` or installing the binary
- Python >=3.14, hatchling build, uv workspace

### UX Design Requirements

None — CLI tool, no UI.

### FR Coverage Map

FR-1 (Palette Extraction): Epic 1 — Extract Your First Palette
FR-2 (Backend Selection): Epic 2 — Configure & Extend
FR-3 (Per-Backend Parameters): Epic 2 — Configure & Extend
FR-4 (Show Command): Epic 1 — Extract Your First Palette
FR-5 (Dry-Run Mode): Epic 4 — Production Polish
FR-6 (Install Backends): Epic 3 — Container Execution
FR-7 (Uninstall Backends): Epic 3 — Container Execution
FR-8 (Config Resolution): Epic 2 — Configure & Extend
FR-9 (Override Rules): Epic 2 — Configure & Extend
FR-10 (Info Command): Epic 2 — Configure & Extend
FR-11 (Dump-Config Command): Epic 2 — Configure & Extend
FR-12 (Dump-Templates Command): Epic 2 — Configure & Extend
FR-13 (List-Backends Command): Epic 2 — Configure & Extend
FR-14 (Version Command): Epic 1 — Extract Your First Palette
FR-15 (Template Rendering): Epic 2 — Configure & Extend
FR-16 (JSON Output): Epic 1 — Extract Your First Palette
FR-17 (Rich Output): Epic 2 — Configure & Extend
FR-18 (Plain Output): Epic 2 — Configure & Extend
FR-19 (Container-Mode Processing): Epic 3 — Container Execution
FR-20 (Runtime/Engine Selection): Epic 3 — Container Execution

## Epic List

### Epic 1: Extract Your First Palette

**User outcome:** After this epic, user can run `csg generate ~/wallpaper.jpg` and get a color palette in JSON format using the custom backend (PIL + KMeans — no external binary deps). No config file needed — hardcoded defaults work out of the box. `csg show` and `csg version` are also available.

**FRs covered:** FR-1, FR-4, FR-14, FR-16

**Rationale:** This is a vertical slice that delivers user value on day one. Domain models, ports, and adapters are scoped to only what this epic's `generate`/`show` commands need. The hexagonal skeleton is established but minimal — remaining ports/adapters are added in Epic 2.

#### Story 1.1: Domain Foundation (Models + Enums + Exceptions)

As a theming user,
I want a color palette to be extracted from my wallpaper,
So that I can use it to theme my desktop — this story defines the data structures that represent a palette.

**Acceptance Criteria:**

**Given** Color, ColorScheme, GeneratorConfig, GenerationRequest, GenerationResult domain models
**When** instantiated
**Then** they are frozen dataclasses with validation in __post_init__
**And** Color enforces hex pattern `^#[0-9a-fA-F]{6}$` with case-preserving canonicalization
**And** Color.rgb tuple values are clamped to 0-255
**And** ColorScheme holds exactly 16 palette colors plus background, foreground, cursor

**Given** Backend, ColorAlgorithm, ColorFormat, OutputFormat, Verbosity enums
**When** Backend is used
**Then** it has CUSTOM, PYWAL, WALLUST members — no AUTO (ADR-010)
**When** ColorFormat is used
**Then** it has JSON, SH, CSS, GTK_CSS, YAML, SEQUENCES, RASI, SCSS

**Given** ColorSchemeError exception hierarchy
**When** InvalidImageError is raised
**Then** it carries image_path and reason
**When** ColorExtractionError is raised
**Then** it carries backend and message
**When** BackendNotAvailableError is raised
**Then** it carries backend and hint string containing `pip install` suggestion

#### Story 1.2: Core Ports (Minimal)

As a developer,
I want the minimal port interfaces for palette extraction defined,
So that backend adapters and output adapters implement against stable contracts.

**Acceptance Criteria:**

**Given** PaletteGeneratorPort (Protocol)
**When** defined
**Then** it has `generate(image_path: Path, config: GeneratorConfig) -> ColorScheme`
**And** `is_available() -> bool`
**And** it is `@runtime_checkable`

**Given** ColorSchemeProcessorPort (Protocol)
**When** defined
**Then** it has `process_generate(request: GenerationRequest, settings: AppSettings) -> GenerationResult`
**And** `process_show(request: GenerationRequest, settings: AppSettings) -> GenerationResult`
**And** the interface is runtime-agnostic (no local/container assumptions)

**Given** OutputPort (Protocol)
**When** defined
**Then** it has `process_result(result: GenerationResult)` and `error(exc: ColorSchemeError)`
**And** `palette_display(scheme: ColorScheme)`

**Given** all three protocols
**When** verified via `isinstance(obj, Protocol)`
**Then** they pass structural subtype checking

#### Story 1.3: Custom Backend Adapter

As a theming user,
I want to extract a color palette from my wallpaper using PIL + scikit-learn,
So that I get colors without installing any external binary.

**Acceptance Criteria:**

**Given** CustomGenerator implementing PaletteGeneratorPort
**When** generate() is called with a valid image and GeneratorConfig
**Then** it uses PIL to load and resize the image (200x200)
**And** applies scikit-learn KMeans to extract 16 color clusters
**And** applies saturation adjustment via colorsys.rgb_to_hls / hls_to_rgb
**And** returns a ColorScheme with background (darkest), foreground (lightest), and 16 sorted colors
**And** PIL and sklearn are lazily imported inside generate() — not at module or class level

**Given** CustomGenerator with missing optional deps
**When** is_available() is called
**Then** it attempts the import and returns False on ImportError — no side effects
**When** generate() is called while unavailable
**Then** it raises BackendNotAvailableError with hint "pip install color-scheme-generator[custom]"

**Given** an image that PIL cannot decode (corrupt file)
**When** generate() is called
**Then** it raises InvalidImageError, not a bare OSError

**Given** KMeans returns fewer than 16 clusters (e.g. solid-color image)
**When** PaletteNormalizationService pads the result
**Then** it pads with copies of the nearest color, not black

#### Story 1.4: JsonOutput Adapter

As a CI pipeline,
I want extraction results in structured JSON format,
So that I can parse them without terminal formatting.

**Acceptance Criteria:**

**Given** JsonOutput implementing OutputPort
**When** process_result() is called with a successful GenerationResult
**Then** it outputs: `{"success": true, "color_scheme": {...}, "output_files": [...], "backend": "...", "duration": ...}`
**When** error() is called with a ColorSchemeError
**Then** it outputs: `{"success": false, "error": {"type": "InvalidImageError", "message": "..."}}`
**And** error output is always JSON — never terminal-only formatting

#### Story 1.5: LocalProcessor + Generation Service

As a developer,
I want LocalProcessor to orchestrate backend extraction and return structured results,
So that the CLI command layer only handles presentation.

**Acceptance Criteria:**

**Given** LocalProcessor implementing ColorSchemeProcessorPort
**When** process_generate() is called with a GenerationRequest and AppSettings
**Then** it looks up the active backend in BackendRegistry by GeneratorConfig.backend
**And** calls PaletteGeneratorPort.generate()
**And** returns a GenerationResult with success=True, color_scheme, backend, duration
**And** output_files is empty (no template rendering yet — added in Epic 2)

**Given** process_show() is called
**Then** it runs extraction and returns the ColorScheme without writing files

**Given** the active backend's is_available() returns False
**When** process_generate() is called
**Then** it raises BackendNotAvailableError before attempting extraction

#### Story 1.6: CLI Generate Command

As a theming user,
I want to run `csg generate ~/wallpaper.jpg` and get a color palette,
So that I can theme my desktop without manual color picking.

**Acceptance Criteria:**

**Given** the Typer CLI app
**When** `csg generate ~/wallpaper.jpg` is run
**Then** it uses hardcoded defaults (backend=custom, output dir=/tmp/color-scheme, format=none yet)
**And** calls LocalProcessor.process_generate()
**And** renders the result via JsonOutput (default)
**And** returns exit code 0 on success

**Given** an invalid image path
**When** `csg generate /nonexistent.jpg` is run
**Then** it returns a JSON error payload and exit code 1

**Given** `csg generate --help`
**When** run
**Then** it shows usage with <image_path> positional arg

**Out of Scope:** `--backend`, `-o`, `--param`, `-f` flags — these are added in Epic 2.

#### Story 1.7: CLI Show + Version Commands

As a theming user,
I want to preview a palette without writing files and check the tool version,
So that I can decide whether to run the full generate.

**Acceptance Criteria:**

**Given** the CLI show command
**When** `csg show ~/wallpaper.jpg` is run
**Then** it runs extraction via LocalProcessor.process_show()
**And** displays the palette via OutputPort.palette_display()
**And** does not write any output files

**Given** the CLI version command
**When** `csg version` is run
**Then** it outputs the version from importlib.metadata.version("color-scheme-generator")
**And** supports --output-format json (defaults to json)

### Epic 2: Configure & Extend

**User outcome:** User can configure the tool via settings.toml, use all three backends, all 8 output formats, all 3 display formats, and inspect runtime state via info/dump-config/list-backends. Shell completion and first-run experience are polished.

**FRs covered:** FR-2, FR-3, FR-8, FR-9, FR-10, FR-11, FR-12, FR-13, FR-15, FR-17, FR-18

#### Story 2.1: Full Domain & Remaining Ports

As a developer,
I want the full domain model and all port interfaces defined,
So that config resolution, template rendering, and container support have contracts.

**Acceptance Criteria:**

**Given** AppSettings, BackendParameterDefinition, BackendDefinition, OutputSettings, GenerationSettings, TemplateSettings, RuntimeSettings, ContainerSettings domain models
**When** instantiated
**Then** they are frozen dataclasses
**And** AppSettings composes all sub-settings

**Given** ParameterResolutionService
**When** resolve_all() is called with BackendDefinition.parameters and override dict
**Then** it returns override values where present, defaults otherwise
**And** raises ConfigResolutionError if a required param has no default and no override

**Given** HexValidationService, ColorAdjustmentService, PaletteNormalizationService
**When** called with valid input
**Then** they return correct transformed output (pure functions, no I/O)

**Given** remaining port interfaces: ConfigResolverPort, TemplateRendererPort, TemplateDirResolverPort, SettingsSerializerPort, VersionProviderPort, BackendCatalogLoaderPort, ContainerRuntimePort
**When** defined
**Then** each is a @runtime_checkable Protocol with documented method signatures
**And** ContainerRuntimePort abstracts oci-runtime's ContainerEngine interface behind a CSG-specific port

#### Story 2.2: Settings Config Resolution Pipeline

As a maintainer,
I want the tool to find and validate a settings.toml file,
So that I can configure defaults and override them per-invocation.

**Acceptance Criteria:**

**Given** AssembledConfigResolver implementing ConfigResolverPort
**When** resolve() is called
**Then** it uses config-assembler-engine AssembleConfiguration with CoreSettingsSchema (Pydantic)
**And** follows 5-strategy chain: CliPathStrategy > EnvPathStrategy > DirectoryTraversalStrategy > XdgStrategy > DefaultFileStrategy
**And** returns AppSettings (domain dataclass, not Pydantic model)
**And** returns resolved path and applied overrides

**Given** CoreSettingsSchema with @field_validator
**When** runtime.mode is invalid
**Then** Pydantic rejects with accepted values
**When** container.engine is invalid
**Then** Pydantic rejects with accepted values
**When** generation.backend is "auto"
**Then** Pydantic rejects — no AUTO member (ADR-010)

**Given** OverrideRule definitions
**When** COLORSCHEME__RUNTIME__MODE=container is set
**Then** the override is applied and coerced
**When** --backend custom is passed via CLI
**Then** CLI override wins over ENV
**When** COLORSCHEME_CONFIG_FILE_PATH=/path.toml is set
**Then** CLI explicit --config wins over ENV
**And** ENV wins over traversal/XDG/default

**Given** a malformed settings.toml
**When** parsed
**Then** ConfigResolutionError is raised with line number and parse error

#### Story 2.3: Backend YAML Catalog Resolution

As a maintainer,
I want backend parameter definitions loaded from a backends.yaml catalog,
So that I can inspect and edit per-backend parameters without touching code.

**Acceptance Criteria:**

**Given** YamlBackendCatalogLoader implementing BackendCatalogLoaderPort
**When** load() is called
**Then** it resolves backends.yaml via config-assembler-engine with same 5-strategy chain as settings
**And** uses YamlConfigParser + BackendsCatalogSchema (Pydantic)
**And** converts to dict[Backend, BackendDefinition]
**And** no OverrideRules apply — catalog content is file-source only

**Given** defaults/backends.yaml with three backends
**When** loaded
**Then** custom has saturation (float, 0-2, default 1.0), n_clusters (int, 1-32, default 16), algorithm (str, choices=["kmeans"])
**And** pywal has saturation + algorithm (choices=["auto","thief","color","haishoku","colorthief","wal"])
**And** wallust has saturation + algorithm (choices=["kmeans","kmeans-new","kmeans-old","kmeans-improved","fastkmeans","kmeans-euclid","pam","pam-new","pam-old"])

#### Story 2.4: Pywal Backend Adapter

As a theming user,
I want to extract palettes using pywal (wal binary),
So that I get colors matching my pywal-based workflow.

**Acceptance Criteria:**

**Given** PywalGenerator implementing PaletteGeneratorPort
**When** generate() is called
**Then** it shells out to `wal -i <image> -n -s -t -e --backend <algorithm>` via subprocess
**And** reads the palette from stdout (using wal's `--stdout` or equivalent flag — investigated in this story)
**Or** falls back to reading `~/.cache/wal/colors.json` if stdout mode is unavailable
**And** applies saturation adjustment via ColorAdjustmentService
**And** non-zero exit code raises ColorExtractionError with captured stderr
**And** subprocess has a configurable timeout (default 60s) — timeout raises ColorExtractionError

**Given** PywalGenerator.is_available()
**When** `wal` is on PATH
**Then** returns True
**When** `wal` is not on PATH
**Then** returns False (no exception)

#### Story 2.5: Wallust Backend Adapter

As a theming user,
I want to extract palettes using wallust (Rust binary),
So that I get colors matching my wallust-based workflow.

**Acceptance Criteria:**

**Given** WallustGenerator implementing PaletteGeneratorPort
**When** generate() is called
**Then** it shells out to `wallust run <image> --backend <type> -s -T -q` via subprocess
**And** reads the palette from stdout (using wallust's `--stdout` or equivalent — investigated in this story)
**Or** falls back to reading the wallust cache file
**And** applies saturation adjustment
**And** non-zero exit code raises ColorExtractionError with stderr
**And** subprocess has a configurable timeout (default 60s)

**Given** WallustGenerator.is_available()
**When** `wallust` is on PATH
**Then** returns True
**When** `wallust` is not on PATH
**Then** returns False

#### Story 2.6: Template Rendering

As a theming user,
I want color schemes rendered into all my config file formats,
So that my terminal, rofi, GTK, and other tools get themed automatically.

**Acceptance Criteria:**

**Given** JinjaTemplateRenderer implementing TemplateRendererPort
**When** render() is called with template name, ColorScheme, and output path
**Then** it resolves the template from the TemplateDirResolver-resolved directory
**And** uses Jinja2 Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
**And** writes to the specified output path

**Given** 8 bundled templates in defaults/templates/
**When** each format is rendered
**Then** colors.json.j2 produces valid JSON
**And** colors.sh.j2 produces a valid shell script (key=value pairs)
**And** colors.css.j2, colors.gtk.css.j2, colors.yaml.j2, colors.rasi.j2, colors.scss.j2 each produce valid files
**And** colors.sequences.j2 renders with binary post-processing: `]` → `\x1b]`, `\` → `\x1b\\`

**Given** TemplateDirResolver implementing TemplateDirResolverPort
**When** resolve() is called
**Then** it uses CompositePathResolver with: env var > XDG > package defaults
**And** returns a directory Path

**Given** a missing template name
**When** render() is called
**Then** TemplateNotFoundError is raised with searched paths

#### Story 2.7: Rich + Plain Output Adapters

As a theming user,
I want terminal-formatted and pipe-friendly output,
So that I can read results in a terminal or pipe them to other tools.

**Acceptance Criteria:**

**Given** RichOutput implementing OutputPort
**When** process_result() is called with a successful GenerationResult
**Then** it renders with Rich formatting (colors, tables)
**When** error() is called
**Then** it renders a Rich-formatted error message

**Given** PlainOutput implementing OutputPort
**When** process_result() is called
**Then** it renders plain text with no formatting or color codes

**Given** the --output-format flag
**When** --output-format json is passed
**Then** JsonOutput is selected
**When** --output-format rich is passed
**Then** RichOutput is selected
**When** --output-format plain is passed
**Then** PlainOutput is selected
**When** no flag is passed
**Then** JSON is the default

#### Story 2.8: Operational Commands (Info, Dump-Config, Dump-Templates, List-Backends)

As a maintainer debugging a CI failure,
I want to inspect the resolved config, backends, and templates,
So that I can trace why extraction produced unexpected results.

**Acceptance Criteria:**

**Given** the info command
**When** `csg info` is run
**Then** it displays resolved settings.toml path and its source (CLI/ENV/XDG/DEFAULT)
**And** all applied overrides with source and coerced value
**And** effective runtime mode and container engine
**And** resolved templates directory
**And** backend availability for all three backends

**Given** the dump-config command
**When** `csg dump-config` is run
**Then** it outputs full resolved AppSettings as TOML to stdout
**When** `--output /path/file.toml --overwrite` is passed
**Then** it writes to file (overwriting if exists)

**Given** the dump-templates command
**When** `csg dump-templates` is run
**Then** it copies all 8 bundled .j2 templates to XDG templates dir (mkdir parents)
**And** --overwrite replaces existing files; without it, skips existing files
**And** if a target file is read-only, raises OutputWriteError
**When** `--output /custom/path` is passed
**Then** it copies to the custom path

**Given** the list-backends command
**When** `csg list-backends` is run
**Then** it shows each backend's name, description, host availability, image presence (container mode), and supported parameters with type/default/range

**Given** all four commands
**When** run
**Then** they support --output-format json|rich|plain

#### Story 2.9: Full Generate/Show with Config, Backends, Formats

As a theming user,
I want `csg generate` to use my settings.toml, selected backend, and output formats,
So that the tool respects my configuration.

**Acceptance Criteria:**

**Given** the config resolution pipeline (2.2)
**When** `csg generate ~/wallpaper.jpg` is run
**Then** it resolves settings.toml via AssembledConfigResolver
**And** uses settings.generation.backend as the default backend
**And** uses settings.generation.default_formats for output formats
**And** writes rendered template files to settings.output.directory

**Given** the --backend flag
**When** `csg generate --backend pywal` is run
**Then** it overrides the configured default
**When** `csg generate --backend invalid` is run
**Then** it raises a validation error with accepted values

**Given** the --param flag
**When** `csg generate --param saturation=1.5 --param algorithm=thief` is run
**Then** it parses params via _parse_params, coerces via PydanticTypeCoercer, resolves via ParameterResolutionService, and passes to GeneratorConfig.params
**When** `--param bogus=1` is passed for a backend without that param
**Then** it raises ConfigResolutionError

**Given** the -f / --format flag
**When** `csg generate -f json -f css` is run
**Then** only those formats are rendered

**Given** the -o / --output-dir flag
**When** `csg generate -o ~/my-theme` is run
**Then** output files are written to ~/my-theme

**Given** all backends are unavailable in local mode
**When** `csg generate` is run
**Then** it raises BackendNotAvailableError with a message suggesting `csg install` or installing the binary

#### Story 2.10: Shell Completion & First-Run Experience

As a theming user,
I want shell completion installed and the tool to work out of the box,
So that I don't need to read documentation to get started.

**Acceptance Criteria:**

**Given** Typer's built-in completion support
**When** `csg --install-completion` is run
**Then** shell completion is installed for the current shell (bash/zsh/fish)
**And** completion covers all commands, flags, and backend values

**Given** a fresh install with no settings.toml
**When** `csg generate ~/wallpaper.jpg` is run for the first time
**Then** it falls back to package-bundled defaults/settings.toml
**And** extraction succeeds without any user configuration

**Given** no backends are available on the host
**When** `csg list-backends` is run
**Then** it shows all three with is_available=False
**And** the output suggests `csg install` for container-mode execution

### Epic 3: Container Execution

**User outcome:** User can extract palettes without installing backends locally. `csg install` builds per-backend images, `csg uninstall` removes them, and `--runtime container` runs extraction inside a container. Error mapping from oci-runtime exceptions is clean.

**FRs covered:** FR-6, FR-7, FR-19, FR-20
**NFRs covered:** NFR-1, NFR-4, NFR-5

#### Story 3.1: Runtime Mode Wiring & Composition Root

As a developer,
I want the composition root wired with runtime mode selection,
So that --runtime and --container-engine flags work orthogonally.

**Acceptance Criteria:**

**Given** factory.py composition root
**When** the Typer app starts
**Then** CliDependencies are built in @app.callback() with all ports and adapters
**And** stashed on ctx.obj["deps"]
**And** create_* helpers exist for: config_resolver, template_renderer, backend_registry, container_engine, output_adapter, backend_catalog_loader, version_provider

**Given** runtime mode selection
**When** --runtime local is passed
**Then** LocalProcessor is selected
**When** --runtime container is passed
**Then** ContainerProcessor is selected
**When** --container-engine docker is passed
**Then** oci-runtime uses DockerRuntimeProvider
**When** --container-engine podman is passed
**Then** oci-runtime uses PodmanRuntimeProvider

**Given** the ContainerRuntimePort
**When** container mode is selected
**Then** ContainerProcessor depends on ContainerRuntimePort, not directly on oci-runtime
**And** the port is resolved via RuntimeFactory.create() in the composition root

**Given** the pyproject.toml console_scripts entry point
**When** the package is installed
**Then** `csg` points to `color_scheme_generator.cli.main:app`
**And** optional-dependencies exist for [custom] (pillow, numpy, scikit-learn) and [pywal]

#### Story 3.2: Container Processor

As a theming user,
I want to extract palettes in container mode when backends aren't installed locally,
So that I don't need to install wal/wallust/sklearn on my host.

**Acceptance Criteria:**

**Given** ContainerProcessor implementing ColorSchemeProcessorPort via ContainerRuntimePort
**When** process_generate() is called with RuntimeMode.CONTAINER
**Then** it pre-flights: resolves config, templates, and backend params
**And** selects image `[registry/]color-scheme-<backend>:<tag>`
**And** verifies engine is available via ContainerRuntimePort (raises ContainerRuntimeUnavailableError)
**And** verifies image exists (raises ContainerImageNotFoundError)
**And** serializes AppSettings as-resolved (no rewrite) to a temp TOML
**And** builds RunConfig with 4 BIND mounts: input parent → /input (RO), output → /output (RW), temp TOML → /csg-config/settings.toml (RO), templates → /templates (RO)
**And** inner command receives --runtime local (prevents recursion via CLI override priority)
**And** --param pairs are forwarded verbatim
**And** temp TOML is cleaned up in finally — even when engine.containers.run() raises

**Given** input file's parent dir is `/` (filesystem root)
**When** mount paths are resolved
**Then** it raises InvalidImageError — mounting `/` is rejected

**Given** a container-mode process_show()
**When** called
**Then** it runs extraction inside the container but does not mount an output directory
**And** returns the ColorScheme for host-side display

**Given** the temp TOML file
**When** written on host
**Then** it is world-readable (non-root container user can read it)
**And** contains the AppSettings as-resolved (runtime.mode is honest — CLI --runtime local overrides it)

**Given** an OCI runtime that times out
**When** execution exceeds the configured timeout
**Then** OperationTimeoutError maps to ContainerTimeoutError via error mapping

#### Story 3.3: Install/Uninstall Commands

As a theming user,
I want to build and remove per-backend container images,
So that I can use container-mode execution.

**Acceptance Criteria:**

**Given** the install command
**When** `csg install` is run
**Then** it builds all three backend images via engine.images.build()
**And** uses per-backend Dockerfiles from adapters/docker/ based on Dockerfile.base (python:3.14-slim)
**When** `csg install --backend custom` is run
**Then** only custom image is built
**And** image is named [registry/]color-scheme-custom:<tag>
**And** supports --engine docker|podman and --dry-run

**Given** Dockerfile discovery via importlib.resources
**When** running in editable dev install
**Then** Dockerfiles are found correctly (tested for both editable and installed modes)

**Given** the uninstall command
**When** `csg uninstall` is run
**Then** it removes all backend images (with confirmation prompt)
**When** `csg uninstall --backend wallust --yes` is run
**Then** removes only wallust image without prompting

**Given** image lifecycle errors
**When** engine.images.build() fails
**Then** error maps to a domain exception with diagnostic message
**When** engine.images.remove() fails
**Then** error maps similarly

#### Story 3.4: Error Mapping (oci-runtime → Domain)

As a developer,
I want OCI runtime exceptions mapped to domain exceptions,
So that container errors produce structured, typed error output.

**Acceptance Criteria:**

**Given** error_mapping.py
**When** oci-runtime raises ImageNotFoundError
**Then** it maps to ContainerImageNotFoundError(image, backend)
**When** oci-runtime raises RuntimeNotAvailableError
**Then** it maps to ContainerRuntimeUnavailableError(runtime)
**When** oci-runtime raises ImagePullAccessDeniedError
**Then** it maps to ImagePullAccessError(image, registry)
**When** oci-runtime raises OperationTimeoutError
**Then** it maps to ContainerTimeoutError
**When** any other oci-runtime exception (base OciError) is raised
**Then** it maps to a generic ColorSchemeError with the original message preserved
**When** the mapped domain exception is serialized by OutputPort.error()
**Then** it produces a valid JSON error payload with type code and message

### Epic 4: Production Polish

**User outcome:** Pre-flight validation via dry-run, hardened edge cases, robust error handling everywhere.

**FRs covered:** FR-5
**NFRs covered:** NFR-2

#### Story 4.1: Dry-Run Processor

As a maintainer debugging a CI failure,
I want to pre-flight a command without executing it,
So that I can validate inputs, backends, and params before running.

**Acceptance Criteria:**

**Given** DryRunProcessor implementing ColorSchemeProcessorPort
**When** process_generate() is called with --dry-run
**Then** it validates: input exists and is readable, backend available (local) or engine+image available (container), output dir writable, templates dir resolvable, all --param overrides coerce cleanly against BACKEND_DEFINITIONS[backend].parameters
**And** renders the resolved command via OutputPort without executing

**Given** dry-run in container mode with no host backend
**When** the backend is not installed on the host
**Then** it does NOT check host-side is_available — only validates engine availability + image existence
**And** does NOT attempt to pull the image — only checks existence

**Given** dry-run with invalid --param values
**When** validation fails
**Then** it raises the first validation error with a clear message

#### Story 4.2: Edge Case Hardening

As a maintainer,
I want edge cases handled gracefully across all adapters,
So that the tool is robust in production use.

**Acceptance Criteria:**

**Given** subprocess-based backends (Pywal, Wallust)
**When** the subprocess hangs
**Then** a configurable timeout (default 60s) kills the process and raises ColorExtractionError
**When** the subprocess exits non-zero
**Then** stderr is captured and included in ColorExtractionError
**When** the cache file (fallback path) is partially written
**Then** the adapter retries once after a short delay before raising ColorExtractionError

**Given** container mode
**When** input file is on a filesystem root (parent dir is `/`)
**Then** InvalidImageError is raised — mounting `/` is rejected
**When** chmod of output dir fails
**Then** a warning is logged but execution continues (best-effort)

**Given** the sequences format
**When** rendered
**Then** `]` is post-processed to `\x1b]` and `\` to `\x1b\\`
**And** the output is bytes (not string), written as binary

**Given** config resolution runs both settings and backends pipelines
**When** both run during the same invocation
**Then** they use separate AssembleConfiguration instances (no cross-contamination)

**Given** all three backends are unavailable on the host
**When** `csg generate` is run in local mode
**Then** BackendNotAvailableError is raised with message listing which backends were tried and suggesting `csg install` for container mode

#### Story 4.3: Port Contract Tests

As a developer,
I want contract tests for every port,
So that adapter swaps are safe and verified.

**Acceptance Criteria:**

**Given** a PaletteGeneratorContract test suite
**When** a new backend adapter is implemented
**Then** running the contract suite verifies it satisfies PaletteGeneratorPort

**Given** contract test suites for all ports
**When** run against production adapters
**Then** they verify structural subtyping via isinstance() and method signature compatibility
