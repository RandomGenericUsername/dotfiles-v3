from abc import ABC

import pytest

from oci_runtime.ports.engine import ContainerEngine


class TestContainerEngine:
    def test_is_abc(self):
        assert issubclass(ContainerEngine, ABC)

    def test_images_is_abstract_property(self):
        assert isinstance(ContainerEngine.images, property)
        assert ContainerEngine.images.fget.__isabstractmethod__

    def test_containers_is_abstract_property(self):
        assert isinstance(ContainerEngine.containers, property)
        assert ContainerEngine.containers.fget.__isabstractmethod__

    def test_volumes_is_abstract_property(self):
        assert isinstance(ContainerEngine.volumes, property)
        assert ContainerEngine.volumes.fget.__isabstractmethod__

    def test_networks_is_abstract_property(self):
        assert isinstance(ContainerEngine.networks, property)
        assert ContainerEngine.networks.fget.__isabstractmethod__

    def test_capabilities_is_abstract_property(self):
        assert isinstance(ContainerEngine.capabilities, property)
        assert ContainerEngine.capabilities.fget.__isabstractmethod__

    def test_is_available_is_abstract(self):
        assert ContainerEngine.is_available.__isabstractmethod__

    def test_version_is_abstract(self):
        assert ContainerEngine.version.__isabstractmethod__

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            ContainerEngine()
