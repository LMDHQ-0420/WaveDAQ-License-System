from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path


def launch(path: Path, arguments: list[str] | None = None) -> subprocess.Popen[bytes]:
    arguments = arguments or []
    if platform.system() == "Darwin" and path.suffix == ".app":
        return subprocess.Popen(["open", str(path), "--args", *arguments])
    if not os.access(path, os.X_OK) and platform.system() != "Windows":
        path.chmod(path.stat().st_mode | 0o100)
    return subprocess.Popen([str(path), *arguments])
