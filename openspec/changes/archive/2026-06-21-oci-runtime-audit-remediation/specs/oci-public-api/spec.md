## ADDED Requirements

### Requirement: Public API re-exports the full domain layer
`oci_runtime/__init__.py` SHALL re-export every public name from the domain layer: all enums (`RuntimeKind`, `ContainerState`, `RestartPolicy`, `NetworkMode`, `VolumeMountType`), all exceptions (`OciError`, `ContainerError`, `ContainerRuntimeError`, `ContainerNotFoundError`, `ImageError`, `ImageNotFoundError`, `VolumeError`, `VolumeNotFoundError`, `NetworkError`, `NetworkNotFoundError`, `RuntimeNotAvailableError`, `ParsingError`), all types (`BuildContext`, `RunConfig`, `ContainerInfo`, `ImageInfo`, `VolumeInfo`, `NetworkInfo`, `PortMapping`, `VolumeMount`, `PruneResult`, `ExecResult`, `RawExecResult`, `RuntimePreference`, `CancellationToken`), and `RuntimeCapabilities`.

#### Scenario: RuntimeKind importable from top level
- **WHEN** a consumer does `from oci_runtime import RuntimeKind`
- **THEN** `RuntimeKind` is the same object as `oci_runtime.domain.enums.RuntimeKind`

#### Scenario: OciError importable from top level
- **WHEN** a consumer does `from oci_runtime import OciError`
- **THEN** `OciError` is the same object as `oci_runtime.domain.exceptions.OciError`

#### Scenario: ParsingError importable from top level
- **WHEN** a consumer does `from oci_runtime import ParsingError`
- **THEN** `ParsingError` is the same object as `oci_runtime.domain.exceptions.ParsingError`

#### Scenario: PruneResult importable from top level
- **WHEN** a consumer does `from oci_runtime import PruneResult`
- **THEN** `PruneResult` is the same object as `oci_runtime.domain.types.PruneResult`

### Requirement: Public API re-exports the port interfaces
`oci_runtime/__init__.py` SHALL re-export the port ABCs: `ContainerEngine`, `ImageManager`, `ContainerManager`, `VolumeManager`, `NetworkManager`, `ContainerParser`, `ImageParser`, `VolumeParser`, `NetworkParser`, `Transport`, `StreamingTransport`, `TtyDetector`, `OutputStream`, `RuntimeDiscovery`, `RuntimeProvider`. It SHALL also re-export `RuntimeFactory` and `RuntimeFactoryConfig`.

#### Scenario: ContainerEngine importable from top level
- **WHEN** a consumer does `from oci_runtime import ContainerEngine`
- **THEN** `ContainerEngine` is the same object as `oci_runtime.ports.engine.ContainerEngine`

#### Scenario: Transport importable from top level
- **WHEN** a consumer does `from oci_runtime import Transport`
- **THEN** `Transport` is the same object as `oci_runtime.ports.transport.Transport`

### Requirement: Adapters are not exported
`oci_runtime/__init__.py` MUST NOT re-export any adapter class (`CliTransport`, `CliRuntime`, `CliContainerManager`, `DockerRuntimeProvider`, etc.). Adapters are implementation details reachable via their submodules.

#### Scenario: adapter not in __all__
- **WHEN** `oci_runtime.__all__` is inspected
- **THEN** it does not contain `"CliTransport"`, `"CliRuntime"`, `"CliContainerManager"`, `"DockerRuntimeProvider"`, or `"PodmanRuntimeProvider"`

#### Scenario: adapter still importable from submodule
- **WHEN** a consumer does `from oci_runtime.adapters.transport.cli import CliTransport`
- **THEN** the import succeeds (submodule access is unchanged)

### Requirement: __all__ matches the exported names
`oci_runtime.__init__.py` SHALL define `__all__` listing every re-exported name, and every name in `__all__` MUST be importable from the package top level.

#### Scenario: every __all__ name is importable
- **WHEN** `for name in oci_runtime.__all__: getattr(oci_runtime, name)` is executed
- **THEN** no `AttributeError` is raised
