## ADDED Requirements

### Requirement: pull returns a non-empty id or raises
`ImageManager.pull()` SHALL return a non-empty image id string on success. If the parser cannot extract an image id from the runtime output (the parser returns `""`), `pull()` MUST raise `ImageError` with the raw output attached as `stderr`.

#### Scenario: successful pull returns image id
- **WHEN** `pull("alpine")` is called and the transport returns output containing `Digest: sha256:abc123`
- **THEN** the method returns `"sha256:abc123"`

#### Scenario: empty pull output raises ImageError
- **WHEN** `pull("alpine")` is called and the transport returns `RawExecResult(returncode=0, stdout=b"", stderr=b"")`
- **THEN** the method raises `ImageError` (not returning `""`)

#### Scenario: unparseable pull output raises ImageError
- **WHEN** `pull("alpine")` is called and the transport returns `RawExecResult(returncode=0, stdout=b"some random text\n", stderr=b"")`
- **THEN** the method raises `ImageError`

### Requirement: pull still raises not-found on pull-access-denied
`ImageManager.pull()` SHALL raise `ImageNotFoundError` when the runtime reports the image does not exist (stderr matches the parser's `is_not_found_error`, e.g. `pull access denied`). This behavior is unchanged.

#### Scenario: pull access denied raises ImageNotFoundError
- **WHEN** `pull("nonexistent:latest")` is called and the transport returns `RawExecResult(returncode=1, stdout=b"", stderr=b"pull access denied for nonexistent:latest")`
- **THEN** the method raises `ImageNotFoundError` whose `image_name` attribute equals `"nonexistent:latest"`
