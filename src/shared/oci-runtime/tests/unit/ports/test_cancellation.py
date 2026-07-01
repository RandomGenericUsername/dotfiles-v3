from abc import ABC


class TestCancellationTokenRelocated:
    """CancellationToken was moved from domain.types to ports.cancellation."""

    def test_importable_from_ports(self):
        from oci_runtime.ports.cancellation import CancellationToken

        assert issubclass(CancellationToken, ABC)
        assert hasattr(CancellationToken, "cancel")
        assert hasattr(CancellationToken, "is_cancelled")
