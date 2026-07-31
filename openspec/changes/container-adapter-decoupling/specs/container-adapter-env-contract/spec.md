# Container Adapter Env Contract

## Why

Container processors in WEG and CSG need to tell the in-container process
where to find config files, resource files, and how to configure its
runtime mode. Using CLI flags for this creates a coupling between the
adapter and the CLI flag-scope layout — a coupling that has already
caused production failures (see `cli-flag-scope-completion`).

Environment variables are the correct channel for in-container configuration
because:

1. They are scope-agnostic — the CLI's flag scope does not affect env var
   resolution.
2. They are already supported by both tools' `config-assembler-engine`
   (via `EnvPathStrategy` for file paths and `OverrideMatchingService`
   for field overrides).
3. They survive across process boundaries trivially.
4. CSG already uses this pattern successfully for
   `COLORSCHEME_CONFIG_FILE_PATH` and `COLORSCHEME_TEMPLATES_TEMPLATES_DIR`.

## Spec

### 1. WEG `_CONTAINER_ENV`

The `container_processor.py` module must define a module-level constant:

```python
_CONTAINER_ENV: dict[str, str] = {
    "HOME": "/tmp",
    "XDG_CONFIG_HOME": "/tmp/.config",
    "XDG_CACHE_HOME": "/tmp/.cache",
    "WALLPAPER_CONFIG_FILE_PATH": "/weg-config/settings.toml",
    "WALLPAPER_EFFECTS_CONFIG_FILE_PATH": "/weg-effects/effects.yaml",
    "WALLPAPER__RUNTIME__MODE": "local",
}
```

Every call to `self._get_engine().containers.run(run_config)` must pass
`environment=_CONTAINER_ENV` in the `RunConfig`.

#### Key mapping

| Key | Value | Why |
|-----|-------|-----|
| `HOME` | `/tmp` | Prevents writes to non-writable home dir |
| `XDG_CONFIG_HOME` | `/tmp/.config` | Prevents XDG fallback to nonexistent dir |
| `XDG_CACHE_HOME` | `/tmp/.cache` | Prevents cache writes to nonexistent dir |
| `WALLPAPER_CONFIG_FILE_PATH` | `/weg-config/settings.toml` | Points at mounted config volume |
| `WALLPAPER_EFFECTS_CONFIG_FILE_PATH` | `/weg-effects/effects.yaml` | Points at mounted effects volume |
| `WALLPAPER__RUNTIME__MODE` | `local` | Serialized settings.toml already has this; env adds belt-and-suspenders |

### 2. CSG `_CONTAINER_ENV` extension

The existing `_CONTAINER_ENV` in `color_scheme_generator/adapters/container_processor.py`
must be extended with one key:

```python
_CONTAINER_ENV = {
    "HOME": "/tmp",
    "XDG_CONFIG_HOME": "/tmp/.config",
    "XDG_CACHE_HOME": "/tmp/.cache",
    "COLORSCHEME_CONFIG_FILE_PATH": "/csg-config/settings.toml",
    "COLORSCHEME_TEMPLATES_TEMPLATES_DIR": "/templates",
    "COLORSCHEME__RUNTIME__MODE": "local",  # NEW
}
```

### 3. No CLI flags for config/resource/runtime in in-container argv

The in-container argv must NOT contain any of these flags at any scope:

| Tool | Flags excluded |
|------|----------------|
| WEG | `--config`, `-c`, `--effects`, `-e` |
| CSG | `--runtime`, `-r` |

These flags remain valid on the host side (unchanged by this spec).

### 4. No new flags introduced

The env vars defined here do not create new CLI flags. They only reuse
the env-var discovery mechanism that already exists in both tools'
`config-assembler-engine` configuration.

### 5. Test: `test_passes_expected_environment`

Both tools must have a test confirming that the container runtime receives
the exact `_CONTAINER_ENV` dict:

```python
def test_passes_expected_environment(self, processor, ...):
    processor.process_effect("blur", request, params)
    call_kwargs = processor._get_engine().containers.run.call_args[1]
    env = call_kwargs.get("environment", {})
    assert env == _CONTAINER_ENV
```

#### WEG-specific note

WEG's `_run_in_container` uses `RunConfig` with a typed `environment` field.
The test inspects `run_config.environment` from the call args.

#### CSG-specific note

CSG already has this test (`test_passes_expected_environment`, line 333).
It must be updated to assert the new key
`COLORSCHEME__RUNTIME__MODE` is present.
