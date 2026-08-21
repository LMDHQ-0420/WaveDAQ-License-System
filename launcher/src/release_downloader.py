from __future__ import annotations

import hashlib
import os
import ssl
import shutil
import tempfile
from pathlib import Path
from collections.abc import Callable
from urllib.request import Request, urlopen
from urllib.error import URLError

try:
    import certifi
except ImportError:
    certifi = None


def download_verified(url: str, expected_sha256: str, destination: Path, headers: dict[str, str] | None = None, progress: Callable[[int, int], None] | None = None) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix="wavedaq-download-", suffix=".part", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    digest = hashlib.sha256()
    try:
        request = Request(url, headers=headers or {})
        context = ssl.create_default_context(cafile=certifi.where()) if certifi else ssl.create_default_context()
        try:
            with urlopen(request, timeout=60, context=context) as response, temporary.open("wb") as output:
                total = int(response.headers.get("content-length", "0") or 0)
                received = 0
                while chunk := response.read(1024 * 1024):
                    digest.update(chunk)
                    output.write(chunk)
                    received += len(chunk)
                    if progress:
                        progress(received, total)
        except (URLError, TimeoutError, ssl.SSLError, ConnectionError) as exc:
            raise RuntimeError("网络波动，请重试") from exc
        if digest.hexdigest().lower() != expected_sha256.lower():
            raise ValueError("软件包 SHA-256 校验失败")
        shutil.move(str(temporary), destination)
        return destination
    finally:
        temporary.unlink(missing_ok=True)
