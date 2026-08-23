from __future__ import annotations

import os
import platform
import plistlib
import shutil
import stat
import subprocess
import zipfile
from pathlib import Path
from pathlib import PurePosixPath

from src.local_storage import data_dir


def launch(path: Path, arguments: list[str] | None = None) -> subprocess.Popen[bytes]:
    arguments = arguments or []
    if not path.exists():
        raise RuntimeError(f"找不到已安装程序：{path}")
    if platform.system() == "Darwin" and path.suffix == ".app":
        _repair_macos_framework_symlinks(path)
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


def _repair_macos_framework_symlinks(app: Path) -> None:
    """Repair symlinks flattened by an older ZIP installer.

    Python's ``zipfile.extractall`` used to turn symlink entries into ordinary
    text files containing the link target. PyInstaller's macOS runtime then
    tries to load those text files as Mach-O libraries and exits immediately.
    Only repair short relative targets that resolve to an existing path inside
    the Frameworks directory.
    """
    frameworks = app / "Contents" / "Frameworks"
    if not frameworks.is_dir():
        return
    root = frameworks.resolve()
    for candidate in frameworks.rglob("*"):
        if not candidate.is_file() or candidate.is_symlink():
            continue
        try:
            content = candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not content or "\n" in content or "\r" in content or Path(content).is_absolute():
            continue
        target = (candidate.parent / content).resolve()
        if target == root or root not in target.parents or not target.exists():
            continue
        try:
            candidate.unlink()
            candidate.symlink_to(content)
        except OSError as exc:
            raise RuntimeError(f"无法修复应用程序框架链接：{candidate}（{exc}）") from exc


def _safe_extract_zip(package: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(package) as archive:
        members = archive.infolist()
        symlink_names: set[str] = set()
        for member in members:
            _validate_archive_name(member.filename)
            target = destination / member.filename
            resolved_target = target.resolve(strict=False)
            if resolved_target != root and root not in resolved_target.parents:
                raise RuntimeError("安装包包含不安全的文件路径")
            if _zip_member_is_symlink(member):
                link_target = archive.read(member).decode("utf-8")
                if Path(link_target).is_absolute():
                    raise RuntimeError("安装包包含不安全的绝对符号链接")
                resolved_link = (target.parent / link_target).resolve(strict=False)
                if resolved_link != root and root not in resolved_link.parents:
                    raise RuntimeError("安装包包含不安全的符号链接")
                symlink_names.add(member.filename.rstrip("/"))
        for member in members:
            member_path = PurePosixPath(member.filename)
            if any(str(PurePosixPath(*member_path.parts[:index])) in symlink_names for index in range(1, len(member_path.parts))):
                raise RuntimeError("安装包不能在符号链接目录下写入文件")
        for member in members:
            target = destination / member.filename
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if _zip_member_is_symlink(member):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
        for member in members:
            if not _zip_member_is_symlink(member):
                continue
            target = destination / member.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.unlink(missing_ok=True)
            target.symlink_to(archive.read(member).decode("utf-8"))


def _zip_member_is_symlink(member: zipfile.ZipInfo) -> bool:
    return stat.S_IFMT(member.external_attr >> 16) == stat.S_IFLNK


def _validate_archive_name(name: str) -> None:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts:
        raise RuntimeError("安装包包含不安全的文件路径")


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
    _validate_local_component(product_id, "产品 ID")
    _validate_local_component(platform_id, "平台标识")
    _validate_local_component(version, "版本号")
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


def _validate_local_component(value: str, label: str) -> None:
    path = Path(str(value))
    if not value or path.name != value or value in {".", ".."} or "/" in value or "\\" in value:
        raise RuntimeError(f"{label}无效")
