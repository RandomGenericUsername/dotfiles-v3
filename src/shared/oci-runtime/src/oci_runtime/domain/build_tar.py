import io
import posixpath
import tarfile
from collections.abc import Mapping


def _validate_tar_path(path: str) -> None:
    norm = posixpath.normpath(path)
    if posixpath.isabs(norm):
        raise ValueError(f"Absolute path not allowed in tar: {path!r}")
    if norm == ".." or norm.startswith("../"):
        raise ValueError(f"Path with parent reference not allowed in tar: {path!r}")


def create_build_tar(
    build_file_content: str,
    files: Mapping[str, bytes],
    tar_entry_name: str = "Dockerfile",
) -> bytes:
    _validate_tar_path(tar_entry_name)
    for path in files:
        _validate_tar_path(path)

    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
        info = tarfile.TarInfo(name=tar_entry_name)
        content = build_file_content.encode("utf-8")
        info.size = len(content)
        info.uid = 0
        info.gid = 0
        info.mtime = 0
        tar.addfile(info, io.BytesIO(content))
        for path, data in files.items():
            info = tarfile.TarInfo(name=path)
            info.size = len(data)
            info.uid = 0
            info.gid = 0
            info.mtime = 0
            tar.addfile(info, io.BytesIO(data))
    return tar_buffer.getvalue()
