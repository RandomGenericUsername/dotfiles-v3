from __future__ import annotations

import json
from pathlib import Path

import pytest

from oci_runtime.domain.exceptions import SourceRootNotFoundError
from oci_runtime.source_locator import (
    SourceRoot,
    _direct_url_package_dir,
    _repo_root_from_candidate,
    resolve_source_root,
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A fake monorepo: <root>/src/{cli-tools,shared}/..."""
    root = tmp_path / "dotfiles-repo"
    (root / "src" / "cli-tools").mkdir(parents=True)
    (root / "src" / "shared").mkdir(parents=True)
    return root


class TestRepoRootFromCandidate:
    def test_candidate_is_repo_root(self, repo: Path) -> None:
        assert _repo_root_from_candidate(repo) == repo

    def test_candidate_is_package_dir(self, repo: Path) -> None:
        pkg = repo / "src" / "cli-tools" / "color-scheme-generator"
        pkg.mkdir(parents=True)
        assert _repo_root_from_candidate(pkg) == repo

    def test_candidate_is_deep_nested(self, repo: Path) -> None:
        pkg = (
            repo
            / "src"
            / "cli-tools"
            / "color-scheme-generator"
            / "src"
            / "color_scheme_generator"
        )
        pkg.mkdir(parents=True)
        assert _repo_root_from_candidate(pkg) == repo

    def test_no_marker_returns_none(self, tmp_path: Path) -> None:
        assert _repo_root_from_candidate(tmp_path / "no-such-dir") is None


def _fake_dist(direct_url_content: str) -> object:
    dist = type("FakeDist", (), {})()
    dist.read_text = lambda _name: direct_url_content
    return dist


class TestDirectUrlPackageDir:
    def test_parses_file_url(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pkg = tmp_path / "csg"
        pkg.mkdir()
        monkeypatch.setattr(
            "oci_runtime.source_locator.distribution",
            lambda _pkg: _fake_dist(
                json.dumps({"url": pkg.as_uri(), "dir_info": {}})
            ),
        )
        assert _direct_url_package_dir("color_scheme_generator") == pkg

    def test_editable_url_parsed_the_same(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pkg = tmp_path / "csg"
        pkg.mkdir()
        monkeypatch.setattr(
            "oci_runtime.source_locator.distribution",
            lambda _pkg: _fake_dist(
                json.dumps({"url": pkg.as_uri(), "dir_info": {"editable": True}})
            ),
        )
        assert _direct_url_package_dir("p") == pkg

    def test_non_file_url_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "oci_runtime.source_locator.distribution",
            lambda _pkg: _fake_dist(
                json.dumps({"url": "https://example.com/csg.tar.gz", "dir_info": {}})
            ),
        )
        assert _direct_url_package_dir("p") is None

    def test_missing_package_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "oci_runtime.source_locator.distribution",
            lambda _pkg: (_ for _ in ()).throw(
                __import__("importlib.metadata", fromlist=["PackageNotFoundError"]).PackageNotFoundError("p")
            ),
        )
        assert _direct_url_package_dir("p") is None

    def test_bad_json_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "oci_runtime.source_locator.distribution",
            lambda _pkg: _fake_dist("{not json"),
        )
        assert _direct_url_package_dir("p") is None


class TestResolveSourceRoot:
    def test_override_wins(self, repo: Path) -> None:
        result = resolve_source_root(
            package="color_scheme_generator", override=repo, env=None
        )
        assert result == SourceRoot(root=repo, source="override")

    def test_override_is_package_dir(self, repo: Path) -> None:
        pkg = repo / "src" / "cli-tools" / "color-scheme-generator"
        pkg.mkdir(parents=True)
        result = resolve_source_root(package="p", override=pkg)
        assert result.root == repo
        assert result.source == "override"

    def test_env_var_is_used_when_no_override(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "oci_runtime.source_locator._direct_url_package_dir", lambda p: None
        )
        monkeypatch.setattr(
            "oci_runtime.source_locator._resource_package_dir", lambda p: None
        )
        result = resolve_source_root(
            package="p",
            env_var="CSG_SOURCE_ROOT",
            env={"CSG_SOURCE_ROOT": str(repo)},
        )
        assert result.root == repo
        assert result.source == "env"

    def test_direct_url_fallback(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pkg = repo / "src" / "cli-tools" / "color-scheme-generator"
        pkg.mkdir(parents=True)
        monkeypatch.setattr(
            "oci_runtime.source_locator._direct_url_package_dir", lambda p: pkg
        )
        monkeypatch.setattr(
            "oci_runtime.source_locator._resource_package_dir", lambda p: None
        )
        result = resolve_source_root(package="p")
        assert result.root == repo
        assert result.source == "direct_url"

    def test_package_walk_fallback(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pkg = repo / "src" / "shared" / "oci-runtime"
        pkg.mkdir(parents=True)
        monkeypatch.setattr(
            "oci_runtime.source_locator._direct_url_package_dir", lambda p: None
        )
        monkeypatch.setattr(
            "oci_runtime.source_locator._resource_package_dir", lambda p: pkg
        )
        result = resolve_source_root(package="p")
        assert result.root == repo
        assert result.source == "package"

    def test_nothing_resolves_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "oci_runtime.source_locator._direct_url_package_dir", lambda p: None
        )
        monkeypatch.setattr(
            "oci_runtime.source_locator._resource_package_dir", lambda p: None
        )
        with pytest.raises(SourceRootNotFoundError) as exc:
            resolve_source_root(package="p", env_var="CSG_SOURCE_ROOT")
        assert "source repo" in str(exc.value)
        assert "CSG_SOURCE_ROOT" in str(exc.value)

    def test_bad_override_falls_back_to_direct_url(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pkg = repo / "src" / "cli-tools" / "color-scheme-generator"
        pkg.mkdir(parents=True)
        monkeypatch.setattr(
            "oci_runtime.source_locator._direct_url_package_dir", lambda p: pkg
        )
        monkeypatch.setattr(
            "oci_runtime.source_locator._resource_package_dir", lambda p: None
        )
        result = resolve_source_root(package="p", override=Path("/no/such/repo"))
        assert result.root == repo
        assert result.source == "direct_url"
