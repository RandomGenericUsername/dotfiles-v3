# Deferred Work

## Deferred from: code review of gt-2-1-palette-artifact-set-growth (2026-09-07)

- Evict-and-regenerate migration is convergent but not lock-safe under concurrent populate — two processes racing on the same incomplete `<ph>` can interleave so that one rmtree deletes the other's just-renamed complete entry (content identical, deterministic — end state converges), or the rmtree/rename interleaving raises a spurious OSError (fails loudly; the completeness guard self-heals on the next run). No cross-process lock exists anywhere in the cache layer (pre-existing design; `populate_via_staging` is the only race surface it defends). Fixing requires a lockfile or pid-aware eviction — cache-hygiene hardening beyond story scope. [src/runtime/src/runtime/application/derive.py:256-299, src/runtime/src/runtime/adapters/cache.py:176-197]
- POSITIVE side effect worth recording: the shared completeness guard RESOLVES the palette half of the rt-1-13 deferred item ("corrupt/missing meta.json bricks that layer permanently") — corrupt/absent meta.json now evicts + regenerates the palette entry instead of failing every subsequent run. Effects/icons layers remain un-self-healed. [src/runtime/src/runtime/application/derive.py:256-299, deferred-work.md "rt-1-13-applywallpaperusecase"]

## Deferred from: code review of gt-1-1-colorformat-adw-css-template (2026-09-07)

- AC-4 container-mode real exec (`csg generate <img> -f adw.css` with `runtime.mode=container`) never ran: environment had only the stale `csg-custom-latest` image, which errors because it bakes old code; templates bind-mount at `/templates` so no rebuild is needed for the template itself — manual verification owed to gt-4-1/G1.1 [src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/container_processor.py:216-217]

## Deferred from: code review of rt-3-4-inspect-cache-list-command (2026-09-03)

- TOCTOU symlink race on `cache/` root (is_symlink → is_dir → scandir non-atomic); attacker swapping cache for symlink between checks bypasses ValueError — local-diagnostic hardening beyond spec, not reachable in normal use [src/runtime/src/runtime/application/inspect.py:551-556]
- Single-entry OSError aborts entire listing; layer open catches only FileNotFoundError (NotADirectoryError/PermissionError propagate as exit 1) — spec says genuine OSError propagates to ErrorView, skip-and-continue would go beyond AC 5 [src/runtime/src/runtime/application/inspect.py:592-618]
- Frozen `InspectCacheResult` exposes mutable `dict` fields (layers/counts); callers could mutate despite frozen — internal-only construction, use Mapping/MappingProxy if ever exposed [src/runtime/src/runtime/application/inspect.py:495-507]

## Deferred from: code review of rt-2-6-terminal-palette-applier (2026-09-02)

- No test renders the real pinned `colors.yaml.j2` — the runtime `TerminalColorApplier` parser's coupling to csg's template output (3 scalars + 16-item list + 3 trailing scalars, no blank lines between items thanks to `trim_blocks=True`) is guarded only by hand-written fixtures in both test layers. If csg's Jinja environment ever changes, every real cache artifact becomes unparseable and every reconcile surfaces `TerminalColorApplier` as failed (fail-loud, but with no structural guard). A template-render parity test crosses the runtime/csg package boundary — decide whether it belongs in runtime tests, a shared test util, or csg's own suite [src/runtime/tests/unit/test_terminal_color_applier.py:26-38, src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/colors.yaml.j2]

## Deferred from: code review of 2-11-settings-role (2026-08-12)

- No fail-loud fact-gathering guard for `ansible_facts.env` — config_copies leads with an `ansible_facts.env.HOME is defined` assert; settings asserts only `install_dir`. A future 2.12 aggregator (bootstrap.yaml) that forgets `gather_facts: true` dies with an opaque undefined-var error; the settings playbook always sets `gather_facts: true`, so not reachable today — flag at 2.12 build time [src/provisioning/ansible/roles/settings/tasks/main.yml:35-41]
- `csg info --config` gate is vacuous — csg's `info` swallows ConfigResolutionError and exits 0 even on a parse-broken file; the WEG half can actually fail. Authoritative AC 8 gate owned by 2.12 (verify) + 3.3 (settings-parity) [src/provisioning/tests/unit/test_settings_role.py:562-614, src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/info_cmd.py:43-44]
- No schema-parity coverage tying rendered files to the tool schemas — literal string asserts can't catch a new required schema field; 3.3 settings-parity invokes the CLIs as the schema gate [src/provisioning/tests/unit/test_settings_role.py:362-430]
- `HOME=""` (XDG unset) resolves to `/.config` at the filesystem root — inner `default()` lacks `boolean=true`, empty HOME passes through; identical derivation shared verbatim with filesystem/compositor_configs/config_copies, so the fix must land chain-wide [src/provisioning/ansible/roles/settings/vars/main.yml:38]

## Deferred from: code review of 2-6-assets-role (2026-08-10)

- `assets_weg_bin_dir` re-derives `~/.local/bin` instead of consuming `cli_tools_bin_dir`; both roles diverge from uv's real bin dir when UV_TOOL_BIN_DIR/XDG_BIN_HOME are set — cross-role shared-var design, not this story [src/provisioning/ansible/roles/assets/vars/main.yml:25]

## Deferred from: code review of story 2-4-cli-tools-role (2026-08-10)

- `command -v yay` in the sibling packages role has the same shell-builtin defect (Story 2.3's `failed_when: false` swallows the exec error) — real but caused by Story 2.3, not this change; fix together with F1 when the packages role is next touched [src/provisioning/ansible/roles/packages/tasks/main.yml:59]

## Deferred from: code review of 1-3-custom-backend-adapter (2026-07-15)

- pyproject.toml test deps — pre-existing, not in scope for this story's ACs
- CustomGenerator not re-exported from adapters/__init__.py — not required by spec
- Timezone-naive datetime.now() — can be addressed when multi-zone support needed

## Deferred from: code review of 1-3-custom-backend-adapter (2026-07-16)

- Timezone-naive datetime.now() [custom_generator.py:82] — pre-existing, re-deferred
- Empty colors list fallback to black [domain/services.py:33] — pre-existing domain code, out of scope for this story
- n_clusters upper bound [custom_generator.py:47] — performance concern (cap at 40000 for 200x200 images), not a correctness issue

## Deferred from: code review of 1-5-local-processor-generation-service (2026-07-16)

- success=True hardcoded without post-generation validation [local_processor.py:47,70] — matches current spec
- generator.generate() exceptions propagate raw across port boundary [local_processor.py:43,66] — design choice
- request.image_path not validated before use [local_processor.py:43,66] — out of scope for this story
- settings parameter silently ignored [local_processor.py:34,57] — AppSettings is a known placeholder

## Deferred from: code review of 1-6-cli-generate-command (2026-07-16)

- Backend generators eagerly instantiated [factory.py:28-30] — low overhead (stubs + no custom __init__)
- Hardcoded /tmp/color-scheme output dir [main.py:36] — out of scope (Epic 2 adds -o/--output-dir)
- `.` in pythonpath is a fixture hazard [pyproject.toml:25] — pre-existing, not specific to this change
- Only ColorSchemeError caught [main.py:47] — by design per spec ("let unexpected errors propagate")
- Callback has no error handling for factory failures [main.py:22-26] — low risk, systemic config issues handled at app level
- CliDependencies.processor field declared but never set [factory.py:23] — forward-looking, will be used in Epic 2/3

## Deferred from: code review of 1-7-cli-show-version-commands (2026-07-16)

- Hardcoded `/tmp/color-scheme` output directory — pre-existing pattern from story 1.6, output customization is Epic 2 scope
- Empty `formats=()` produces no output files — pre-existing from story 1.6; `show` by design doesn't write files
- Hardcoded `Backend.CUSTOM` with empty `params` — backend selection is Epic 2 scope
- Duplicate `GeneratorConfig` construction across `generate` and `show` — pre-existing pattern from story 1.6
- Silent success in `generate` command (no console feedback) — by-design for JSON output mode, pre-existing
- `build_deps()` exception propagates uncaught through callback — pre-existing pattern from story 1.6
- `image_path` not validated for type (accepts directories, special files) — file validation is processor responsibility

## Deferred from: code review of story 2-1-full-domain-and-remaining-ports (2026-07-16)

- `resolve_all` silently ignores unknown override keys — caller typos produce no warning
- `resolve_all` never enforces `choices` constraint — override values not validated against BackendParameterDefinition.choices
- ContainerSettings fields lack validation — `timeout_seconds` can be negative, `memory_limit` is unvalidated
- BackendParameterDefinition.choices and default are type-incompatible — no static check
- `resolve_all` ignores GenerationSettings.default_params — pipeline not yet built (story 2.2 scope)
- ConfigResolverPort has no failure contract — undocumented exceptions
- TemplateRendererPort has no error contract — undocumented exceptions
- TemplateDirResolverPort returns Path even when both dirs can be None — no fallback contract
- SettingsSerializerPort has no error contract — undocumented exceptions
- BackendCatalogLoaderPort contract allows empty dict — no minimum-registration guarantee

## Deferred from: code review of 2-2-settings-config-resolution-pipeline (2026-07-16)

- `explicit_path` to missing file not wrapped — depends on config-assembler-engine contract
- `resolved_path` and `applied_overrides` could be `None` — depends on config-assembler-engine contract

## Deferred from: code review of 2-3-backend-yaml-catalog-resolution (2026-07-16)

- Cross-field validation on BackendParameterSchema — no validators for `min <= max`, `default` type matching `param_type`, or `default` in `choices`. Pre-existing pattern from settings resolver.
- Empty `choices` list accepted — `choices: []` passes all validators but is semantically void.
- Duplicate param keys silently accepted — two parameters with same key in one backend both added.
- AssemblyResult metadata discarded — `resolved_path` and `applied_overrides` not exposed by `load()`. Port signature limits this.
- `min_version="0.0.0"` hardcoded — no source of truth in YAML for this domain field.
- Integration test doesn't test actual bundled file — test writes own YAML to `tmp_path`, never loads real `defaults/backends.yaml`.

## Deferred from: code review of 2-4-pywal-backend-adapter (2026-07-16)

- Hardcoded cache path ignores XDG_CACHE_HOME [pywal_generator.py:19] — spec says `~/.cache/wal/colors.json`, pre-existing design choice
- Stdout parsing only accepts 6-digit hex [pywal_generator.py:95] — wal outputs 6-digit format, not a practical concern
- Cache parsing doesn't handle 8-digit ARGB [pywal_generator.py:110-112] — wal uses `#RRGGBB`, not triggered
- No test validates bg/fg/cursor selection semantics — test gap, not a production bug
- No isolated tests for parse methods — tested indirectly through `generate()`, adequate coverage

## Deferred from: code review of 2-5-wallust-backend-adapter (2026-07-16)

- Naive sort key `sum(c.rgb)` for luminance [wallust_generator.py:84] — matches codebase-wide `PaletteNormalizationService.sort_by_brightness()`; pre-existing project pattern, not specific to this change

## Deferred from: code review of 2-10-shell-completion-and-first-run (2026-07-19)

- Fragile test accesses private internals [test_first_run.py:59,136] — tests access `_assembler._path_resolver._strategies[-1]._path`; pre-existing, internal refactoring will break tests

## Deferred from: code review of 3-1-runtime-mode-wiring-and-composition-root (2026-07-22)

- Missing `pywal` optional dependency in `pyproject.toml` [pyproject.toml:18-19] — pre-existing, not caused by this change
- `create_container_processor` doesn't forward `template_dir_resolver` [factory.py:99-105] — will be needed in story 3.2 when ContainerProcessor is fully implemented
- `duration` hardcoded to 0.0 in `OciContainerRuntimeAdapter` [oci_container_runtime.py:54] — adapter not yet in production use
- Empty command/image/mounts edge cases in `OciContainerRuntimeAdapter` [oci_container_runtime.py:15-55] — adapter not yet in production use

## Deferred from: code review of 3-2-container-processor (2026-07-22)

- `return_code=-1` for timeouts is non-standard [container_processor.py:227,338] — POSIX exit codes are 0-255; `-1` conflicts with conventions. Would require documenting/changing `GenerationResult.return_code` contract.
- Code duplication between `process_generate` and `process_show` [container_processor.py:112-232,234-343] — ~90% body shared. Maintenance concern, not a bug.

## Deferred from: code review of story 3-3-install-uninstall-commands (2026-07-22)

- Partial failure orphans images [install_cmd.py, uninstall_cmd.py] — no rollback for partially built/removed images; inherent to sequential CLI pattern
- Unknown output adapter silent [install_cmd.py:74-91, uninstall_cmd.py:67-84] — future adapter types silently discard results
- Non-ImageError engine exceptions unhandled [oci_container_runtime.py:74-76, 87-89] — requires oci-runtime exception knowledge
- No .dockerignore [Dockerfiles] — builds include unnecessary context
- No --image-tag CLI flag [install_cmd.py, uninstall_cmd.py] — feature request, tag always from config
- No CLI integration tests — tests use unit mocking pattern
- build_image return value discarded [install_cmd.py:67] — image SHA not captured/displayed

## Deferred from: code review of 3-4-error-mapping-oci-runtime-to-domain (2026-07-22)

- Missing coverage for exec_container failure path [test_image_lifecycle.py] — Tests only mock `containers.run` to fail, never `exec_container`. Half the wrapped code path is untested.

## Deferred from: code review of 4-1-dry-run-processor (2026-07-22)

- `_validate_params` reloads backend catalog on every invocation [dry_run_processor.py:94] — catalog should handle caching, not the processor

## Deferred from: code review of story 4-2-edge-case-hardening (2026-07-22)

- `None` timeout raises TypeError instead of ValueError [oci_container_runtime.py:25] — pre-existing; type is `int` (not `Optional[int]`), typing should catch at dev time

## Deferred from: code review of story 4-3-port-contract-tests (2026-07-22)

- `inspect.isfunction` skips `@classmethod`/`@staticmethod` on ports [conftest.py:73-74,122-123] — all methods currently use regular functions
- AC 8 uses test stub instead of production VersionProvider adapter — no production adapter exists yet

## Deferred from: code review of story 1-2-domain-models-and-enums (2026-08-04)

- `ProvisionResult.tasks` is an anonymous `tuple[str, str]` with no status enum [models.py:44] — real shape arrives with adapters (Story 1.5)
- `ProvisionManifest.kind` is a free-form `str` overlapping `AssetKind` semantics [models.py:35] — **RESOLVED in Story 2.1**: typed as `ManifestKind` enum
- `AssetKind` values may not match future install-spine path segments (`icon-mapping` vs `icon-mappings`) [enums.py:34-38] — **RESOLVED in Story 2.1**: `AssetKind.spine_segment()` added as single source of truth

## Deferred from: code review of story 1-1-scaffold-the-provisioning-package (2026-08-03)

- Version hard-fails from bare checkout — `importlib.metadata` raises PackageNotFoundError when dist metadata absent, exiting 1 even though `__version__` exists in `__init__.py`. Matches CSG `version_cmd.py` convention; success test depends on install state.
- Duplicate version source — `__version__` in `__init__.py:6` is dead code vs `importlib.metadata.version()` used by the CLI; two `0.1.0` literals can drift. Standard library-package convention.
- `--help` advertises not-yet-existing plan/apply/verify/bootstrap commands — forward-looking; resolved when the commands land in Story 1.8.

## Deferred from: code review of 1-5-adapters (2026-08-05)

- YAML alias-expansion (billion-laughs) exhaustion via `safe_load` [yaml_manifest_reader.py:22-29] — manifests are the user's own dotfiles; hardening item, not in story scope

## Deferred from: code review of story 1-6-provision-use-case (2026-08-05)

- Resolved spine path is opaque to callers: plan mode can't surface `install_dir` and apply re-resolves it from env — plan/apply can diverge. Story 1.8 CLI scope [use_cases.py:49-56]

## Deferred from: code review of story 1-7-verify-and-bootstrap-use-cases (2026-08-05)

- Overloaded `check` flag — `verify()` hardcodes `False` for "real assertions" while the port uses it for plan/apply; a named semantic or second port method would clarify [use_cases.py:87]
- Undifferentiated `ProvisionResult` — verify-gate failure vs bootstrap failure indistinguishable at type level; Story 1.8 CLI infers meaning from which playbook ran [use_cases.py:86-108]
- ~90% identical constructor/run bodies across three use cases; a private base/mixin would collapse duplication — design debt, not a bug [use_cases.py:52-108]
- `os_family()` not validated against `Distro` before passing as extra-var — pre-existing port contract (IFactReader returns "arch"|"debian-family"); invalid values would select nonexistent group_vars silently [use_cases.py:38]

## Deferred from: code review of story 1-8-typer-cli (2026-08-08)

- `version` builds the full dependency graph on every invocation — callback unconditionally calls `build_deps()`; if it ever raises, `version` breaks. Matches deferred CSG pattern (deferred-work.md#38) [cli/main.py:96]
- No timeout set in production composition root — `AnsibleExecutor` constructed without `timeout`, so a hung `ansible-playbook` blocks the CLI forever and the handled `ProvisionTimeoutError` path can never fire. Choosing a default timeout is a product decision, not in story scope [cli/main.py:74]
- Success output drops Ansible stderr — exit-0 warnings are discarded from the JSON success payload, unlike the error path which preserves `details.stderr`; success payload shape is locked in the 1.8 dev notes [cli/main.py:124-135]
- `dict(result.tasks)` collapses duplicate task labels — `ProvisionResult.tasks` is `tuple[tuple[str, str], ...]` with no uniqueness guarantee in the domain contract; safe today only because `_parse_tasks` dedupes (adapter impl detail) [cli/main.py:132]
- `--output-format` non-default branches untested — only the JSON default path is exercised; `plain`/`rich` renderings and `case_sensitive=False` variants of the callback option have no CLI-level test [cli/options.py:13]

## Deferred from: code review of 2-1-declarative-manifests (2026-08-08)

- `spine_segment()` "single source of truth" unenforced — no check that entry `name` == `spine_segment()`; `weg-effects` name diverges (file target). Ansible (Stories 2.3-2.12) should key off `kind`+`spine_segment()`, not `name` [enums.py:87-104]
- filesystem.yaml flat `name` list can't express base (XDG vs install-spine) or node type (file vs dir) — story-ratified minimal schema; revisit at Story 2.5 (filesystem role) [filesystem.yaml:4-16]
- Domain view drops `target`/`source`/asset `kind` — explicit story decision ("avoid over-modeling"; Ansible is consumer); revisit when plan/verify wires manifest consumption [models.py:15-21]
- "≤200-char error payloads" claim unenforced — unknown-kind message embeds full path + supported kinds and can exceed [yaml_manifest_reader.py:101-112]
- Whitespace-only `version` not coerced to `None` (only `""` → None) [yaml_manifest_reader.py:150]
- Entry-level `kind` key collides with top-level manifest `kind` for assets (misleading "unknown AssetKind" on authoring slip) [yaml_manifest_reader.py:153-168]
- `ProvisionManifest.kind: ManifestKind` is annotation-only, unvalidated at runtime [models.py:35]

## Deferred from: code review of 2-3-packages-role (2026-08-09)

- Debian-family `hyprland`/`hyprpaper`/`waybar` don't resolve in default apt repos — AC3 "packages present" unreachable on stock Debian/Ubuntu via the plain `ansible.builtin.package` path; PPA/repo enablement is the spec's acknowledged open question, deferred to integration stories 3.2/3.3 [group_vars/debian-family.yml:11-16]
- Pre-existing `aur_builder` user with non-login shell or missing `wheel` group breaks makepkg — the `ansible.builtin.user` task never sets `shell`, and forcing `packages_use_aur=true` on a non-Arch host errors "group wheel does not exist"; deployment path is fresh-machine bootstrap where the user does not pre-exist [tasks/main.yml:39-45]
- `creates: /usr/bin/yay` means the role never upgrades yay; stale/broken binary not rebound — accepted as by-design (yay is a bootstrap that self-updates; kewlfft.aur fails loudly on a broken binary, NFR-9) [tasks/main.yml:72-79]

## Deferred from: code review of 2-2-ansible-scaffold (2026-08-09)

- `config_file` silently ignored when a runner is injected (env never built on that path) — no production caller combines `runner=...` + `config_file=...`; latent footgun [ansible_executor.py:128-133]
- Env passthrough widens `_parse_tasks` stdout-callback breakage surface (`ANSIBLE_STDOUT_CALLBACK=json` → empty tasks, misleading `success=True`) — pre-existing env inheritance; consider pinning `default` callback separately [ansible_executor.py:52-55]
- `debian-family` `hyprland`/`hyprpaper`/`waybar` names don't resolve on default apt — Story 2.3 explicitly handles PPA/repo enablement; group_vars carries logical names by design [group_vars/debian-family.yml:13-16]
- `ansible-core` un-pinned vs collection `requires_ansible` compat — ansible-core pinning out of scope (declared Story 1.1) [requirements.yml:6-15]
- `ansible_playbook_python` magic var undefined outside playbook context — latent risk if `AnsibleFactReader` ever wired to load this inventory; no current call site loads it for `ansible -m setup` [inventory/localhost.yaml:17]
- `_ansible_env` doesn't `.resolve()` or reject empty `Path` (relative/`Path("")` → broken `ANSIBLE_CONFIG`) — only caller passes an absolute resolved path; latent hardening [ansible_executor.py:52-55]
- `packages` map value-shape contract (scalar vs list per key) deferred to Story 2.3 (packages role) — `hyprland` scalar / `fonts` list currently undocumented [group_vars/arch.yml:8-15]
- Font-set parity across distros (arch 4 fonts incl. nerd font vs debian 3, no nerd equivalent) deferred to Story 2.3 (packages role) [group_vars/arch.yml vs debian-family.yml]

## Deferred from: code review of story 2-7-default-palette-role (2026-08-12)

- `default_palette_bin_dir` hardcodes `{{ ansible_facts.env.HOME }}/.local/bin`, ignoring uv's `$UV_TOOL_BIN_DIR → $XDG_BIN_HOME → $HOME/.local/bin` chain — a user with either env var set gets `csg` installed elsewhere and the guard/generate false-fail. Extends the 2.6-deferred cross-role shared-var item (`assets_weg_bin_dir`); the fix must land chain-wide (2.4+ so `cli_tools_bin_dir`'s `creates:` and this role's PATH prepend agree) [src/provisioning/ansible/roles/default_palette/vars/main.yml:37-43]
- `ansible_facts.env` (HOME/PATH) unguarded when the role is consumed outside its one-per-role playbook — only a header comment declares the `gather_facts: true` requirement; Story 2.12's aggregate `bootstrap.yaml` must set `gather_facts: true` or every env reference raises a raw undefined-var error. Flag at 2.12 build time [src/provisioning/ansible/roles/default_palette/vars/main.yml:43, tasks/main.yml:72,104]
- No root/user-scope guard; a root invocation silently writes the spine + palette under `/root/...` — `ansible_facts.env.HOME` follows the running user; matches the no-become discipline of 2.3-2.6, so a chain-wide user-scope assertion is the right fix [src/provisioning/ansible/playbooks/default-palette.yaml:10-12]
- Non-string `install_dir` bypasses the friendly seam assert — `-e install_dir=12345` passes `is defined`, then `| trim` raises a raw Jinja TypeError instead of the intended `fail_msg`; the assert is a verbatim copy of the 2.5/2.6 assert, so hardening would diverge from the locked pattern — consider chain-wide [src/provisioning/ansible/roles/default_palette/tasks/main.yml:55]
- WEG local-mode → container mode (product directive 2026-08-12): the 2.6 assets role runs `weg dump-effects` in local mode, but the product decision is that both CLIs run via their `install` command in container mode with podman preferred. **WEG CLI side fixed in e18ecfe** (install.py now resolves the source root); remaining: the assets role needs a `weg install` task + `WALLPAPER__RUNTIME__MODE=container` + `WALLPAPER__CONTAINER__ENGINE=<detected/override>` on the emit task when a role runs weg in container mode — mirror the cli_tools/default_palette engine detection (podman → docker → fail loud, optional override), do NOT pin podman. Cross-story (2.6), not this review's patch scope [src/provisioning/ansible/roles/assets/tasks/main.yml]
- `csg install` could not bootstrap/refresh container images from a `uv tool`-installed csg — `_find_project_root` (cli/install_cmd.py:29-36) walked up from the INSTALLED package path (uv tool venv), found no `pyproject.toml`, returned None → base image build SKIPPED (install_cmd.py:63-77), backend builds cache-hit the stale image; on a fresh machine (no images) install failed (`FROM csg-base-podman:latest` resolves nothing). **RESOLVED in e18ecfe**: `resolve_source_root()` (override → env → PEP 610 `direct_url.json` → package walk) in `oci_runtime/source_locator.py`; base always built with `context_path` set; `Dockerfile.base` COPY paths normalized to `src/...` (context = repo root). Verified: fresh rebuild from scratch + container-mode generate green [src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/install_cmd.py]
- **podman/docker are DOCUMENTED RUNTIME DEPENDENCIES** of the container-mode chain (product directive 2026-08-12): the cli_tools role (`csg install` image build) and the default_palette role (`csg generate` container runtime) both DETECT the engine at runtime — podman preferred, then docker, then FAIL LOUD — and neither installs one. Installing podman or docker is OUT OF SCOPE for these roles; address it in the packages role (Story 2.3) / fresh-machine bootstrap (Story 3.1) when dependency provisioning is done. Contract recorded in group_vars/all.yml (2026-08-12) [src/provisioning/ansible/roles/cli_tools/tasks/main.yml, roles/default_palette/tasks/main.yml, src/provisioning/ansible/group_vars/all.yml]
- Engine detection is presence-only, not usability (code review 2026-08-12) — a broken podman (rootless misconfig, stale storage lock, missing cgroup/subuid) passes the `command -v` probe, then `csg install`/`csg generate` fail later with the engine's raw error. A `podman info`/`docker info` usability pre-flight would make the fail-loud earlier; deferred as an enhancement since the chain still fails loudly downstream [src/provisioning/ansible/roles/cli_tools/tasks/main.yml:75, roles/default_palette/tasks/main.yml:120]
- Cross-role engine agreement is comment-only, not enforced (code review 2026-08-12) — cli_tools builds `csg-<backend>-<engine>`, default_palette later re-probes; they agree in the aggregate bootstrap play but a direct-run split or an engine installed between the two roles makes generate request an image never built. Fix: cli_tools `set_fact` propagation + default_palette prefer-fact-else-probe. Deferred (edge) [src/provisioning/ansible/roles/default_palette/tasks/main.yml:120,142]

## Deferred from: code review of 2-8-compositor-skeleton-configs (2026-08-12)

- Hyprland fragment `rgb(hex)` notation only valid on Hyprland ≥0.55; no version pinned — value format is emitted by csg/Story 2.7 and version pinning is the packages role (2.3) concern [dotfiles/config/hypr/hyprland.conf:17-18, src/provisioning/ansible/group_vars/arch.yml:8]
- **RESOLVED (2026-08-22):** hyprlang syntax deprecated since Hyprland 0.55 (config moved to Lua) — migrated to Lua format with modular structure. See `docs/99-dotfiles-hexagonal-architecture.md` "Phase 1 Patch" section and commits `e00a677`, `87728fc`. [dotfiles/config/hypr/hyprland.lua]
- Missing/partial palette fragment at first boot has no fallback — skeleton correctly sources a fragment only 2.9 places; ordering/verify is owned by 2.9 + 2.12 + 3.2/3.3 integration [dotfiles/config/hypr/hyprland.conf:7, dotfiles/config/waybar/style.css:1]

## Deferred from: code review of 2-10-config-copies-role (2026-08-12)

- `config_copies_repo_root: "{{ playbook_dir }}/../../../.."` resolves against the calling playbook's dir — a 2.12 aggregator at a different depth than `playbooks/` would silently mis-resolve or fail misleadingly; shared pattern across assets/compositor_configs [src/provisioning/ansible/roles/config_copies/vars/main.yml:28]
- Live-playbook tests `pytest.skip` when `ansible-playbook` is absent and `assert "changed=0" in second.stdout` is brittle across ansible-core recap formats — suite can be green with runtime behavior unverified [src/provisioning/tests/unit/test_config_copies_role.py:481-501]
- Nested `name`/`target` manifest entries would fail with an opaque ENOENT (no dest parent creation; only the config home is ensured) — latent; manifest is locked flat [src/provisioning/ansible/roles/config_copies/tasks/main.yml:67-73]
- Relative `XDG_CONFIG_HOME` accepted unvalidated — shared spec-mandated derivation with the filesystem role; any fix belongs to both roles [src/provisioning/ansible/roles/config_copies/vars/main.yml:46]

## Deferred from: code review of 2-12-verify-role-and-aggregate-bootstrap-playbook (2026-08-13)

- `verify_cli_bin_dir` hardcodes `$HOME/.local/bin`, ignoring `UV_TOOL_BIN_DIR`/`XDG_BIN_HOME` — criterion 3 false-fails after a cli_tools install to a customized bin dir; pre-existing in cli_tools (which documents the env overrides but hardcodes the same default); verify mirrors it exactly [src/provisioning/ansible/roles/verify/vars/main.yml:100, src/provisioning/ansible/roles/cli_tools/vars/main.yml:10-14]
- System-binary/CLI shell checks rely on the ansible-core 2.20.3 auto-skip of command/shell under `--check` for dry-run cleanliness — if a future ansible-core changes skip behavior, `bootstrap.yaml --check` breaks; the convention is documented, mirrored, and empirically verified but not test-locked against a version [src/provisioning/ansible/roles/verify/tasks/main.yml:82-87, 102-109]

## Deferred from: code review of 3-1-fresh-machine-bootstrap-script (2026-08-15)

- AC 5 (Arch + Debian-family) verified only by the NFR-3 token-absence scan in `test_no_distro_branching_tokens` — no test exercises the script under a second distro or any distro-specific behavior; real dual-distro runs are Story 3.2/3.3 integration territory (in-scope boundary) [src/provisioning/tests/unit/test_bootstrap_script.py:131-141]
- Full-suite "455 green" claim not reproducible from the repo root in this environment — `uv run pytest -q` aborts with 70 collection errors in unrelated `src/shared/oci-runtime`/`config-assembler-engine` modules; not caused by this change, the 18 new tests pass in isolation (pre-existing test-harness context)

## Deferred from: story 3-2-playbook-dry-run-integration-tests (2026-08-15) — dry-run suite surfaced two packages-chain defects

- **`ansible/group_vars/{all,arch,debian-family}.yml` are NOT discoverable by ansible — every packages/aggregate invocation fails with `'packages' is undefined` at the packages role's `Assemble package list` set_fact.** Ansible's group_vars discovery only searches `group_vars/` beside the INVENTORY dir (`ansible/inventory/`) or the PLAYBOOK dir (`ansible/playbooks/`); the vars live one level up at `ansible/group_vars/`, so they never load for the runtime `group_by` group. The dev host never noticed: packages.yaml is become-gated (host `--check` dies at the sudo prompt BEFORE task-args resolution), Story 2.3's tests are structural, and bootstrap.sh/CLI always ran against... the same broken path — the real `dotfiles-provision plan`/`bootstrap` fail exactly here (verified 2026-08-15 in a disposable root Arch container: ansible-core 2.21.2). FIX: relocate/symlink `group_vars/` adjacent to `inventory/` or `playbooks/`, or source the inventory as the `ansible/` directory (`-i <ansible-dir>`) — both verified working in-container 2026-08-15 (with the become_user caveat below). Until fixed, the AC-2 become-gated dry-runs and the AC-4 yay-proof cannot complete; Story 3.2 records them as blocked (host skip / in-container xfail). [src/provisioning/ansible/group_vars/*.yml, src/provisioning/ansible/playbooks/packages.yaml:22-30, src/provisioning/ansible/inventory/localhost.yaml]
- **become_user + root `--check` hits ansible's temp-file ownership guard** — with group_vars made reachable, packages.yaml `--check` as root proceeds to the `Build and install yay-bin via makepkg` task (become_user: aur_builder) and aborts: "Failed to change ownership of the temporary files Ansible (via chmod nor setfacl) needs to create despite connecting as a privileged user. Unprivileged become user would be unable to read the file." Blocks the AC-4 root-container verification even after the group_vars fix; needs a remote_tmp/become_method arrangement for root→non-root become_user under `--check` (or run the become_user tasks as root in the test target). [src/provisioning/ansible/roles/packages/tasks/main.yml:74-81]

## Deferred from: code review of story 3-2-playbook-dry-run-integration-tests (2026-08-15)

- Vacuous "clean dry-run" gate for state-asserting playbooks — `verify.yaml`'s asserts are all `when: not ansible_check_mode`-gated, so `verify.yaml --check` performs no work and an all-skipped run passes; the test never asserts `ok>0`/`changed>0`. Spec-explicit design (story #51: assert recap exists + failed=0, do NOT assert changed counts); the real coverage is the container apply+verify [src/provisioning/ansible/roles/verify/tasks/main.yml:138-273]
- Recap matching is fragile — `_RECAP_LINE_RE` (`^\s*\S+\s*:.*\bok=\d+.*\bfailed=\d+.*$`) can match stray task-result lines and never validates the expected recap-line count or non-zero `ok`/`changed`; a missing host/play recap line is silently tolerated [src/provisioning/tests/integration/test_ansible_dryrun.py:73,165-174]
- `_become_available()` can diverge from ansible's actual become capability — `sudo -n true` succeeds under command-scoped NOPASSWD while the become play may still need a password, producing a wrong skip/run decision [src/provisioning/tests/integration/test_ansible_dryrun.py:129-141]
- Killed/timed-out test processes leak the disposable container — cleanup is only in-process; no external sweep for stale `dotfiles-ac3-*` containers [src/provisioning/tests/integration/test_apply_verify_container.py:324-325]
- `uv run --directory /repo/...` against the read-only repo mount is brittle — a stale `uv.lock` or any project-dir write fails `prepare()` → skip, and the container-local venv is re-resolved on every module run rather than cached [src/provisioning/tests/integration/test_apply_verify_container.py:83-109,145-175]

## Deferred from: code review of rt-1-1-nested-hexagon-scaffold (2026-08-24)

- NetworkManager verify uses `shell` instead of `systemd` module — consistency improvement, not a bug; mirrors packages role's pattern but could use the more robust systemd module [src/provisioning/ansible/roles/verify/tasks/main.yml:154]
- Version command catches only `PackageNotFoundError` — other importlib errors are rare and would show traceback; add broader catch when polishing [src/runtime/src/runtime/cli/main.py:39-48]
- `_DIST_TO_IMPORT_ROOT` incomplete — only affects future deps with non-standard import roots (e.g., Pillow→PIL, scikit-learn→sklearn) [src/runtime/tests/architecture/test_layering.py:137-142]
- Ansible `systemctl set-default` fails on non-systemd — outside story scope, pre-existing [src/provisioning/ansible/roles/display_manager/tasks/main.yml:106]
- Ansible `systemd` module fails on non-systemd — outside story scope, pre-existing [src/provisioning/ansible/roles/display_manager/tasks/main.yml:99-103]
- `display_manager_enable_service` undefined guard — outside story scope, pre-existing [src/provisioning/ansible/roles/display_manager/tasks/main.yml:100]
- Docstring enumeration format inconsistency — documentation-only, code is correct [src/runtime/tests/architecture/test_layering.py:31-32]

## Deferred from: code review of rt-1-3-ports-domain-capabilities (2026-08-28)

- `reload()` return type inconsistency — `IDesktopReloader.reload() -> bool` vs `IStaticWallpaperBackend.reload() -> None`; design choice, adapters handle semantics [desktop_reloader.py:6, wallpaper_backend.py:16]
- `set_playlist` lacks parameters from `set_video` — intentional subset; no per-video control for playlist items [wallpaper_backend.py:35-40]
- `set_color` format unspecified — format constraint belongs in adapter docstrings [wallpaper_backend.py:12]
- Empty `paths` list in `set_playlist` — undefined behavior for empty list; adapter-specific [wallpaper_backend.py:35-40]
- Input/output directory overlap in generators — could clobber input files; adapter-specific validation [color_scheme_generator.py, effects_generator.py, icon_renderer.py]

## Deferred from: code review of rt-1-5-content-hashing-and-cache-key (2026-08-28)

- Very large directory OOM / unbounded `entries` list + no size cap on file read — `entries: list[tuple[str,str]]` unbounded, 1M files can OOM; 100MB wallpaper already chunked but mutating file is torn-read; FIFO `-> /dev/zero` causes infinite loop — trusted local spine (AD-11, AD-12 synchronous) makes this pre-existing out-of-scope for hashing-only story — deferred, not caused by this change — `src/runtime/src/runtime/adapters/hashing.py:119`
- Case-insensitive FS + Unicode normalization divergence (macOS HFS/APFS NFC vs NFD, Windows casing) — `as_posix()` + lexicographic sort is case-sensitive; same logical template set hashes differently on Linux vs macOS. Provisioning is Linux-only (Arch) per phase1, so out-of-scope for this story — deferred — `src/runtime/src/runtime/adapters/hashing.py:149`

## Deferred from: code review of rt-1-6-layered-cache-populator (2026-08-29)

- `CACHE_LAYERS` duplicates domain layer literals (`domain/models.py` Literal) — pre-existing layering choice; domain owns enums, adapter redeclares. No action now — consider centralizing in domain later. [src/runtime/src/runtime/adapters/cache.py:48]
- No explicit `chmod`/`umask` for staging/cache dirs — `mkdir` inherits umask, no explicit mode. Consider `mode=0o755` in future hardening pass. [src/runtime/src/runtime/adapters/cache.py:160,164]

## Deferred from: code review of rt-1-7-csg-adapter-env-override (2026-08-29)

- Duplicated _find_default_templates_dir + permission swallowing — adapter and integration test duplicate repo walk with divergent `alt` paths; `is_dir()` returns False on PermissionError silently returning None. Low, pre-existing pattern. [src/runtime/src/runtime/adapters/csg_adapter.py:46-64]
- Unbounded hash_file read (multi-hundred MB / sparse / FIFO DoS) — no size/time cap; large wallpaper blocks before subprocess timeout. Trusted local spine makes this out-of-scope for 1.7. [src/runtime/src/runtime/adapters/hashing.py:75-81]

## Deferred from: code review of rt-1-8-weg-adapter-env-override (2026-08-30)

- Unbounded `capture_output` buffers entire stdout/stderr in RAM — `weg` verbose catalog could OOM; no `MAX_BUFFER`. Copied from CsgAdapter, pre-existing — deferred, revisit with streaming [src/runtime/src/runtime/adapters/weg_adapter.py:267]
- Concurrent `generate` to same `output_dir` races `mkdir→rglob→hash_file` — no file lock; but `populate_via_staging` caller owns atomicity per docstring, so out-of-scope for adapter — deferred [src/runtime/src/runtime/adapters/weg_adapter.py:228-343]
- Copy-paste divergence from `csg_adapter.py` — 90% validation/mkdir/error logic duplicated without shared helper; drift risk but not a bug for this story — deferred as tech-debt [src/runtime/src/runtime/adapters/weg_adapter.py:88-106]

## Deferred from: code review of rt-1-9-itr-adapter-env-overrides (2026-08-30)

- CsgAdapter silently swallows OSError on symlink check (fail-open vs ItrAdapter's fail-closed) — pre-existing, not caused by this change [src/runtime/src/runtime/adapters/csg_adapter.py:104-106]
- Private `_validate_hex64` imported externally from itr_adapter — architectural pattern shared with CsgAdapter/WegAdapter; consider making public or inlining [src/runtime/src/runtime/adapters/itr_adapter.py:243]

## Deferred from: code review of rt-1-10-minimal-istaterepository (2026-08-31)

- `_validate_save` raw `KeyError` on dict access (w["hash"], entry["hash"], etc.) — unreachable in practice since data comes from `_state_to_dict` which always produces valid keys; align with `_dict_to_state` wrapping or document as developer-only check [src/runtime/src/runtime/adapters/json_state_repository.py:192-229]
- `..` traversal check bypassable via symlinked parent — state_root is trusted input (tests inject tmp_path); production callers resolve before injection [src/runtime/src/runtime/adapters/json_state_repository.py:103]
- `Path.home()` can raise `RuntimeError` in containers — extreme edge case, caught at constructor time [src/runtime/src/runtime/adapters/json_state_repository.py:94]
- Extra keys in projection/monitor dicts silently accepted — defense-in-depth; not harmful since _state_to_dict produces known shapes [src/runtime/src/runtime/adapters/json_state_repository.py:220-226,287-299]

## Deferred from: code review of rt-1-11-first-run-self-seeding (2026-08-31)

- Hardlink alias to mutable provisioning file — cache/wallpapers/<hash>/wallpaper.png is hardlinked to install_spine/generated/default.png; if provisioning ever mutates default.png in place, the cache entry's content diverges from its directory-name hash. AD-16 mandated; relies on provisioning discipline. [src/runtime/src/runtime/adapters/seeder.py:286-305]
- CSG raw-output nondeterminism — .csg_determinism.json records colors.yaml hashes differing between run1/run2 (normalized hash matches); any consumer relying on raw artifact hash stability across regenerations is affected. [src/runtime/tests/integration/.csg_determinism.json]
- Duplicated fake adapters (_FakeCsg/_FakeWeg/_FakeItr/_FakeFactory) copy-pasted across unit and integration suites, encoding the meta.json-less generate contract in both. Shared conftest fixture recommended. [src/runtime/tests/unit/test_seed_cache.py, src/runtime/tests/integration/test_seed_cache_integration.py]
- Template discovery couples runtime to dev-repo layout — walks install_spine ancestors for src/cli-tools/... (never exists in production XDG layout); silently binds dev behavior to whatever checkout sits in an ancestor dir. [src/runtime/src/runtime/application/seed_cache.py:396-500]

## Deferred from: code review of rt-1-13-applywallpaperusecase (2026-09-01)

- Corrupt/missing `meta.json` in an existing palette/effects/icons cache entry bricks that layer permanently — cache-hit is entry-dir existence, populate is write-once, and `load_*_entry` raises on bad/absent meta with no self-heal path; pattern inherited from rt-1-11 (applies to seed equally), now shared via DerivationPipeline. Self-heal (rename aside / rmtree + repopulate on meta load failure) is cache-hygiene beyond this story's scope. [src/runtime/src/runtime/application/derive.py:239-240, src/runtime/src/runtime/adapters/seeder.py:344-353]

## Deferred from: code review of rt-2-1-atomic-symlink-repoint (2026-09-02)

- History/save outside lock inconsistency and crash-recovery atomicity — save after repoint can fail leaving FS ahead of store, history append outside lock can be lost [reconcile.py:183, reconcile.py:185] — deferred, pre-existing design; Story 2.2 owns crash-mid-swap recovery. **RESOLVED (2026-09-02, Story rt-3.1):** both crash windows traced, behavior test-pinned, and the residual gap explicitly re-scoped — see "Deferred from: rt-3-1-history-jsonl-persistence" below.
- Arbitrary file read via source_path — trusts current.json source_path to import arbitrary files [reconcile.py:281] — deferred, pre-existing spec-intended; requires write to current.json
- Cache entry exists as file not dir crashes with unmapped exception [reconcile.py:226] — deferred, pre-existing cache layer behavior
- Dangling symlink false miss: cache_entry_path.exists() false for dangling symlink triggers unnecessary regeneration [reconcile.py:226] — deferred, edge case of corrupt cache
- Composition root side effect runs on --help/--version [cli/main.py:159] — deferred, pre-existing
- Idempotence relies on existence not content hash — stale/corrupt entry resurrected [derive.py:239] — deferred, deferred-work rt-1-11

## Deferred from: code review of rt-2-4-ags-restart-reload-adapter (2026-09-02)

- ~140 lines of test scaffolding copy-pasted into a 4th location — `_FakeMutex`/`_FakeCsg`/`_FakeWeg`/`_FakeItr`/`_setup_spine`/`_make_applied` are byte-identical to the copies in test_hyprland_reloader*.py; should be shared conftest fixtures [src/runtime/tests/unit/test_ags_reloader.py:197-339, src/runtime/tests/integration/test_ags_reloader_integration.py]
- Test hygiene: process-global `shutil.which` patches coupled to `hyprland_reloader`'s module location (breaks if the resolver moves to a shared module), and reconcile-integration tests (full use case + on-disk repos) living in the unit test file [src/runtime/tests/unit/test_ags_reloader.py:146-149,360-379]

## Deferred from: code review of rt-2-5-hyprpaper-channel-verification (2026-09-02)

- Non-symlink / directory-target `wallpaper-*.png` entries treated as valid monitors — the dangling check only guards missing targets and `is_file()` is never checked on the resolved target; masked upstream by repoint's P2 guard and stale-cleanup, reachable only by manual tampering [src/runtime/src/runtime/adapters/hyprpaper_reloader.py:170-179]
- "Hyprpaper reload skipped" log wording undercuts the surfaced-failure it produces — spec-mandated verbatim copy of the Hyprland/AGS sibling reloaders; behavior is correctly `False` [src/runtime/src/runtime/adapters/hyprpaper_reloader.py:159]
- `_resolve_state_root` duplicates `cli/main.py`'s resolution instead of sharing — spec-directed mirror and the composition root passes `state_root` explicitly; a shared helper is not layering-clean across application/adapters [src/runtime/src/runtime/adapters/hyprpaper_reloader.py:88-99]
- Failure log concatenates stdout+stderr without a separator and drops a `TimeoutExpired`'s captured output — cosmetic logging, mirrors HyprlandReloader [src/runtime/src/runtime/adapters/hyprpaper_reloader.py:195-201]

## Deferred from: rt-3-1-history-jsonl-persistence (2026-09-02) — crash-window verdict (AC 5)

The "save after repoint can fail leaving FS ahead of store, history append outside lock can be lost" gap exists in TWO windows with different consequences. Both are traced and test-pinned; the residual loss is re-scoped as ACCEPTED (must-not-lose = append-only + atomicity, NOT cross-crash after-save reconstruction).

### Reconcile window (reconcile.py:253 save → :265 append) — lazy self-heal, no backfill

- A crash between save and append leaves `current.json` MATCHING the repointed `current/` symlinks, so rt-2-2's `_revert_stale_symlinks` divergence detection CANNOT detect it (by construction; the divergence signal is absent).
- Reconcile self-heals lazily: the NEXT reconcile appends unconditionally, so history resumes — but the crashed transition's line is permanently missing (never backfilled).
- **Pinned:** `test_crash_window_reconcile_save_append_lost_line_not_backfilled` (integration) proves the lost line is NOT resurrected and exactly one new reconcile line lands. Detection limitation itself is structural, not test-pinned (no observable signal exists).

### Seed window (seed_cache.py:229 save → :232 append) — PERMANENT loss

- A crash here is the worse half: after save, `load_current()` returns non-None, so every subsequent seed run is a NO-OP → the `trigger: "seed"` line is NEVER written. A later reconcile appends a `"reconcile"` line (or nothing), never the seed line.
- **Pinned:** `test_crash_window_seed_save_append_seed_line_permanently_lost` (integration) proves the no-op and the permanent absence.

**Decision (with acceptance):** do not add a dir-fsync or a post-crash line-reconstruction pass. AD-4/AR-3 are satisfied by O_APPEND + fsync atomicity + append-only semantics; reconstructing a lost line after a crash is beyond the architecture (no durable per-transaction intent log exists, and adding one contradicts AD-12's synchronous no-daemon design). The must-not-lose guarantee is per-line atomicity, not post-crash retro-recovery. [src/runtime/src/runtime/adapters/seeder.py:567-617, src/runtime/src/runtime/application/reconcile.py:253-273, src/runtime/src/runtime/application/seed_cache.py:229-239]

## Deferred from: code review of rt-3-1-history-jsonl-persistence (2026-09-02)

- Torn/partial history line — the real crash artifact of the short-write loop — is never simulated or handled: a process killed between two `os.write` calls leaves a truncated non-JSON tail that would crash every `json.loads(line)` consumer (Epic 3 rt-3-3 history readers). Handling requires a tolerance/repair policy (a design decision), not a patch [src/runtime/src/runtime/adapters/seeder.py:617-624]
- O_APPEND atomicity is per single `write(2)`; the append loop issues multiple writes, so two concurrent writers (reconcile appends outside the lock, reconcile.py:265-266) can interleave and tear each other's lines; `test_concurrent_recovery_safety` asserts symlink state only, never history.jsonl integrity. The "O_APPEND + fsync is atomic" comment overstates per-write reality. Fixing = writer redesign, explicitly out of scope for rt-3.1 ("do NOT rebuild the existing writer") [src/runtime/src/runtime/adapters/seeder.py:620-623]
- `os.write` returning 0 makes `data = data[written:]` a no-op — the append loop spins forever with no progress guard [src/runtime/src/runtime/adapters/seeder.py:621-623]

## Deferred from: code review of rt-3-3-inspect-history-command (2026-09-03)

- Concurrent writer interleave torn lines — two writers appending outside the lock can interleave/tear lines; reader has no snapshot contract. Pre-existing writer-side (rt-3.1), not caused by this reader change [src/runtime/src/runtime/adapters/seeder.py:620-623]
- Brittle argv substring guard — `if "inspect" in sys.argv` false-positives on paths like `my-inspect`. Pre-existing rt-3.2, spec says do NOT touch guard [src/runtime/src/runtime/cli/main.py:181]
- FIFO/directory/BOM at history.jsonl path — directory raises raw IsADirectoryError, FIFO blocks on open, BOM-prefixed file misclassified as torn tail. Out-of-scope hardening; writer never emits BOM [src/runtime/src/runtime/application/inspect.py:332]

## Incident 2026-09-07: live desktop spawn from unit tests (FIXED, gt-fix-1)

- `test_cli_crash_recovery` CLI tests stubbed only 2 of 4 reloaders; the real `AgsReloader` spawned `ags run` under a monkeypatched `XDG_STATE_HOME` (pytest tmp). The spawned bar survived pytest, replaced the dev's live bar (its gjs child outlived the killed parent, holding the `io.Astal.ags` D-Bus name), and rendered broken icons from the deleted tmp dir. [src/runtime/tests/unit/test_cli_crash_recovery.py:219]
- Fix: autouse `shutil.which` guards in `tests/unit/conftest.py` + `tests/integration/conftest.py` — system-installed desktop binaries (ags/hyprctl/hyprpaper/swaybg/swww/mpvpaper) resolve to None so adapters fail fast; pytest-tmp shims still resolve (integration shim tests verified green). Affected CLI tests now stub all four reloaders explicitly.
- Residual: production-side hardening (reloader refuses to spawn when it detects a session-foreign env) is NOT added — tests-only fix; composition-root seam (`_build_reloaders` monkeypatch) is the long-term cleaner seam, deferred.

## Deferred from: code review of gt-2-2-iconsumerpathspec-declarative-pointers (2026-09-07)

- `CacheSeeder.__init__` falls back via `consumer_spec or StaticConsumerPathSpec()` — a falsy custom spec implementation would silently receive the default table instead of raising; unreachable today (class instances are truthy), but `is None` would be the precise guard. Fix opportunistically when the constructor is next touched [src/runtime/src/runtime/adapters/seeder.py:110-111]
- Inspect `_link_status` classifies a regular FILE squatting at a pointer dest as `missing` (not `diverged`) — consistent with the existing `current_symlinks` semantics the AC pins ("SAME status semantics"), but a pre-migration provisioning file at a gtk dest reads as `missing` rather than flagging divergence; revisit if a future doctor command needs the distinction [src/runtime/src/runtime/application/inspect.py:261-263]
- `ConsumerPointerRules` flags are consumed conditionally but only the all-True semantics are tested: `remove_on_null_palette: False` (null palette keeps stale pointers) and `skip_on_missing_target: False` (dangling pointer creation) paths have no coverage because the pinned table has no per-pointer variation (YAGNI per Dev Notes decision 1). If a real consumer ever flips a flag, dedicated tests for the flipped semantics are required at that time [src/runtime/src/runtime/adapters/seeder.py:626-640]
