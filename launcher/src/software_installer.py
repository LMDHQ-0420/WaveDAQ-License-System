from __future__ import annotations

import os
import platform
import plistlib
import shutil
import subprocess
import zipfile
from pathlib import Path

from src.local_storage import data_dir


def launch(path: Path, arguments: list[str] | None = None) -> subprocess.Popen[bytes]:
    arguments = arguments or []
    if not path.exists():
        raise RuntimeError(f"找不到已安装程序：{path}")
    if platform.system() == "Darwin" and path.suffix == ".app":
        _ensure_macos_app_executable(path)
        return subprocess.Popen(["open", str(path), "--args", *arguments])
    if platform.system() == "Darwin" and path.suffix in {".dmg", ".pkg"}:
        return subprocess.Popen(["open", str(path), "--args", *arguments])
    if not os.access(path, os.X_OK) and platform.system() != "Windows":
        try:
            path.chmod(path.stat().st_mode | 0o100)
        except OSError as exc:
            raise RuntimeError(f"程序没有执行权限，且无法修复：{path}（{exc}）") from exc
    return subprocess.Popen([str(path), *arguments])


def _ensure_macos_app_executable(app: Path) -> None:
    """Make the executable inside a downloaded .app runnable.

    ZIP extraction preserves the archive's file contents but may lose the
    executable bit. macOS then silently refuses to launch the bundle through
    Finder/open, so repair the bit before handing the bundle to LaunchServices.
    """
    info_path = app / "Contents" / "Info.plist"
    try:
        with info_path.open("rb") as stream:
            info = plistlib.load(stream)
    except (OSError, ValueError, plistlib.InvalidFileException) as exc:
        raise RuntimeError(f"应用程序信息损坏，无法启动：{info_path}（{exc}）") from exc
    executable_name = str(info.get("CFBundleExecutable") or "")
    if not executable_name or Path(executable_name).name != executable_name:
        raise RuntimeError("应用程序缺少有效的可执行文件配置")
    executable = app / "Contents" / "MacOS" / executable_name
    if not executable.is_file():
        raise RuntimeError(f"应用程序缺少可执行文件：{executable}")
    if not os.access(executable, os.X_OK):
        try:
            executable.chmod(executable.stat().st_mode | 0o111)
        except OSError as exc:
            raise RuntimeError(f"应用程序没有执行权限，且无法修复：{executable}（{exc}）") from exc


def _safe_extract_zip(package: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(package) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if target != root and root not in target.parents:
                raise RuntimeError("安装包包含不安全的文件路径")
        archive.extractall(destination)


def _find_launch_target(root: Path, product_id: str, platform_id: str) -> Path:
    if platform_id.startswith("macos-"):
        apps = sorted(root.rglob("*.app"))
        if apps:
            return apps[0]
    else:
        executables = sorted(path for path in root.rglob("*.exe") if path.is_file())
        preferred = [path for path in executables if product_id.lower() in path.stem.lower()]
        if preferred:
            return preferred[0]
        if executables:
            return executables[0]
    raise RuntimeError("安装包中没有找到可启动的产品程序")


def install_product(package: Path, product_id: str, platform_id: str, version: str) -> Path:
    """Install a downloaded product into Launcher-owned private storage."""
    versions_root = data_dir() / "products" / product_id / platform_id
    versions_root.mkdir(parents=True, exist_ok=True)
    target = versions_root / version
    temporary = versions_root / f".{version}.installing"
    shutil.rmtree(temporary, ignore_errors=True)
    temporary.mkdir(parents=True, exist_ok=True)
    try:
        if package.suffix.lower() == ".zip":
            _safe_extract_zip(package, temporary)
        elif package.suffix.lower() == ".exe":
            shutil.copy2(package, temporary / package.name)
        elif package.suffix.lower() == ".app" and platform_id.startswith("macos-"):
            shutil.copytree(package, temporary / package.name)
        else:
            raise RuntimeError("当前版本不是 Launcher 可直接管理的产品包")
        launch_target = _find_launch_target(temporary, product_id, platform_id)
        shutil.rmtree(target, ignore_errors=True)
        temporary.rename(target)
        # Keep only the current product version and remove older downloaded
        # package directories after the new version has been installed.
        for sibling in versions_root.iterdir():
            if sibling != target and sibling.is_dir():
                shutil.rmtree(sibling, ignore_errors=True)
        downloads_root = data_dir() / "downloads" / product_id / platform_id
        if downloads_root.exists():
            for sibling in downloads_root.iterdir():
                if sibling.name != version and sibling.is_dir():
                    shutil.rmtree(sibling, ignore_errors=True)
        return target / launch_target.relative_to(temporary)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
