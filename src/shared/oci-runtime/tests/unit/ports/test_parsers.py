from abc import ABC

import pytest

from oci_runtime.domain.exceptions import ContainerError, OciError
from oci_runtime.ports.parsers import (
    ContainerParser,
    ImageParser,
    NetworkParser,
    ParsingError,
    VolumeParser,
)


class TestContainerParser:
    def test_is_abc(self):
        assert issubclass(ContainerParser, ABC)

    def test_parse_inspect_abstract(self):
        assert ContainerParser.parse_inspect.__isabstractmethod__

    def test_parse_list_abstract(self):
        assert ContainerParser.parse_list.__isabstractmethod__

    def test_is_not_found_error_abstract(self):
        assert ContainerParser.is_not_found_error.__isabstractmethod__

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            ContainerParser()


class TestImageParser:
    def test_is_abc(self):
        assert issubclass(ImageParser, ABC)

    def test_parse_inspect_abstract(self):
        assert ImageParser.parse_inspect.__isabstractmethod__

    def test_parse_list_abstract(self):
        assert ImageParser.parse_list.__isabstractmethod__

    def test_parse_build_output_abstract(self):
        assert ImageParser.parse_build_output.__isabstractmethod__

    def test_is_not_found_error_abstract(self):
        assert ImageParser.is_not_found_error.__isabstractmethod__

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            ImageParser()


class TestVolumeParser:
    def test_is_abc(self):
        assert issubclass(VolumeParser, ABC)

    def test_parse_inspect_abstract(self):
        assert VolumeParser.parse_inspect.__isabstractmethod__

    def test_parse_list_abstract(self):
        assert VolumeParser.parse_list.__isabstractmethod__

    def test_is_not_found_error_abstract(self):
        assert VolumeParser.is_not_found_error.__isabstractmethod__

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            VolumeParser()


class TestNetworkParser:
    def test_is_abc(self):
        assert issubclass(NetworkParser, ABC)

    def test_parse_inspect_abstract(self):
        assert NetworkParser.parse_inspect.__isabstractmethod__

    def test_parse_list_abstract(self):
        assert NetworkParser.parse_list.__isabstractmethod__

    def test_is_not_found_error_abstract(self):
        assert NetworkParser.is_not_found_error.__isabstractmethod__

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            NetworkParser()


class TestParsingError:
    def test_stores_raw_and_message(self):
        err = ParsingError(raw='{"invalid": json', message="failed to parse JSON")
        assert err.raw == '{"invalid": json'
        assert "failed to parse JSON" in str(err)

    def test_str_includes_raw_and_message(self):
        err = ParsingError(raw="some bad output", message="parse failure")
        msg = str(err)
        assert "some bad output" in msg or "parse failure" in msg

    def test_is_oci_error(self):
        assert issubclass(ParsingError, OciError)

    def test_is_not_container_error(self):
        assert not issubclass(ParsingError, ContainerError)

    def test_is_exception(self):
        assert issubclass(ParsingError, Exception)
