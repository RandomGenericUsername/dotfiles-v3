import oci_runtime


class TestPublicAPI:
    def test_all_names_importable(self):
        for name in oci_runtime.__all__:
            assert getattr(oci_runtime, name) is not None

    def test_adapters_not_exported(self):
        for name in ("CliTransport", "CliRuntime", "DockerRuntimeProvider", "PodmanRuntimeProvider"):
            assert name not in oci_runtime.__all__

    def test_runtime_kind_importable(self):
        from oci_runtime import RuntimeKind
        assert RuntimeKind is oci_runtime.RuntimeKind
