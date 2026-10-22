# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("cryptography") + ["PySide6.QtSvg"]
spec_dir = Path(SPECPATH).resolve()
project_dir = spec_dir.parent
app_icon = project_dir / "assets" / ("app.icns" if sys.platform == "darwin" else "app.ico")
logo_file = project_dir / "assets" / "logo.png"
if not app_icon.is_file():
    raise FileNotFoundError(f"Launcher 图标不存在：{app_icon}")
if not logo_file.is_file():
    raise FileNotFoundError(f"Launcher Logo 不存在：{logo_file}")

a = Analysis(
    [str(spec_dir / "src" / "main.py")],
    pathex=[str(spec_dir)],
    binaries=[],
    # Keep the brand mark in the launcher distribution.  The launcher release
    # is the validation product; individual products do not need this asset.
    datas=[(str(logo_file), ".")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="WaveDAQ-Launcher", debug=False, strip=False, upx=True, console=False)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name="WaveDAQ-Launcher")
    app = BUNDLE(coll, name="WaveDAQ-Launcher.app", icon=str(app_icon), bundle_identifier="com.lmdhq.wavedaq.launcher", info_plist={"CFBundleShortVersionString": "1.2.0", "NSHighResolutionCapable": True})
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="WaveDAQ-Launcher", debug=False, strip=False, upx=True, console=False, icon=str(app_icon))
    coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=True, name="WaveDAQ-Launcher")
