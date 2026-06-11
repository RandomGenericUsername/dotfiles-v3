import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from oci_runtime import engines
from oci_runtime.adapters.engine.cli import CliRuntime
from oci_runtime.domain.enums import RuntimeKind
from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.factory import RuntimeFactory
from oci_runtime.ports.capabilities import RuntimeCapabilities, RuntimePreference


def test_importing_factory_has_no_side_effects():
    code = """\
from oci_runtime.factory import _PROVIDER_REGISTRY, RuntimeFactory

# 1. Import must NOT trigger side effects
assert len(_PROVIDER_REGISTRY) == 0, \
    f"Import triggered side effects: {list(_PROVIDER_REGISTRY.keys())}"

# 2. Lazy registration must happen on first factory creation
factory = RuntimeFactory()
assert len(_PROVIDER_REGISTRY) == 2, \
    f"Expected 2 providers, got {len(_PROVIDER_REGISTRY)}: {list(_PROVIDER_REGISTRY.keys())}"
"""

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": ":".join(sys.path)},
    )
    assert result.returncode == 0, result.stderr


class TestRuntimeFactoryCreate:
    @patch("shutil.which", return_value="/usr/bin/docker")
    @patch("subprocess.run")
    def test_docker_returns_cli_runtime(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout="Docker version 24.0.0", stderr="")
        runtime = RuntimeFactory().create(engines.docker_pref)
        assert isinstance(runtime, CliRuntime)

    @patch("shutil.which", return_value="/usr/bin/podman")
    @patch("subprocess.run")
    def test_podman_returns_cli_runtime(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout="podman version 4.0.0", stderr="")
        runtime = RuntimeFactory().create(engines.podman_pref)
        assert isinstance(runtime, CliRuntime)

    def test_bogus_raises_runtime_not_available(self):
        bogus = RuntimePreference(kind=RuntimeKind.DOCKER, binary="nonexistent-runtime-xyz")
        with pytest.raises(RuntimeNotAvailableError):
            RuntimeFactory().create(bogus)
