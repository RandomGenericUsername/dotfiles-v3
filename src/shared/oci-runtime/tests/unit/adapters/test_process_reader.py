import io
from unittest.mock import MagicMock

import pytest

from oci_runtime.adapters.transport.pipe_reader import ProcessPipeReader


class TestProcessPipeReaderFromProcess:
    def test_from_process_raises_typeerror_for_bytesio(self):
        bio = io.BytesIO(b"hello")
        process = MagicMock()
        process.stdout = bio
        with pytest.raises(TypeError):
            ProcessPipeReader.from_process(process)

    def test_from_process_raises_typeerror_for_magicmock_without_fileno(self):
        process = MagicMock()
        process.stdout = MagicMock(spec=[])
        with pytest.raises(TypeError):
            ProcessPipeReader.from_process(process)
