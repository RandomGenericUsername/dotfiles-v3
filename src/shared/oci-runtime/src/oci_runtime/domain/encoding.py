def safe_decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")
