from __future__ import annotations

import stat
import sys

import pytest

from oci_runtime.adapters.binary import CliBinaryResolver
from oci_runtime.domain.exceptions import RuntimeNotAvailableError


def _resolve_from_path(name: str, path: str) -> str | None:
    """Resolve a binary name against a PATH string."""
    from shutil import which

    return which(name, path=path)


class TestCliBinaryResolver:
    def test_resolve_raises_when_not_found(self):
        resolver = CliBinaryResolver()
        with pytest.raises(RuntimeNotAvailableError):
            resolver.resolve("this-binary-does-not-exist-12345")

    def test_is_available_returns_false_when_not_found(self):
        resolver = CliBinaryResolver()
        assert resolver.is_available("this-binary-does-not-exist-12345") is False

    def test_resolve_caches_result(self, monkeypatch):
        called: list[str] = []
        original_which = __import__("shutil").which

        def tracking_which(cmd, **kw):
            called.append(cmd)
            return original_which(cmd, **kw)

        monkeypatch.setattr("shutil.which", tracking_which)
        resolver = CliBinaryResolver()
        resolver.resolve("python3")
        resolver.resolve("python3")
        assert len(called) == 1

    def test_resolve_returns_path_for_python(self):
        resolver = CliBinaryResolver()
        path = resolver.resolve("python3")
        assert path is not None
        assert isinstance(path, str)
        assert len(path) > 0

    def test_is_available_returns_true_for_python(self):
        resolver = CliBinaryResolver()
        assert resolver.is_available("python3") is True

    # ── Edge cases ──────────────────────────────────────

    def test_path_with_empty_segment_resolves(self, monkeypatch, tmp_path):
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        exe = bin_dir / "my-tool"
        exe.write_text("#!/bin/sh\necho hello")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)

        monkeypatch.setenv("PATH", f"/usr/bin::{bin_dir}")
        resolver = CliBinaryResolver()
        path = resolver.resolve("my-tool")
        assert path == str(exe)

    def test_path_ending_with_separator_resolves(self, monkeypatch, tmp_path):
        bin_dir = tmp_path / "bin2"
        bin_dir.mkdir()
        exe = bin_dir / "my-tool2"
        exe.write_text("#!/bin/sh\necho hello")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)

        monkeypatch.setenv("PATH", f"{bin_dir}:")
        resolver = CliBinaryResolver()
        path = resolver.resolve("my-tool2")
        assert path == str(exe)

    @pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows-only")
    def test_resolve_exe_extension_on_windows(self, monkeypatch, tmp_path):
        bin_dir = tmp_path / "bin3"
        bin_dir.mkdir()
        exe = bin_dir / "my-tool.exe"
        exe.write_text("dummy")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)

        monkeypatch.setenv("PATH", str(bin_dir))
        resolver = CliBinaryResolver()
        path = resolver.resolve("my-tool.exe")
        assert path == str(exe)

    def test_file_not_found_in_first_path_entry_found_in_second(
        self, monkeypatch, tmp_path
    ):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        bin_dir = tmp_path / "real-bin"
        bin_dir.mkdir()
        exe = bin_dir / "my-tool3"
        exe.write_text("#!/bin/sh\necho hello")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)

        monkeypatch.setenv("PATH", f"{empty_dir}:{bin_dir}")
        resolver = CliBinaryResolver()
        path = resolver.resolve("my-tool3")
        assert path == str(exe)

    def test_resolve_from_path_finds_in_second_entry(self, tmp_path):
        empty_dir = tmp_path / "a"
        empty_dir.mkdir()
        bin_dir = tmp_path / "b"
        bin_dir.mkdir()
        exe = bin_dir / "tool"
        exe.write_text("#!/bin/sh\necho hi")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)

        result = _resolve_from_path("tool", f"{empty_dir}:{bin_dir}")
        assert result == str(exe)

    def test_resolve_from_path_returns_none_when_not_found(self):
        result = _resolve_from_path("no-such-tool", "/usr/bin")
        assert result is None
