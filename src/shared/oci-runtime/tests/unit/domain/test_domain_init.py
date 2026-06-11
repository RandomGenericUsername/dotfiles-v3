def test_domain_exports_enums():
    from oci_runtime.domain import ContainerState, RuntimeKind, RestartPolicy, NetworkMode


def test_domain_exports_exceptions():
    from oci_runtime.domain import OciError, ContainerError


def test_domain_exports_types():
    from oci_runtime.domain import ContainerInfo, RunConfig, ExecOutput


def test_domain_star_import():
    import importlib
    mod = importlib.import_module("oci_runtime.domain")
    names = getattr(mod, "__all__", [])
    assert "ContainerState" in names
