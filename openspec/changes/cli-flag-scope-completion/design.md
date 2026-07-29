## Context

After `cli-flag-scope-refinement` (which moved `--runtime` and `--container-engine` from root), the root callbacks still carry three non-cross-cutting flags. The cross-cutting set (retained) is `--output-format`, `--verbose`, `--quiet` — concerns that affect HOW every command communicates. The remaining flags are "operational resources" flags (which file/config to read) — they affect WHAT each command processes.

The existing `cli/options.py` module in both tools provides the pattern for sharing option definitions without DRY violations. This change extends the same pattern.

The `templates-dir-isolation` change (prerequisite) has already removed `TemplateSettings` from the settings schema and routed `--templates-dir` directly through `TemplateDirResolver`. This change simply relocates where the `--templates-dir` Typer option is declared — from root to leaf — while keeping the same direct-resolution plumbing.

## Goals / Non-Goals

**Goals:**
- Root callback in both tools declares only `--output-format`, `--verbose`, `--quiet` (plus inherent framework options).
- Every non-cross-cutting flag is declared at the smallest scope that contains all its consumers (leaf for singletons, sub-typer callback for families).
- CSG `dump-config` behavior matches WEG's: print bundled default template, no config resolution.
- CSG `install`/`uninstall` pass `--config` to config resolver.
- WEG `show` sub-typer gets a callback for `--effects`.

**Non-Goals:**
- Changing `templates-dir-isolation` architecture (already landed).
- Changing `TemplateDirResolver` API, `JinjaTemplateRenderer` API, or any adapter code.
- Changing `--output-format`, `--verbose`, `--quiet` behavior or position.
- Any WEG `--config`/`--effects` changes beyond position — the underlying plumbing (`_resolve_context`, `effect_loader.load`, `config_resolver.resolve`) is untouched.

## Decisions

### D1: Sub-typer callback for process/batch families (WEG); leaf option for singletons

**Choice:** `--config` and `--effects` are declared on `process_app.callback()` and `batch_app.callback()` (existing callbacks, extended). They are declared as leaf options on `info`, `install`, `uninstall`. `--effects` is declared on a new `show_app.callback()`.

**Rationale (from D1 of `cli-flag-scope-refinement`):** Sub-typer callback is the natural scope for "all commands in this group" when every leaf consumes the flag. Standalone commands (info, install, uninstall) use leaf options.

### D2: `--config` and `--effects` store in sub-typer's `ctx` not root's `ctx`

**Choice:** Each sub-typer callback stores its parsed `config` and `effects` values in its own `ctx.obj["config"]` / `ctx.obj["effects"]`. The leaf commands (process effect, batch effects, etc.) read from the sub-typer's `ctx.obj`, which is inherited from the parent. The root callback no longer stores these.

**Rationale:** `_resolve_context()` (process.py:59-78), `_run_batch()` (batch.py:50-80), and `_load_catalog()` (show.py:24-31) all read `ctx.obj.get("config")` / `ctx.obj.get("effects")`. When `ctx.obj` is inherited from the sub-typer callback (the callback runs before the leaf command), the leaf reads the sub-typer-set values transparently. No leaf logic changes needed.

### D3: CSG `dump-config` prints bundled default — `info --config` covers inspection

**Choice:** Replace CSG `dump_config_cmd.py` body with: read `defaults/settings.toml` from package resources, write string to output or stdout. Match WEG's `dump_config_command()` structure exactly. Remove `config_resolver.resolve()` call and all `ctx.obj` reads.

**Rationale:** After `templates-dir-isolation`, `dump-config` no longer resolves config for the `[template]` section (it's gone). The remaining resolve+serialize path exists only for the `[template]` section — after removal, the serializer is doing pointless work (resolving config only to dump it verbatim). WEG's approach (print bundled template) is simpler, serves the same "give me a starter config" purpose, and removes `--config` from `dump-config`'s surface. Users who want to inspect resolved settings use `csg info --config /path`.

### D4: CSG `install`/`uninstall` pass `config_path` to resolver (bug fix)

**Choice:** Both commands gain `--config` as a leaf option. Their command bodies pass `config_path` to `config_resolver.resolve(explicit_path=config_path)` instead of calling `resolve()` with no args.

**Rationale:** Already documented in D3 of `cli-flag-scope-refinement`'s design and identified as a concrete bug in the investigation report. WEG's equivalents (`install_command`, `uninstall_command`) already receive and pass `config_path`. This fix makes CSG's behavior match WEG's.

### D5: Sequencing — runs after `templates-dir-isolation` and preflight commit

**Choice:** This change is implemented on a clean baseline that already has `templates-dir-isolation` landed, the preflight commit done, and `engine-qualified-image-tags` completed.

**Rationale:** `cli-flag-scope-completion` moves `--templates-dir` to leaf options. The leaf logic reads the flag value and calls `renderer.update_templates_dir(value)` — which assumes the `templates-dir-isolation` cleanup (no `cli_overrides` involvement, no settings field). Without that prerequisite, the flag-scope change would route through stale plumbing.

## Risks / Trade-offs

- **[Discoverability regresses for `--config`/`--effects`]** Users typing `csg --help` won't see `--config` listed (it was previously in the global options section). They must type `csg generate --help`, `csg info --help`, or `weg process --help` to discover it. **Mitigation:** This is the correct behavior — `--config` is relevant in the context of a specific command (which config to use for THIS generate operation). The path to the config file is not a universal output/format concern. Industry precedent (docker, git, kubectl) follows this pattern.

- **[CSG `dump-config` loses inspect capability]** Users who relied on `csg dump-config --config /special.toml` to see resolved settings must now use `csg info --config /special.toml`. **Mitigation:** `info` shows the same resolved settings (including all sections and sources). The behavioral overlap between `dump-config` (resolve+serialize) and `info` (resolve+display) was confusing — both did the same thing in different output formats. Aligning `dump-config` to print the bundled default removes the confusion.

- **[Merge with `templates-dir-isolation`]** This change restructures flag declarations in files that `templates-dir-isolation` also touches (CLI files that read `settings.template.*`). **Mitigation:** `templates-dir-isolation` lands first and is committed. This change is applied on top. The two changes touch different concerns in the same files (isolation removes settings reads; scoping moves flag declarations) — minimal merge conflict risk since the isolation change deletes/prepares the lines that this change restructures.

- **[User scripts break if flags repositioned]** Any user scripts passing flags as global options will see parse errors. **Mitigation:** Document the new flag positions prominently. The pattern `csg generate --config /x --templates-dir /y` is intuitive and follows CLI conventions.

- **[WEG `show_app.callback()` introduces new ctx scope]** Currently `show` commands read `ctx.obj["effects"]` from the root-level ctx. Adding a sub-typer callback creates a sub-scoped ctx that inherits from root. `ctx.obj["effects"]` is set in the callback; leaf commands read it. **Mitigation:** Typer's ctx nesting behaves like Python's `ChainMap` — child ctx lookup falls through to parent. If a sub-typer callback sets `ctx.obj["effects"]`, the leaf reads the sub-typer's value. This is the identical pattern to WEG's existing `process_app.callback()` setting `ctx.obj["runtime"]` and `ctx.obj["container_engine"]`.
