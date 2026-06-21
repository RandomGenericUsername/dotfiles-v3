from abc import ABC
from dataclasses import is_dataclass, fields

import pytest

from oci_runtime.domain.types import RawExecResult
from oci_runtime.ports.transport import Transport


class TestTransport:
    def test_is_abc(self):
        assert issubclass(Transport, ABC)

    def test_execute_is_abstract(self):
        assert Transport.execute.__isabstractmethod__

    def test_get_runtime_binary_is_abstract(self):
        assert Transport.get_runtime_binary.__isabstractmethod__

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            Transport()

    def test_concrete_subclass_must_implement_all_abstract(self):
        with pytest.raises(TypeError):
            type("BadImpl", (Transport,), {})()

    def test_concrete_subclass_works(self):
        class GoodTransport(Transport):
            def execute(self, command, *, timeout=None, input_data=None):
                return RawExecResult(returncode=0, stdout=b"", stderr=b"")
            def get_runtime_binary(self) -> str:
                return "docker"
            def probe(self) -> bool:
                return True
        t = GoodTransport()
        assert isinstance(t, Transport)
        assert t.get_runtime_binary() == "docker"


class TestExecResult:
    def test_is_dataclass(self):
        assert is_dataclass(RawExecResult)

    def test_fields(self):
        fs = {f.name: f for f in fields(RawExecResult)}
        assert fs["returncode"].type is int
        assert fs["stdout"].type is bytes
        assert fs["stderr"].type is bytes

    def test_construct(self):
        r = RawExecResult(returncode=0, stdout=b"out", stderr=b"err")
        assert r.returncode == 0
        assert r.stdout == b"out"
        assert r.stderr == b"err"
