import re

import pytest


pytestmark = pytest.mark.smoke


class TestFactoryCreatesEngine:
    @pytest.mark.docker_required
    def test_factory_creates_live_docker_engine(self, live_docker_engine):
        from oci_runtime.ports.engine import ContainerEngine
        assert isinstance(live_docker_engine, ContainerEngine)

    @pytest.mark.podman_required
    def test_factory_creates_live_podman_engine(self, live_podman_engine):
        from oci_runtime.ports.engine import ContainerEngine
        assert isinstance(live_podman_engine, ContainerEngine)


class TestLiveEngineBasicCommands:
    @pytest.mark.runtime_required
    def test_live_engine_version_is_non_empty(self, live_docker_engine):
        version = live_docker_engine.version()
        assert len(version) > 0

class TestLiveEngineContainerLifecycle:
    @pytest.mark.docker_required
    def test_live_engine_can_pull_and_run_container(self, live_docker_engine):
        image_id = live_docker_engine.images.pull("alpine")
        assert len(image_id) > 0
        from oci_runtime.domain.types import RunConfig
        cid = live_docker_engine.containers.run(RunConfig(image="alpine"))
        assert re.match(r"^[a-f0-9]{12,64}$", cid) is not None
        live_docker_engine.containers.remove(cid, force=True)

    @pytest.mark.docker_required
    def test_live_engine_container_lifecycle(self, live_docker_engine):
        from oci_runtime.domain.types import RunConfig
        live_docker_engine.images.pull("alpine")
        cid = live_docker_engine.containers.run(RunConfig(image="alpine", detach=True))
        assert len(cid) > 0
        live_docker_engine.containers.stop(cid)
        live_docker_engine.containers.start(cid)
        logs = live_docker_engine.containers.logs(cid)
        assert isinstance("".join(logs), str)
        live_docker_engine.containers.remove(cid, force=True, volumes=True)

    @pytest.mark.docker_required
    def test_live_engine_image_tag_and_remove(self, live_docker_engine):
        live_docker_engine.images.pull("alpine")
        live_docker_engine.images.tag("alpine", "test-smoke:latest")
        assert live_docker_engine.images.exists("test-smoke:latest") is True
        live_docker_engine.images.remove("test-smoke:latest")
        assert live_docker_engine.images.exists("test-smoke:latest") is False


class TestLiveEngineVolumeLifecycle:
    @pytest.mark.docker_required
    def test_live_engine_creates_and_removes_volume(self, live_docker_engine):
        vol_name = "test-smoke-vol"
        name = live_docker_engine.volumes.create(vol_name)
        assert name.strip()
        live_docker_engine.volumes.remove(vol_name)


class TestLiveEngineNetworkLifecycle:
    @pytest.mark.docker_required
    def test_live_engine_creates_and_removes_network(self, live_docker_engine):
        net_name = "test-smoke-net"
        name = live_docker_engine.networks.create(net_name)
        assert name.strip()
        live_docker_engine.networks.remove(net_name)
