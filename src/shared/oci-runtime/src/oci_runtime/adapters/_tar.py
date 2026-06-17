import io
import tarfile


def create_build_tar(
    build_file_content: str,
    files: dict[str, bytes],
    tar_entry_name: str = "Dockerfile",
) -> bytes:
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
