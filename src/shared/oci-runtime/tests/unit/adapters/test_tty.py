import sys
from unittest.mock import patch

from oci_runtime.adapters.tty import StdoutTtyDetector


class TestStdoutTtyDetector:
    def test_is_tty_true_when_isatty(self):
        with patch.object(sys.stdout, "isatty", return_value=True):
            d = StdoutTtyDetector()
            assert d.is_tty() is True

    def test_is_tty_false_when_not_isatty(self):
        with patch.object(sys.stdout, "isatty", return_value=False):
            d = StdoutTtyDetector()
            assert d.is_tty() is False
