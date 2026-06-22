import concurrent.futures


from oci_runtime.adapters.engine.cli import CliRuntime
from oci_runtime.factory import RuntimeFactory
from oci_runtime.domain.types import RuntimePreference
from oci_runtime.domain.enums import RuntimeKind


class TestConcurrency:
    def test_concurrent_factory_create(self):
        """Factory.create() is safe for concurrent use — it returns independent
        ContainerEngine instances (each with its own transport, parser, and
        manager object graphs), and the factory itself holds no mutable state
        during creation."""
        pref = RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker")
        factory = RuntimeFactory()
        n = 20
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            engines = list(ex.map(lambda _: factory.create(pref), range(n)))
        assert len(engines) == n
        for engine in engines:
            assert isinstance(engine, CliRuntime)
