from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path
from urllib.request import urlopen


def download_verified(url: str, expected_sha256: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkstemp(prefix="wavedaq-download-", suffix=".part", dir=destination.parent)[1])
    digest = hashlib.sha256()
    try:
        with urlopen(url, timeout=60) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                output.write(chunk)
        if digest.hexdigest().lower() != expected_sha256.lower():
            raise ValueError("软件包 SHA-256 校验失败")
        shutil.move(str(temporary), destination)
        return destination
    finally:
        temporary.unlink(missing_ok=True)
