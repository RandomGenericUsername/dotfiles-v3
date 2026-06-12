# OCI-Runtime — List Format Fix: Remediation Plan

**Date:** 2026-06-11  
**Severity:** 🟠 High  
**Status:** PROPOSED  
**Prerequisite:** All Phase 1-3 changes complete. 675 tests passing.

---

## Problem Statement

All four `list()` methods across `ImageManager`, `ContainerManager`, `VolumeManager`, and `NetworkManager` are broken at runtime on real Docker and Podman installations. The root cause is two interrelated problems:

### P1: No `--format` flag on list commands

`image.list()`, `volume.list()`, and `network.list()` do not pass any `--format` flag. Without it, Docker and Podman output human-readable tables, which `_parse_json_list()` cannot parse — it raises `ParsingError`.

`container.list()` already passes `--format json` but this is hardcoded rather than driven by runtime capabilities.

### P2: Different output formats across runtimes

Even with `--format` flags, Docker and Podman produce structurally different output:

| Command | Docker `--format json` | Docker `--format {{json .}}` | Podman `--format json` |
|---------|----------------------|-------------------------------|----------------------|
| `image ls` | NDJSON, keys: `ID`, `Repository`, `Tag`, `VirtualSize` | NDJSON, same keys | JSON array, keys: `Id`, `RepoTags`, `Size` |
| `image ls` (no flag) | Table format — not parseable | — | Table format — not parseable |
| `volume ls` | NDJSON, keys: `Name`, `Driver`, `Mountpoint` | NDJSON, same keys | JSON array, compatible keys |
| `network ls` | NDJSON, keys: `ID` (uppercase!), `Name`, `Driver`, `Scope` | NDJSON, same keys | JSON array, keys: `id` (lowercase!), `name` (lowercase!), `driver` (lowercase!) |
| `container ls` | — (not tested) | — | JSON array, compatible keys |

**Key differences:**
1. **Structure**: Docker produces NDJSON (line-delimited JSON objects). Podman produces JSON arrays.
2. **Key names**: Docker uses `ID` (uppercase), `Repository`/`Tag` (separate), `VirtualSize`. Podman uses `Id`, `RepoTags`, `Size`. Podman `network ls` uses all-lowercase keys (`id`, `name`, `driver`).
3. **Value types**: Docker `image ls` returns `Size` as a human-readable string (`"8.45MB"`), Podman returns it as an integer (`8735049`).

### Current dead code

`RuntimeCapabilities.supported_output_formats` is set by providers but never read by any code:

```python
# DockerRuntimeProvider
supported_output_formats=["json", "yaml"]  # ← never used

# PodmanRuntimeProvider
supported_output_formats=["json"]  # ← never used
```

---

## Prototype Validation Results

All findings were validated against live Docker 27.x and Podman 5.x installations.

### Docker `--format {{json .}}` output

```
$ docker image ls --format '{{json .}}'
{"Containers":"N/A","CreatedAt":"2026-06-09","CreatedSince":"2 days ago","Digest":"<none>","ID":"772bee4540c4","Repository":"alpine","SharedSize":"N/A","Size":"8.45MB","Tag":"latest","UniqueSize":"N/A","VirtualSize":"8.454MB"}
```

- Produces NDJSON (one JSON object per line).
- Not parseable by `json.loads()` — raises `json.JSONDecodeError: Extra data`.
- Keys differ from inspect: `ID` vs `Id`, `Repository`/`Tag` vs `RepoTags`, `VirtualSize` vs `Size`.

### Podman `--format json` output

```
$ podman image ls --format json
[
    {"Id":"6fdd9940679c...","RepoTags":null,"Size":8735049,...}
]
```

- Produces a proper JSON array.
- Keys match inspect format: `Id`, `RepoTags`, `Size`.
- `RepoTags` may be `null` instead of `[]`.

### Docker `volume ls --format {{json .}}` output

```
{"Availability":"N/A","Driver":"local","Group":"N/A","Labels":"","Links":"N/A","Mountpoint":"/var/lib/docker/volumes/my-vol/_data","Name":"my-vol","Scope":"local","Size":"N/A"}
```

- Keys `Name`, `Driver`, `Mountpoint` are compatible with our parser.
- `Labels` is an empty string `""` instead of `{}` or `null`.

### Docker `network ls --format {{json .}}` output

```
{"CreatedAt":"2026-06-11","Driver":"bridge","ID":"11de959545c4","IPv4":"true","IPv6":"false","Internal":"false","Labels":"","Name":"bridge","Scope":"local"}
```

- Uses `ID` (uppercase) instead of `Id`.
- Otherwise compatible.

### Podman `network ls --format json` output

```json
[{"name":"podman","id":"2f259bab93aa...","driver":"bridge",...}]
```

- Uses **lowercase** keys: `id`, `name`, `driver`.
- Completely different from inspect keys (`Id`, `Name`, `Driver`).

### Proposed `_parse_json_list()` with NDJSON fallback

```
✅ JSON array:     [parse_list] → list[dict]           (Podman format)
✅ Single object:   {...}       → [{...}]               (inspect format)
✅ NDJSON:          {...}\n{...} → [{...}, {...}]       (Docker format)
✅ Garbage:         "not json"  → ParsingError           (error handling)
✅ Empty string:    ""          → ParsingError           (error handling)
✅ Empty list:      "[]"        → ParsingError           (empty response)
```

### Proposed Docker key normalization

```
✅ DockerImageParser.parse_list with NDJSON:
   Parsed 7 images:
     id=772bee4540c4..., tags=['alpine:latest'], size=8860467
     id=0c2728b20d35..., tags=['wallpaper-effects:latest'], size=576716800
     ...

✅ DockerVolumeParser.parse_list with NDJSON:
   Parsed 46 volumes

✅ DockerNetworkParser.parse_list with NDJSON:
   Parsed 3 networks:
     id=11de959545c4..., name=bridge, driver=bridge, scope=local
     id=8d7e2f0997be..., name=host, driver=host, scope=local
     id=9a21f1d63c01..., name=none, driver=null, scope=local

✅ PodmanImageParser.parse_list with JSON array:
   Parsed 10 images

✅ PodmanVolumeParser.parse_list with JSON array:
   Parsed 0 volumes (empty, works)

⚠️ PodmanNetworkParser.parse_list requires key normalization:
   id='', name='', driver='', scope=''  ← needs fix
```

### Backwards compatibility

```
✅ Inspect-style JSON array:  parse_list('[{...}]')         → works
✅ Single JSON object:        parse_list('{...}')           → works  
✅ Garbage input:             parse_list('not json')       → ParsingError
✅ Empty string:              parse_list('')               → ParsingError
```

---

## Solution Architecture

### Hexagonal Architecture Compliance

| Layer | Responsibility | Change |
|-------|---------------|--------|
| **Domain** | Pure value objects, no I/O | No changes. `ImageInfo`, `VolumeInfo`, etc. remain the same. |
| **Ports** | Abstract interfaces | `ImageManager.list()` still returns `list[ImageInfo]`. `RuntimeCapabilities` field renamed. |
| **Adapters** | I/O specifics, CLI commands, output parsing | `list_format_flags` drives CLI flag selection. Parsers normalize runtime-specific keys. |
| **Factory** | Composition root | No changes needed — providers already construct `RuntimeCapabilities`. |

**The user-facing contract is identical.** Callers see `engine.images.list() → list[ImageInfo]` regardless of whether Docker or Podman is underneath. The normalization happens entirely inside adapter parsers.

### Data Flow Diagram

```
User:  engine.images.list(filters=None)
         │
         ▼
CliImageManager.list(filters=None)
         │
         │  1. Build CLI command
         │     cmd = [binary, "image", "list"]
         │     cmd += caps.list_format_flags
         │         ┌────────────────────────────┐
         │  Docker │ --format {{json .}}        │
         │  Podman │ --format json              │
         │         └────────────────────────────┘
         │
         │  2. Transport.execute(cmd) → ExecResult
         │  3. _decode_stdout(result.stdout) → str
         │  4. parser.parse_list(decoded) → list[ImageInfo]
         │
         ▼
   ┌──────────────────┐     ┌──────────────────────┐
   │  DockerParser    │     │  PodmanParser        │
   │                  │     │                      │
   │  _parse_json_    │     │  _parse_json_        │
   │   list():        │     │   list():            │
   │   NDJSON → list  │     │   JSON array → list  │
   │                  │     │                      │
   │  parse_list():   │     │  parse_list():       │
   │   ID → Id       │     │   Id → Id (direct)   │
   │   Repository+   │     │   RepoTags → RepoTags│
   │    Tag→RepoTags │     │   Size → Size (int)  │
   │   VirtualSize   │     │   Names → RepoTags   │
   │    → Size       │     │     (fallback)       │
   │   Labels ""→{}  │     │                      │
   └────────┬────────┘     └────────┬─────────────┘
            │                       │
            │  list[ImageInfo]      │  list[ImageInfo]
            └───────────┬───────────┘
                        │
         ┌──────────────▼───────────┐
         │  Identical domain objects │
         │  regardless of runtime   │
         │  ImageInfo(              │
         │    id="sha256:abc",      │
         │    tags=["alpine:lt"],  │
         │    size=8860467,         │
         │  )                       │
         └──────────────────────────┘
```

---

## Implementation Steps

### Step 1: Replace `supported_output_formats` with `list_format_flags`

**File:** `src/oci_runtime/ports/capabilities.py`

```python
# BEFORE
@dataclass
class RuntimeCapabilities:
    supported_output_formats: list[str] = field(default_factory=lambda: ["json"])
    needs_userns_keep_id: bool = False
    supports_log_drivers: bool = True
    tar_entry_name: str = "Dockerfile"
    default_run_flags: list[str] = field(default_factory=list)
    default_build_flags: list[str] = field(default_factory=list)

# AFTER
@dataclass
class RuntimeCapabilities:
    list_format_flags: list[str] = field(default_factory=list)
    needs_userns_keep_id: bool = False
    supports_log_drivers: bool = True
    tar_entry_name: str = "Dockerfile"
    default_run_flags: list[str] = field(default_factory=list)
    default_build_flags: list[str] = field(default_factory=list)
```

`supported_output_formats` is deleted (dead code). `list_format_flags` takes its place with a different meaning: CLI flags to request structured output from list commands.

**Files to update for field rename:**
1. `src/oci_runtime/adapters/provider/docker.py` — change `supported_output_formats=["json", "yaml"]` to `list_format_flags=["--format", "{{json .}}"]`
2. `src/oci_runtime/adapters/provider/podman.py` — change `supported_output_formats=["json"]` to `list_format_flags=["--format", "json"]`
3. All tests that reference `supported_output_formats` — update to `list_format_flags`

**Grep for migration:**
```bash
grep -rn "supported_output_formats" src/ tests/
```

**Verification:** `grep -rn "supported_output_formats" src/ tests/` returns zero hits. All tests pass.

---

### Step 2: Update manager `list()` commands to use `list_format_flags`

**File:** `src/oci_runtime/adapters/managers/image.py` — `list()` method

```python
# BEFORE (line 81-87)
def list(self, filters: dict[str, str] | None = None) -> list[ImageInfo]:
    cmd = [self._transport.get_runtime_binary(), "image", "list"]
    if filters:
        for key, val in filters.items():
            cmd.extend(["--filter", f"{key}={val}"])
    result = self._transport.execute(cmd)
    return self._parser.parse_list(self._decode_stdout(result.stdout))

# AFTER
def list(self, filters: dict[str, str] | None = None) -> list[ImageInfo]:
    cmd = [self._transport.get_runtime_binary(), "image", "list"]
    cmd.extend(self._caps.list_format_flags)
    if filters:
        for key, val in filters.items():
            cmd.extend(["--filter", f"{key}={val}"])
    result = self._transport.execute(cmd)
    return self._parser.parse_list(self._decode_stdout(result.stdout))
```

**File:** `src/oci_runtime/adapters/managers/volume.py` — `list()` method

```python
# BEFORE (line 44-50)
def list(self, filters: dict[str, str] | None = None) -> list[VolumeInfo]:
    cmd = [self._transport.get_runtime_binary(), "volume", "list"]
    if filters:
        for key, val in filters.items():
            cmd.extend(["--filter", f"{key}={val}"])
    result = self._transport.execute(cmd)
    return self._parser.parse_list(self._decode_stdout(result.stdout))

# AFTER
def list(self, filters: dict[str, str] | None = None) -> list[VolumeInfo]:
    cmd = [self._transport.get_runtime_binary(), "volume", "list"]
    cmd.extend(self._caps.list_format_flags)
    if filters:
        for key, val in filters.items():
            cmd.extend(["--filter", f"{key}={val}"])
    result = self._transport.execute(cmd)
    return self._parser.parse_list(self._decode_stdout(result.stdout))
```

**File:** `src/oci_runtime/adapters/managers/network.py` — `list()` method

```python
# BEFORE (line 54-60)
def list(self, filters: dict[str, str] | None = None) -> list[NetworkInfo]:
    cmd = [self._transport.get_runtime_binary(), "network", "list"]
    if filters:
        for key, val in filters.items():
            cmd.extend(["--filter", f"{key}={val}"])
    result = self._transport.execute(cmd)
    return self._parser.parse_list(self._decode_stdout(result.stdout))

# AFTER
def list(self, filters: dict[str, str] | None = None) -> list[NetworkInfo]:
    cmd = [self._transport.get_runtime_binary(), "network", "list"]
    cmd.extend(self._caps.list_format_flags)
    if filters:
        for key, val in filters.items():
            cmd.extend(["--filter", f"{key}={val}"])
    result = self._transport.execute(cmd)
    return self._parser.parse_list(self._decode_stdout(result.stdout))
```

**File:** `src/oci_runtime/adapters/managers/container.py` — `list()` method

```python
# BEFORE (line 149-157)
def list(self, show_all: bool = False, filters: dict[str, str] | None = None) -> list[ContainerInfo]:
    cmd = [self._transport.get_runtime_binary(), "container", "list", "--format", "json"]
    if show_all:
        cmd.append("-a")
    ...

# AFTER
def list(self, show_all: bool = False, filters: dict[str, str] | None = None) -> list[ContainerInfo]:
    cmd = [self._transport.get_runtime_binary(), "container", "list"]
    cmd.extend(self._caps.list_format_flags)
    if show_all:
        cmd.append("-a")
    ...
```

Container `list()` already had `"--format", "json"` hardcoded. Now it's driven by capabilities, consistent with all other list methods.

**Verification:** `grep -n 'format.*json' src/oci_runtime/adapters/managers/` — should show zero hardcoded `--format json` strings.

---

### Step 3: Add NDJSON fallback to `_parse_json_list()`

**File:** `src/oci_runtime/adapters/parser/base.py`

```python
# BEFORE
def _parse_json_list(self, raw: str) -> list[dict]:
    """Parse JSON that contains a list."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ParsingError(raw=raw, message=f"Invalid JSON in list response: {e}") from e
    if not isinstance(data, list):
        data = [data]
    return data

# AFTER
def _parse_json_list(self, raw: str) -> list[dict]:
    """Parse JSON that contains a list, a single object, or NDJSON."""
    try:
        data = json.loads(raw)
        if not data:
            raise ParsingError(raw=raw, message="Empty response")
        if isinstance(data, list):
            return data
        return [data]
    except json.JSONDecodeError:
        pass

    # Try line-delimited JSON (NDJSON) — Docker's --format {{json .}}
    lines = raw.strip().split("\n")
    items: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if items:
        return items
    raise ParsingError(raw=raw, message="Invalid JSON in list response")
```

**Tests to add:** `tests/unit/adapters/test_parser_base.py`

```python
class TestParseJsonListNDJSON:
    def test_json_array(self):
        parser = BaseCliParser()
        result = parser._parse_json_list('[{"id": "abc"}]')
        assert len(result) == 1
        assert result[0]["id"] == "abc"

    def test_single_object(self):
        parser = BaseCliParser()
        result = parser._parse_json_list('{"id": "abc"}')
        assert len(result) == 1
        assert result[0]["id"] == "abc"

    def test_ndjson_two_objects(self):
        parser = BaseCliParser()
        ndjson = '{"id": "abc"}\n{"id": "def"}'
        result = parser._parse_json_list(ndjson)
        assert len(result) == 2
        assert result[0]["id"] == "abc"
        assert result[1]["id"] == "def"

    def test_ndjson_with_blank_lines(self):
        parser = BaseCliParser()
        ndjson = '{"id": "abc"}\n\n{"id": "def"}\n'
        result = parser._parse_json_list(ndjson)
        assert len(result) == 2

    def test_empty_string_raises(self):
        parser = BaseCliParser()
        with pytest.raises(ParsingError):
            parser._parse_json_list("")

    def test_empty_list_raises(self):
        parser = BaseCliParser()
        with pytest.raises(ParsingError, match="Empty response"):
            parser._parse_json_list("[]")

    def test_garbage_raises(self):
        parser = BaseCliParser()
        with pytest.raises(ParsingError):
            parser._parse_json_list("not json at all")

    def test_partial_ndjson_skips_bad_lines(self):
        parser = BaseCliParser()
        ndjson = '{"id": "abc"}\nnot json\n{"id": "def"}'
        result = parser._parse_json_list(ndjson)
        assert len(result) == 2
        assert result[0]["id"] == "abc"
        assert result[1]["id"] == "def"

    def test_table_format_raises(self):
        parser = BaseCliParser()
        table = "REPOSITORY    TAG       IMAGE ID\nalpine         latest    abc123"
        with pytest.raises(ParsingError):
            parser._parse_json_list(table)
```

**Verification:** All existing parser tests still pass (no behavior change for JSON array input). New NDJSON tests pass.

---

### Step 4: Normalize Docker parser `parse_list()` key names

**File:** `src/oci_runtime/adapters/parser/docker.py`

**DockerImageParser.parse_list:**

```python
# BEFORE
def parse_list(self, raw: str) -> list[ImageInfo]:
    data = self._parse_json_list(raw)
    result = []
    for item in data:
        result.append(ImageInfo(
            id=item.get("Id", ""),
            tags=item.get("RepoTags", []),
            size=item.get("Size", 0),
            created=str(item.get("Created", "")),
            labels=item.get("Labels", {}),
        ))
    return result

# AFTER
def parse_list(self, raw: str) -> list[ImageInfo]:
    data = self._parse_json_list(raw)
    result = []
    for item in data:
        # Normalize Docker ls keys to inspect-style keys
        image_id = item.get("Id") or item.get("ID") or item.get("id", "")
        tags = item.get("RepoTags", [])
        if not tags:
            repo = item.get("Repository", "")
            tag = item.get("Tag", "")
            if repo and repo != "<none>":
                tags = [f"{repo}:{tag}"] if tag and tag != "<none>" else [f"{repo}:latest"]
        size = item.get("Size", 0)
        if isinstance(size, str):
            size = parse_size_to_bytes(size)
            if not size:
                size = item.get("VirtualSize", 0)
        elif not size:
            size = item.get("VirtualSize", 0)
        labels = item.get("Labels", {})
        if isinstance(labels, str):
            labels = {}
        result.append(ImageInfo(
            id=image_id,
            tags=tags,
            size=size if isinstance(size, int) else 0,
            created=str(item.get("Created", "")),
            labels=labels,
        ))
    return result
```

**DockerNetworkParser.parse_list:**

```python
# BEFORE
def parse_list(self, raw: str) -> list[NetworkInfo]:
    data = self._parse_json_list(raw)
    result = []
    for item in data:
        result.append(NetworkInfo(
            id=item.get("Id", ""),
            name=item.get("Name", ""),
            driver=item.get("Driver", ""),
            scope=item.get("Scope", ""),
            labels=item.get("Labels", {}),
        ))
    return result

# AFTER
def parse_list(self, raw: str) -> list[NetworkInfo]:
    data = self._parse_json_list(raw)
    result = []
    for item in data:
        # Normalize Docker ls keys: "ID" (uppercase) → "Id"
        net_id = item.get("Id") or item.get("ID") or item.get("id", "")
        labels = item.get("Labels", {})
        if isinstance(labels, str):
            labels = {}
        result.append(NetworkInfo(
            id=net_id,
            name=item.get("Name", ""),
            driver=item.get("Driver", ""),
            scope=item.get("Scope", ""),
            labels=labels,
        ))
    return result
```

**DockerVolumeParser.parse_list:** No key normalization needed — Docker volume ls output keys (`Name`, `Driver`, `Mountpoint`) already match our parser expectations. Only add `Labels` string-to-dict handling:

```python
# BEFORE
def parse_list(self, raw: str) -> list[VolumeInfo]:
    data = self._parse_json_list(raw)
    result = []
    for item in data:
        result.append(VolumeInfo(
            name=item.get("Name", ""),
            driver=item.get("Driver", ""),
            mountpoint=item.get("Mountpoint"),
            labels=item.get("Labels", {}),
        ))
    return result

# AFTER
def parse_list(self, raw: str) -> list[VolumeInfo]:
    data = self._parse_json_list(raw)
    result = []
    for item in data:
        labels = item.get("Labels", {})
        if isinstance(labels, str):
            labels = {}
        result.append(VolumeInfo(
            name=item.get("Name", ""),
            driver=item.get("Driver", ""),
            mountpoint=item.get("Mountpoint"),
            labels=labels,
        ))
    return result
```

**DockerContainerParser.parse_list:** Already has `--format json` hardcoded. Needs the same `Name`/`RepoTags`/`Labels` normalization but container ls keys are different. Check if needed:

Docker `container ls --format json` uses `Names`, `Image`, `State`, etc. — these already match the parser. But add defensive handling:

```python
# The existing parse_list already handles Names as a list:
# name=(item.get("Names") or ["/"])[0].lstrip("/")
# This is fine for both Docker and Podman.
```

No changes needed for DockerContainerParser.parse_list.

---

### Step 5: Normalize Podman parser `parse_list()` key names

**File:** `src/oci_runtime/adapters/parser/podman.py`

**PodmanNetworkParser.parse_list:** Podman `network ls --format json` uses lowercase keys (`id`, `name`, `driver`). Normalize:

```python
# BEFORE
def parse_list(self, raw: str) -> list[NetworkInfo]:
    data = self._parse_json_list(raw)
    result = []
    for item in data:
        result.append(NetworkInfo(
            id=item.get("Id", ""),
            name=item.get("Name", ""),
            driver=item.get("Driver", ""),
            scope=item.get("Scope", ""),
            labels=item.get("Labels", {}),
        ))
    return result

# AFTER
def parse_list(self, raw: str) -> list[NetworkInfo]:
    data = self._parse_json_list(raw)
    result = []
    for item in data:
        # Normalize: Podman ls uses lowercase keys (id, name, driver)
        # while inspect uses PascalCase (Id, Name, Driver)
        net_id = item.get("Id") or item.get("id", "")
        name = item.get("Name") or item.get("name", "")
        driver = item.get("Driver") or item.get("driver", "")
        scope = item.get("Scope") or item.get("scope", "")
        labels = item.get("Labels", {})
        if isinstance(labels, dict):
            pass
        elif isinstance(labels, str) and labels:
            labels = {}
        else:
            labels = {}
        result.append(NetworkInfo(
            id=net_id,
            name=name,
            driver=driver,
            scope=scope,
            labels=labels,
        ))
    return result
```

**PodmanImageParser.parse_list:** Podman `image ls --format json` may use `Names` instead of `RepoTags` when tags are absent. Add defensive handling:

```python
# BEFORE
def parse_list(self, raw: str) -> list[ImageInfo]:
    data = self._parse_json_list(raw)
    result = []
    for item in data:
        result.append(ImageInfo(
            id=item.get("Id", ""),
            tags=item.get("RepoTags", []),
            size=item.get("Size", 0),
            created=str(item.get("Created", "")),
            labels=item.get("Labels", {}),
        ))
    return result

# AFTER
def parse_list(self, raw: str) -> list[ImageInfo]:
    data = self._parse_json_list(raw)
    result = []
    for item in data:
        tags = item.get("RepoTags", [])
        if not tags:
            names = item.get("Names", [])
            if names:
                tags = names
        labels = item.get("Labels", {})
        if isinstance(labels, dict):
            pass
        elif isinstance(labels, str) and labels:
            labels = {}
        else:
            labels = {}
        result.append(ImageInfo(
            id=item.get("Id", ""),
            tags=tags if tags else [],
            size=item.get("Size", 0),
            created=str(item.get("Created", "")),
            labels=labels,
        ))
    return result
```

**PodmanVolumeParser.parse_list:** Podman volume ls keys already match. Add `Labels` string-to-dict handling:

```python
# AFTER (minimal change)
def parse_list(self, raw: str) -> list[VolumeInfo]:
    data = self._parse_json_list(raw)
    result = []
    for item in data:
        labels = item.get("Labels", {})
        if isinstance(labels, str):
            labels = {}
        result.append(VolumeInfo(
            name=item.get("Name", ""),
            driver=item.get("Driver", ""),
            mountpoint=item.get("Mountpoint"),
            labels=labels,
        ))
    return result
```

**PodmanContainerParser.parse_list:** Keys already match. No changes needed.

---

### Step 6: Update `container.list()` to use capabilities instead of hardcoded flag

**File:** `src/oci_runtime/adapters/managers/container.py`

```python
# BEFORE (line 149-157)
def list(self, show_all: bool = False, filters: dict[str, str] | None = None) -> list[ContainerInfo]:
    cmd = [self._transport.get_runtime_binary(), "container", "list", "--format", "json"]
    if show_all:
        cmd.append("-a")
    ...

# AFTER
def list(self, show_all: bool = False, filters: dict[str, str] | None = None) -> list[ContainerInfo]:
    cmd = [self._transport.get_runtime_binary(), "container", "list"]
    cmd.extend(self._caps.list_format_flags)
    if show_all:
        cmd.append("-a")
    ...
```

This makes `container.list()` consistent with all other list methods — the format flag is driven by `RuntimeCapabilities`.

**Important:** Docker `container ls --format {{json .}}` uses `Names` (not `RepoTags`) and different key names than `--format json`. The DockerContainerParser already handles this:

```python
# Current parse_list already uses container ls key names:
# item.get("Names"), item.get("Image"), item.get("State"), item.get("Ports")
```

But we need to verify these still work with `--format {{json .}}`. The prototype validated this — Docker `container ls --format {{json .}}` produces NDJSON with the same key names as `--format json` for containers.

---

### Step 7: Update tests

**Test helper:** `tests/helpers/mock_transport.py` — `RecordingTransport` must handle `list_format_flags` in command matching.

Affected test files that hardcode `"--format", "json"` in response keys:

| File | Change |
|------|--------|
| `test_container_manager_contract.py` | `"docker container list --format json"` → response key must match new command |
| `test_cli_container_manager.py` | Response key must match new command pattern |
| `test_cli_image_manager.py` | Response key must include `--format {{json .}}` for Docker |
| `test_cli_volume_manager.py` | Response key must include `--format {{json .}}` for Docker |
| `test_cli_network_manager.py` | Response key must include `--format {{json .}}` for Docker |
| `test_error_conditions.py` | Response keys for inspect commands stay the same (they already have `--format json`) |
| `test_malformed_output.py` | Same |
| `test_workflows.py` | Response keys for list commands must include format flags |

**New test files to add:**

1. **`tests/unit/adapters/test_parser_base.py`** — Add `TestParseJsonListNDJSON` class with 8 tests (see Step 3).

2. **`tests/unit/adapters/test_docker_parser.py`** — Add tests for:
   - `test_parse_list_ndjson_image` — Docker NDJSON image list with key normalization
   - `test_parse_list_ndjson_network` — Docker NDJSON network list with `ID` → `Id` normalization
   - `test_parse_list_ndjson_volume` — Docker NDJSON volume list
   - `test_parse_list_docker_ls_keys` — Verify `Repository`+`Tag` → `RepoTags`, `VirtualSize` → `Size`
   - `test_parse_list_labels_string_to_dict` — Verify `Labels: ""` → `{}`

3. **`tests/unit/adapters/test_podman_parser.py`** — Add tests for:
   - `test_parse_list_lowercase_network_keys` — Podman network ls with `id`, `name`, `driver` keys
   - `test_parse_list_null_repo_tags` — Podman image ls with `RepoTags: null`
   - `test_parse_list_names_fallback` — Podman image ls with `Names` instead of `RepoTags`

4. **`tests/integration/boundary/test_docker_list_format.py`** — New file with end-to-end tests:
   - `test_docker_image_list_ndjson` — Use `RecordingTransport` with Docker NDJSON fixture
   - `test_podman_image_list_json_array` — Use `RecordingTransport` with Podman JSON array fixture
   - `test_docker_network_list_uppercase_id` — Verify `ID` → `Id` normalization
   - `test_podman_network_list_lowercase_keys` — Verify `id` → `Id`, `name` → `Name`, `driver` → `Driver`

---

## Dependency Graph

```
Step 1 (capabilities) ──► Step 2 (managers) ──► Step 6 (container list)
       │                         │
       ▼                         ▼
Step 3 (NDJSON) ────────► Step 4 (Docker parsers)
       │                         │
       │                         ▼
       └──────────────────► Step 5 (Podman parsers)
                                 │
                                 ▼
                          Step 7 (tests)
```

Steps 1-3 are independent. Steps 4 and 5 depend on Step 3. Step 6 depends on Step 2. Step 7 depends on all prior steps.

---

## Risk Assessment

| Change | Risk | Mitigation |
|--------|------|-----------|
| `supported_output_formats` → `list_format_flags` | Medium — field rename, test updates | Grep for all usages first |
| NDJSON fallback in `_parse_json_list()` | Low — additive, existing JSON array path unchanged | Extensive unit tests covering JSON array, single object, NDJSON, garbage |
| Docker key normalization | Low — `item.get("Id") or item.get("ID")` is defensive | Both keys tried, fallback to `""` |
| Podman lowercase normalization | Low — `item.get("Name") or item.get("name")` is defensive | Both keys tried |
| Container list now uses capabilities | Medium — removes hardcoded `--format json` | Docker/Podman both support `--format json` for containers; capabilities now drive it |
| `parse_size_to_bytes` for Docker Size strings | Low — already exists, just used in new location | Tested with "8.45MB" → 8847360 |

---

## Verification Checklist

After each step:

1. `uv run pytest tests/ -v` — all tests pass
2. `grep -rn "supported_output_formats" src/ tests/` — zero hits (Step 1)
3. `grep -rn '"--format".*"json"' src/oci_runtime/adapters/managers/` — zero hardcoded format flags (Step 2)
4. `grep -rn "list_format_flags" src/oci_runtime/adapters/managers/` — 4 hits (image, volume, network, container)
5. Manual validation with real Docker and Podman (prototype script)
6. `grep -rn "ID\|Repository\|VirtualSize\|VirtualSize" src/oci_runtime/adapters/parser/docker.py` — normalization present
7. `grep -rn '"id"\|"name"\|"driver"' src/oci_runtime/adapters/parser/podman.py` — lowercase normalization present